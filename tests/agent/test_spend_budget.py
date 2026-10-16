"""Tests for the spend budget: session/day caps, named reasons, the day store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import spend_budget as sb


def cfg(**over):
    base = sb.default_config()
    base.update(over)
    return base


# ── the guard is inert until it is switched on ────────────────────────────
def test_disabled_never_blocks():
    v = sb.evaluate(session_usd=999.0, day_usd=999.0, cfg=cfg())
    assert v.action == sb.ALLOW
    assert v.reason == sb.REASON_DISABLED
    assert not v.blocks


def test_disabled_short_circuits_before_reading_the_day_store(monkeypatch):
    """The turn loop asks this every iteration: off must mean no disk I/O."""
    monkeypatch.setattr(sb, "day_spend", lambda *a, **k: pytest.fail("read the day store while disabled"))
    budget = sb.SpendBudget(cfg=cfg())
    assert budget.ok_to_continue(session_usd=123.0) is True


# ── caps ──────────────────────────────────────────────────────────────────
def test_session_cap_blocks_with_a_named_reason():
    v = sb.evaluate(2.5, 0.0, cfg(enabled=True, max_usd_per_session=2.0))
    assert (v.action, v.reason, v.scope) == (sb.BLOCK, sb.REASON_SESSION_CAP, "session")
    assert v.limit_usd == 2.0 and v.spent_usd == 2.5


def test_day_cap_blocks_with_a_named_reason():
    v = sb.evaluate(0.1, 5.0, cfg(enabled=True, max_usd_per_day=5.0))
    assert (v.action, v.reason, v.scope) == (sb.BLOCK, sb.REASON_DAY_CAP, "day")


def test_warn_threshold_reports_a_warning_not_a_block():
    v = sb.evaluate(0.85, 0.0, cfg(enabled=True, max_usd_per_session=1.0, warn_at_percent=80))
    assert (v.action, v.reason) == (sb.WARN, sb.REASON_SESSION_WARN)
    assert not v.blocks


def test_on_exceed_warn_turns_a_breach_into_a_warning():
    v = sb.evaluate(2.0, 0.0, cfg(enabled=True, max_usd_per_session=1.0, on_exceed="warn"))
    assert (v.action, v.reason) == (sb.WARN, sb.REASON_SESSION_CAP)
    assert not v.blocks


def test_zero_limit_is_unbounded():
    v = sb.evaluate(50.0, 50.0, cfg(enabled=True, max_usd_per_session=0.0, max_usd_per_day=0.0))
    assert (v.action, v.reason) == (sb.ALLOW, sb.REASON_WITHIN)


def test_an_unknown_on_exceed_value_falls_back_to_blocking():
    v = sb.evaluate(2.0, 0.0, cfg(enabled=True, max_usd_per_session=1.0, on_exceed="nonsense"))
    assert v.action == sb.BLOCK


def test_garbage_numbers_cannot_raise():
    v = sb.evaluate("not-a-number", None, cfg(enabled=True, max_usd_per_session=1.0))
    assert v.action == sb.ALLOW  # unreadable spend reads as zero, it must not crash


def test_negative_limits_are_treated_as_no_cap():
    v = sb.evaluate(10.0, 0.0, cfg(enabled=True, max_usd_per_session=-5))
    assert v.action == sb.ALLOW


# ── the day store ─────────────────────────────────────────────────────────
def test_record_accrues_and_round_trips(tmp_path):
    p = tmp_path / "spend_day.json"
    assert sb.day_spend(p) == 0.0
    assert sb.record(0.25, p) == pytest.approx(0.25)
    assert sb.record(0.75, p) == pytest.approx(1.0)
    assert sb.day_spend(p) == pytest.approx(1.0)
    assert json.loads(p.read_text(encoding="utf-8"))["date"]


def test_a_previous_day_does_not_count_towards_today(tmp_path):
    p = tmp_path / "spend_day.json"
    p.write_text(json.dumps({"date": "1999-01-01", "spent_usd": 42.0}), encoding="utf-8")
    assert sb.day_spend(p) == 0.0
    assert sb.record(1.0, p) == pytest.approx(1.0)  # resets, does not add to 42


def test_a_corrupt_store_reads_as_zero(tmp_path):
    p = tmp_path / "spend_day.json"
    p.write_text("{not json", encoding="utf-8")
    assert sb.day_spend(p) == 0.0


def test_a_non_positive_amount_is_ignored(tmp_path):
    p = tmp_path / "spend_day.json"
    sb.record(1.0, p)
    assert sb.record(0.0, p) == pytest.approx(1.0)
    assert sb.record(-3.0, p) == pytest.approx(1.0)


def test_note_is_a_no_op_while_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(sb, "_store_path", lambda: tmp_path / "spend_day.json")
    assert sb.SpendBudget(cfg=cfg()).note(5.0) == 0.0
    assert not (tmp_path / "spend_day.json").exists()


# ── config wiring ─────────────────────────────────────────────────────────
def test_the_config_ships_the_section_switched_off():
    from openamer_cli.config import DEFAULT_CONFIG

    section = DEFAULT_CONFIG["budget"]
    assert section["enabled"] is False
    assert section["max_usd_per_session"] == 0.0
    assert section["max_usd_per_day"] == 0.0
    assert section["on_exceed"] == "block"
    assert section["warn_at_percent"] == 80


def test_describe_names_the_scope_and_the_reason():
    v = sb.evaluate(1.0, 0.0, cfg(enabled=True, max_usd_per_session=1.0))
    text = v.describe()
    assert sb.REASON_SESSION_CAP in text and "session" in text


def test_spend_budget_uses_the_configured_store(monkeypatch, tmp_path):
    monkeypatch.setattr(sb, "_store_path", lambda: tmp_path / "spend_day.json")
    budget = sb.SpendBudget(cfg=cfg(enabled=True, max_usd_per_day=1.0))
    assert budget.ok_to_continue(0.0) is True
    budget.note(0.5)
    assert budget.ok_to_continue(0.0) is True
    budget.note(0.5)
    assert budget.ok_to_continue(0.0) is False
    assert budget.verdict(0.0).reason == sb.REASON_DAY_CAP


def test_module_file_exists_at_the_expected_path():
    """A cheap shape guard: the module lives where the loop imports it from."""
    assert Path(sb.__file__).name == "spend_budget.py"
