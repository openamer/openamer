"""Tests for the memory-consolidation age calculation.

`_age_days` decides whether an episode is old enough to be compressed. It used to
return 0 on any failure, and 0 means "brand new" - so a stamp it could not handle
made an old episode look fresh and it would never be compressed again, silently,
because a blind `except Exception` swallowed the reason.

Measured 2026-10-10: a tz-aware stamp raised
`TypeError: can't subtract offset-naive and offset-aware datetimes` against the
naive `now()`, and an entry 38 days old came back as `0 days`. This mattered
immediately, because linting the episodic store asks for tz-aware `ts` values -
applying that suggestion without this fix would have quietly disabled
compression.
"""

from __future__ import annotations

import datetime
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MODULE = REPO / "scripts" / "training" / "memory_consolidation.py"

# A fixed, clearly-old stamp so the expected day count cannot drift with the hour.
OLD_NAIVE = "2026-01-01T00:00:00"
OLD_AWARE = "2026-01-01T00:00:00+00:00"


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("memory_consolidation", MODULE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _expected_days() -> int:
    return (datetime.datetime.now() - datetime.datetime(2026, 1, 1)).days


def test_a_naive_stamp_gives_the_real_age(mod):
    """The store writes naive stamps today - this is the live path."""
    assert mod._age_days(OLD_NAIVE) == _expected_days()


def test_a_tz_aware_stamp_gives_the_same_real_age(mod):
    """The regression: an aware stamp returned 0 (brand new) instead of 38 days."""
    assert mod._age_days(OLD_AWARE) == _expected_days()
    assert mod._age_days(OLD_AWARE) != 0, "0 means 'fresh' and would disable compression"


def test_both_stamp_forms_agree(mod):
    """Whatever the store's format, the same moment must age the same."""
    assert mod._age_days(OLD_NAIVE) == mod._age_days(OLD_AWARE)


def test_an_unreadable_stamp_falls_back_to_fresh(mod):
    """Only a genuinely unreadable stamp may report 0 - never a parse mismatch."""
    assert mod._age_days("not-a-date") == 0
    assert mod._age_days(None) == 0
