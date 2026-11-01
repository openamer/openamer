"""Corpus curation for the local CPU brain.

The raw brain log is not a good training corpus as-is. Measured on this
machine (145 MB, 7,672 records, 60,345 messages):

  * 59.7% of messages are duplicates — every trajectory re-writes the whole
    conversation history, so the same text appears once per turn.
  * 42% of messages carry role "tool"; 36.6% carry tool_calls.
  * 7.4% of messages hold 81% of all characters (95.8M of 117.7M). A model
    with a 256-token window only ever sees fragments of those.

Result before curation: the model learned `ls` output and markdown table
fragments instead of dialogue.

This module turns the raw log into a corpus that is (a) deduplicated,
(b) length-capped per message, (c) role-filtered. Every stage reports how
much it removed, so the trade-off is measurable instead of assumed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MAX_MSG_CHARS = 1200
DEFAULT_MIN_MSG_CHARS = 1  # keep "Ja." — only drop messages that are empty after strip


@dataclass
class CurationStats:
    records_read: int = 0
    messages_seen: int = 0
    chars_seen: int = 0
    dropped_role: int = 0
    dropped_empty: int = 0
    dropped_duplicate: int = 0
    truncated: int = 0
    chars_dropped_role: int = 0
    chars_dropped_duplicate: int = 0
    chars_truncated: int = 0
    messages_kept: int = 0
    chars_kept: int = 0
    by_role: dict[str, int] = field(default_factory=dict)

    @property
    def kept_ratio(self) -> float:
        return self.chars_kept / self.chars_seen if self.chars_seen else 0.0

    def as_dict(self) -> dict:
        return {
            "records_read": self.records_read,
            "messages_seen": self.messages_seen,
            "chars_seen": self.chars_seen,
            "messages_kept": self.messages_kept,
            "chars_kept": self.chars_kept,
            "kept_ratio": round(self.kept_ratio, 4),
            "dropped_role": self.dropped_role,
            "dropped_empty": self.dropped_empty,
            "dropped_duplicate": self.dropped_duplicate,
            "truncated": self.truncated,
            "chars_dropped_role": self.chars_dropped_role,
            "chars_dropped_duplicate": self.chars_dropped_duplicate,
            "chars_truncated": self.chars_truncated,
            "by_role": dict(sorted(self.by_role.items())),
        }


def _content_text(msg: dict) -> str:
    """Flatten a message's content, including tool_calls, into plain text."""
    content = msg.get("content") or ""
    if isinstance(content, list):
        content = " ".join(
            str(part.get("text", "")) for part in content if isinstance(part, dict)
        )
    content = str(content)
    calls = msg.get("tool_calls")
    if calls:
        try:
            content = f"{content} {json.dumps(calls, ensure_ascii=False, sort_keys=True)}".strip()
        except (TypeError, ValueError):
            content = f"{content} {calls}".strip()
    return content


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    """Keep head and tail of an over-long message.

    Head+tail beats a pure head cut: tool output usually carries its meaning
    at the start (command, path) and at the end (result, error).
    """
    if len(text) <= limit:
        return text, False
    head = int(limit * 0.7)
    tail = limit - head
    return f"{text[:head]}\n…[{len(text) - limit} chars cut]…\n{text[-tail:]}", True


def _dedupe_key(role: str, text: str) -> str:
    """Normalised key: identical text in the same role counts once."""
    return f"{role}\x00{' '.join(text.split())[:600]}"


def curate_message_stream(
    sources: list[Path],
    *,
    max_msg_chars: int = DEFAULT_MAX_MSG_CHARS,
    min_msg_chars: int = DEFAULT_MIN_MSG_CHARS,
    drop_roles: tuple[str, ...] = ("tool",),
    dedupe: bool = True,
    keep_roles: tuple[str, ...] | None = None,
) -> tuple[str, CurationStats]:
    """Build training text from the raw brain sources.

    Returns (text, stats). ``drop_roles`` applies before ``keep_roles``; with
    the defaults, tool output is removed entirely and dialogue is kept.
    """
    stats = CurationStats()
    seen: set[str] = set()
    out: list[str] = []

    for fpath in sources:
        if not fpath.exists() or not fpath.is_file():
            continue
        is_jsonl = fpath.suffix == ".jsonl"
        try:
            handle = fpath.open("r", encoding="utf-8", errors="ignore")
        except OSError:
            continue
        with handle as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if not is_jsonl:
                    stats.chars_seen += len(line)
                    out.append(line)
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    stats.chars_seen += len(line)
                    out.append(line)
                    continue
                stats.records_read += 1
                msgs = obj.get("messages") if isinstance(obj, dict) else None
                if not msgs:
                    # {"u","a"} / {"text"} shaped records: single block
                    for key in ("u", "a", "text", "content", "prompt"):
                        val = obj.get(key) if isinstance(obj, dict) else None
                        if isinstance(val, str) and val.strip():
                            text, _ = _truncate(val.strip(), max_msg_chars)
                            stats.messages_seen += 1
                            stats.chars_seen += len(val)
                            stats.chars_truncated += max(0, len(val) - len(text))
                            out.append(text)
                            stats.messages_kept += 1
                            stats.chars_kept += len(text)
                    continue

                blocks: list[str] = []
                for msg in msgs:
                    if not isinstance(msg, dict):
                        continue
                    role = str(msg.get("role") or "user")
                    text = _content_text(msg).strip()
                    stats.messages_seen += 1
                    stats.chars_seen += len(text)

                    if role in drop_roles or (keep_roles is not None and role not in keep_roles):
                        stats.dropped_role += 1
                        stats.chars_dropped_role += len(text)
                        continue
                    if len(text) < min_msg_chars:
                        stats.dropped_empty += 1
                        continue
                    key = _dedupe_key(role, text)
                    if dedupe and key in seen:
                        stats.dropped_duplicate += 1
                        stats.chars_dropped_duplicate += len(text)
                        continue
                    if dedupe:
                        seen.add(key)

                    text, cut = _truncate(text, max_msg_chars)
                    if cut:
                        stats.truncated += 1
                        stats.chars_truncated += 0
                    blocks.append(f"<|{role}|> {text}")
                    stats.messages_kept += 1
                    stats.chars_kept += len(text)
                    stats.by_role[role] = stats.by_role.get(role, 0) + 1

                if blocks:
                    out.append("\n".join(blocks))

    return "\n\n".join(out), stats


def default_sources(home: Path, data_dir: Path | None = None) -> list[Path]:
    """The corpus locations the trainer reads, in priority order."""
    srcs = [
        home / "a2a" / "openamer-brain.jsonl",
        home / "scripts" / "training" / "sft_openamer.jsonl",
        home / "scripts" / "training" / "online_buffer.jsonl",
    ]
    if data_dir is not None and data_dir.exists():
        for pattern in ("*.txt", "*.jsonl", "*.md"):
            srcs.extend(sorted(data_dir.glob(pattern)))
    return srcs
