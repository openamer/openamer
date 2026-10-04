"""Regression tests for local terminal initial cwd normalization."""

from pathlib import Path

from tools.environments.local import (
    LocalEnvironment,
    _msys_to_windows_path,
    _resolve_local_initial_cwd,
)


def _same_path(output: str, expected) -> bool:
    """Compare a shell-reported path against a native Path.

    The shell prints its own spelling — MSYS renders ``C:\\x`` as ``/c/x`` — so
    translate with the module's own converter before comparing. The invariant
    under test is *which* directory, not how the shell spells it.
    """
    return Path(_msys_to_windows_path(output.strip())).resolve() == Path(expected).resolve()


def test_relative_initial_cwd_resolves_from_parent(tmp_path, monkeypatch):
    project = tmp_path / "openamer-agent"
    project.mkdir()
    monkeypatch.chdir(tmp_path)

    assert _resolve_local_initial_cwd("openamer-agent") == str(project)


def test_relative_initial_cwd_matching_current_dir_uses_current_dir(tmp_path, monkeypatch):
    project = tmp_path / "openamer-agent"
    project.mkdir()
    monkeypatch.chdir(project)

    assert _resolve_local_initial_cwd("openamer-agent") == str(project)


def test_local_environment_does_not_cd_into_nested_matching_relative_cwd(tmp_path, monkeypatch):
    project = tmp_path / "openamer-agent"
    project.mkdir()
    monkeypatch.chdir(project)

    env = LocalEnvironment(cwd="openamer-agent", timeout=5)
    try:
        result = env.execute("pwd", timeout=5)
    finally:
        env.cleanup()

    assert result["returncode"] == 0
    assert _same_path(result["output"], project), result["output"]
    assert "cd: openamer-agent" not in result["output"]


def test_local_environment_keeps_existing_relative_child_cwd(tmp_path, monkeypatch):
    project = tmp_path / "openamer-agent"
    project.mkdir()
    monkeypatch.chdir(tmp_path)

    env = LocalEnvironment(cwd="openamer-agent", timeout=5)
    try:
        result = env.execute("pwd", timeout=5)
    finally:
        env.cleanup()

    assert result["returncode"] == 0
    assert _same_path(result["output"], project), result["output"]
