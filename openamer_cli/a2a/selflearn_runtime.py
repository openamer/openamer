"""openamer_cli.a2a.selflearn_runtime — autonomous runtime learning loop.

Phase 7. A hook the conversation runtime can call at the end of a turn (or after
a task) without manual CLI. It decides whether this turn produced a lesson worth
keeping, distills it, signs it, adopts it into the node's mesh memory, and
(behind a flag) stages it for the shared GitHub mesh directory.

The default extractor is a deterministic heuristic (tool-calling turns), so by
default it runs offline with no LLM cost. A caller can supply an LLM ``distill``
callback for richer lessons.

Guarded: any failure is a fast no-op; the loop can never affect a conversation.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from openamer_cli.a2a import selflearn, autolog as _auto
from openamer_cli.a2a.core import IdentityStore


def _base_dir() -> Path:
    base = os.environ.get("OPENAMER_HOME") or str(Path.home() / ".openamer")
    return Path(base)


def _memory_path() -> Path:
    return _base_dir() / "MEMORY-official-mesh.md"


def _should_learn(turn: dict) -> bool:
    if not turn:
        return False
    msgs = turn.get("messages") or []
    n_tool = sum(1 for m in msgs if m.get("role") == "tool" and m.get("content"))
    n_user = sum(1 for m in msgs if m.get("role") in ("user",))
    return n_tool >= 1 and n_user >= 1


def _extract_lesson(turn: dict) -> tuple[str, str]:
    msgs = turn.get("messages") or []
    title, body = "", ""
    for m in msgs:
        if m.get("role") == "user" and not title:
            title = (m.get("content") or "").strip()[:70]
        if m.get("role") == "assistant":
            body = (m.get("content") or "").strip()
    if not title:
        title = "Session note"
    return title, body


def maybe_learn(turn: Optional[dict], *, distill: Optional[Callable] = None,
                publish: bool = False, home: Optional[Path] = None) -> dict:
    """Called by the runtime after a turn. Returns {} when skipped (fast)."""
    if not _auto.enabled():
        return {}
    if not _should_learn(turn or {}):
        return {}
    try:
        base = home or _base_dir()
        st = IdentityStore(home=base)
        if distill is not None:
            title, body = distill(turn or {}, "")
        else:
            title, body = _extract_lesson(turn or {})
        if not body:
            return {}
        res = selflearn.auto_learn(identity_store=st, memory_path=_memory_path() if home is None else base / "MEMORY-official-mesh.md",
                                   learn_from=body, topic="auto", title=title,
                                   skip_publish=not publish)
        return {"ok": bool(res.get("ok")), "learned": bool(res.get("adopted")),
                "source": res.get("source"), "publish": publish}
    except Exception:
        return {}