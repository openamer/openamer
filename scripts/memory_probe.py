#!/usr/bin/env python
"""memory_probe — a repeatable benchmark for the episodic store's retrieval.

Any change to `longterm_memory.query` needs a number, not an opinion. This runs a
fixed probe set against the live store and prints, per question, where the first
relevant episode lands under three schemes:

    vector   cosine only
    hybrid   RRF over an IDF-weighted lexical list (what ships)
    rescue   hybrid plus pseudo-relevance feedback when no term matches at all

Two probe families, because they exercise opposite weaknesses:

    identifier   built from rare words of a real episode - file names, ports,
                 command fragments, the way this store is actually searched
    paraphrase   a question sharing little or no vocabulary with the answer

Exit code is 1 when hybrid loses to plain vector on any identifier probe: that is
the regression this benchmark exists to catch.

    python scripts/memory_probe.py            # live store
    python scripts/memory_probe.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import longterm_memory as memory  # noqa: E402

STOPWORDS = frozenset(
    "the and for with that this from were was has have not but you der die das und "
    "ist nicht ein eine mit auf für den dem des ich wir sie es zu von im".split()
)
TOKEN = re.compile(r"[a-z0-9_\-]{4,}")

# Fixed on purpose: a benchmark that redraws its questions every run cannot be
# compared across runs. Each expects a distinctive term that the target episode
# must contain.
PARAPHRASE_PROBES = [
    ("wie sorge ich dafuer dass ein prozess nach absturz neu startet", "watchdog"),
    ("wie speichere ich erinnerungen dauerhaft", "embedding"),
    ("git konflikte beim zusammenfuehren", "rebase"),
    ("warum schlaegt der build auf windows fehl", "windows"),
    ("wie sende ich eine nachricht an telegram", "telegram"),
    ("wie zaehle ich die skills die installiert sind", "skills"),
]


def tokens(text: str) -> set[str]:
    return {word for word in TOKEN.findall(text.lower()) if word not in STOPWORDS}


def identifier_probes(episodes: list[dict], count: int = 12, seed: int = 7) -> list[tuple[str, str]]:
    """Questions assembled from rare words of real episodes.

    The needle is the *rarest* of the three words: judging relevance by the whole
    episode text means matching a 2,000-character string against itself, which
    quietly fails on any case difference and reports "not found" for every probe.

    Deterministic: same seed, same corpus size -> comparable runs.
    """
    import random

    frequency: dict[str, int] = {}
    for episode in episodes:
        for word in tokens(episode.get("text", "")):
            frequency[word] = frequency.get(word, 0) + 1

    random.seed(seed)
    pool = [e for e in episodes if len(e.get("text", "")) > 200]
    probes = []
    for episode in random.sample(pool, min(count * 2, len(pool))):
        words = sorted(tokens(episode["text"]))
        if len(words) < 3:
            continue
        chosen = random.sample(words, 3)
        needle = min(chosen, key=lambda word: frequency.get(word, 10 ** 9))
        probes.append((" ".join(chosen), needle))
        if len(probes) == count:
            break
    return probes


def rank_of(results: list[tuple[float, dict]], needle: str) -> int | None:
    needle = needle.lower()
    for position, (_score, record) in enumerate(results, start=1):
        if needle in record.get("text", "").lower():
            return position
    return None


def cosine_only_rank(episodes: list[dict], question: str, needle: str) -> int | None:
    import numpy as np  # local import: the benchmark is the only caller that needs it

    vectors = [(i, e["embedding"]) for i, e in enumerate(episodes) if e.get("embedding")]
    matrix = np.array([v for _i, v in vectors], dtype=np.float32)
    matrix /= (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
    query = np.array(memory.embed(question), dtype=np.float32)
    query /= (np.linalg.norm(query) + 1e-9)
    order = np.argsort(-(matrix @ query))
    for position, offset in enumerate(order, start=1):
        if needle in episodes[vectors[offset][0]].get("text", "").lower():
            return position
    return None


def measure(episodes: list[dict], question: str, needle: str) -> tuple[int | None, int | None]:
    """Where the needle lands under plain cosine and under the shipped retrieval."""
    total = len(episodes)
    return cosine_only_rank(episodes, question, needle), rank_of(memory.query(question, total), needle)


def run(json_output: bool) -> int:
    episodes = memory._load()
    if not episodes:
        print("store is empty", file=sys.stderr)
        return 2

    rows = []
    regressions = []
    families = (("identifier", identifier_probes(episodes)), ("paraphrase", PARAPHRASE_PROBES))

    for family, probes in families:
        for question, needle in probes:
            vector_rank, hybrid_rank = measure(episodes, question, needle)
            rows.append({"family": family, "question": question, "expected": needle[:40],
                         "vector": vector_rank, "hybrid": hybrid_rank})
            lost = hybrid_rank is None or (vector_rank is not None and hybrid_rank > vector_rank)
            if family == "identifier" and lost:
                regressions.append(question)

    if json_output:
        print(json.dumps({"episodes": len(episodes), "probes": rows,
                          "identifier_regressions": regressions}, indent=1, ensure_ascii=False))
        return 1 if regressions else 0

    print(f"store: {len(episodes)} episodes\n")
    print(f"{'family':<11} {'question':<44} {'vector':>8} {'hybrid':>8}")
    for row in rows:
        mark = ""
        if row["family"] == "identifier" and None not in (row["vector"], row["hybrid"]):
            mark = "  better" if row["hybrid"] < row["vector"] else ""
        print(f"{row['family']:<11} {row['question'][:42]:<44} {str(row['vector']):>8} {str(row['hybrid']):>8}{mark}")
    print(f"\nidentifier regressions: {len(regressions)}")
    return 1 if regressions else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memory_probe", description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    return run(args.json)


if __name__ == "__main__":
    raise SystemExit(main())
