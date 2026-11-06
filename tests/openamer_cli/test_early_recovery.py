"""Tests for openamer_cli._early_recovery — the dependency-light bootstrap
repair that runs BEFORE openamer_cli.main's third-party imports (#57828 / #58004).

Covers:
- entry-point lifecycle: a broken core import (dotenv) crashes the import of
  openamer_cli.main WITHOUT early recovery, and imports fine when recovery runs
  first (proving main.py invokes recovery before its third-party imports)
- recover_if_needed unit behavior: fast path, marker gating, update-argv skip,
  lock single-flight, no marker clearing, pinned repair specs
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from openamer_cli import _early_recovery as er

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Entry-point lifecycle (subprocess, real imports)
# ---------------------------------------------------------------------------

def _make_broken_dotenv_shadow(tmp_path: Path) -> Path:
    """A sys.path dir shadowing ``dotenv`` with the #57828 failure state:
    distribution metadata intact, import files wiped/broken."""
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "dotenv.py").write_text(
        "raise ImportError('import files wiped mid-install (#57828)')\n",
        encoding="utf-8",
    )
    return shadow


def _run_lifecycle_subprocess(tmp_path: Path, *, repair: bool) -> subprocess.CompletedProcess:
    shadow = _make_broken_dotenv_shadow(tmp_path)
    openamer_home = tmp_path / "openamer_home"
    openamer_home.mkdir()
    script = tmp_path / "lifecycle.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import sys

            shadow = {str(shadow)!r}
            sys.path.insert(0, shadow)

            # _early_recovery must be importable on the corrupted venv
            # (stdlib-only) — this import itself is part of the contract.
            import openamer_cli._early_recovery as er

            REPAIR = {repair!r}

            def recorder(*args, **kwargs):
                print("EARLY_RECOVERY_CALLED", flush=True)
                if REPAIR:
                    sys.path.remove(shadow)
                    sys.modules.pop("dotenv", None)

            er.recover_if_needed = recorder

            import openamer_cli.main  # noqa: F401
            print("MAIN_IMPORTED_OK", flush=True)
            """
        ),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "OPENAMER_HOME": str(openamer_home),
    }
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=120,
    )


def test_broken_dotenv_crashes_main_import_without_repair(tmp_path):
    """Negative control: the shadow really breaks importing openamer_cli.main,
    and recovery was invoked BEFORE the crash (i.e. before third-party
    imports) — so a real repair at that point can save the launch."""
    result = _run_lifecycle_subprocess(tmp_path, repair=False)
    assert result.returncode != 0
    assert "EARLY_RECOVERY_CALLED" in result.stdout
    assert "MAIN_IMPORTED_OK" not in result.stdout
    assert "wiped mid-install" in result.stderr


def test_early_recovery_runs_before_main_imports_and_saves_launch(tmp_path):
    """When recovery repairs the broken package, openamer_cli.main imports
    cleanly — proving the recovery hook fires before env_loader/dotenv."""
    result = _run_lifecycle_subprocess(tmp_path, repair=True)
    assert "EARLY_RECOVERY_CALLED" in result.stdout
    assert "MAIN_IMPORTED_OK" in result.stdout, result.stderr
    assert result.returncode == 0


