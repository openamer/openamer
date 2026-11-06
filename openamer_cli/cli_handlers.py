"""
CLI handlers for Plugin Framework, Evaluation, and RAG Pipeline.

These are the cmd_* functions that implement ``openamer plugins``,
``openamer eval``, and ``openamer rag`` CLI commands.

Import and wire them into ``main.py:main()``::

    from openamer_cli.subcommands.eval import build_eval_parser
    from openamer_cli.subcommands.rag import build_rag_parser
    from openamer_cli.cli_handlers import cmd_eval, cmd_rag

    build_eval_parser(subparsers, cmd_eval=cmd_eval)
    build_rag_parser(subparsers, cmd_rag=cmd_rag)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from openamer_cli.evaluation import (
    BenchmarkRun,
    BenchmarkSuite,
    TestCase,
    compare_runs,
    get_leaderboard,
    print_leaderboard,
)
from openamer_cli.plugin_framework import (
    PluginHost,
    PluginRegistry,
)
from openamer_cli.rag_pipeline import (
    ChunkingStrategy,
    RagPipeline,
)


# ── Plugin Framework CLI ───────────────────────────────────────────────────────


def cmd_plugins_framework(args: Any) -> None:
    """Handle ``openamer plugins list|install|reload``."""
    host = _get_plugin_host()

    action = getattr(args, "plugins_framework_action", None) or "list"

    if action == "list":
        plugins = host.registry.list_plugins(include_disabled=getattr(args, "all", True))
        if not plugins:
            print("No plugins registered.")
            return
        print(f"{'Name':<25} {'State':<12} {'Version'}")
        print("-" * 50)
        for name, state, version in plugins:
            print(f"{name:<25} {state.value:<12} {version}")

    elif action == "install":
        path_str = getattr(args, "path", "")
        if not path_str:
            print("Error: path argument is required.", file=sys.stderr)
            sys.exit(1)
        source = Path(path_str).resolve()
        if not source.exists():
            print(f"Error: path does not exist: {source}", file=sys.stderr)
            sys.exit(1)
        name = host.install(source)
        if name:
            print(f"Plugin '{name}' installed successfully.")
        else:
            print("Failed to install plugin.", file=sys.stderr)
            sys.exit(1)

    elif action == "reload":
        name = getattr(args, "name", None)
        count = host.reload(name=name)
        if count > 0:
            label = name or "all plugins"
            print(f"Reloaded {count} plugin(s): {label}")
        else:
            print(f"No plugins reloaded (name: {name!r})", file=sys.stderr)

    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(1)


# ── Evaluation CLI ────────────────────────────────────────────────────────────


def _make_model_fn(
    model_name: str = "",
    *,
    max_tokens: int = 1024,
    timeout: float = 120.0,
) -> Optional[Callable[[str], str]]:
    """Build a prompt function backed by OpenAmer's production LLM path.

    Uses :func:`agent.auxiliary_client.call_llm` with the ``evaluation``
    auxiliary task, so provider/model resolution is the same chain every other
    auxiliary surface uses: ``auxiliary.evaluation`` config → the user's main
    provider + model → auto-detect. There is no bespoke "simple_send_prompt"
    shim; a run either reaches a real configured provider or every case is
    recorded as an ``error``.

    Returns None only when the LLM client stack cannot be imported (broken
    install), so the caller can exit with a clear message instead of a
    traceback.
    """
    try:
        from agent.auxiliary_client import call_llm, extract_content_or_reasoning
    except Exception as exc:  # pragma: no cover - broken install only
        logging.getLogger(__name__).debug(
            "eval model fn unavailable (auxiliary client import failed): %s", exc
        )
        return None

    def model_fn(prompt: str) -> str:
        response = call_llm(
            task="evaluation",
            model=model_name or None,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        text = (extract_content_or_reasoning(response) or "").strip()
        if not text:
            # An empty reply is not an answer; surface it as a per-case error
            # instead of letting an observation-shaped case look successful.
            raise RuntimeError("model returned an empty response")
        return text

    return model_fn


def _print_eval_run(run: BenchmarkRun) -> None:
    """Print a run summary, making provenance and unscored cases explicit."""
    if run.is_baseline:
        print(
            "\nBASELINE RUN — replays gold/reference outputs through the "
            "evaluators.\nThis is a harness sanity check, NOT a model or agent "
            "score.\n"
        )
    print(f"\nBenchmark: {run.name}")
    print(f"Model:     {run.model or '(none)'}")
    print(f"Date:      {run.date}")
    print(f"Provenance:{' ' + run.provenance}")
    print(f"Total:     {run.total}")
    print(f"Scored:    {run.scored}")
    print(f"Passed:    {run.passed}")
    print(f"Pass rate: {run.pass_rate:.1f}% (of scored cases)")
    print(f"Avg latency: {run.avg_latency:.1f}ms")
    if run.unscored:
        print(
            f"Unscored:  {run.unscored} (observation-only cases — excluded "
            "from the pass rate)"
        )
    if run.errors:
        print(f"Errors:    {run.errors} (harness/model failures — counted as failures)")
    if run.not_run:
        print(f"Not run:   {run.not_run}")


def _eval_run_summary(run: BenchmarkRun, path: Path) -> None:
    _print_eval_run(run)
    print(f"Saved to:  {path}")

    if run.results:
        print("\nResults:")
        for r in run.results:
            marker = {
                "pass": "PASS",
                "fail": "FAIL",
                "error": "ERROR",
                "not_run": "SKIP",
                "unscored": "OBSERVE",
            }.get(r.status, r.status.upper())
            print(f"  [{marker}] {r.test_name} ({r.latency_ms:.0f}ms) — {r.reason}")


def cmd_self_critique(args: Any) -> Optional[int]:
    """Handle ``openamer self-critique``.

    Exit codes: 0 clean or warnings only, 1 when any CRITICAL finding stands
    (a failing organ, a red cron, stale evidence), 2 when the audit itself could
    not run. A tool that reports "fine" because it could not look is worse than
    no tool, so an unreadable home is an error, not a pass.
    """
    import json as _json

    try:
        from agent.self_critique import CHECKS, audit, render
    except Exception as exc:
        print(f"self-critique unavailable: {exc}")
        return 2

    only = getattr(args, "check", None)
    report = audit()
    if only:
        wanted = only.strip().lower()
        matching = [label for label, _ in CHECKS if wanted in label.lower()]
        if not matching:
            print(f"unknown check {only!r}; available: " +
                  ", ".join(label for label, _ in CHECKS))
            return 2
        report["findings"] = [f for f in report["findings"]
                              if any(w in f["kind"].replace("-", " ") for w in matching)]

    if getattr(args, "json", False):
        print(_json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render(report))

    return 1 if report["counts"]["critical"] else 0


def cmd_eval(args: Any) -> Optional[int]:
    """Handle ``openamer eval run|compare|leaderboard``.

    Returns an exit code: 0 on success, 1 when a run produced no scored cases
    or contained harness/model errors (a broken harness must not exit green),
    2 for usage/availability problems.
    """
    action = getattr(args, "eval_action", None)

    if action == "run":
        suite_ref = args.suite
        suite_path = Path(suite_ref)

        if suite_path.is_file():
            try:
                suite = BenchmarkSuite.from_file(suite_path)
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                print(f"Error: cannot load suite {suite_path}: {exc}", file=sys.stderr)
                return 2
        else:
            suite = BenchmarkSuite(name=suite_ref)

        if not suite.test_cases:
            print(f"Suite '{suite.name}' has no test cases.")
            print("To define cases, create a JSON/YAML file or add cases programmatically.")
            return 1

        provenance = (getattr(args, "baseline", None) or "agent").strip().lower()
        if provenance == "gold":
            # Offline harness check: no provider, no model call.
            run = suite.run_gold_baseline()
        else:
            model_fn = _make_model_fn(
                model_name=getattr(args, "model", ""),
                max_tokens=int(getattr(args, "max_tokens", 1024) or 1024),
            )
            if model_fn is None:
                print(
                    "Error: the OpenAmer LLM client stack is unavailable, so no "
                    "model can be reached. Run `openamer doctor` or "
                    "`openamer eval run <suite> --baseline gold` for an offline "
                    "harness check.",
                    file=sys.stderr,
                )
                return 2
            run = suite.run(
                # Record the requested model, or say plainly that the configured
                # default was used — never the suite path, which is not a model.
                model=getattr(args, "model", "") or "(configured default)",
                model_fn=model_fn,
            )

        path = run.save()
        _eval_run_summary(run, path)

        if run.scored == 0:
            print(
                "\nError: no scored cases — every case was observation-only or "
                "skipped, so this run measures nothing.",
                file=sys.stderr,
            )
            return 1
        if run.errors:
            print(
                f"\nError: {run.errors} case(s) could not be scored (model "
                "call/evaluator failure). Fix the errors above before treating "
                "this run as a measurement.",
                file=sys.stderr,
            )
            return 1
        return 0

    elif action == "compare":
        run1_path = Path(args.run1)
        run2_path = Path(args.run2)

        if not run1_path.is_file():
            print(f"Error: run file not found: {run1_path}", file=sys.stderr)
            return 2
        if not run2_path.is_file():
            print(f"Error: run file not found: {run2_path}", file=sys.stderr)
            return 2

        run1 = BenchmarkRun.load(run1_path)
        run2 = BenchmarkRun.load(run2_path)
        comparison = compare_runs(run1, run2)

        print("\nComparison:")
        for label, key in (("Run 1", "run1"), ("Run 2", "run2")):
            info = comparison[key]
            print(
                f"  {label}: {info['name']} ({info['model']}, "
                f"{info['provenance']}) — {info['pass_rate']:.1f}% pass over "
                f"{info['scored']} scored @ {info['avg_latency_ms']:.1f}ms"
            )
            if info.get("unscored"):
                print(f"          {info['unscored']} unscored case(s) excluded")
            if info.get("errors"):
                print(f"          {info['errors']} error(s) counted as failures")
        print(f"  Pass rate diff: {comparison['pass_rate_diff']:+.1f}%")
        print(f"  Latency diff:   {comparison['latency_diff_ms']:+.1f}ms")

        if comparison["regressions"]:
            print(f"\n  Regressions ({len(comparison['regressions'])}):")
            for r in comparison["regressions"]:
                print(f"    ✗ {r['test_name']}: {r['detail']}")
        if comparison["improvements"]:
            print(f"\n  Improvements ({len(comparison['improvements'])}):")
            for r in comparison["improvements"]:
                print(f"    ✓ {r['test_name']}: {r['detail']}")
        if comparison.get("incomparable"):
            print(f"\n  Not comparable ({len(comparison['incomparable'])}):")
            for r in comparison["incomparable"]:
                print(f"    ~ {r['test_name']}: {r['detail']}")
        return 0

    elif action == "leaderboard":
        print(print_leaderboard())
        return 0

    else:
        print(f"Unknown eval action: {action}", file=sys.stderr)
        print("Usage: openamer eval run|compare|leaderboard", file=sys.stderr)
        return 2


# ── RAG Pipeline CLI ──────────────────────────────────────────────────────────


def _get_rag_pipeline(args: Any) -> RagPipeline:
    """Create or load a RagPipeline from CLI args."""
    strategy_map = {
        "fixed_size": ChunkingStrategy.FIXED_SIZE,
        "paragraph": ChunkingStrategy.PARAGRAPH,
        "recursive": ChunkingStrategy.RECURSIVE,
    }
    strategy = strategy_map.get(
        getattr(args, "strategy", "recursive"), ChunkingStrategy.RECURSIVE
    )
    pipeline = RagPipeline(chunking_strategy=strategy)
    index_name = getattr(args, "index_name", "default")
    pipeline.load_index(name=index_name)
    return pipeline


def cmd_rag(args: Any) -> None:
    """Handle ``openamer rag ingest|query|info``."""
    action = getattr(args, "rag_action", None)

    if action == "ingest":
        path_str = args.path
        path = Path(path_str).resolve()

        if not path.exists():
            print(f"Error: path does not exist: {path}", file=sys.stderr)
            sys.exit(1)

        pipeline = _get_rag_pipeline(args)
        chunk_size = getattr(args, "chunk_size", 500)

        if path.is_dir():
            n = pipeline.ingest_directory(
                path,
                pattern="**/*",
                recursive=True,
                chunk_size=chunk_size,
            )
            print(f"Ingested {n} chunk(s) from directory: {path}")
        else:
            n = pipeline.ingest_file(path, chunk_size=chunk_size)
            print(f"Ingested {n} chunk(s) from file: {path}")

        index_name = getattr(args, "index_name", "default")
        pipeline.save_index(name=index_name)
        print(f"Index saved as: {index_name}")
        print(f"Pipeline stats: {pipeline.stats}")

    elif action == "query":
        query_text = args.query
        top_k = getattr(args, "top_k", 5)
        pipeline = _get_rag_pipeline(args)

        if pipeline.stats["chunks"] == 0:
            print("No indexed documents. Use `openamer rag ingest` first.")
            return

        # Show retrieved context
        print(f"\nQuery: {query_text}")
        print(f"Retrieving top {top_k} chunks...\n")

        results = pipeline.retrieve(query_text, top_k=top_k)
        if not results:
            print("No relevant results found.")
            return

        for r in results:
            source = f" ({r.chunk.source})" if r.chunk.source else ""
            print(f"  [{r.rank}] score={r.score:.3f}{source}")
            # Show first 200 chars
            preview = r.chunk.text[:200].replace("\n", " ")
            print(f"      {preview}...")
            print()

    elif action == "info":
        pipeline = _get_rag_pipeline(args)
        stats = pipeline.stats
        print("\nRAG Pipeline Status:")
        print(f"  Chunks:           {stats['chunks']}")
        print(f"  Documents:        {stats['documents']}")
        print(f"  Vectorizer ready: {stats['fitted']}")
        print(f"  Chunking:         {stats['chunking_strategy']}")

    else:
        print(f"Unknown rag action: {action}", file=sys.stderr)
        print("Usage: openamer rag ingest|query|info", file=sys.stderr)
        sys.exit(1)


# ── Internal helpers ──────────────────────────────────────────────────────────


_PLUGIN_HOST_CACHE: Optional[PluginHost] = None


def _get_plugin_host() -> PluginHost:
    """Get or create the cached PluginHost singleton."""
    global _PLUGIN_HOST_CACHE
    if _PLUGIN_HOST_CACHE is None:
        _PLUGIN_HOST_CACHE = PluginHost()
        _PLUGIN_HOST_CACHE.load_all()
    return _PLUGIN_HOST_CACHE