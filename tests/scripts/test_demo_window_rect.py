"""Tests for scripts/demo_window_rect.py — the region maths only.

The window lookup needs a real, running demo window; the part that broke in
practice was the ARITHMETIC: the script emitted a 1071-px-wide region, and
libx264+yuv420p refuses odd dimensions — but only when you actually record
(a one-frame capture still succeeds, so the trap is easy to miss).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "demo_window_rect.py"


def _load():
    spec = importlib.util.spec_from_file_location("demo_window_rect", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["demo_window_rect"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_region_is_always_even():
    m = _load()
    # the exact real-world rect that produced the failing 1071x696
    gx, gy, gw, gh = m.even_region(210, 226, 1075, 700)
    assert (gw, gh) == (1070, 696)
    assert gw % 2 == 0 and gh % 2 == 0


def test_region_is_inset_by_the_border():
    m = _load()
    assert m.even_region(100, 200, 800, 600) == (102, 202, 796, 596)


def test_odd_widths_and_heights_both_snap_down_never_up():
    m = _load()
    for w, h in ((1075, 701), (999, 601), (101, 99)):
        _, _, gw, gh = m.even_region(0, 0, w, h)
        assert gw % 2 == 0 and gh % 2 == 0
        assert gw <= w and gh <= h  # never grows past the window


def test_main_reports_not_found_without_a_window(monkeypatch, capsys):
    m = _load()
    monkeypatch.setattr(m, "find_window", lambda *a, **k: None)
    assert m.main() == 1
    assert capsys.readouterr().out.strip() == "NOT_FOUND"


def test_main_prints_even_gdigrab_args(monkeypatch, capsys):
    m = _load()
    monkeypatch.setattr(m, "find_window", lambda *a, **k: (210, 226, 1075, 700))
    assert m.main() == 0
    out = capsys.readouterr().out
    assert "video_size 1070x696" in out