def test_early_recovery_module_is_stdlib_only(tmp_path):
    """The module must import in a process where every non-stdlib import
    fails — that is the whole point of its existence."""
    script = tmp_path / "stdlib_only.py"
    script.write_text(
        textwrap.dedent(
            """
            import builtins
            import sys

            STDLIB = set(sys.stdlib_module_names) | {"openamer_cli"}
            real_import = builtins.__import__

            def guard(name, *args, **kwargs):
                top = name.split(".")[0]
                if top not in STDLIB:
                    raise ImportError(f"non-stdlib import blocked: {name}")
                return real_import(name, *args, **kwargs)

            builtins.__import__ = guard
            import openamer_cli._early_recovery  # noqa: F401
            print("STDLIB_ONLY_OK")
            """
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        timeout=60,
    )
    assert "STDLIB_ONLY_OK" in result.stdout, result.stderr


# ---------------------------------------------------------------------------
# recover_if_needed unit behavior
# ---------------------------------------------------------------------------

def _project(tmp_path: Path, *, pyproject: bool = True) -> Path:
    root = tmp_path / "proj"
    root.mkdir(exist_ok=True)
    if pyproject:
        (root / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = [\n'
            '  "PyYAML==6.0.2",\n'
            '  "python-dotenv==1.2.2",\n'
            '  "PyJWT[crypto]==2.13.0",\n'
            "]\n",
            encoding="utf-8",
        )
    return root


def test_fast_path_no_marker_never_probes(tmp_path, monkeypatch):
    root = _project(tmp_path)
    probed = []
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: probed.append(1) or [])
    er.recover_if_needed(project_root=root, argv=[])
    assert probed == []


def test_update_argv_skips_recovery(tmp_path, monkeypatch):
    root = _project(tmp_path)
    (root / ".lazy-refresh-incomplete").write_text("x", encoding="utf-8")
    probed = []
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: probed.append(1) or [])
    er.recover_if_needed(project_root=root, argv=["update"])
    assert probed == []


def test_no_pyproject_skips_and_preserves_marker(tmp_path, monkeypatch):
    root = _project(tmp_path, pyproject=False)
    marker = root / ".update-incomplete"
    marker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: ["PyYAML"])
    installs = []
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: installs.append(specs) or True)
    er.recover_if_needed(project_root=root, argv=[])
    assert installs == []
    assert marker.exists()


def test_marker_plus_broken_probe_repairs_with_pinned_specs(tmp_path, monkeypatch):
    root = _project(tmp_path)
    marker = root / ".lazy-refresh-incomplete"
    marker.write_text("x", encoding="utf-8")

    probe_results = iter([["PyYAML", "python-dotenv"], []])
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: next(probe_results))
    installs = []
    monkeypatch.setattr(
        er, "_run_repair_install", lambda specs, r: installs.append(specs) or True
    )

    er.recover_if_needed(project_root=root, argv=[])

    assert installs == [["PyYAML==6.0.2", "python-dotenv==1.2.2"]]
    # Marker lifecycle belongs to main.py's full recovery — never cleared here.
    assert marker.exists()
    # Lock released for the full recovery pass.
    assert not (root / ".update-incomplete.lock").exists()


def test_healthy_probe_skips_install(tmp_path, monkeypatch):
    root = _project(tmp_path)
    (root / ".update-incomplete").write_text("x", encoding="utf-8")
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: [])
    installs = []
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: installs.append(specs) or True)
    er.recover_if_needed(project_root=root, argv=[])
    assert installs == []


def test_lock_held_skips_repair(tmp_path, monkeypatch):
    root = _project(tmp_path)
    (root / ".lazy-refresh-incomplete").write_text("x", encoding="utf-8")
    (root / ".update-incomplete.lock").write_text("123\n", encoding="utf-8")
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: ["PyYAML"])
    installs = []
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: installs.append(specs) or True)
    er.recover_if_needed(project_root=root, argv=[])
    assert installs == []
    # Fresh (non-stale) lock is left for its owner.
    assert (root / ".update-incomplete.lock").exists()


def test_failed_repair_prints_manual_command_with_pins(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path)
    (root / ".lazy-refresh-incomplete").write_text("x", encoding="utf-8")
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: ["PyJWT"])
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: False)
    er.recover_if_needed(project_root=root, argv=[])
    err = capsys.readouterr().err
    assert "--force-reinstall" in err
    assert "PyJWT[crypto]==2.13.0" in err


def test_pinned_specs_falls_back_to_bare_names_without_pyproject(tmp_path):
    root = _project(tmp_path, pyproject=False)
    assert er._pinned_specs(["PyYAML", "unknown-pkg"], root) == ["PyYAML", "unknown-pkg"]


def test_pinned_specs_strips_env_markers_and_matches_extras(tmp_path):
    root = _project(tmp_path)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = [\n'
        '  "cryptography==46.0.7; python_version >= \'3.11\'",\n'
        '  "PyJWT[crypto]==2.13.0",\n'
        "]\n",
        encoding="utf-8",
    )
    assert er._pinned_specs(["cryptography", "PyJWT"], root) == [
        "cryptography==46.0.7",
        "PyJWT[crypto]==2.13.0",
    ]


