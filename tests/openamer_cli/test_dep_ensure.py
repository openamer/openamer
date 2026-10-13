from unittest.mock import patch


def test_ensure_dependency_skips_when_present():
    """ensure_dependency is a no-op when the dep is already available."""
    from openamer_cli.dep_ensure import ensure_dependency
    with patch("openamer_cli.dep_ensure.shutil") as mock_shutil:
        mock_shutil.which.return_value = "/usr/bin/node"
        result = ensure_dependency("node", interactive=False)
        assert result is True


def test_ensure_dependency_returns_false_when_missing_noninteractive():
    """ensure_dependency returns False for missing dep in non-interactive mode."""
    from openamer_cli.dep_ensure import ensure_dependency
    with patch("openamer_cli.dep_ensure.shutil") as mock_shutil:
        mock_shutil.which.return_value = None
        with patch("openamer_cli.dep_ensure._find_install_script", return_value=(None, None)):
            result = ensure_dependency("node", interactive=False)
            assert result is False


def test_find_install_script_from_checkout(tmp_path):
    """_find_install_script finds scripts/install.sh in a git checkout."""
    from openamer_cli.dep_ensure import _find_install_script
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "install.sh").write_text("#!/bin/bash", encoding="utf-8")
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", False):
        path, shell = _find_install_script(package_dir=tmp_path / "openamer_cli", repo_root=tmp_path)
    assert path is not None
    assert path.name == "install.sh"
    assert shell == "bash"


def test_find_install_script_from_wheel(tmp_path):
    """_find_install_script finds bundled install.sh in a wheel."""
    from openamer_cli.dep_ensure import _find_install_script
    bundled = tmp_path / "openamer_cli" / "scripts"
    bundled.mkdir(parents=True)
    (bundled / "install.sh").write_text("#!/bin/bash", encoding="utf-8")
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", False):
        path, shell = _find_install_script(package_dir=tmp_path / "openamer_cli", repo_root=tmp_path)
    assert path is not None
    assert path.name == "install.sh"
    assert shell == "bash"


def test_find_install_script_prefers_ps1_on_windows(tmp_path):
    """On Windows, _find_install_script should find install.ps1."""
    scripts_dir = tmp_path / "openamer_cli" / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "install.ps1").write_text("# fake")
    (scripts_dir / "install.sh").write_text("# fake")
    from openamer_cli.dep_ensure import _find_install_script
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", True):
        path, shell = _find_install_script(package_dir=tmp_path / "openamer_cli")
        assert path == scripts_dir / "install.ps1"
        assert shell == "powershell"


def test_find_install_script_returns_sh_on_posix(tmp_path):
    """On POSIX, _find_install_script should find install.sh."""
    scripts_dir = tmp_path / "openamer_cli" / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "install.ps1").write_text("# fake")
    (scripts_dir / "install.sh").write_text("# fake")
    from openamer_cli.dep_ensure import _find_install_script
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", False):
        path, shell = _find_install_script(package_dir=tmp_path / "openamer_cli")
        assert path == scripts_dir / "install.sh"
        assert shell == "bash"


def test_find_install_script_falls_back_to_repo_root(tmp_path):
    """When no bundled script, check repo root."""
    repo_root = tmp_path / "repo"
    (repo_root / "scripts").mkdir(parents=True)
    (repo_root / "scripts" / "install.sh").write_text("# fake")
    from openamer_cli.dep_ensure import _find_install_script
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", False):
        path, shell = _find_install_script(package_dir=tmp_path / "openamer_cli", repo_root=repo_root)
        assert path == repo_root / "scripts" / "install.sh"
        assert shell == "bash"


def test_find_install_script_returns_none_when_missing(tmp_path):
    from openamer_cli.dep_ensure import _find_install_script
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", False):
        result = _find_install_script(package_dir=tmp_path / "x", repo_root=tmp_path / "y")
        assert result == (None, None)


def test_has_system_browser_checks_windows_names():
    from openamer_cli.dep_ensure import _has_system_browser
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", True), \
         patch("openamer_cli.dep_ensure.shutil") as mock_shutil:
        mock_shutil.which.side_effect = lambda name: "/fake/msedge.exe" if name == "msedge" else None
        assert _has_system_browser() is True


def test_has_system_browser_checks_posix_names():
    from openamer_cli.dep_ensure import _has_system_browser
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", False), \
         patch("openamer_cli.dep_ensure.shutil") as mock_shutil:
        mock_shutil.which.return_value = None
        assert _has_system_browser() is False


def test_has_openamer_agent_browser_windows_path(tmp_path):
    node_dir = tmp_path / "node"
    node_dir.mkdir(parents=True)
    (node_dir / "agent-browser.cmd").write_text("@echo off")
    from openamer_cli.dep_ensure import _has_openamer_agent_browser
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", True), \
         patch("openamer_constants.get_openamer_home", return_value=tmp_path):
        assert _has_openamer_agent_browser() is True


def test_has_openamer_agent_browser_posix_path(tmp_path):
    bin_dir = tmp_path / "node" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "agent-browser").write_text("#!/bin/sh")
    from openamer_cli.dep_ensure import _has_openamer_agent_browser
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", False), \
         patch("openamer_constants.get_openamer_home", return_value=tmp_path):
        assert _has_openamer_agent_browser() is True


