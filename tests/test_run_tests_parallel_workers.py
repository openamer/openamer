"""Worker-count default must respect RAM, not only CPU count.

Regression contract for the bug measured 2026-10-25 on a 16-thread / 24 GB box:
``run_tests_parallel.py`` defaulted to ``cpu_count() * 2`` (= 32) workers
regardless of free memory. The suite then swapped, which produced two
symptoms that looked unrelated:

  * 33 test files were SIGKILL'd at the 600s per-file cap and thus produced
    NO verdict at all -- invisible to the reported failure count;
  * neighbouring cron jobs (longterm indexer 900s, system snapshot 600s) died
    on their own timeouts in the same window, because the suite had taken the
    RAM.

These tests pin the *relation* rather than a snapshot: the default must never
exceed what free RAM can hold, must never drop below the floor, must still be
CPU-derived when RAM cannot be measured, and must yield to an explicit
override. They also run on CI where ``cpu_count()*2`` is the correct answer --
so they assert the clamp, not a fixed number.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_RUNNER_PATH = Path(__file__).resolve().parent.parent / "scripts" / "run_tests_parallel.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_tests_parallel_wc", _RUNNER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


runner = _load_runner()


def test_ram_clamp_reduces_workers_below_cpu_default(monkeypatch) -> None:
    """With little free RAM the default drops below cpu_count*2.

    The expected number is derived from the module's own budget constant, not
    frozen: a change-detector here would go red for the wrong reason every time
    the measured per-worker cost is revised (which is exactly what happened
    when 700 MB became the measured 400 MB).
    """
    monkeypatch.setattr(runner.os, "cpu_count", lambda: 16)  # cpu default = 32
    free = 4 * 1024**3
    monkeypatch.setattr(runner, "_available_ram_bytes", lambda: free)

    expected = int(free * runner._RAM_SHARE_FOR_WORKERS) // runner._RAM_PER_WORKER_BYTES
    got = runner._default_worker_count()
    assert got == expected
    assert got < 32  # strictly below the CPU-derived default
    assert got >= runner._MIN_WORKERS


def test_plenty_of_ram_keeps_cpu_derived_default(monkeypatch) -> None:
    """A CI runner with lots of RAM is not artificially slowed down."""
    monkeypatch.setattr(runner.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(runner, "_available_ram_bytes", lambda: 64 * 1024**3)

    assert runner._default_worker_count() == 32


def test_never_below_floor(monkeypatch) -> None:
    """A nearly full machine still runs the suite, just with the floor."""
    monkeypatch.setattr(runner.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(runner, "_available_ram_bytes", lambda: 200 * 1024**2)

    assert runner._default_worker_count() == runner._MIN_WORKERS
    assert runner._MIN_WORKERS >= 1


def test_unmeasurable_ram_falls_back_to_cpu(monkeypatch) -> None:
    """No measurement -> the CPU-derived count, never an invented number."""
    monkeypatch.setattr(runner.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(runner, "_available_ram_bytes", lambda: None)

    assert runner._default_worker_count() == 16


def test_explicit_env_override_wins(monkeypatch) -> None:
    """$OPENAMER_TEST_WORKERS beats the measured default."""
    monkeypatch.setattr(runner.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(runner, "_available_ram_bytes", lambda: 4 * 1024**3)
    monkeypatch.setenv("OPENAMER_TEST_WORKERS", "12")

    assert runner._env_or_default_worker_count() == 12


def test_unparsable_env_override_is_ignored(monkeypatch) -> None:
    """A malformed override must not crash the runner before it starts."""
    monkeypatch.setattr(runner.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(runner, "_available_ram_bytes", lambda: 64 * 1024**3)
    monkeypatch.setenv("OPENAMER_TEST_WORKERS", "many")

    assert runner._env_or_default_worker_count() == 32


def test_no_env_uses_ram_aware_default(monkeypatch) -> None:
    """Absent the env var, the RAM-aware default is what runs."""
    monkeypatch.delenv("OPENAMER_TEST_WORKERS", raising=False)
    monkeypatch.setattr(runner.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(runner, "_available_ram_bytes", lambda: 4 * 1024**3)

    assert runner._env_or_default_worker_count() == runner._default_worker_count()


@pytest.mark.parametrize("cpu", [1, 2, 4, 8, 16, 64])
def test_clamp_is_monotonic_and_bounded(monkeypatch, cpu: int) -> None:
    """Whatever the CPU count, the result stays within [floor, cpu*2]."""
    monkeypatch.setattr(runner.os, "cpu_count", lambda: cpu)
    monkeypatch.setattr(runner, "_available_ram_bytes", lambda: 6 * 1024**3)

    got = runner._default_worker_count()
    assert runner._MIN_WORKERS <= got <= cpu * 2


def test_available_ram_is_measurable_on_this_host() -> None:
    """The probe must actually work here -- a silent None would mask the bug.

    Deliberately not asserting a specific number (machines differ); asserting
    that a real measurement is possible, which is what makes the clamp live.
    """
    avail = runner._available_ram_bytes()
    assert avail is None or avail > 0
    if avail is not None:
        assert runner._default_worker_count() >= runner._MIN_WORKERS