def test_probe_tables_shared_with_main():
    """The full recovery layer in main.py must probe/repair the same set as
    the early layer — the tables have one canonical home."""
    import openamer_cli.main as m

    assert m._LAZY_REFRESH_IMPORT_PROBES == er.LAZY_REFRESH_IMPORT_PROBES
    assert m._LAZY_REFRESH_REPAIR_PACKAGES == er.LAZY_REFRESH_REPAIR_PACKAGES


# ---------------------------------------------------------------------------
# Explicit repair: reachable without a marker, and without importing the app
# ---------------------------------------------------------------------------

def test_explicit_repair_works_without_any_marker(tmp_path, monkeypatch):
    """`openamer doctor --runtime --fix` must repair on request: the marker
    only gates the automatic launch-time pass."""
    root = _project(tmp_path)
    probe_results = iter([["PyYAML"], []])
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: next(probe_results))
    installs = []
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: installs.append(specs) or True)

    assert er.recover_if_needed(project_root=root, argv=[], explicit=True) is True
    assert installs == [["PyYAML==6.0.2"]]
    # Still no marker written by a diagnosis the user asked for.
    assert not (root / ".update-incomplete").exists()
    assert not (root / ".lazy-refresh-incomplete").exists()


def test_explicit_repair_reports_healthy_environment(tmp_path, monkeypatch):
    root = _project(tmp_path)
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: [])
    installs = []
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: installs.append(specs) or True)

    assert er.recover_if_needed(project_root=root, argv=[], explicit=True) is True
    assert installs == []


def test_explicit_repair_without_pyproject_reports_nothing_to_do(tmp_path, monkeypatch):
    root = _project(tmp_path, pyproject=False)
    installs = []
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: installs.append(specs) or True)
    assert er.recover_if_needed(project_root=root, argv=[], explicit=True) is False
    assert installs == []


def test_explicit_repair_reports_held_lock_instead_of_skipping_silently(
    tmp_path, monkeypatch, capsys
):
    root = _project(tmp_path)
    (root / ".update-incomplete.lock").write_text("123\n", encoding="utf-8")
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: ["PyYAML"])
    installs = []
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: installs.append(specs) or True)

    assert er.recover_if_needed(project_root=root, argv=[], explicit=True) is False
    assert installs == []
    assert "Another OpenAmer process" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Bounded automatic retries (an offline box must not reinstall forever)
# ---------------------------------------------------------------------------

def test_automatic_repair_stops_after_max_attempts(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path)
    marker = root / ".lazy-refresh-incomplete"
    marker.write_text(
        f"started=1\npid=2\nattempts={er.EARLY_REPAIR_MAX_ATTEMPTS}\n", encoding="utf-8"
    )
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: ["PyYAML"])
    installs = []
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: installs.append(specs) or True)

    assert er.recover_if_needed(project_root=root, argv=[]) is False
    assert installs == []
    err = capsys.readouterr().err
    assert "doctor --runtime --fix" in err
    assert str(er.EARLY_REPAIR_MAX_ATTEMPTS) in err


def test_explicit_repair_ignores_attempt_budget(tmp_path, monkeypatch):
    root = _project(tmp_path)
    marker = root / ".lazy-refresh-incomplete"
    marker.write_text(f"attempts={er.EARLY_REPAIR_MAX_ATTEMPTS + 5}\n", encoding="utf-8")
    probe_results = iter([["PyYAML"], []])
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: next(probe_results))
    installs = []
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: installs.append(specs) or True)

    assert er.recover_if_needed(project_root=root, argv=[], explicit=True) is True
    assert installs == [["PyYAML==6.0.2"]]


def test_failed_automatic_repair_counts_the_attempt(tmp_path, monkeypatch):
    root = _project(tmp_path)
    marker = root / ".lazy-refresh-incomplete"
    marker.write_text("started=1\npid=2\n", encoding="utf-8")
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: ["PyYAML"])
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: False)

    assert er.recover_if_needed(project_root=root, argv=[]) is False
    body = marker.read_text(encoding="utf-8")
    assert "attempts=1" in body
    # main.py's own marker fields survive the counter update.
    assert "started=1" in body and "pid=2" in body
    assert marker.exists()


