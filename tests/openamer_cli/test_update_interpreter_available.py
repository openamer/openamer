"""Dependency installers must retain their target interpreter during quarantine."""

import os
import subprocess
import sys
import venv

import pytest

from openamer_cli import main as cli_main

pytestmark = pytest.mark.real_concurrent_gate


@pytest.mark.parametrize("fails", [False, True])
def test_install_keeps_interpreters_at_canonical_paths(monkeypatch, tmp_path, fails):
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    for name in ("python.exe", "pythonw.exe", "openamer.exe"):
        (scripts / name).write_bytes(name.encode())
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main, "_load_console_script_names", lambda: ["openamer"])
    observed = []

    def install(cmd, *, env=None):
        observed.append(cmd)
        assert (scripts / "python.exe").read_bytes() == b"python.exe"
        assert (scripts / "pythonw.exe").read_bytes() == b"pythonw.exe"
        assert not (scripts / "openamer.exe").exists()
        if fails:
            raise subprocess.CalledProcessError(2, cmd)
        (scripts / "openamer.exe").write_bytes(b"new launcher")

    monkeypatch.setattr(cli_main, "_run_install_with_heartbeat", install)
    if fails:
        with pytest.raises(subprocess.CalledProcessError):
            cli_main._run_quarantined_install(["installer"], scripts_dir=scripts)
        assert (scripts / "openamer.exe").read_bytes() == b"openamer.exe"
    else:
        cli_main._run_quarantined_install(["installer"], scripts_dir=scripts)
        assert (scripts / "openamer.exe").read_bytes() == b"new launcher"
    assert observed == [["installer"]]
    assert not list(scripts.glob("python*.old.*"))


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows venv launcher")
def test_real_venv_interpreter_runs_inside_quarantined_install(monkeypatch, tmp_path):
    target = tmp_path / "venv"
    venv.EnvBuilder(with_pip=False).create(target)
    scripts = target / "Scripts"
    python = scripts / "python.exe"
    monkeypatch.setattr(cli_main, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_main, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli_main, "_project_venv_dir", lambda: target)
    env = dict(os.environ, VIRTUAL_ENV=str(target))
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    receipt = tmp_path / "interpreter-ran.txt"
    code = "from pathlib import Path; Path(%r).write_text('interpreter executed')" % str(receipt)
    cli_main._run_quarantined_install(
        [str(python), "-c", code], env=env, scripts_dir=scripts
    )
    assert receipt.read_text() == "interpreter executed"
    assert python.is_file()
