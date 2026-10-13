#!/usr/bin/env python3
"""One-time cleanup: strip junk + exact duplicates from the online buffer.

The buffer feeds both the rolling CPU LoRA and (via replay) the nightly
training data, so junk rows must be removed from the STORE, not only blocked
at the writer — online_learning's replay branch re-injects old rows.

Archives every removed row to `buffer_junk_archive.jsonl` (never silent, never
destructive) and rewrites the buffer with the survivors. Refuses to write an
empty result (an empty read is a bug, not an intent).
"""
import json
import sys
import re
from pathlib import Path

T = Path(__file__).parent
sys.path.insert(0, str(T))
import buffer_store as bs

BUF = T / "online_buffer.jsonl"

# Instruction ECHO: the loop buffering its own prompt back at itself rather
# than an answer (mirrors internet_learner._INSTRUCTION_OPENER_RE and the
# producer-side guard in active_learn.cross_connect). Anchored + imperative
# on purpose: genuine declarative answers on the same topic must survive.
_ECHO_OPENER_RE = re.compile(
    r"^\s*\**\s*(?:need\b|task\s*:|goal\s*:|ask\s*:|user\s+asks\s*:|"
    r"question\s*:\s*(?:find|identify|what|how|why)\b|"
    r"find\s+(?:the\s+)?(?:structural\s+)?connection|"
    r"identify\s+(?:the\s+)?(?:shared\s+)?(?:underlying\s+)?pattern|"
    r"they\s+want\s+me\s+to|"
    r"what\s+(?:is\s+)?(?:the\s+)?(?:shared|structural))",
    re.IGNORECASE)
# Prompt-echo, FOURTH shape (live 16.09.26): the TAIL form of the same leak --
# `... + Trend\n\nWhat is the shared underlying pattern?` and the bare 26-char
# `Shared underlying pattern?`. Mirrors active_learn._ECHO_TAIL_RE and
# buffer_store._ECHO_TAIL_RE; keep all three in sync.
_ECHO_TAIL_RE = re.compile(
    r"(?:what\s+is\s+the\s+)?shared\s+underlying\s+pattern\s*\??\s*$",
    re.IGNORECASE)
# Fifth shape (16.09.26): the 2B extractor's numbered `**Identify the Goal:**`
# template. Mirrors buffer_store._ECHO_TEMPLATE_RE; keep both in sync.
_ECHO_TEMPLATE_RE = re.compile(
    r"identify\s+the\s+goal\s*:|the\s+insight\s+should\s+be",
    re.IGNORECASE)
ARCHIVE = T / "buffer_junk_archive.jsonl"


def main():
    rows = [json.loads(l) for l in open(BUF, encoding="utf-8") if l.strip()]
    keep, drop = [], []
    seen = set()
    for r in rows:
        a = r.get("a", "")
        if bs.is_junk(a):
            drop.append((r, "junk"))
            continue
        # An empty/whitespace completion is not "junk" by contract (a caller may
        # legitimately record a placeholder) — but it teaches a LoRA nothing, so
        # the STORE cleanup drops it. is_junk stays unchanged to honour that.
        if not (a or "").strip():
            drop.append((r, "empty"))
            continue
        _sa = (a or "").strip()
        # A truncation/degenerate stub teaches a LoRA nothing and is NOT a
        # legitimate SHORT answer. 25 chars is the same floor the extraction
        # gate uses (internet_learner._is_junk), and a real short answer
        # ("Ja.", "Nein!") is spared by the sentence-punctuation pass.
        # live 16.09.26: active_learn.cross_connect buffered "" x5, "S",
        # "What is the shared underlying pattern" and
        # "Need shared underlying pattern. One".
        if (_ECHO_TEMPLATE_RE.search(_sa)
                or _ECHO_TAIL_RE.search(_sa)
                or _ECHO_OPENER_RE.match(_sa)
                or bs.is_ordinal_stub(_sa)
                or (len(_sa) < 25 and not _sa.endswith((".", "!", "?", "\u2026", ":")))):
            drop.append((r, "stub"))
            continue
        key = json.dumps(r, ensure_ascii=False, sort_keys=True)
        if key in seen:
            drop.append((r, "duplicate"))
            continue
        seen.add(key)
        keep.append(r)

    if not keep:
        print(json.dumps({"error": "refused: result would be empty",
                          "total": len(rows)}))
        return 1

    with open(ARCHIVE, "a", encoding="utf-8") as f:
        for r, reason in drop:
            f.write(json.dumps({"reason": reason, **r}, ensure_ascii=False) + "\n")

    tmp = BUF.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(BUF)

    from collections import Counter
    reasons = Counter(x[1] for x in drop)
    print(json.dumps({
        "ok": True, "before": len(rows), "after": len(keep),
        "removed": len(drop), "reasons": dict(reasons),
        "archive": ARCHIVE.name,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
