"""openamer_cli.a2a.autolog — automatic activity capture for the OpenAmer brain.

The runtime hook: when enabled, every user message, assistant reply, reasoning,
command, tool call/result, search, skill, subagent and background event is
logged automatically into the same ActivityLog so the whole stream flows
(without any manual action) into the future training set.

Design: a thin, dependency-free bridge with an idempotent on/off switch stored
in an opt-in flag file. The conversation loop calls the lightweight hooks
below (no LLM, no network, ~microseconds). A disabled hook returns False fast.

Only stdlib.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from openamer_cli.a2a.brainlog import ActivityLog


def brain_dir() -> Path:
    base = os.environ.get("OPENAMER_HOME") or str(Path.home() / ".openamer")
    return Path(base) / "a2a"


def _flag() -> Path:
    return brain_dir() / "brainlog.enabled"


def enabled() -> bool:
    return _flag().exists()


def enable(level: int = 1) -> bool:
    p = _flag()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"{level}\n", encoding="utf-8")
    return True


def disable() -> bool:
    p = _flag()
    if p.exists():
        p.unlink()
    return True


class Autolog:
    """Thin facade the agent runtime can call with negligible overhead.

    Usage in the loop:
        al = Autolog()
        al.user(resolved_text, session=...)
        al.thinking(scratchpad, session=...)
        al.tool(name, args, ok=True, session=...)
        al.assistant(reply, session=...)
    Every call is a fast no-op unless the flag is set.
    """

    def __init__(self, path: Optional[Path] = None, max_len: int = 1600):
        self._enabled = enabled()
        self._log = ActivityLog(path or brain_dir() / "activity.jsonl", max_len=max_len)

    def _m(self, kind: str, content: str, session: str = ""):
        if not self._enabled:
            return
        try:
            self._log.append(kind, content=content, session=session)
        except Exception:
            pass  # capture must never break the loop

    def user(self, content: str, session: str = ""):  self._m("user", content, session)
    def thinking(self, content: str, session: str = ""):  self._m("thinking", content, session)
    def assistant(self, content: str, session: str = ""): self._m("assistant", content, session)
    def command(self, content: str, session: str = ""):   self._m("command", content, session)
    def search(self, content: str, session: str = ""):    self._m("search", content, session)
    def skill(self, content: str, session: str = ""):     self._m("skill", content, session)
    def subagent(self, content: str, session: str = ""):  self._m("subagent", content, session)
    def background(self, content: str, session: str = ""): self._m("background", content, session)
    def a2a(self, content: str, session: str = ""):       self._m("a2a", content, session)

    def tool(self, name: str, args: str = "", ok: bool = True, session: str = ""):
        self._m("tool_call" if ok else "tool_result", f"{name}{' OK' if ok else ' FAIL'}: {args}", session)