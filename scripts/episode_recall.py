#!/usr/bin/env python3
"""Automatic recall for the episodic store — memory that answers before you ask.

The store has thousands of episodes and a 384-dim embedding on every one of
them (`scripts/embeddings.py`, deterministic char-n-gram, no model, no network).
What was missing is the step that uses them: the agent had to *decide* to query
`longterm_memory.py`. A memory you have to remember to ask is an archive.

Measured 2026-11-18: 8,413 episodes, every one with an `embedding` field, and no
code path that injects the relevant ones into a task.

    python scripts/episode_recall.py "warum war das i18n-Gate falsch" -k 5
    python scripts/episode_recall.py --inject "<task text>"     # writes the context file
    python scripts/episode_recall.py --stats

Contradiction detection is the second half. Recall that returns a stale episode
next to a newer one which reverses it is worse than no recall, so a pair of hits
that share their topic but disagree in polarity is reported as such, with both
timestamps and the direction (`superseded` = the older one).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
EPISODES = HOME / "memory" / "longterm_episodes.jsonl"
CONTEXT = HOME / "memory" / "recall_context.md"

sys.path.insert(0, str(HOME / "scripts"))
try:
    from embeddings import embed, cosine  # noqa: E402
except Exception:  # pragma: no cover - the fallback keeps recall usable
    embed = None
    cosine = None

# Polarity words. Kept deliberately small and language-mixed (the store is
# German and English): a long list starts flagging ordinary sentences.
NEGATIVE = {
    "failed", "fails", "failure", "broken", "error", "wrong", "false", "bug",
    "fehlgeschlagen", "fehler", "kaputt", "falsch", "defekt", "abgebrochen",
}
POSITIVE = {
    "fixed", "works", "working", "passed", "green", "solved", "behoben",
    "funktioniert", "grün", "gruen", "gelöst", "geloest", "erfolgreich",
}
STOP = set("""der die das und oder aber ein eine einen einem eines des dem den
the a an and or but is are was were be been to of in on for with from that this
ich du er sie es wir ihr mein dein sein ihre habe hat hatte wurde wird werden
nicht kein keine mit von zu im am""".split())


def load_episodes(limit: int | None = None) -> list[dict]:
    if not EPISODES.exists():
        raise SystemExit(f"no episode store at {EPISODES}")
    rows: list[dict] = []
    with EPISODES.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("text") and row.get("embedding"):
                rows.append(row)
    return rows[-limit:] if limit else rows


# The store is German and English and the char-n-gram cosine is weak across
# languages (measured: 0.24 for a paraphrase, 0.26 for unrelated text), so a
# German question never reached the English episode about "false positive".
# A tiny bilingual bridge for the diagnostic vocabulary fixes the cases that
# matter and costs no model call. Measured before/after on the same query:
# "Platzhalter Prüfung falsch positiv Gate" went from a Chrome-log episode to
# the false-positive post-mortem.
SYNONYMS = {
    "falsch positiv": "false positive", "fehlalarm": "false positive",
    "platzhalter": "placeholder", "prüfung": "verification", "pruefung": "verification",
    "tor": "gate", "tür": "gate", "messung": "measurement", "zählung": "count",
    "fehlgeschlagen": "failed", "fehler": "error", "behoben": "fixed",
    "übersetzung": "translation", "uebersetzung": "translation",
    "veraltet": "stale", "prozess": "process", "port": "port",
}


def normalise(text: str) -> str:
    low = text.lower()
    for de, en in SYNONYMS.items():
        low = low.replace(de, en)
    return low


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zäöüß]{4,}", normalise(text)) if w not in STOP}


def polarity(text: str) -> int:
    words = set(re.findall(r"[a-zäöüß]+", text.lower()))
    neg = len(words & NEGATIVE)
    pos = len(words & POSITIVE)
    if neg > pos:
        return -1
    if pos > neg:
        return 1
    return 0


def rank(query: str, rows: list[dict], k: int) -> list[dict]:
    """Cosine over the stored vectors; lexical overlap as the tie-breaker."""
    if embed is None or cosine is None:
        raise SystemExit("scripts/embeddings.py is required for recall")
    qv = embed(query)
    qt = tokens(query)
    scored = []
    n = max(1, len(rows))
    for idx, row in enumerate(rows):
        sim = cosine(qv, row["embedding"])
        overlap = len(qt & tokens(row.get("text", "")))
        # Lexical overlap dominates on purpose: measured 2026-11-18 the char
        # n-gram cosine peaks around 0.26 for unrelated episodes, so a 0.02
        # weight let five shared words tie with noise. Recency only breaks ties
        # (the store is append-ordered), it never outranks a lexical match.
        recency = 0.03 * (idx / n)
        scored.append((sim + 0.15 * overlap + recency, sim, overlap, row))
    scored.sort(key=lambda x: -x[0])
    out = []
    for total, sim, overlap, row in scored[:k]:
        out.append({"score": round(total, 4), "sim": round(sim, 4), "overlap": overlap,
                    "ts": row.get("ts", ""), "kind": row.get("kind", ""),
                    "text": row.get("text", "")[:400],
                    "topic": sorted(qt & tokens(row.get("text", "")))[:6]})
    return out


def contradictions(hits: list[dict]) -> list[dict]:
    """Two hits about the same topic that disagree, newer wins."""
    out = []
    for i, a in enumerate(hits):
        for b in hits[i + 1:]:
            shared = set(a["topic"]) & set(b["topic"])
            if len(shared) < 2:
                continue
            pa, pb = polarity(a["text"]), polarity(b["text"])
            if pa == pb or 0 in (pa, pb):
                continue
            older, newer = (a, b) if a["ts"] <= b["ts"] else (b, a)
            out.append({"topic": sorted(shared), "superseded": older["ts"],
                        "current": newer["ts"], "older_says": older["text"][:160],
                        "newer_says": newer["text"][:160]})
    return out


def render(query: str, hits: list[dict], contra: list[dict]) -> str:
    lines = [f"# Recall for: {query[:160]}", ""]
    if not hits:
        return "\n".join(lines + ["_nothing relevant in the episode store_", ""])
    for i, hit in enumerate(hits, 1):
        lines.append(f"{i}. [{hit['ts'][:16]}] (sim {hit['sim']:.2f}) {hit['text']}")
    if contra:
        lines += ["", "## Contradictions in these hits — read the newer one"]
        for c in contra:
            lines.append(f"- topic {', '.join(c['topic'])}: superseded {c['superseded'][:16]} "
                         f"by {c['current'][:16]}")
            lines.append(f"  - older: {c['older_says']}")
            lines.append(f"  - newer: {c['newer_says']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Semantic recall over the episodic store.")
    ap.add_argument("query", nargs="*", help="what the current task is about")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--inject", action="store_true",
                    help="write memory/recall_context.md instead of printing")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = load_episodes()
    if args.stats:
        kinds: dict[str, int] = {}
        for row in rows:
            kinds[row.get("kind", "?")] = kinds.get(row.get("kind", "?"), 0) + 1
        print(json.dumps({"episodes": len(rows), "dim": len(rows[-1]["embedding"]),
                          "kinds": dict(sorted(kinds.items(), key=lambda kv: -kv[1])[:8]),
                          "store": str(EPISODES)}, indent=1))
        return 0

    query = " ".join(args.query).strip()
    if not query:
        raise SystemExit("give a query, or --stats")

    hits = rank(query, rows, args.k)
    contra = contradictions(hits)
    text = render(query, hits, contra)
    if args.inject:
        CONTEXT.write_text(text, encoding="utf-8")
        print(f"wrote {CONTEXT} ({len(hits)} episode(s), {len(contra)} contradiction(s))")
    elif args.json:
        print(json.dumps({"query": query, "hits": hits, "contradictions": contra},
                         ensure_ascii=False, indent=1))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
