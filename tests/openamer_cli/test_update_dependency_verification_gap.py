"""Regression tests for the dependency-verification gap in `openamer update`.

Two independent defects let a BROKEN venv pass the update as healthy:

1. **The probe's exit code is ignored.** ``_verify_core_dependencies_installed``
   runs a small ``importlib.metadata`` script inside the target venv and
   reads the missing names from stdout. When that interpreter dies (broken
   venv, missing DLL, wrong base interpreter) the script writes nothing to
   stdout and exits non-zero — so "nothing printed" was read as "nothing
   missing" and the update reported success on a venv that cannot import.

2. **The happy path never verifies at all.**
   ``_install_python_dependencies_with_optional_fallback`` installs
   ``.[all]``; on success it returns immediately after the console-script
   check. ``_verify_core_dependencies_installed`` is only reached via the
   extras-fallback path (after a ``CalledProcessError``). So the normal
   update — the one that actually succeeds — skips the core-dependency
   verification entirely, and a partial install only surfaces hours later
   as a ModuleNotFoundError in a downstream subprocess.

Both tests pin the observable contract: a broken probe must be treated as
"unknown, not healthy", and the successful install path must run the
verification.
"""

from __future__ import annotations

import subprocess
import textwrap
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_pyproject(tmp_path, monkeypatch):
    """Point openamer_cli.main.PROJECT_ROOT at a tmp dir with a minimal pyproject."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent("""\
        [project]
        name = "fake"
        version = "0.0.0"
        dependencies = ["pathspec==1.1.1"]
    """)
    )
    import openamer_cli.main as main_mod

    monkeypatch.setattr(main_mod, "PROJECT_ROOT", tmp_path)
    return tmp_path


@pytest.fixture
def fake_venv_python(tmp_path):
    """Create a fake venv python shim path that exists on disk."""
    venv_root = tmp_path / "venv"
    scripts = venv_root / "Scripts"
    scripts.mkdir(parents=True)
    py = scripts / "python.exe"
    py.write_text("#!/bin/sh\necho fake python")
    return py, venv_root


class TestProbeExitCodeIsHonoured:
    """Defect 1: a crashing probe must not read as "all dependencies present"."""

    def test_nonzero_exit_with_empty_stdout_is_not_healthy(
        self, temp_pyproject, fake_venv_python, capsys
    ):
        """A probe that exits non-zero with no output means UNKNOWN, not healthy.

        The broken venv prints nothing to stdout and dies with a fatal
        Python error on stderr. Before the fix the helper parsed stdout,
        found no missing names, and returned silently — the update then
        reported success on an unusable venv.
        """
        py, venv_root = fake_venv_python
        env = {"VIRTUAL_ENV": str(venv_root)}

        def broken_probe(cmd, **kwargs):
            return MagicMock(
                returncode=1,
                stdout="",
                stderr="Fatal Python error: initfs encoding failed",
            )

        with patch("openamer_cli.main._resolve_install_target_python", return_value=py), \
             patch("openamer_cli.main.subprocess.run", side_effect=broken_probe), \
             patch("openamer_cli.main._run_install_with_heartbeat") as mock_install:
            from openamer_cli.main import _verify_core_dependencies_installed

            _verify_core_dependencies_installed(["uv", "pip"], env=env)

        out = capsys.readouterr().out
        assert "could not be verified" in out or "Verification" in out, (
            "a crashing dependency probe must be reported, not silently treated "
            f"as healthy; output was: {out!r}"
        )
        # The repair path must at least be ATTEMPTED for an unknown state.
        assert mock_install.called, (
            "an unverifiable probe must trigger a repair attempt, not a clean bill of health"
        )

    def test_zero_exit_with_empty_stdout_is_healthy(
        self, temp_pyproject, fake_venv_python, capsys
    ):
        """A probe that exits 0 with no missing names IS healthy — no repair."""
        py, venv_root = fake_venv_python
        env = {"VIRTUAL_ENV": str(venv_root)}

        with patch("openamer_cli.main._resolve_install_target_python", return_value=py), \
             patch("openamer_cli.main.subprocess.run") as mock_run, \
             patch("openamer_cli.main._run_install_with_heartbeat") as mock_install:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            from openamer_cli.main import _verify_core_dependencies_installed

            _verify_core_dependencies_installed(["uv", "pip"], env=env)

        assert not mock_install.called, "a clean probe must not trigger a repair install"


class TestSuccessfulInstallVerifiesCoreDependencies:
    """Defect 2: the successful install path skipped the core verification."""

    def test_core_verification_runs_on_the_success_path(
        self, temp_pyproject, fake_venv_python
    ):
        """Installing ``.[all]`` successfully must STILL verify core deps.

        Before the fix the function returned right after the console-script
        check, so the only path that verified core dependencies was the
        extras-fallback path — i.e. the failing one. The normal update
        never verified anything.
        """
        with patch("openamer_cli.main._run_quarantined_install") as mock_install, \
             patch("openamer_cli.main._verify_console_scripts_installed"), \
             patch("openamer_cli.main._verify_core_dependencies_installed") as mock_verify:
            from openamer_cli.main import _install_python_dependencies_with_optional_fallback

            _install_python_dependencies_with_optional_fallback(["uv", "pip"], env={})

        assert mock_install.called, "the install itself should have run"
        assert mock_verify.called, (
            "the successful install path must verify core dependencies too — "
            "otherwise a partial install passes the update as healthy"
        )

    def test_core_verification_runs_after_the_extras_fallback(self):
        """The fallback path must keep verifying (it already did)."""
        with patch("openamer_cli.main._run_quarantined_install") as mock_install, \
             patch("openamer_cli.main._verify_console_scripts_installed"), \
             patch("openamer_cli.main._verify_core_dependencies_installed") as mock_verify, \
             patch("openamer_cli.main._load_installable_optional_extras", return_value=[]):
            mock_install.side_effect = [
                subprocess.CalledProcessError(1, "uv"),  # the .[all] install fails
                None,  # base install succeeds
            ]
            from openamer_cli.main import _install_python_dependencies_with_optional_fallback

            _install_python_dependencies_with_optional_fallback(["uv", "pip"], env={})

        assert mock_verify.called, "the fallback path must verify core dependencies"