def test_offline_install_failure_is_reported_not_swallowed(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path)
    (root / ".lazy-refresh-incomplete").write_text("x", encoding="utf-8")
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: ["PyYAML"])
    monkeypatch.setattr(er, "_run_repair_install", lambda specs, r: False)

    assert er.recover_if_needed(project_root=root, argv=[], explicit=True) is False
    err = capsys.readouterr().err
    assert "Repair did not restore every core import" in err
    assert "still broken: PyYAML" in err
    assert "network / proxy / index error" in err
    assert "--force-reinstall PyYAML==6.0.2" in err


# ---------------------------------------------------------------------------
# Stale namespace-package re-probe (the repair-then-still-broken trap)
# ---------------------------------------------------------------------------

def test_repair_reprobes_from_disk_not_the_stale_cached_module(tmp_path, monkeypatch):
    """A wiped ``__init__.py`` leaves ``import yaml`` succeeding as an empty
    namespace package, which is then cached.  After a successful reinstall the
    same-process re-probe must read the new files, not that stale module."""
    import types

    root = _project(tmp_path)
    site = tmp_path / "site"
    site.mkdir()
    monkeypatch.syspath_prepend(str(site))
    stale = types.ModuleType("yaml")
    monkeypatch.setitem(sys.modules, "yaml", stale)

    def fake_install(specs, project_root):
        (site / "yaml").mkdir(exist_ok=True)
        (site / "yaml" / "__init__.py").write_text("SafeDumper = object\n", encoding="utf-8")
        return True

    monkeypatch.setattr(er, "_run_repair_install", fake_install)
    assert er._probe_broken_packages() == ["PyYAML"]

    assert er._repair_once(root, ["PyYAML"], explicit=True) is True
    assert sys.modules["yaml"] is not stale


def test_reset_probe_modules_only_drops_the_named_module(monkeypatch):
    import types

    monkeypatch.setitem(sys.modules, "yaml", types.ModuleType("yaml"))
    monkeypatch.setitem(sys.modules, "yaml.composer", types.ModuleType("yaml.composer"))
    keeper = types.ModuleType("unrelated")
    monkeypatch.setitem(sys.modules, "unrelated", keeper)
    er._reset_probe_modules(["yaml"])
    assert "yaml" not in sys.modules
    assert "yaml.composer" not in sys.modules
    assert sys.modules["unrelated"] is keeper


# ---------------------------------------------------------------------------
# Report: what exactly is being diagnosed
# ---------------------------------------------------------------------------

def test_report_shows_interpreter_profile_and_lock_provenance(tmp_path, monkeypatch, capsys):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["PyYAML==6.0.2"]\n', encoding="utf-8"
    )
    (root / "uv.lock").write_text(
        '[[package]]\nname = "pyyaml"\nversion = "6.0.2"\n', encoding="utf-8"
    )
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path / "home"))

    monkeypatch.setattr(
        er,
        "_probe_details",
        lambda: [
            {"module": "yaml", "package": "PyYAML", "ok": False,
             "detail": "ImportError: wiped", "installed": "6.0.2"},
        ],
    )
    monkeypatch.setattr(er, "_probe_broken_packages", lambda: ["PyYAML"])

    report = er.collect_runtime_report(root)
    assert report["interpreter"]["executable"] == sys.executable
    assert report["profile"]["openamer_home"] == str(tmp_path / "home")
    assert report["lock"]["packages"] == 1
    assert len(report["project"]["pyproject"]["sha256"]) == 12
    assert report["healthy"] is False

    assert er.repair_runtime(root) == 1
    out = capsys.readouterr().out
    assert "OpenAmer runtime diagnosis" in out
    assert sys.executable in out
    assert "uv.lock sha256:" in out
    assert "repair into" in out
    assert "BROKEN yaml" in out
    assert "doctor --runtime --fix" in out


