"""Advisory reminder for identical repeated tool calls.

Adapted from deepseek-ai/deepseek-harness ``repeat-tool-reminder``
(``packages/guard/repeat-tool-reminder``).

The difference to OpenAmer's existing ``agent/tool_guardrails.py``:

  * ``tool_guardrails`` counts **failures** (and same-result idempotent
    no-progress). It cannot see a model that keeps calling a tool that
    *succeeds* with identical arguments — the classic "polling loop"
    that burns tokens without ever failing.
  * This module counts identical calls **regardless of outcome**, the way
    upstream does, and stays purely advisory: it never blocks and never
    delays a legitimate repeated call.

Upstream defaults are thresholds ``[3, 5, 8]`` with a short reminder at
the first threshold and a detailed one (naming tool + arguments) at the
later ones. A new user message clears the counts upstream; here the
controller is reset per turn, which gives the same guarantee.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from agent.tool_guardrails import ToolCallSignature, _coerce_args


DEFAULT_THRESHOLDS: tuple[int, ...] = (3, 5, 8)
DEFAULT_ARGUMENTS_PREVIEW_CHARS = 500

#: Tools whose identical repetition is legitimate and must not be tracked.
DEFAULT_EXCLUDE: frozenset[str] = frozenset({"todo_write", "todo"})


@dataclass(frozen=True)
class RepeatToolReminderConfig:
    """Configuration for the advisory repeat-tool reminder."""

    enabled: bool = True
    thresholds: tuple[int, ...] = DEFAULT_THRESHOLDS
    include: frozenset[str] = frozenset()
    exclude: frozenset[str] = field(default_factory=lambda: DEFAULT_EXCLUDE)
    arguments_preview_chars: int = DEFAULT_ARGUMENTS_PREVIEW_CHARS

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "RepeatToolReminderConfig":
        if not isinstance(data, Mapping):
            return cls()

        raw_thresholds = data.get("thresholds", DEFAULT_THRESHOLDS)
        thresholds: list[int] = []
        if isinstance(raw_thresholds, (list, tuple)):
            for value in raw_thresholds:
                if isinstance(value, bool) or not isinstance(value, int):
                    continue
                if value >= 2 and value not in thresholds:
                    thresholds.append(value)
        if not thresholds:
            thresholds = list(DEFAULT_THRESHOLDS)

        def _str_set(value) -> frozenset[str]:
            if isinstance(value, (list, tuple, set, frozenset)):
                return frozenset(str(v) for v in value if isinstance(v, str))
            return frozenset()

        preview = data.get("arguments_preview_chars", DEFAULT_ARGUMENTS_PREVIEW_CHARS)
        if isinstance(preview, bool) or not isinstance(preview, int) or preview < 0:
            preview = DEFAULT_ARGUMENTS_PREVIEW_CHARS

        return cls(
            enabled=bool(data.get("enabled", True)),
            thresholds=tuple(sorted(thresholds)),
            include=_str_set(data.get("include")),
            exclude=_str_set(data.get("exclude")) or DEFAULT_EXCLUDE,
            arguments_preview_chars=preview,
        )


@dataclass(frozen=True)
class RepeatToolReminder:
    """The reminder text for one detected repeat."""

    message: str
    tool_name: str
    count: int
    detailed: bool


class RepeatToolReminderController:
    """Per-turn tracker of identical tool calls."""

    def __init__(self, config: RepeatToolReminderConfig | None = None):
        self.config = config or RepeatToolReminderConfig()
        self.reset_for_turn()

    def reset_for_turn(self) -> None:
        self._counts: dict[ToolCallSignature, int] = {}

    def _tracks(self, tool_name: str) -> bool:
        if tool_name in self.config.exclude:
            return False
        if self.config.include and tool_name not in self.config.include:
            return False
        return True

    def record_call(
        self,
        tool_name: str,
        args: Mapping[str, Any] | None,
    ) -> Optional[RepeatToolReminder]:
        """Count the call and return a reminder when a threshold is hit."""
        if not self.config.enabled or not self._tracks(tool_name):
            return None

        signature = ToolCallSignature.from_call(tool_name, _coerce_args(args))
        count = self._counts.get(signature, 0) + 1
        self._counts[signature] = count

        if count not in self.config.thresholds:
            return None

        # Upstream: the FIRST threshold gets a short reminder, the later
        # ones a detailed reminder naming tool and arguments. So the
        # detailed form starts at the second threshold.
        detailed = len(self.config.thresholds) > 1 and count >= self.config.thresholds[1]
        return RepeatToolReminder(
            message=self._build_message(tool_name, args, count, detailed),
            tool_name=tool_name,
            count=count,
            detailed=detailed,
        )

    def _build_message(
        self,
        tool_name: str,
        args: Mapping[str, Any] | None,
        count: int,
        detailed: bool,
    ) -> str:
        if not detailed:
            return (
                f"You called {tool_name} {count} times in a row with identical "
                "arguments. Before calling it again, analyze the previous "
                "result: either change your approach or finish the task."
            )
        preview = self.config.arguments_preview_chars
        try:
            rendered = json.dumps(_coerce_args(args), ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            rendered = "<unserializable arguments>"
        if preview and len(rendered) > preview:
            rendered = rendered[:preview] + "…"
        return (
            f"You called {tool_name} {count} times in a row with identical "
            f"arguments ({rendered}). Stop repeating it unchanged: use the "
            "result you already have, change the arguments, or finish the "
            "task."
        )


__all__ = [
    "DEFAULT_ARGUMENTS_PREVIEW_CHARS",
    "DEFAULT_EXCLUDE",
    "DEFAULT_THRESHOLDS",
    "RepeatToolReminder",
    "RepeatToolReminderConfig",
    "RepeatToolReminderController",
]
