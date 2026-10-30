"""The gateway's own housekeeping loop ticks the Genesis runtime.

This is the difference between "there is a module" and "the system measures the
24 directives by itself": the tick has to be driven from inside the core. These
tests run ONE iteration of ``_start_gateway_housekeeping`` (the loop body is
cheap when no adapter/hourly branch is due) and assert the runtime was ticked.
"""

from __future__ import annotations

import gateway.run as gw


class _OneShotEvent:
    """``threading.Event`` that reports "not set" once, then "set"."""

    def __init__(self) -> None:
        self._first = True
        self.waited = 0

    def is_set(self) -> bool:  # noqa: D401 - threading.Event API
        if self._first:
            self._first = False
            return False
        return True

    def wait(self, timeout: float | None = None) -> bool:  # noqa: D401
        self.waited += 1
        return True


def test_housekeeping_ticks_the_genesis_runtime(monkeypatch):
    calls = []

    def fake_tick_if_due(*args, **kwargs):
        calls.append((args, kwargs))
        return {"measured_at": 1.0}

    monkeypatch.setattr("agent.genesis_runtime.tick_if_due", fake_tick_if_due)

    stop = _OneShotEvent()
    gw._start_gateway_housekeeping(stop, adapters=None, loop=None, interval=0)

    assert calls, "gateway housekeeping must drive the genesis tick"


def test_a_failing_genesis_tick_does_not_break_housekeeping(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr("agent.genesis_runtime.tick_if_due", boom)

    stop = _OneShotEvent()
    # Must return normally: the housekeeping thread may never die from a probe.
    gw._start_gateway_housekeeping(stop, adapters=None, loop=None, interval=0)

    assert stop.waited >= 1, "the loop reached its wait, i.e. it survived the failure"
