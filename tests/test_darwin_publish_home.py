"""Regression test: darwin_publish must not trust a poisoned OPENAMER_HOME.

Bug (observed live 2026-10-13, cron ``darwin-daily-evolution``): the worker's
process env held ``OPENAMER_HOME=C:/Users/damir/AppData/Local/Temp/rt_test/home``
-- a gateway-restart-test scratch home that no longer EXISTED (the terminal tool
copies the worker env into ``cache/terminal/openamer-snap-*.sh``, so every shell
in the run inherited it). ``darwin_publish.py`` was the one darwin script without
``_resolve_home()``: it read the variable raw, so the daily refresh died at
import with

    FileNotFoundError: .../Temp/rt_test/home/logs/skill-validator-latest.json

and the website's Darwin data was never republished. Its siblings
(``darwin_engine``, ``darwin_synthesize``, ``darwin_promote``) already defend via
``_resolve_home()``; this suite pins the same contract for the publisher, plus
the second half of the bug class: a home that is *findable* but carries no
validator log must raise an error naming every path it tried, never silently
publish against the wrong tree.

See ``tests/test_darwin_phantom_home.py`` for the engine-side regression suite.
"""
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PUBLISH = REPO / "scripts" / "darwin_publish.py"


def _load(monkeypatch, env_home: str | None):
    """Import darwin_publish under a controlled OPENAMER_HOME.

    The module resolves its home and its validator log at import time, which is
    exactly what made the live failure fatal -- so the import itself is the
    subject under test.
    """
    if env_home is None:
        monkeypatch.delenv("OPENAMER_HOME", raising=False)
    else:
        monkeypatch.setenv("OPENAMER_HOME", env_home)
    spec = importlib.util.spec_from_file_location("darwin_publish_home_probe",
                                                  PUBLISH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _msys_form(path: Path) -> str:
    """``C:/Users/x`` -> ``/c/Users/x``, the form git-bash exports."""
    s = str(path).replace("\\", "/")
    return "/c" + s[2:] if s[1:3] == ":/" else s


def _install(root: Path, *, log: bool = True, markers: tuple[str, ...] = ()) -> Path:
    """Shape ``root`` as an install home (and optionally a validator log)."""
    (root / "skills").mkdir(parents=True, exist_ok=True)
    for m in markers:
        target = root / m
        target.write_text("x\n", encoding="utf-8") if "." in m else target.mkdir()
    if log:
        (root / "logs").mkdir(exist_ok=True)
        (root / "logs" / "skill-validator-latest.json").write_text(
            '{"skill_results": [{"name": "a", "score": 50.0}]}', encoding="utf-8")
    return root


def _machine_home(monkeypatch, root: Path) -> Path:
    """Shape ``root`` as a machine whose install lives under ``~/AppData/Local``.

    When ``OPENAMER_HOME`` is unusable, ``darwin_publish`` falls back to the
    install it finds through ``Path.home()``. A CI runner's home has no install,
    so the two fallback tests below could only pass on a dev box that owns one.
    Faking the home with a shaped install makes that fallback contract
    observable on every platform instead of silently host-dependent.
    """
    monkeypatch.setenv("HOME", str(root))
    monkeypatch.setenv("USERPROFILE", str(root))
    return _install(root / "AppData" / "Local" / "openamer-laptop")


def test_missing_scratch_home_does_not_break_the_daily_run(tmp_path, monkeypatch):
    """The exact live shape: a home that does NOT exist must not be adopted."""
    gone = tmp_path / "Temp" / "rt_test" / "home"          # never created
    _machine_home(monkeypatch, tmp_path / "machine")       # the host's install

    mod = _load(monkeypatch, str(gone))

    assert mod.SKILLS_DIR.parent != gone, "vanished scratch home was adopted"
    assert mod.VALIDATOR_LOG.is_file(), (
        f"no validator log resolved; got {mod.VALIDATOR_LOG}")


def test_existing_scratch_home_is_not_adopted(tmp_path, monkeypatch):
    """A dir that EXISTS but carries no install markers falls back."""
    scratch = tmp_path / "oa-home"
    (scratch / "skills").mkdir(parents=True)               # exists, not an install
    _machine_home(monkeypatch, tmp_path / "machine")       # the host's install

    mod = _load(monkeypatch, str(scratch))

    assert mod.SKILLS_DIR.parent != scratch, "scratch dir adopted as OPENAMER_HOME"
    assert mod.VALIDATOR_LOG.is_file()


def test_real_install_home_is_honoured(tmp_path, monkeypatch):
    """A genuine home (install marker + validator log) still wins."""
    real = _install(tmp_path / "real-home", markers=("config.yaml",))

    mod = _load(monkeypatch, str(real))

    assert mod.SKILLS_DIR.parent == real
    assert mod.VALIDATOR_LOG == real / "logs" / "skill-validator-latest.json"


def test_msys_home_form_is_normalised(tmp_path, monkeypatch):
    """git-bash's ``/c/...`` must not expand to a phantom ``C:/c/...`` tree."""
    real = _install(tmp_path / "msys-home", markers=(".env",))

    mod = _load(monkeypatch, _msys_form(real))

    assert mod.SKILLS_DIR.parent == real, (
        f"MSYS path resolved to {mod.SKILLS_DIR.parent}, not {real}")
    assert "c" != mod.SKILLS_DIR.parent.parts[1].lower(), "doubled-drive artefact"


def test_no_log_anywhere_raises_and_names_every_path(tmp_path, monkeypatch):
    """A wrong home must fail loudly, not publish against the wrong tree."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    bare = _install(tmp_path / "bare-home", log=False, markers=("config.yaml",))

    with pytest.raises(FileNotFoundError) as err:
        _load(monkeypatch, str(bare))

    msg = str(err.value)
    assert "skill-validator-latest.json not found" in msg
    assert str(bare) in msg, "error does not name the home it was given"
