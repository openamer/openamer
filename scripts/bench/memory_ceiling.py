#!/usr/bin/env python3
"""How much headroom does retrieval leave before a reranker can help?

A reranker can only reorder what it is given. If the labelled answer is not in
the candidate pool at all, no ranking function of any sophistication can bring
it into the top-k -- so before tuning weights, measure the ceiling:

    recall@k ceiling(pool) = share of labels whose target is inside the top-`pool`
                             of the RRF fusion of cosine + lexical retrieval

Two questions this answers that a score alone cannot:

* Is a weak recall@5 a *ranking* problem (target in the pool, ranked low) or a
  *retrieval* problem (target never retrieved)? The first is fixable by
  reranking, the second only by a better index or a better embedding model.
* How wide does the pool have to be before reranking stops paying?

Writes ``reports/memory-eval/ceiling.json``; read-only otherwise.

Usage::

    python scripts/bench/memory_ceiling.py            # pools 5,10,25,50,100,200,500
    python scripts/bench/memory_ceiling.py --json     # machine-readable only
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path

BASE = Path(
    Path(os.environ.get("OPENAMER_HOME") or "").resolve()
    if os.environ.get("OPENAMER_HOME")
    else (
        Path.home() / "AppData" / "Local" / "openamer-laptop"
        if os.name == "nt"
        else Path.home() / ".openamer-laptop"
    )
)
OUT_DIR = BASE / "reports" / "memory-eval"
DEFAULT_POOLS = (5, 10, 25, 50, 100, 200, 500)

sys.path.insert(0, str(Path(__file__).resolve().parent))

import memory_eval as me  # noqa: E402


def fused_positions(labels: list[dict], hashes: list[str], vectors, limit: int | None = None) -> list[dict]:
    """Rank of each label's target in the RRF fusion over the whole store."""
    rows = []
    for label in labels[:limit] if limit else labels:
        question = label["question"]
        target = label["expect_hash"]
        semantic = me.rank_nomic(question, 0, hashes, vectors, pool=len(hashes))
        lexical = me.rank_lexical(question, pool=len(hashes))

        semantic_position = next((i + 1 for i, (_s, d) in enumerate(semantic) if d == target), None)
        lexical_position = next((i + 1 for i, (_s, d) in enumerate(lexical) if d == target), None)

        combined: dict[str, float] = collections.defaultdict(float)
        for ranking in (semantic, lexical):
            for position, (_score, digest) in enumerate(ranking, start=1):
                combined[digest] += 1.0 / (60 + position)
        ordered = sorted(combined.items(), key=lambda pair: -pair[1])
        fused = next((i + 1 for i, (digest, _v) in enumerate(ordered) if digest == target), None)

        rows.append(
            {
                "id": label["id"],
                "class": label.get("class"),
                "semantic_rank": semantic_position,
                "lexical_rank": lexical_position,
                "fused_rank": fused,
            }
        )
    return rows


def ceiling_table(rows: list[dict], pools: tuple[int, ...], k: int) -> dict:
    total = len(rows)
    reachable = [row for row in rows if row["fused_rank"]]
    table = {}
    for pool in pools:
        inside = sum(1 for row in reachable if row["fused_rank"] <= pool)
        table[str(pool)] = {
            "labels_with_target_in_pool": inside,
            "ceiling_recall_at_k": round(inside / total, 3) if total else 0.0,
        }
    # The share a perfect reranker would add over plain recall@k (pool == k).
    baseline = sum(1 for row in reachable if row["fused_rank"] <= k)
    return {
        "labels": total,
        "k": k,
        "targets_found_in_any_ranking": len(reachable),
        "targets_never_retrieved": total - len(reachable),
        "baseline_hits_at_k": baseline,
        "baseline_recall_at_k": round(baseline / total, 3) if total else 0.0,
        "by_pool": table,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pools", default=",".join(str(p) for p in DEFAULT_POOLS))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    pools = tuple(sorted({int(p) for p in args.pools.split(",") if p.strip()}))
    started = time.perf_counter()

    labels = me.load_labels(args.limit)
    hashes, vectors = me.load_nomic_index()
    rows = fused_positions(labels, hashes, vectors, args.limit)
    summary = ceiling_table(rows, pools, args.k)
    summary["measured_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    summary["elapsed_seconds"] = round(time.perf_counter() - started, 1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "ceiling.json").write_text(json.dumps({**summary, "rows": rows}, indent=1), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=1))
        return 0

    print(f"# Retrieval ceiling\n\nMeasured: {summary['measured_at']}  ")
    print(f"Labels: {summary['labels']} · k={summary['k']} · targets never retrieved: {summary['targets_never_retrieved']}\n")
    print("| pool | labels inside | ceiling recall@k |")
    print("|---|---|---|")
    for pool, stats in summary["by_pool"].items():
        print(f"| {pool} | {stats['labels_with_target_in_pool']} | {stats['ceiling_recall_at_k']} |")
    print(f"\nstored: {OUT_DIR / 'ceiling.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
