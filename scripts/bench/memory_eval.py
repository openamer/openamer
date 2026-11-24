#!/usr/bin/env python3
"""Score episodic memory retrieval against a labelled question set.

Why this exists
---------------
On 2026-11-23 the store held 8356 episodes and nobody could say whether it
returns the *right* episode for a question. A store that is never scored is an
archive, not a memory. This script turns that claim into two numbers
(precision@k, recall@k) plus a list of the questions the store fails.

How the labels work
-------------------
`missions/beyond-all/memory-eval-set.jsonl` holds one line per question:

    {"id": "m01", "expect_hash": "<sha1[:12] of the target episode text>",
     "question": "..."}

The hash is derived from the episode text itself, so a label can be re-checked
years later: the script refuses to score if the target hash is missing from the
store or ambiguous (appears more than once). A label that cannot be resolved is
a broken measurement, not a miss.

Difficulty is derived, not declared
-----------------------------------
For every question this script computes whether it shares a *rare* token
(document frequency <= 2) with its target episode. A question with no such
overlap cannot be solved by keyword matching, so it measures semantic
retrieval; a question with overlap can be solved by a term match. Reporting both
groups separately keeps a good lexical scorer from being mistaken for a good
memory.

Usage
-----
    python scripts/bench/memory_eval.py                # full run, stores result
    python scripts/bench/memory_eval.py --k 5 --limit 10
    python scripts/bench/memory_eval.py --json         # machine-readable only
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Resolve the install home, not the checkout. Previously this was
# `Path(__file__).resolve().parents[2]`, which happened to be correct only
# because the script lived in `<home>/scripts/bench/`. That made it impossible
# to version: a copy inside the repository resolved BASE to the repository and
# then looked for the episode store in a directory that does not exist there.
# The instrument now finds the same data from either location.
BASE = (
    Path(os.environ.get("OPENAMER_HOME") or "").resolve()
    if os.environ.get("OPENAMER_HOME")
    else (
        Path.home() / "AppData" / "Local" / "openamer-laptop"
        if os.name == "nt"
        else Path.home() / ".openamer-laptop"
    )
)
SCRIPTS = BASE / "scripts"
STORE = BASE / "memory" / "longterm_episodes.jsonl"
LABELS = BASE / "missions" / "beyond-all" / "memory-eval-set.jsonl"
OUT_DIR = BASE / "reports" / "memory-eval"

sys.path.insert(0, str(SCRIPTS))

TOKEN = re.compile(r"[a-z\u00e0-\u00ff\u0161\u0111\u010d\u0107\u017e_][a-z\u00e0-\u00ff\u0161\u0111\u010d\u0107\u017e0-9_.\-]{3,}")


def tokens(text: str) -> set[str]:
    return set(TOKEN.findall(text.lower()))


def text_hash(text: str) -> str:
    return hashlib.sha1(text.strip().encode()).hexdigest()[:12]


def load_store_index() -> dict[str, list[str]]:
    """hash -> list of episode texts (list, so ambiguity is visible)."""
    index: dict[str, list[str]] = collections.defaultdict(list)
    with open(STORE, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = (record.get("text") or "").strip()
            if text:
                index[text_hash(text)].append(text)
    return index


def load_labels(limit: int | None = None) -> list[dict]:
    labels = []
    with open(LABELS, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                labels.append(json.loads(line))
    return labels[:limit] if limit else labels


def document_frequencies(index: dict[str, list[str]]) -> collections.Counter:
    df: collections.Counter = collections.Counter()
    for texts in index.values():
        df.update(tokens(texts[0]))
    return df


def embed_query(question: str, model: str = "nomic-embed-text", timeout: float = 120.0):
    """Embed a question with the local model, using its asymmetric query prefix."""
    import urllib.request

    body = json.dumps({"model": model, "input": "search_query: " + question}).encode()
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/embed", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        vector = json.loads(response.read())["embeddings"][0]
    import numpy as np

    array = np.asarray(vector, dtype=np.float32)
    return array / (np.linalg.norm(array) or 1.0)


def load_nomic_index():
    import numpy as np

    data = np.load(BASE / "memory" / "embeddings-nomic.npz", allow_pickle=False)
    hashes = [str(h) for h in data["hashes"]]
    vectors = data["vectors"].astype(np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return hashes, vectors / norms


def rank_nomic(question: str, k: int, hashes: list[str], vectors, pool: int = 300) -> list[tuple[float, str]]:
    import numpy as np

    query_vector = embed_query(question)
    scores = vectors @ query_vector
    order = np.argsort(-scores)[:pool]
    return [(float(scores[i]), hashes[i]) for i in order]


def load_chunk_index():
    import numpy as np

    data = np.load(BASE / "memory" / "embeddings-nomic-chunks.npz", allow_pickle=False)
    hashes = [str(h) for h in data["hashes"]]
    vectors = data["vectors"].astype(np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return hashes, vectors / norms


def rank_chunks(question: str, k: int, hashes: list[str], vectors, pool: int = 600) -> list[tuple[float, str]]:
    """Score an episode by its BEST chunk, then rank episodes.

    A long episode is a summary of several ideas; its mean vector points between
    them and can lose to a short episode about a related but different thing.
    The maximum over chunks answers "does this record contain the fact?" instead
    of "is the average of this record about it?".
    """
    import numpy as np

    query_vector = embed_query(question)
    scores = vectors @ query_vector
    order = np.argsort(-scores)[:pool]
    best: dict[str, float] = {}
    for position in order:
        digest = hashes[position]
        value = float(scores[position])
        if value > best.get(digest, -1.0):
            best[digest] = value
    ranked = sorted(best.items(), key=lambda pair: -pair[1])
    return [(value, digest) for digest, value in ranked]


def rank_lexical(question: str, pool: int = 300) -> list[tuple[float, str]]:
    """The IDF-weighted lexical ranking from longterm_memory, reused verbatim."""
    import longterm_memory as mem

    episodes = mem._load()
    query_tokens = mem._tokens(question)
    df, total = mem._document_frequencies(episodes)
    scored = []
    for record in episodes:
        overlap = mem._keyword_score(query_tokens, record.get("text", ""), df, total)
        if overlap > 0:
            scored.append((overlap, text_hash(record.get("text", ""))))
    scored.sort(key=lambda pair: -pair[0])
    return scored[:pool]


def fuse_rankings(rankings: list[list[tuple[float, str]]], k: int, rrf_k: int = 60) -> list[str]:
    combined: dict[str, float] = {}
    for ranking in rankings:
        for position, (_score, digest) in enumerate(ranking[:300], start=1):
            combined[digest] = combined.get(digest, 0.0) + 1.0 / (rrf_k + position)
    ordered = sorted(combined.items(), key=lambda pair: -pair[1])[:k]
    return [digest for digest, _value in ordered]



def _idf(document_frequency: int, total: int) -> float:
    import math

    return math.log((total + 1.0) / (document_frequency + 1.0)) + 1.0


def _question_features(question: str, df: collections.Counter, total: int) -> tuple[list[str], list[str], float]:
    """Content terms (in order), numbers, and the total IDF mass of the question."""
    sequence = TOKEN.findall(question.lower())
    ceiling = max(40, int(total * 0.05))
    content = [term for term in sequence if len(term) >= 4 and df.get(term, 0) <= ceiling]
    numbers = [n for n in re.findall(r"\d{2,}", question)]
    mass = sum(_idf(df.get(term, 0), total) for term in set(content)) or 1.0
    return content, numbers, mass


def rerank_scores(
    question: str,
    candidates: list[str],
    index: dict[str, list[str]],
    df: collections.Counter,
    total: int,
    semantic_scores: dict[str, float],
) -> list[tuple[float, str]]:
    """Score already-retrieved candidates on evidence readable in the text.

    Pure function: no store access, no embeddings call, no I/O. Split out of
    `rank_rerank` so the weights and the ordering they produce can be tested
    without a live embedding model.

    * cosine   -- semantic proximity (raw), weight 1.5
    * coverage -- IDF-weighted share of the question's content terms present,
                  weight 1.3
    * numbers  -- share of the question's multi-digit numbers present,
                  weight 0.5 (many labels ask "wie viele", "welche drei")
    * rare     -- question terms with df <= 2 present, weight 0.2 each, cap 4

    Scale: measured on the local nomic index, the top-50 of a question spans
    0.03-0.11 cosine, so the semantic term moves by at most 1.5 * 0.11 = 0.17
    while coverage moves by up to 1.3. That is deliberate: this reranker exists
    to let readable evidence overturn a *near-tie* in embedding space, not to
    overrule a clear semantic preference. A candidate that is far ahead of the
    pool on similarity still wins.

    (Normalising the cosine to [0,1] per pool was tried and rejected: it turns
    an arbitrary 0.002 difference at the top of the pool into a full-scale 1.5
    signal, which makes the semantic term maximally influential exactly when it
    carries the least information.)
    """
    content, numbers, mass = _question_features(question, df, total)
    unique_content = set(content)

    scored: list[tuple[float, str]] = []
    for digest in candidates:
        texts = index.get(digest)
        if not texts:
            continue
        text = texts[0]
        lowered = text.lower()
        candidate_terms = tokens(text)

        coverage = sum(
            _idf(df.get(term, 0), total) for term in unique_content if term in candidate_terms
        ) / mass
        rare = sum(1 for term in unique_content if df.get(term, 0) <= 2 and term in candidate_terms)
        numeric = (sum(1 for n in numbers if n in lowered) / len(numbers)) if numbers else 0.0
        cosine = semantic_scores.get(digest, 0.0)

        score = 1.5 * cosine + 1.3 * coverage + 0.5 * numeric + 0.2 * min(rare, 4)
        scored.append((score, digest))

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return scored


def rank_rerank(
    question: str,
    k: int,
    index: dict[str, list[str]],
    df: collections.Counter,
    total: int,
    nomic_hashes: list[str],
    nomic_vectors,
    pool: int = 50,
    chunk_index: tuple[list[str], object] | None = None,
) -> list[tuple[float, str]]:
    """Retrieve a wide pool, then rerank it with question-to-document evidence.

    P1.2c: fusion alone (RRF over cosine + IDF) decides the top-5 from two
    *uncalibrated* scores, so a candidate that is obviously the answer -- because
    it carries the rare term and the number the question asks for -- can lose to
    a candidate that is merely nearby in embedding space. Weights are fixed a
    priori, never fitted on the label set; `memory_ceiling.py` measures how much
    headroom a pool of this width leaves before any reranker can help.

    When ``chunk_index`` is supplied, the semantic score of a candidate is
    ``max(episode_cosine, best_chunk_cosine)``: an episode-level mean vector is a
    blend of everything the episode says, so a record that *contains* the fact
    can sit below one that is merely *about* the topic. The max answers "does
    this record contain it", in the same units, so no new weight is introduced.

    Returns the full reranked pool; the caller truncates to k.
    """
    import numpy as np

    semantic = rank_nomic(question, k, nomic_hashes, nomic_vectors, pool=max(pool * 4, 200))
    semantic_scores = {digest: score for score, digest in semantic}
    lexical = rank_lexical(question, pool=pool)
    candidates: list[str] = list(
        dict.fromkeys([digest for _s, digest in semantic[:pool]] + [digest for _s, digest in lexical])
    )

    if chunk_index is not None:
        chunk_hashes, chunk_vectors = chunk_index
        query_vector = embed_query(question)
        scores = chunk_vectors @ query_vector
        best: dict[str, float] = {}
        for position in np.argsort(-scores):
            digest = chunk_hashes[position]
            if digest in candidates or digest in semantic_scores:
                value = float(scores[position])
                if value > best.get(digest, -1.0):
                    best[digest] = value
        for digest, value in best.items():
            if value > semantic_scores.get(digest, -1.0):
                semantic_scores[digest] = value

    return rerank_scores(question, candidates, index, df, total, semantic_scores)


def run(
    k: int,
    limit: int | None,
    as_json: bool,
    backend: str = "current",
    pool: int = 200,
    rerank_chunks: bool = False,
) -> int:
    import longterm_memory as mem

    index = load_store_index()
    df = document_frequencies(index)
    labels = load_labels(limit)

    nomic_hashes: list[str] = []
    nomic_vectors = None
    chunk_hashes: list[str] = []
    chunk_vectors = None
    if backend == "chunks":
        chunk_hashes, chunk_vectors = load_chunk_index()
        indexed = set(chunk_hashes)
        missing = [label["id"] for label in labels if label["expect_hash"] not in indexed]
        if missing:
            print(f"WARNING: {len(missing)} labels have no chunk yet ({', '.join(missing[:5])}...)", file=sys.stderr)
    if backend in ("nomic", "hybrid", "rerank"):
        nomic_hashes, nomic_vectors = load_nomic_index()
        missing = [label["id"] for label in labels if label["expect_hash"] not in set(nomic_hashes)]
        if missing:
            print(f"WARNING: {len(missing)} labels have no nomic vector yet ({', '.join(missing[:5])}...)", file=sys.stderr)

    chunk_index = None
    if backend == "rerank" and rerank_chunks:
        chunk_index = load_chunk_index()

    broken = []
    for label in labels:
        hits = index.get(label["expect_hash"])
        if not hits:
            broken.append(f"{label['id']}: target hash {label['expect_hash']} not in store")
        elif len(hits) > 1:
            broken.append(f"{label['id']}: target hash appears {len(hits)}x (ambiguous)")
    if broken:
        print("REFUSING TO SCORE — the label set itself is broken:", file=sys.stderr)
        for problem in broken:
            print("  " + problem, file=sys.stderr)
        return 2

    rows = []
    for label in labels:
        question = label["question"]
        target = index[label["expect_hash"]][0]
        rare = {t for t in tokens(target) if df.get(t, 0) <= 2}
        lexical_possible = bool(tokens(question) & rare)

        started = time.perf_counter()
        if backend == "current":
            results = mem.query(question, k=k)
            returned = [text_hash((record.get("text") or "").strip()) for _score, record in results]
        elif backend == "nomic":
            # The ranking function returns a POOL (300) so it can be fused; the
            # metric is @k, so it must be truncated here. Without this cut the
            # score silently became recall@300 (measured: 29/50 instead of
            # 12/50) while still being printed as recall@5.
            returned = [digest for _score, digest in rank_nomic(question, k, nomic_hashes, nomic_vectors)][:k]
        elif backend == "chunks":
            returned = [digest for _score, digest in rank_chunks(question, k, chunk_hashes, chunk_vectors)][:k]
        elif backend == "hybrid":
            returned = fuse_rankings(
                [rank_nomic(question, k, nomic_hashes, nomic_vectors), rank_lexical(question)], k
            )
        elif backend == "rerank":
            returned = [
                digest
                for _score, digest in rank_rerank(
                    question,
                    k,
                    index,
                    df,
                    len(index),
                    nomic_hashes,
                    nomic_vectors,
                    pool=pool,
                    chunk_index=chunk_index,
                )
            ][:k]
        else:
            raise ValueError(f"unknown backend {backend}")
        elapsed = time.perf_counter() - started

        rank = returned.index(label["expect_hash"]) + 1 if label["expect_hash"] in returned else None
        rows.append({
            "id": label["id"],
            "question": question,
            "expect_hash": label["expect_hash"],
            "rank": rank,
            "hit": rank is not None,
            "lexical_possible": lexical_possible,
            "seconds": round(elapsed, 3),
            "returned": returned,
            "target_preview": target[:160],
        })

    def summarise(subset: list[dict]) -> dict:
        if not subset:
            return {"n": 0}
        hits = sum(1 for r in subset if r["hit"])
        # precision@k counts the single correct document against the k returned
        precision = sum((1.0 / k) if r["hit"] else 0.0 for r in subset) / len(subset)
        mrr = sum((1.0 / r["rank"]) if r["rank"] else 0.0 for r in subset) / len(subset)
        return {
            "n": len(subset),
            "hits": hits,
            "recall_at_k": round(hits / len(subset), 3),
            "precision_at_k": round(precision, 3),
            "mrr": round(mrr, 3),
            "median_seconds": round(statistics.median(r["seconds"] for r in subset), 3),
        }

    overall = summarise(rows)
    by_class = {
        "keyword_solvable": summarise([r for r in rows if r["lexical_possible"]]),
        "semantic_only": summarise([r for r in rows if not r["lexical_possible"]]),
    }
    failures = [
        {"id": r["id"], "question": r["question"], "rank": r["rank"],
         "class": "keyword" if r["lexical_possible"] else "semantic",
         "target_preview": r["target_preview"]}
        for r in rows if not r["hit"]
    ]

    result = {
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "backend": backend,
        "store": str(STORE),
        "store_episodes": len(index),
        "labels": str(LABELS),
        "k": k,
        "overall": overall,
        "by_class": by_class,
        "failures": failures,
        "rows": rows,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    (OUT_DIR / f"{stamp}-{backend}.json").write_text(payload, encoding="utf-8")

    # A partial run must never become "latest": that file is what the trend and
    # the docs quote, and a `--limit 5` smoke run once overwrote the 50-label
    # score with a 5-label one that looked authoritative.
    if limit:
        print(f"partial run ({len(labels)} labels) - not written to latest/comparison", file=sys.stderr)
        return 0

    (OUT_DIR / f"latest-{backend}.json").write_text(payload, encoding="utf-8")
    # `latest.json` must mean "the newest complete run", whatever backend that
    # was -- and it must say which one, because the payload carries `backend`.
    # Measured trap this fixes (2026-11-24): `latest.json` was a leftover
    # 19:09 baseline run that this code never rewrote, so a reader (me) took
    # 0.14 to be the `chunks` score when the real chunks score was 0.18 and
    # lived in `latest-chunks.json`. An unqualified "latest" that points at a
    # stale run is worse than no file: it is believed.
    (OUT_DIR / "latest.json").write_text(payload, encoding="utf-8")

    # Keep every backend's latest score side by side, so a comparison is one read.
    comparison_path = OUT_DIR / "comparison.json"
    comparison = {}
    if comparison_path.exists():
        try:
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            comparison = {}
    comparison[backend] = {
        "measured_at": result["measured_at"],
        "k": k,
        "overall": overall,
        "by_class": by_class,
        "failures": [f["id"] for f in failures],
    }
    comparison_path.write_text(json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8")


    lines = [
        "# Memory retrieval score",
        "",
        f"Measured: {result['measured_at']}  ",
        f"Store: {len(index)} episodes · labels: {len(rows)} · k={k}",
        "",
        "| Group | n | hits | recall@k | precision@k | MRR | median s |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, stats in [("overall", overall), *by_class.items()]:
        if stats.get("n"):
            lines.append(
                f"| {name} | {stats['n']} | {stats['hits']} | {stats['recall_at_k']} | "
                f"{stats['precision_at_k']} | {stats['mrr']} | {stats['median_seconds']} |"
            )
    lines += ["", "## Failures", ""]
    if failures:
        for f in failures:
            lines.append(f"- **{f['id']}** ({f['class']}) — {f['question']}")
    else:
        lines.append("None: every labelled question returned its target within top-{}.".format(k))
    (OUT_DIR / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if as_json:
        print(json.dumps({k2: v for k2, v in result.items() if k2 != "rows"}, indent=2, ensure_ascii=False))
    else:
        print("\n".join(lines))
        print(f"\nstored: {OUT_DIR / f'latest-{backend}.json'}  (and latest.json)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--backend",
        default="current",
        choices=["current", "nomic", "hybrid", "chunks", "rerank"],
        help=(
            "current = production query(); nomic = local model vectors only; "
            "chunks = best-chunk per episode; hybrid = nomic fused with the IDF "
            "lexical ranking; rerank = top-pool of both, reranked on cosine + "
            "term coverage + numbers + rare terms"
        ),
    )
    parser.add_argument(
        "--pool",
        type=int,
        default=200,
        help=(
            "rerank candidate-pool width per retriever (default 200, which "
            "memory_ceiling.py measures as the widest pool that still pays: "
            "ceiling recall@5 0.68 against 0.34 at pool 10)"
        ),
    )
    parser.add_argument(
        "--rerank-chunks",
        action="store_true",
        help=(
            "rerank backend only: score a candidate by max(episode cosine, "
            "best-chunk cosine) instead of the episode mean vector alone. "
            "Measured 2026-11-24 and NOT adopted: recall@5 0.32 / MRR 0.218 "
            "against 0.34 / 0.245 without it, so the flag defaults off"
        ),
    )
    args = parser.parse_args()
    return run(args.k, args.limit, args.json, args.backend, args.pool, args.rerank_chunks)


if __name__ == "__main__":
    raise SystemExit(main())
