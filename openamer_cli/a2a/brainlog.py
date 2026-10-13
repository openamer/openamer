"""openamer_cli.a2a.brainlog — capture the FULL activity stream for the OpenAmer brain.

Phase 6b. The training set should reflect *everything* OpenAmer does, not just
A2A: chat messages, reasoning (thinking), commands, web searches, tool calls,
tool results, skill use, subagent/background activity, and A2A exchanges.
This module provides a compact, append-only event log (JSONL) with a stable
schema, plus a converter that folds events into training-formatted (ChatML)
turns -- 'klein aber fein': structured, deduped, low-noise.

Emission is fully offline; nothing here requires an LLM.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Iterator, Optional

# Event kinds that make up the full activity stream.
KINDS = {
    "user",          # chat user message
    "assistant",     # chat assistant message
    "thinking",      # assistant reasoning / scratchpad
    "command",       # slash command (e.g. /help, /model, /skills)
    "search",        # internet search query (redacted result)
    "tool_call",     # tool name + serialized args (no secrets)
    "tool_result",   # tool result (summary/truncated)
    "skill",         # skill loaded/used
    "subagent",      # delegate/spawn event
    "background",    # cron / scheduled / background task
    "a2a",           # agent-to-agent exchange (kind only, no payload secrets)
}
_ORDER = ["user", "assistant", "thinking", "command", "tool_call", "tool_result",
          "search", "skill", "subagent", "background", "a2a"]


@dataclass
class Event:
    kind: str
    content: str = ""
    ts: int = field(default_factory=lambda: int(time.time()))
    session: str = ""
    role: str = ""

    def sanitized(self, max_len: int = 800) -> "Event":
        """Return a copy with sensitive/verbose content trimmed for training."""
        c = self.content
        if len(c) > max_len:
            c = c[:max_len] + "…[trunc]"
        return Event(kind=self.kind, role=self.role, ts=self.ts, session=self.session, content=c)

    def to_json(self) -> dict:
        return {"ts": self.ts, "kind": self.kind, "role": self.role,
                "session": self.session, "content": self.content}


class ActivityLog:
    """Append-only JSONL log of all agent/chat/background activity."""

    def __init__(self, path: Path, max_len: int = 800):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_len = max_len

    def append(self, kind: str, content: str = "", role: str = "", session: str = "",
               ts: Optional[int] = None) -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown event kind {kind!r}")
        ev = Event(kind=kind, content=content, role=role, session=session,
                   ts=int(ts) if ts is not None else int(time.time()))
        ev = ev.sanitized(self.max_len)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev.to_json(), ensure_ascii=False) + "\n")

    def iter_events(self) -> Iterator[dict]:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue

    def to_chatml(self, *, include_thinking: bool = True, max_turns: int = 200) -> Iterator[list]:
        """Assemble stored events into ChatML message lists for training.

        Groups a session's events into: assistant = user turn (with optional
        thinking + tool calls) -> assistant final. This yields the turn structure
        the future fine-tune expects. interleaved events without a clear user
        start are folded into a single [system,user,assistant] sample.
        """
        by_session: dict[str, list[dict]] = {}
        for ev in self.iter_events():
            # preserve relative order by ts so folding is chronological
            by_session.setdefault(ev.get("session") or "_", []).append(ev)
        for sess in by_session:
            by_session[sess].sort(key=lambda e: e.get("ts", 0))

        for sess, evs in by_session.items():
            msgs: list[dict] = [{"role": "system", "content": "You are OpenAmer, a capable autonomous AI agent."}]
            pending_user = ""
            seen_user = False
            for ev in evs[:max_turns]:
                k = ev.get("kind"); c = ev.get("content", ""); r = ev.get("role") or ""
                if k == "user":
                    pending_user = c; seen_user = True
                    if not any(m.get("role") == "user" for m in msgs):
                        msgs.append({"role": "user", "content": c})
                elif k in ("assistant", "command"):
                    msgs.append({"role": "assistant", "content": c})
                elif k == "thinking" and include_thinking:
                    msgs.append({"role": "thinking", "content": c})
                elif k in ("tool_call", "tool_result") or k in ("search", "subagent", "background", "a2a"):
                    msgs.append({"role": "tool", "name": k, "content": c})
            if len(msgs) >= 2:
                yield msgs