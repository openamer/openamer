"""Tracing helpers used by the command line entry point."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpanRecorder:
    """Collects named spans for a single command invocation."""

    spans: list[dict[str, Any]] = field(default_factory=list)

    def record_span(self, name: str, duration_ms: float) -> dict[str, Any]:
        span = {"name": name, "duration_ms": duration_ms}
        self.spans.append(span)
        return span

    def flush(self) -> list[dict[str, Any]]:
        collected = list(self.spans)
        self.spans.clear()
        return collected


def record_span(name: str, recorder: SpanRecorder | None = None) -> dict[str, Any]:
    """Time a no-op span on *recorder* (or a throwaway recorder)."""
    started = time.perf_counter()
    elapsed = (time.perf_counter() - started) * 1000.0
    recorder = recorder or SpanRecorder()
    return recorder.record_span(name, elapsed)
