"""Tests for scripts/desktop_ledger.py.

The load-bearing behaviours, in order of importance:

1. An action that changed NOTHING on screen is flagged NO-VISIBLE-EFFECT —
   that silent failure ("ok:true, nothing happened") is the whole reason the
   ledger exists.
2. The evidence SURVIVES the loss of the source screenshot: frames are copied
   into the ledger, so deleting %TEMP% does not destroy the record.
3. The comparison degrades honestly when it cannot measure (no invented
   percentages), and `verify()` detects a tampered frame.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "desktop_ledger.py"


def _load():
    spec = importlib.util.spec_from_file_location("desktop_ledger", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["desktop_ledger"] = mod
    spec.loader.exec_module(mod)
    return mod


dl = _load()


def _img(path, color, size=(120, 90)):
    from PIL import Image

    Image.new("RGB", size, color).save(path)
    return path


# --- comparison ----------------------------------------------------------

def test_identical_frames_are_not_a_change(tmp_path):
    a = _img(tmp_path / "a.png", (10, 20, 30))
    b = _img(tmp_path / "b.png", (10, 20, 30))
    result = dl.compare(a, b)
    assert result["changed"] is False
    assert result["pct_changed"] == 0.0
    assert result["method"] == "pixel-diff"


def test_a_visible_change_is_measured(tmp_path):
    a = _img(tmp_path / "a.png", (0, 0, 0))
    b = _img(tmp_path / "b.png", (255, 255, 255))
    result = dl.compare(a, b)
    assert result["changed"] is True
    assert result["pct_changed"] == 100.0
    assert "bbox" in result


def test_sub_tolerance_noise_is_not_a_change(tmp_path):
    """A blinking caret or AA jitter must not read as an effective action."""
    a = _img(tmp_path / "a.png", (100, 100, 100))
    b = _img(tmp_path / "b.png", (104, 100, 100))  # delta 4 < tolerance 8
    assert dl.compare(a, b)["changed"] is False


def test_size_mismatch_is_a_change(tmp_path):
    a = _img(tmp_path / "a.png", (0, 0, 0), size=(100, 100))
    b = _img(tmp_path / "b.png", (0, 0, 0), size=(120, 90))
    result = dl.compare(a, b)
    assert result["changed"] is True
    assert result["method"] == "size-mismatch"


# --- verdicts ------------------------------------------------------------

def test_effective_action_is_recorded(tmp_path):
    led = dl.Ledger(home=tmp_path)
    a = _img(tmp_path / "a.png", (0, 0, 0))
    b = _img(tmp_path / "b.png", (255, 255, 255))
    entry = led.record("click Save", a, b, note="dialog closed")
    assert entry["verdict"] == "effective"
    assert entry["change"]["pct_changed"] == 100.0


def test_the_silent_failure_is_flagged(tmp_path):
    """ok:true but nothing moved => the audit must surface it."""
    led = dl.Ledger(home=tmp_path)
    a = _img(tmp_path / "a.png", (7, 7, 7))
    b = _img(tmp_path / "b.png", (7, 7, 7))
    led.record("click Save", a, b)
    assert [e["action"] for e in led.suspicious()] == ["click Save"]


def test_expect_no_effect_is_informational_not_a_failure(tmp_path):
    led = dl.Ledger(home=tmp_path)
    a = _img(tmp_path / "a.png", (7, 7, 7))
    b = _img(tmp_path / "b.png", (7, 7, 7))
    entry = led.record("probe window", a, b, expect_effect=False)
    assert entry["verdict"] == "informational"
    assert led.suspicious() == []


def test_single_frame_is_unpaired_not_a_false_claim(tmp_path):
    led = dl.Ledger(home=tmp_path)
    entry = led.record("note only", before=_img(tmp_path / "a.png", (1, 2, 3)))
    assert entry["verdict"] == "unpaired"


# --- the evidence must outlive the source --------------------------------

def test_frames_are_copied_so_evidence_survives_deletion(tmp_path):
    led = dl.Ledger(home=tmp_path)
    a = _img(tmp_path / "src_a.png", (0, 0, 0))
    b = _img(tmp_path / "src_b.png", (255, 255, 255))
    led.record("click OK", a, b)
    a.unlink()
    b.unlink()
    assert led.verify()["intact"] is True
    assert led.verify()["checked"] == 2


def test_verify_detects_a_tampered_frame(tmp_path):
    led = dl.Ledger(home=tmp_path)
    a = _img(tmp_path / "a.png", (0, 0, 0))
    b = _img(tmp_path / "b.png", (255, 255, 255))
    led.record("click OK", a, b)
    victim = sorted(led.frames_dir.glob("*-after.png"))[0]
    _img(victim, (1, 2, 3))  # overwrite with different pixels
    report = led.verify()
    assert report["intact"] is False
    assert report["modified"]


def test_rotations_keep_the_ledger_bounded(tmp_path):
    led = dl.Ledger(home=tmp_path, max_frames=4)
    for i in range(6):
        led.record(f"action {i}",
                   _img(tmp_path / f"a{i}.png", (i, i, i)),
                   _img(tmp_path / f"b{i}.png", (i + 100, i, i)))
    assert len(list(led.frames_dir.glob("*"))) <= 4


# --- report + CLI --------------------------------------------------------

def test_report_lists_actions_and_flags_the_bad_one(tmp_path, capsys):
    led = dl.Ledger(home=tmp_path)
    led.record("good", _img(tmp_path / "a.png", (0, 0, 0)), _img(tmp_path / "b.png", (255, 0, 0)))
    led.record("bad", _img(tmp_path / "c.png", (5, 5, 5)), _img(tmp_path / "d.png", (5, 5, 5)))
    out = led.report()
    assert "good" in out and "bad" in out
    assert "NO-VISIBLE-EFFECT" in out


def test_cli_record_then_report(tmp_path, capsys):
    a = _img(tmp_path / "a.png", (0, 0, 0))
    b = _img(tmp_path / "b.png", (255, 255, 255))
    rc = dl.main(["--home", str(tmp_path), "record", "--action", "click X",
                  "--before", str(a), "--after", str(b)])
    assert rc == 0
    assert json_loads(capsys.readouterr().out)["verdict"] == "effective"


def test_cli_verify_exit_code_reflects_integrity(tmp_path, capsys):
    led = dl.Ledger(home=tmp_path)
    led.record("x", _img(tmp_path / "a.png", (0, 0, 0)), _img(tmp_path / "b.png", (255, 255, 255)))
    rc = dl.main(["--home", str(tmp_path), "verify"])
    assert rc == 0
    assert json_loads(capsys.readouterr().out)["intact"] is True


def json_loads(text):
    import json

    return json.loads(text)