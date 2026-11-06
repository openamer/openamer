#!/usr/bin/env python3
"""Measure repo-map retrieval quality at a fixed context-token budget.

The script is the evidence harness for the repo-map ranking change: it runs
the *keyword* strategy (the pre-existing behaviour) and the *graph* strategy
(syntax-aware symbols + reference graph) over the same versioned fixture
corpus, at the same token budget, and reports file/symbol recall plus MRR,
latency and peak memory.

Usage::

    python scripts/repomap_retrieval_bench.py            # both strategies
    python scripts/repomap_retrieval_bench.py --json out.json
    python scripts/repomap_retrieval_bench.py --strategy keyword

The corpus is copied to a temporary directory before scanning so the fixture
is enumerated with the same ``os.walk`` fallback in a developer checkout and
in CI (``git ls-files`` would otherwise only see committed files).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from openamer_cli.repomap import (  # noqa: E402
    RepoMap,
    build_repo_map,
    estimate_tokens,
)

_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "repomap_retrieval"


def _load_fixture() -> dict[str, Any]:
    fixture = json.loads((_FIXTURE_DIR / "queries.json").read_text(encoding="utf-8"))
    if fixture.get("version") != 1:
        raise SystemExit(f"unsupported fixture version: {fixture.get('version')!r}")
    return fixture


def _stage_corpus(corpus: Path, destination: Path) -> Path:
    """Copy the fixture corpus somewhere without a ``.git`` directory."""
    staged = destination / "corpus"
    shutil.copytree(corpus, staged)
    return staged


def render_keyword_context(
    repo_map: RepoMap,
    built: dict[str, Any],
    query: str,
    budget_tokens: int,
) -> str:
    """Render the pre-existing keyword ranking within *budget_tokens*.

    Mirrors what ``RepoMap.get_context`` prints for a file listing: the path
    followed by the definition names extracted for that file. Keeping the
    payload shape close to the graph renderer is what makes the token budget
    comparison fair.
    """
    ranked = repo_map.rank_files(query, built)
    blocks: list[str] = []
    used = 0
    for file_path, score in ranked:
        if score <= 0:
            continue
        block = [f"  - {file_path}"]
        classes = built["classes_by_file"].get(file_path, [])
        functions = built["functions_by_file"].get(file_path, [])
        if classes:
            block.append(f"      classes: {', '.join(classes)}")
        if functions:
            block.append(f"      functions: {', '.join(functions)}")
        text = "\n".join(block)
        cost = estimate_tokens(text)
        if used + cost > budget_tokens:
            break
        blocks.append(text)
        used += cost
    return "\n".join(blocks)


def _norm(path: str) -> str:
    """Normalise a repo-relative path so fixtures match on every platform."""
    return path.replace("\\", "/")


def _rendered_files(text: str) -> list[str]:
    """Extract the file paths a context rendering mentions, in order."""
    files: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("classes:", "functions:")):
            continue
        if stripped.startswith("- "):
            candidate = stripped[2:].strip()
        else:
            candidate = re.split(r":\d+", stripped)[0]
            if "  " in candidate:
                candidate = candidate.split("  ")[0]
        files.append(_norm(candidate.strip()))
    return files


def _score_context(
    text: str,
    gold_files: list[str],
    gold_symbols: list[list[str]],
    ranked_files: list[str],
) -> dict[str, Any]:
    normalised_text = _norm(text)
    file_hits = [f for f in gold_files if _norm(f) in normalised_text]
    symbol_hits = [sym for _, sym in gold_symbols if sym in normalised_text]

    rendered_files = _rendered_files(text)

    reciprocal_rank = 0.0
    for position, file_path in enumerate((_norm(f) for f in ranked_files), start=1):
        if file_path in gold_files:
            reciprocal_rank = 1.0 / position
            break

    return {
        "file_recall": len(file_hits) / len(gold_files) if gold_files else 0.0,
        "symbol_recall": len(symbol_hits) / len(gold_symbols) if gold_symbols else 0.0,
        "precision": (
            len([f for f in rendered_files if f in gold_files]) / len(rendered_files)
            if rendered_files
            else 0.0
        ),
        "files_rendered": len(rendered_files),
        "mrr": reciprocal_rank,
        "file_hits": file_hits,
        "symbol_hits": symbol_hits,
    }


def _timed(fn, repeats: int = 3) -> tuple[Any, float]:
    timings: list[float] = []
    result: Any = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = fn()
        timings.append((time.perf_counter() - started) * 1000.0)
    return result, statistics.median(timings)


def run(strategies: list[str]) -> dict[str, Any]:
    fixture = _load_fixture()
    budget = int(fixture["token_budget"])
    corpus = _FIXTURE_DIR / fixture["corpus"]

    with tempfile.TemporaryDirectory(prefix="repomap-bench-") as tmp:
        staged = _stage_corpus(corpus, Path(tmp))
        repo_map = RepoMap(str(staged))

        tracemalloc.start()
        built, build_ms = _timed(repo_map.build_map, repeats=3)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        results: dict[str, Any] = {
            "fixture_version": fixture["version"],
            "token_budget": budget,
            "corpus_files": built["file_count"],
            "build_ms": round(build_ms, 2),
            "build_peak_kib": round(peak / 1024.0, 1),
            "imported_from": sys.modules["openamer_cli.repomap"].__file__,
            "strategies": {},
        }

        for strategy in strategies:
            per_query: list[dict[str, Any]] = []
            latencies: list[float] = []
            tokens_used: list[int] = []

            for entry in fixture["queries"]:
                query = entry["query"]

                def render(query: str = query, strategy: str = strategy) -> str:
                    if strategy == "keyword":
                        return render_keyword_context(repo_map, built, query, budget)
                    if strategy == "graph":
                        return repo_map.render_context(query, budget, built)
                    raise SystemExit(f"unknown strategy: {strategy}")

                if strategy == "graph" and not hasattr(repo_map, "render_context"):
                    raise SystemExit(
                        "graph strategy is not implemented in this tree; "
                        "run with --strategy keyword for the baseline"
                    )

                text, latency_ms = _timed(render, repeats=5)
                tracemalloc.start()
                measure_text = render()
                _, query_peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                if strategy == "graph":
                    ranked_files = [f for f, _ in repo_map.rank_files_graph(query, built)]
                else:
                    ranked_files = [
                        f for f, score in repo_map.rank_files(query, built) if score > 0
                    ]

                scores = _score_context(
                    measure_text,
                    entry["gold_files"],
                    entry["gold_symbols"],
                    ranked_files,
                )
                tokens = estimate_tokens(measure_text)
                latencies.append(latency_ms)
                tokens_used.append(tokens)
                per_query.append(
                    {
                        "id": entry["id"],
                        "query": query,
                        "tokens": tokens,
                        "latency_ms": round(latency_ms, 3),
                        "peak_kib": round(query_peak / 1024.0, 1),
                        **scores,
                        "ranked_head": ranked_files[:5],
                    }
                )

            results["strategies"][strategy] = {
                "file_recall": round(
                    statistics.mean(q["file_recall"] for q in per_query), 4
                ),
                "symbol_recall": round(
                    statistics.mean(q["symbol_recall"] for q in per_query), 4
                ),
                "precision": round(statistics.mean(q["precision"] for q in per_query), 4),
                "mrr": round(statistics.mean(q["mrr"] for q in per_query), 4),
                "median_latency_ms": round(statistics.median(latencies), 3),
                "mean_tokens": round(statistics.mean(tokens_used), 1),
                "queries": per_query,
            }

        return results


def _print_table(results: dict[str, Any]) -> None:
    print(
        f"fixture v{results['fixture_version']} | {results['corpus_files']} files | "
        f"budget {results['token_budget']} tokens"
    )
    print(f"imported from: {results['imported_from']}")
    print(f"build: {results['build_ms']} ms, peak {results['build_peak_kib']} KiB\n")

    header = f"{'strategy':<10} {'file_recall':>11} {'sym_recall':>10} {'precision':>9} {'mrr':>6} {'tokens':>7} {'lat_ms':>7}"
    print(header)
    print("-" * len(header))
    for name, data in results["strategies"].items():
        print(
            f"{name:<10} {data['file_recall']:>11.4f} {data['symbol_recall']:>10.4f} "
            f"{data['precision']:>9.4f} {data['mrr']:>6.3f} {data['mean_tokens']:>7.1f} "
            f"{data['median_latency_ms']:>7.2f}"
        )

    for name, data in results["strategies"].items():
        print(f"\n[{name}] per query")
        for q in data["queries"]:
            print(
                f"  {q['id']:<24} tokens={q['tokens']:<4} files={q['files_rendered']:<2} "
                f"file_recall={q['file_recall']:.2f} sym_recall={q['symbol_recall']:.2f} "
                f"precision={q['precision']:.2f} mrr={q['mrr']:.2f}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategy",
        action="append",
        choices=("keyword", "graph"),
        help="strategy to run (repeatable; default: keyword then graph)",
    )
    parser.add_argument("--json", type=Path, default=None, help="write raw results here")
    args = parser.parse_args()

    strategies = args.strategy or ["keyword", "graph"]
    results = run(strategies)
    _print_table(results)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