def test_report_flags_version_drift_against_uv_lock(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    (root / "uv.lock").write_text(
        '[[package]]\nname = "pyyaml"\nversion = "9.9.9"\n', encoding="utf-8"
    )
    monkeypatch.setattr(
        er,
        "_probe_details",
        lambda: [
            {"module": "yaml", "package": "PyYAML", "ok": True,
             "detail": "", "installed": "1.2.3"},
        ],
    )
    report = er.collect_runtime_report(root)
    assert report["healthy"] is True
    assert report["drifted"] == ["PyYAML"]
    assert "venv out of date with uv.lock" in er.format_runtime_report(report)


def test_report_without_lock_says_so(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    report = er.collect_runtime_report(root)
    assert report["lock"]["file"]["present"] is False
    assert "MISSING" in er.format_runtime_report(report)


def test_repair_runtime_refuses_without_a_source_checkout(tmp_path, capsys):
    assert er.repair_runtime(tmp_path) == 2
    assert "no source checkout" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Early CLI dispatch (`openamer doctor --runtime` before the app's imports)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "argv",
    [["doctor"], ["gateway"], ["doctor", "--fix"], ["config", "set", "doctor", "--runtime"]],
)
def test_early_command_ignores_unrelated_argv(argv, monkeypatch):
    called = []
    monkeypatch.setattr(er, "repair_runtime", lambda **kw: called.append(kw) or 0)
    assert er.maybe_run_early_command(argv) is None
    assert called == []


def test_early_command_dispatches_doctor_runtime(monkeypatch):
    called = []
    monkeypatch.setattr(er, "repair_runtime", lambda **kw: called.append(kw) or 7)
    assert er.maybe_run_early_command(["doctor", "--runtime"]) == 7
    assert er.maybe_run_early_command(["--verbose", "doctor", "--runtime", "--fix"]) == 7
    assert called == [{"should_fix": False}, {"should_fix": True}]


def test_early_command_module_cli_json(tmp_path, capsys):
    report = er.main(["--json"])
    assert report == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["interpreter"]["executable"] == sys.executable


def test_doctor_runtime_flag_delegates_to_the_same_implementation(monkeypatch):
    """The `doctor` handler keeps the flag working for in-process invocations
    (and keeps `openamer doctor --help` truthful) — it must never grow a second
    implementation of the diagnosis."""
    import types

    from openamer_cli import doctor as doctor_mod

    calls = []
    monkeypatch.setattr(er, "repair_runtime", lambda **kw: calls.append(kw) or 3)
    args = types.SimpleNamespace(fix=True, ack=None, runtime=True)
    with pytest.raises(SystemExit) as exc:
        doctor_mod.run_doctor(args)
    assert exc.value.code == 3
    assert calls == [{"should_fix": True}]


def _run_lifecycle_cli_payload(tmp_path: Path) -> subprocess.CompletedProcess:
    """Import openamer_cli.main with a raising ``dotenv`` shadow in that state
    the recovery markers exist for, once with and once without --runtime."""
    shadow = _make_broken_dotenv_shadow(tmp_path)
    openamer_home = tmp_path / "openamer_home"
    openamer_home.mkdir()
    script = tmp_path / "cli_reachability.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import sys

            sys.path.insert(1, {str(shadow)!r})
            sys.argv = ["openamer", "doctor", "--runtime"]

            try:
                import openamer_cli.main  # noqa: F401
            except SystemExit as exc:
                print(f"EARLY_EXIT {{exc.code}}")
            else:
                print("MAIN_IMPORTED")
            """
        ),
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT), "OPENAMER_HOME": str(openamer_home)},
        timeout=180,
    )


def test_doctor_runtime_reachable_while_app_import_is_broken(tmp_path):
    """The whole point: while `import openamer_cli.main` dies on a wiped core
    package (proved by the negative control above), `openamer doctor --runtime`
    still prints the diagnosis instead of crashing, and does not import the app."""
    result = _run_lifecycle_cli_payload(tmp_path)
    assert "EARLY_EXIT 1" in result.stdout, result.stderr
    assert "OpenAmer runtime diagnosis" in result.stdout
    assert "BROKEN dotenv" in result.stdout
    assert "wiped mid-install" in result.stdout
    assert "MAIN_IMPORTED" not in result.stdout
