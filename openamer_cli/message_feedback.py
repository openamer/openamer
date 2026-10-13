"""Persistent, deterministic user-message feedback for self-improvement.

Captures lightweight user signals about agent replies (``helpful`` /
``not_helpful`` / a free-form note) as an append-only JSONL log. The signal is
stored with enough context (session id, assistant message id/snippet, model,
timestamp) that downstream consumers — e.g. the A2A self-learning loop or a
curator pass — can turn it into a lesson. The storage layer is pure and
deterministic (no LLM, no network), so it is safe to call from anywhere and
trivially unit-testable.

This is intentionally a *recording* seam, not an intrusive feature: it never
mutates the conversation or the agent loop. A caller decides when and how to
act on the signals (aggregate, distill, feed the mesh).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional


def _default_log_path() -> Path:
    """Return the feedback log under the OpenAmer home, best-effort."""
    home = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / ".openamer")))
    return home / "feedback.jsonl"


# Monotone sequence counter so ordering stays deterministic even when several
# records share the same second (time.time() has ~us resolution but calls in
# a tight loop can collide; a per-process seq makes newest-first stable).
_seq_counter = 0


def _next_seq() -> int:
    global _seq_counter
    _seq_counter += 1
    return _seq_counter


def record_feedback(
    *,
    signal: str,
    assistant_text: str = "",
    session_id: Optional[str] = None,
    model: Optional[str] = None,
    note: Optional[str] = None,
    topic: Optional[str] = None,
    log_path: Optional[Path] = None,
) -> dict:
    """Append one feedback record and return it (never raises on disk errors).

    Parameters
    ----------
    signal
        ``"helpful"`` or ``"not_helpful"`` (or any short label the caller
        defines). Stored verbatim; no validation is enforced so callers can
        use their own vocabulary.
    assistant_text
        The assistant reply (or a snippet) being rated. Stored as-is.
    session_id, model, topic, note
        Optional context to make the signal actionable downstream.
    log_path
        Where to append. Defaults to ``OPENAMER_HOME/feedback.jsonl``.

    Returns
    -------
    The record dict written (with ``ts`` added). If the write fails, returns
    the record anyway with ``_persisted=False`` so callers can degrade
    gracefully instead of raising in the agent path.
    """
    record: dict[str, Any] = {
        "signal": signal,
        "ts": time.time(),
        "seq": _next_seq(),
        "assistant_text": assistant_text[:2000],  # cap for hygiene
    }
    if session_id:
        record["session_id"] = session_id
    if model:
        record["model"] = model
    if topic:
        record["topic"] = topic
    if note:
        record["note"] = note[:2000]

    record["_persisted"] = False
    try:
        path = log_path or _default_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        record["_persisted"] = True
    except Exception:
        # Storage must never break the agent loop.
        pass
    return record


def load_feedback(
    log_path: Optional[Path] = None,
    *,
    limit: Optional[int] = None,
) -> list[dict]:
    """Read feedback records, newest first.

    Parameters
    ----------
    log_path
        Path to read. Defaults to the same default as :func:`record_feedback`.
    limit
        Return at most this many newest records. ``None`` returns all.

    Returns
    -------
    A list of record dicts (newest first). Malformed lines are skipped. Never
    raises — a missing/unreadable file yields ``[]``.
    """
    path = log_path or _default_log_path()
    rows: list[dict] = []
    if not path.is_file():
        return rows
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    rows.sort(key=lambda r: (r.get("ts", 0.0), r.get("seq", 0)), reverse=True)
    if limit is not None and limit >= 0:
        rows = rows[:limit]
    return rows


def summarize_feedback(
    records: list[dict],
) -> dict:
    """Aggregate a set of feedback records into counts.

    Pure and deterministic. Returns a dict with per-signal counts and the
    latest helpful/not-helpful snippets, useful for a curator or self-learning
    pass without re-parsing raw rows.
    """
    counts: dict[str, int] = {}
    latest_helpful: Optional[str] = None
    latest_not_helpful: Optional[str] = None
    for r in sorted(records, key=lambda x: (x.get("ts", 0.0), x.get("seq", 0))):
        sig = r.get("signal", "unknown")
        counts[sig] = counts.get(sig, 0) + 1
        text = (r.get("assistant_text") or "").strip()
        # Ascending (oldest->newest) pass: keep overwriting so the LAST
        # occurrence is the newest — that is the "latest" snippet.
        if sig == "helpful" and text:
            latest_helpful = text[:200]
        if sig == "not_helpful" and text:
            latest_not_helpful = text[:200]
    return {
        "counts": counts,
        "latest_helpful": latest_helpful,
        "latest_not_helpful": latest_not_helpful,
    }
