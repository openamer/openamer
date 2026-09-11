#!/usr/bin/env python3
"""Buffer Store — single source of truth for the online experience buffer.

Every writer (active_learn, internet_learner, online_learning.collect_new)
must append through `append()` so the cap is enforced on EVERY write, not
only in the replay branch. Before this module the cap lived inside
online_learning's replay path, so any cycle that produced new data grew the
buffer without bound (training on unbounded duplicates degrades loss).

Cap policy: keep the newest MAX_BUF examples, FIFO. Trimming is
best-effort/atomic-ish (write temp + replace) and never raises into callers —
a failed trim must not break a learning cycle.

Quality policy (added 11.09.26): the buffer is TRAINING DATA. Three classes
of non-signal were observed live in online_buffer.jsonl and are now rejected
before they can be written, because a LoRA fine-tuned on them learns the
garbage:

  1. reasoning-trace leaks  — thinking models emit "Here's a thinking
     process:" / "Analyze User Input:" into the completion (64 of 300
     entries on 11.09.26).
  2. degenerate repetition  — "Self\\n\\nSelf\\n\\nSelf..." (20 of 300):
     the model repeating one token; unique-token ratio near zero.
  3. raw tool-call JSON     — the completion is `{"tool": "web_search", ...}`
     instead of an answer (28 of 300).

`is_junk()` is the single predicate; `append()` refuses junk and returns the
unchanged count. Callers that need to report honestly check `is_junk()` (or
the count delta) rather than assuming their write landed.
"""
import json
import os
from pathlib import Path

_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    Path.home() / "AppData" / "Local" / "openamer-laptop",
))
DEFAULT_BUFFER = _HOME / "scripts" / "training" / "online_buffer.jsonl"
MAX_BUF = int(os.environ.get("OPENAMER_BUFFER_MAX", "300"))
# audit trail of rejected examples — never silent, always inspectable
JUNK_LOG = DEFAULT_BUFFER.with_name("buffer_junk.jsonl")

# --- junk markers: reasoning-trace leaks, meta-commentary, tool-call dumps ---
_JUNK_MARKERS = (
    "thinking process",          # "Here's a thinking process:"
    "analyze user input",        # reasoning-trace step header
    "analyze the user's request",
    "[tool_result",              # raw tool plumbing
    "tool_result:",              # raw tool plumbing
    '"tool":',                   # completion IS a tool call, not an answer
    "'tool':",
    "function_call",
    "<tool_call",
    "**analyze",                 # bolded reasoning header
)

# a completion this short carries no trainable content
_MIN_CHARS = 12
# degenerate-repetition thresholds (measured: junk ~0.14 unique-ratio,
# real prose ~0.5+; a 6-token floor catches short loops like 7x "Self")
_MIN_TOKENS_FOR_REPEAT_CHECK = 6
_MIN_UNIQUE_RATIO = 0.15
_MAX_TOP_TOKEN_SHARE = 0.5


def is_junk(text):
    """True when a completion is not trainable signal.

    Structural markers first (cheap + unambiguous), then degenerate
    repetition. Empty/whitespace text is NOT classified here — callers may
    legitimately record a placeholder and the historical contract tolerates
    it; this predicate only rejects content that actively poisons training.
    """
    if text is None:
        return False
    s = text.strip()
    if not s:
        return False
    low = s.lower()
    if any(m in low for m in _JUNK_MARKERS):
        return True
    tokens = s.split()
    if len(tokens) >= _MIN_TOKENS_FOR_REPEAT_CHECK:
        uniq = len(set(tokens))
        if uniq / len(tokens) < _MIN_UNIQUE_RATIO:
            return True
        top = max(tokens.count(t) for t in set(tokens))
        if top / len(tokens) > _MAX_TOP_TOKEN_SHARE:
            return True
    return False


def _audit(user_text, assistant_text, reason):
    """Append a rejected example to the audit log (best-effort)."""
    try:
        with open(JUNK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "reason": reason,
                "u": (user_text or "")[:300],
                "a": (assistant_text or "")[:300],
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


def append(user_text, assistant_text, buffer=None, max_buf=None):
    """Append one (u, a) example and enforce the cap. Returns buffer line count.

    Junk completions (see `is_junk`) are refused: nothing is written, the
    rejection is logged to `buffer_junk.jsonl`, and the current count is
    returned so callers can detect the no-op by comparing counts.
    """
    buf = Path(buffer or DEFAULT_BUFFER)
    cap = int(max_buf or MAX_BUF)
    buf.parent.mkdir(parents=True, exist_ok=True)
    if is_junk(assistant_text):
        _audit(user_text, assistant_text, "junk")
        return count(buf)
    rec = {
        "u": (user_text or "")[:3000],
        "a": (assistant_text or "")[:4000],
    }
    with open(buf, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return enforce_cap(buf, cap)


def count(buffer=None):
    """Number of examples currently in the buffer."""
    buf = Path(buffer or DEFAULT_BUFFER)
    try:
        return sum(1 for _ in open(buf, encoding="utf-8"))
    except FileNotFoundError:
        return 0


def enforce_cap(buffer=None, max_buf=None):
    """Trim the buffer to the newest `max_buf` lines. Returns the new count."""
    buf = Path(buffer or DEFAULT_BUFFER)
    cap = int(max_buf or MAX_BUF)
    try:
        lines = open(buf, encoding="utf-8").readlines()
        if len(lines) > cap:
            tmp = buf.with_suffix(buf.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(lines[-cap:])
            os.replace(tmp, buf)
            return cap
        return len(lines)
    except Exception:
        # never let a trim failure break a learning cycle
        return count(buf)