def test_has_openamer_agent_browser_legacy_node_modules_path(tmp_path):
    """Legacy git-clone installs put agent-browser in $OPENAMER_HOME/node_modules/.bin/."""
    bin_dir = tmp_path / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "agent-browser").write_text("#!/bin/sh")
    from openamer_cli.dep_ensure import _has_openamer_agent_browser
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", False), \
         patch("openamer_constants.get_openamer_home", return_value=tmp_path):
        assert _has_openamer_agent_browser() is True


def _drive_windows_ensure(monkeypatch, tmp_path, script_name="install.ps1"):
    """Run ensure_dependency on the Windows path and return the argv it built."""
    from openamer_cli.dep_ensure import ensure_dependency
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / script_name).write_text("# fake")
    with patch("openamer_cli.dep_ensure._IS_WINDOWS", True), \
         patch("openamer_cli.dep_ensure._DEP_CHECKS", {"node": lambda: False}), \
         patch("openamer_cli.dep_ensure._find_install_script", return_value=(scripts_dir / script_name, "powershell")), \
         patch("openamer_cli.dep_ensure.shutil") as mock_shutil, \
         patch("subprocess.run") as mock_run, \
         patch("sys.stdin") as mock_stdin:
        mock_shutil.which.side_effect = lambda name: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" if name == "powershell" else None
        mock_stdin.isatty.return_value = False
        mock_run.return_value = type("R", (), {"returncode": 0})()
        ensure_dependency("node", interactive=False)
        return mock_run.call_args[0][0]


def test_ensure_dependency_uses_powershell_on_windows(tmp_path, monkeypatch):
    cmd = _drive_windows_ensure(monkeypatch, tmp_path)

    assert "powershell" in cmd[0].lower()
    assert "-Ensure" in cmd
    assert cmd[cmd.index("-Ensure") + 1] == "node"


def test_ensure_dependency_pins_the_breadcrumb_home_not_the_platform_default(tmp_path, monkeypatch):
    """#45300: the dep path used to hand install.ps1 ``get_openamer_home()``.

    With OPENAMER_HOME unset that is the *platform default* -- a guess -- and
    install.ps1 persisted whatever it was handed to the user environment, which
    is how the desktop app ended up booting against an empty
    ``%LOCALAPPDATA%\\openamer``. The install-scoped resolver must win here.
    """
    import openamer_constants

    home = tmp_path / "openamer-laptop"
    checkout = home / "openamer-agent"
    (checkout / ".git").mkdir(parents=True)
    (checkout / ".openamer-home").write_text(str(home), encoding="utf-8")

    monkeypatch.delenv("OPENAMER_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.setattr(openamer_constants, "_running_checkout_root", lambda: checkout)

    cmd = _drive_windows_ensure(monkeypatch, tmp_path)

    assert "-OpenAmerHome" in cmd
    assert cmd[cmd.index("-OpenAmerHome") + 1] == str(home)
    # The guess that caused the bug must not appear anywhere in the argv.
    assert str(tmp_path / "LocalAppData" / "openamer") not in cmd


def test_ensure_dependency_omits_the_home_flag_when_the_install_cannot_prove_one(tmp_path, monkeypatch):
    """No evidence => no ``-OpenAmerHome``, so install.ps1 runs its own ladder.

    Passing the platform default here is precisely the transfer of a guess that
    ends up persisted. Omission leaves install.ps1's proof-gated resolution in
    charge instead.
    """
    import openamer_constants

    checkout = tmp_path / "work" / "openamer-repo"
    checkout.mkdir(parents=True)

    monkeypatch.delenv("OPENAMER_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.setattr(openamer_constants, "_running_checkout_root", lambda: checkout)

    cmd = _drive_windows_ensure(monkeypatch, tmp_path)

    assert "-OpenAmerHome" not in cmd
    assert str(tmp_path / "LocalAppData" / "openamer") not in cmd


def test_ensure_dependency_never_passes_the_platform_default_when_openamer_home_is_unset(tmp_path, monkeypatch):
    """The blunt invariant, independent of which rung answers: no guesses.

    Nothing here is patched beyond the environment, so this fails on the OLD
    code for the reason that matters -- the argv *carried* the platform default
    (``-OpenAmerHome <LOCALAPPDATA>\\openamer``) -- rather than on a missing
    symbol. That value is what install.ps1 then persisted machine-wide.
    """
    import openamer_constants

    monkeypatch.delenv("OPENAMER_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))

    platform_default = str(openamer_constants._get_platform_default_openamer_home())
    cmd = _drive_windows_ensure(monkeypatch, tmp_path)

    assert platform_default not in cmd, (
        "the dep path must never hand install.ps1 the platform default as if it "
        "were this install's home (#45300)"
    )
    assert not any(platform_default in str(part) for part in cmd)
    if "-OpenAmerHome" in cmd:
        # A pinned home is allowed only if this install could prove it.
        assert cmd[cmd.index("-OpenAmerHome") + 1] != platform_default


