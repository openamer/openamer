"""Regression tests for scripts/self-healer.py's scan-safety.

Root cause this pins (run 2026-09-23 00:23):

    os.walk() listed 10248 .py files, then compile() raised
    FileNotFoundError: 'C:\\...\\openamer_agent-2026.9.22\\batch_runner.py'
    and killed heal() before the REPORT was ever written.

Build/install staging trees (openamer_agent-<version>/) are created and
removed *while the scan runs*, so a listed path can be gone by the time it is
read. check_syntax() only caught SyntaxError, so the OSError propagated.

Contract: a file that is missing (or unreadable) is NOT a fault. It must never
abort the run, and a genuine SyntaxError must still be reported.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "self_healer", REPO / "scripts" / "self-healer.py"
)
SH = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SH)


def test_missing_file_is_not_a_fault(tmp_path):
    """The exact crash: a path listed by walk() that no longer exists."""
    gone = tmp_path / "openamer_agent-2026.9.22" / "batch_runner.py"
    assert not gone.exists()
    assert SH.check_syntax(gone) == []


def test_file_vanishing_between_walk_and_read(tmp_path, monkeypatch):
    """Same race, expressed as the read failing after the path was resolved."""
    pf = tmp_path / "runner.py"
    pf.write_text("x = 1\n", encoding="utf-8")

    real_read = Path.read_text

    def flaky(self, *a, **kw):
        if self.name == "runner.py":
            raise FileNotFoundError(2, "No such file or directory")
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", flaky)
    assert SH.check_syntax(pf) == []


def test_real_syntax_error_is_still_reported(tmp_path):
    """The fix must not swallow real faults."""
    broken = tmp_path / "broken.py"
    broken.write_text("def f(:\n    pass\n", encoding="utf-8")
    errs = SH.check_syntax(broken)
    assert len(errs) == 1
    assert "SyntaxError" in errs[0] and "broken.py" in errs[0]
    assert "line 1" in errs[0]


def test_valid_file_reports_nothing(tmp_path):
    ok = tmp_path / "ok.py"
    ok.write_text("def f():\n    return 1\n", encoding="utf-8")
    assert SH.check_syntax(ok) == []


def test_scan_loop_survives_an_unreadable_file(tmp_path, monkeypatch):
    """heal()'s per-file guard: one bad file must not abort the whole scan."""
    scanned = tmp_path / "scan"
    scanned.mkdir()
    (scanned / "good.py").write_text("x = 1\n", encoding="utf-8")
    (scanned / "bad.py").write_text("y = 2\n", encoding="utf-8")

    real = SH.check_syntax

    def explode_on_bad(path):
        if path.name == "bad.py":
            raise PermissionError(13, "Access is denied")
        return real(path)

    monkeypatch.setattr(SH, "check_syntax", explode_on_bad)
    monkeypatch.setattr(SH, "REPO", str(scanned))
    monkeypatch.setattr(SH, "SKILLS", str(tmp_path / "nonexistent"))
    monkeypatch.setattr(SH, "LOG_FILE", str(tmp_path / "self-healer.log"))
    monkeypatch.setattr(SH, "clear_pycache", lambda p: 0)

    # Must return a report tuple, not raise.
    issues, fixed = SH.heal()
    assert (issues, fixed) == (0, 0)
    assert "REPORT" in (tmp_path / "self-healer.log").read_text(encoding="utf-8")