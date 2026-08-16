"""Tests for openamer_cli.security — hardening posture audit."""
import os


def test_check_reports_structure(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    from openamer_cli import security as sec
    c = sec.check()
    assert set(c) >= {"yolo_mode", "approval_enabled", "hardline_rm", "sudo_guard",
                      "config_exists", "notes"}
    assert isinstance(c["hardline_rm"], bool)


def test_safe_mode_clears_yolo_and_writes_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    monkeypatch.setenv("OPENAMER_YOLO_MODE", "1")
    from openamer_cli import security as sec
    before = sec.check()
    assert before["yolo_mode"] is True
    r = sec.apply_safe_mode()
    after = sec.check()
    assert after["yolo_mode"] is False
    assert (tmp_path / ".safe-mode").exists()
    assert r["ok"] is True
