"""Tests for the dependency-spec fast path in ``openamer update``.

Why this exists: an update whose ``pyproject.toml``/``uv.lock`` never moved has
no dependency work to do, yet the old flow still wrote a half-install breadcrumb
and ran a full ``.[all]`` reinstall. On Windows that reinstall has to quarantine
the running ``openamer.exe`` — which the app itself holds — so the breadcrumb
could never be cleared and blocked every launch instead. Measured 2026-10-30: a
version-bump-only update left ``.update-incomplete`` set for an hour, printed the
interruption warning on every boot and made ``openamer --version`` report no
version at all.

The invariant under test: reinstall only when the dependency SPEC changed OR the
venv is unhealthy. Neither condition alone is enough.
"""

from __future__ import annotations

import openamer_cli.main as m


def _write_spec(root, *, pyproject="[project]\nname='x'\nversion='1.0'\n", lock=None):
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    if lock is not None:
        (root / "uv.lock").write_text(lock, encoding="utf-8")


def test_fingerprint_ignores_code_changes(tmp_path):
    _write_spec(tmp_path, lock="lock-v1\n")
    first = m._dependency_spec_fingerprint(tmp_path)

    # Code churn must not look like a dependency change.
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").read_bytes()  # untouched
    assert m._dependency_spec_fingerprint(tmp_path) == first


def test_fingerprint_tracks_spec_mutations(tmp_path):
    _write_spec(tmp_path, lock="lock-v1\n")
    base = m._dependency_spec_fingerprint(tmp_path)
    assert base

    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\nversion='1.1'\n", encoding="utf-8"
    )
    after_pyproject = m._dependency_spec_fingerprint(tmp_path)
    assert after_pyproject != base

    (tmp_path / "uv.lock").write_text("lock-v2\n", encoding="utf-8")
    assert m._dependency_spec_fingerprint(tmp_path) != after_pyproject


def test_fingerprint_none_without_spec_files(tmp_path):
    # PyPI/Docker install: no spec on disk => "unknown", never "unchanged".
    assert m._dependency_spec_fingerprint(tmp_path) is None


def test_marker_records_dependency_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    _write_spec(tmp_path, lock="lock-v1\n")

    m._write_update_incomplete_marker()

    body = m._update_marker_path().read_text(encoding="utf-8")
    assert "started=" in body and "pid=" in body
    recorded = m._read_marker_deps_fingerprint(m._update_marker_path())
    assert recorded == m._dependency_spec_fingerprint(tmp_path)


def test_legacy_marker_without_deps_reads_none(tmp_path):
    legacy = tmp_path / ".update-incomplete"
    legacy.write_text("started=1.0\npid=42\n", encoding="utf-8")
    assert m._read_marker_deps_fingerprint(legacy) is None


def test_skippable_requires_both_halves(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(m, "_venv_core_imports_healthy", lambda: (True, ""))
    assert m._dependency_install_is_skippable("abc", "abc") is True

    monkeypatch.setattr(m, "_venv_core_imports_healthy", lambda: (False, "fastapi missing"))
    assert m._dependency_install_is_skippable("abc", "abc") is False

    monkeypatch.setattr(m, "_venv_core_imports_healthy", lambda: (True, ""))
    assert m._dependency_install_is_skippable("abc", "def") is False
    assert m._dependency_install_is_skippable(None, "abc") is False
    assert m._dependency_install_is_skippable("abc", None) is False


def _spy_install(monkeypatch):
    seen = {"install": False}

    def fake_install(*a, **k):
        seen["install"] = True

    monkeypatch.setattr(m, "_install_python_dependencies_with_optional_fallback", fake_install)
    monkeypatch.setattr(m, "_default_venv_install_target", lambda: (["pip"], None))
    return seen


def _stub_reinstall_environment(monkeypatch):
    class R:
        returncode = 0

    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: R())
    monkeypatch.setattr(m, "_is_termux_env", lambda *a, **k: False)
    monkeypatch.setattr("openamer_cli.managed_uv.ensure_uv", lambda: None)


def test_recovery_clears_marker_without_install_when_nothing_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    _write_spec(tmp_path, lock="lock-v1\n")
    # Marker written exactly as the interrupted update wrote it.
    m._write_update_incomplete_marker()

    seen = _spy_install(monkeypatch)
    _stub_reinstall_environment(monkeypatch)
    monkeypatch.setattr(m, "_repair_venv_via_import_probes", lambda *a, **k: "healthy")

    m._recover_from_interrupted_install()

    assert seen["install"] is False, "nothing was pending — the venv must not be touched"
    assert not m._update_marker_path().exists(), "marker must be cleared, not left blocking"


def test_recovery_reinstalls_when_spec_moved(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    _write_spec(tmp_path, lock="lock-v1\n")
    m._write_update_incomplete_marker()
    # A real dependency change between marker and recovery.
    _write_spec(tmp_path, lock="lock-v2\n")

    seen = _spy_install(monkeypatch)
    _stub_reinstall_environment(monkeypatch)
    monkeypatch.setattr(m, "_repair_venv_via_import_probes", lambda *a, **k: "healthy")

    m._recover_from_interrupted_install()

    assert seen["install"] is True, "a moved spec must still trigger the full reinstall"
    assert not m._update_marker_path().exists()


def test_recovery_reinstalls_when_probes_indeterminate(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    _write_spec(tmp_path, lock="lock-v1\n")
    m._write_update_incomplete_marker()

    seen = _spy_install(monkeypatch)
    _stub_reinstall_environment(monkeypatch)
    monkeypatch.setattr(m, "_repair_venv_via_import_probes", lambda *a, **k: "indeterminate")

    m._recover_from_interrupted_install()

    assert seen["install"] is True, "unverifiable health must never be treated as healthy"
    assert not m._update_marker_path().exists()


def test_recovery_legacy_marker_still_reinstalls(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PROJECT_ROOT", tmp_path)
    _write_spec(tmp_path, lock="lock-v1\n")
    (tmp_path / ".update-incomplete").write_text("started=1.0\npid=42\n", encoding="utf-8")

    seen = _spy_install(monkeypatch)
    _stub_reinstall_environment(monkeypatch)
    monkeypatch.setattr(m, "_repair_venv_via_import_probes", lambda *a, **k: "healthy")

    m._recover_from_interrupted_install()

    assert seen["install"] is True, "old markers carry no proof — keep the conservative path"
