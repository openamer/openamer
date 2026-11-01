"""Turn real agent sessions into a dialogue corpus.

Why: the brain was trained on `a2a/openamer-brain.jsonl`, which is an
ASSISTANT-TEXT corpus, not a dialogue corpus. Measured 2026-11-01 on the
curated corpus:

    assistant markers  21,362
    user markers          936
    user->assistant       899 pairs in 12.9M chars (one per 14,350 chars)

Result: top-1 accuracy 49.7% (it learned the byte statistics of OpenAmer text)
but 0% on dialogue format — it never opens with `<|assistant|>` because it
almost never saw that transition.

This module mines `state.db` (read-only) instead: 2,849 sessions with 6,756
real user messages and 98,977 assistant replies. Each user turn plus the
assistant reply that answers it is one training pair.

    python session_corpus.py --limit 500        # dry run, show what it finds
    python session_corpus.py --write            # append to session_dialogues.jsonl

Privacy: everything stays on this machine. The rows come from this install's
own session store and are written to this install's own corpus file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME") or Path.home() / ".openamer")
DEFAULT_DB = HOME / "state.db"
OUT_FILE = HOME / "scripts" / "training" / "session_dialogues.jsonl"

MIN_USER = 12
MAX_USER = 4000
MAX_ASST = 4000

# Turns that are machinery, not conversation.
NOISE_PATTERNS = (
    re.compile(r"^\[System note:", re.I),
    re.compile(r"previous turn was interrupted", re.I),
    re.compile(r"^\s*<[a-z_]+>.*</[a-z_]+>\s*$", re.S),   # bare xml wrappers
    re.compile(r"^\[OUT-OF-BAND USER MESSAGE", re.I),
    re.compile(r"^\[IMPORTANT: Background process", re.I),
    re.compile(r"^(Context compacted|Conversation compressed)", re.I),
    re.compile(r"^\s*/\w+\s*$"),                            # bare slash-commands
    re.compile(r"^\[Request interrupted", re.I),
    # Compaction artefacts appear MID-text, not only at the start: a reply that
    # begins with the user's next sentence and then embeds the summary block.
    re.compile(r"\[PRIOR CONTEXT\b", re.I),
    re.compile(r"\[END OF PRIOR CONTEXT\b", re.I),
    re.compile(r"COMPACTION SUMMARY", re.I),
    re.compile(r"\[Context compacted\b", re.I),
)


def is_noise(text: str) -> bool:
    return any(p.search(text) for p in NOISE_PATTERNS)


def clean(text: str) -> str:
    return re.sub(r"[ \t\u00a0]+", " ", (text or "").replace("\r", "")).strip()


def iter_pairs(db_path: Path, limit_sessions: int | None = None):
    """Yield (session_id, user_text, assistant_text) from the session store."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    try:
        sessions = [r[0] for r in con.execute(
            "SELECT DISTINCT session_id FROM messages "
            "WHERE role IN ('user','assistant') ORDER BY session_id")]
        if limit_sessions:
            sessions = sessions[:limit_sessions]
        for sid in sessions:
            rows = con.execute(
                "SELECT role, content FROM messages "
                "WHERE session_id = ? AND role IN ('user','assistant') "
                "AND (active IS NULL OR active = 1) ORDER BY id",
                (sid,),
            )
            pending_user = None
            for role, content in rows:
                text = clean(content)
                if not text:
                    continue
                if role == "user":
                    pending_user = text
                    continue
                if pending_user and role == "assistant":
                    yield sid, pending_user, text
                    pending_user = None
    finally:
        con.close()


def build_records(db_path: Path = DEFAULT_DB, limit_sessions: int | None = None,
                  min_user: int = MIN_USER) -> tuple[list[dict], dict]:
    """Turn pairs into corpus records, dropping machinery and duplicates."""
    stats = {"sessions_seen": 0, "pairs_raw": 0, "dropped_noise": 0,
             "dropped_short": 0, "dropped_duplicate": 0, "kept": 0,
             "chars_kept": 0}
    if not Path(db_path).exists():
        return [], stats
    seen: set[str] = set()
    records: list[dict] = []
    last_sid = None

    for sid, user, asst in iter_pairs(db_path, limit_sessions):
        if sid != last_sid:
            stats["sessions_seen"] += 1
            last_sid = sid
        stats["pairs_raw"] += 1
        if is_noise(user) or is_noise(asst):
            stats["dropped_noise"] += 1
            continue
        if len(user) < min_user or len(asst) < 2:
            stats["dropped_short"] += 1
            continue
        key = " ".join(user.lower().split())[:200]
        if key in seen:
            stats["dropped_duplicate"] += 1
            continue
        seen.add(key)
        u = user[:MAX_USER]
        a = asst[:MAX_ASST]
        records.append({
            "messages": [{"role": "user", "content": u},
                         {"role": "assistant", "content": a}],
            "engine": "session-dialogue",
            "session": sid,
        })
        stats["kept"] += 1
        stats["chars_kept"] += len(u) + len(a)
    return records, stats


def write_records(records: list[dict], out: Path = OUT_FILE) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--limit", type=int, default=0,
                    help="only the first N sessions (0 = all)")
    ap.add_argument("--write", action="store_true", help="write the corpus file")
    ap.add_argument("--out", default=str(OUT_FILE))
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"✗ session store not found: {db}")
        return 1

    records, stats = build_records(db, args.limit or None)
    print(f"sessions scanned : {stats['sessions_seen']:,}")
    print(f"pairs found      : {stats['pairs_raw']:,}")
    print(f"  dropped noise  : {stats['dropped_noise']:,}")
    print(f"  dropped short  : {stats['dropped_short']:,}")
    print(f"  dropped dupes  : {stats['dropped_duplicate']:,}")
    print(f"kept             : {stats['kept']:,} pairs, {stats['chars_kept']:,} chars")
    if records:
        lens = sorted(len(r["messages"][0]["content"]) + len(r["messages"][1]["content"])
                      for r in records)
        print(f"median pair      : {lens[len(lens)//2]:,} chars")
        print("\nsample:")
        for r in records[:2]:
            print(f"  U: {r['messages'][0]['content'][:100]!r}")
            print(f"  A: {r['messages'][1]['content'][:100]!r}")
    if args.write and records:
        out = write_records(records, Path(args.out))
        print(f"\n[written] {out} ({out.stat().st_size/1e6:.2f} MB)")
    return 0 if records else 1


if __name__ == "__main__":
    raise SystemExit(main())
