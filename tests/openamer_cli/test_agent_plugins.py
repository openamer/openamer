"""Tests for portable agent-plugin packages (Agent Plugins v1).

Every test builds a real package on disk in ``tmp_path``. Nothing here imports
package Python or starts an MCP server — in fact the tests assert that this
never happens.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from openamer_cli import agent_plugins as ap

PLUGIN_MANIFEST = {
    "$schema": ap.PLUGIN_SCHEMA_V1,
    "name": "demo-plugin",
    "version": "1.0.0",
    "description": "Demo portable package",
    "author": {"name": "Test Author"},
    "license": "MIT",
}

MCP_MANIFEST = {
    "$schema": ap.MCP_SCHEMA_V1,
    "mcpServers": {
        "echo": {"type": "stdio", "command": "python", "args": ["-m", "echo_server"]},
    },
}


def _write(path, content) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, (dict, list)):
        content = json.dumps(content, indent=2)
    path.write_text(content, encoding="utf-8")


def _skill(root, name="demo-skill", description="A demo skill."):
    _write(
        root / "skills" / name / "SKILL.md",
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
    )


def _package(root, *, name="demo-plugin", manifest=None, mcp=None, skill=True):
    root.mkdir(parents=True, exist_ok=True)
    data = dict(PLUGIN_MANIFEST)
    data.update(manifest or {})
    data["name"] = name
    _write(root / "plugin.json", data)
    if mcp is not None:
        _write(root / "mcp.json", mcp)
    if skill:
        _skill(root, name="demo-skill")
    return root


def _home(tmp_path):
    return tmp_path / "home"


# --- loading ---------------------------------------------------------------


def test_load_reads_manifest_skills_and_mcp(tmp_path):
    root = _package(tmp_path / "src", mcp=MCP_MANIFEST)
    package = ap.load_agent_plugin(root)

    assert package.name == "demo-plugin"
    assert package.version == "1.0.0"
    assert [s.name for s in package.skills] == ["demo-skill"]
    assert package.skills[0].description == "A demo skill."
    assert package.mcp_servers["echo"]["command"] == "python"
    assert package.mcp_servers["echo"]["args"] == ["-m", "echo_server"]
    assert package.diagnostics == ()


def test_load_never_imports_package_python(tmp_path, monkeypatch):
    root = _package(tmp_path / "src")
    sentinel = tmp_path / "imported.flag"
    _write(
        root / "__init__.py",
        f"import pathlib\npathlib.Path({str(sentinel)!r}).write_text('imported')\n",
    )
    _write(root / "register.py", "raise SystemExit('package code ran')\n")

    def _no_spawn(*args, **kwargs):  # pragma: no cover - only runs on failure
        raise AssertionError("a portable package must never spawn a process")

    monkeypatch.setattr(subprocess, "Popen", _no_spawn)
    package = ap.load_agent_plugin(root)

    assert package.name == "demo-plugin"
    assert not sentinel.exists(), (
        "package Python must not be imported during inspection"
    )
    assert "demo-plugin" not in sys.modules


def test_load_rejects_wrong_schema(tmp_path):
    root = _package(
        tmp_path / "src", manifest={"$schema": "https://example.com/other.json"}
    )
    with pytest.raises(ap.AgentPluginError):
        ap.load_agent_plugin(root)


def test_load_rejects_path_traversal_in_name(tmp_path):
    root = _package(tmp_path / "src", name="../../evil")
    with pytest.raises(ap.AgentPluginError):
        ap.load_agent_plugin(root)


def test_mcp_cwd_traversal_is_rejected(tmp_path):
    mcp = {
        "$schema": ap.MCP_SCHEMA_V1,
        "mcpServers": {
            "escape": {"type": "stdio", "command": "python", "cwd": "../../outside"},
            "fine": {"type": "stdio", "command": "python"},
        },
    }
    package = ap.load_agent_plugin(_package(tmp_path / "src", mcp=mcp))

    assert "escape" not in package.mcp_servers
    assert "fine" in package.mcp_servers
    assert any(
        d.scope == "mcp:escape" and "escapes" in d.message for d in package.diagnostics
    )


def test_stdio_command_with_path_separator_is_rejected(tmp_path):
    mcp = {
        "$schema": ap.MCP_SCHEMA_V1,
        "mcpServers": {"bad": {"type": "stdio", "command": "../evil/binary"}},
    }
    package = ap.load_agent_plugin(_package(tmp_path / "src", mcp=mcp))
    assert "bad" not in package.mcp_servers


def test_remote_http_non_loopback_is_rejected(tmp_path):
    mcp = {
        "$schema": ap.MCP_SCHEMA_V1,
        "mcpServers": {
            "insecure": {"type": "streamable-http", "url": "http://example.com/mcp"},
            "loopback": {"type": "streamable-http", "url": "http://127.0.0.1:9000/mcp"},
            "tls": {"type": "streamable-http", "url": "https://example.com/mcp"},
        },
    }
    package = ap.load_agent_plugin(_package(tmp_path / "src", mcp=mcp))
    assert "insecure" not in package.mcp_servers
    assert "loopback" in package.mcp_servers
    assert "tls" in package.mcp_servers


def test_symlinked_skill_is_not_followed(tmp_path):
    outside = tmp_path / "outside-skill"
    _skill(outside.parent, name=outside.name)
    root = _package(tmp_path / "src")
    link = root / "skills" / "linked-skill"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted on this platform")

    package = ap.load_agent_plugin(root)
    assert "linked-skill" not in [s.name for s in package.skills]
    assert any(d.scope == "skill:linked-skill" for d in package.diagnostics)


def test_symlinked_mcp_manifest_is_rejected(tmp_path):
    root = _package(tmp_path / "src")
    outside = tmp_path / "outside-mcp.json"
    _write(outside, MCP_MANIFEST)
    try:
        (root / "mcp.json").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted on this platform")

    package = ap.load_agent_plugin(root)
    assert package.mcp_servers == {}
    assert any(d.scope == "mcp" for d in package.diagnostics)


# --- install ---------------------------------------------------------------


def test_install_is_inert_and_enable_is_explicit(tmp_path):
    root = _package(tmp_path / "src", mcp=MCP_MANIFEST)
    home = _home(tmp_path)

    record = ap.install_package(root, home=home)
    assert record["name"] == "demo-plugin"
    assert record["enabled"] is False
    assert (home / "plugin-packages" / "demo-plugin" / "plugin.json").is_file()

    # Installing declares servers but never activates them.
    assert ap.portable_mcp_servers(home) == {}

    assert ap.set_enabled("demo-plugin", True, home=home) is True
    servers = ap.portable_mcp_servers(home)
    assert list(servers) == ["demo-plugin__echo"]
    assert servers["demo-plugin__echo"]["command"] == "python"

    assert ap.set_enabled("demo-plugin", False, home=home) is True
    assert ap.portable_mcp_servers(home) == {}


def test_install_never_copies_secret_files(tmp_path):
    root = _package(tmp_path / "src", mcp=MCP_MANIFEST)
    _write(root / ".env", "API_KEY=not-a-real-key\n")
    _write(root / "certs" / "server.pem", "placeholder\n")
    home = _home(tmp_path)

    ap.install_package(root, home=home)
    stored = home / "plugin-packages" / "demo-plugin"
    assert not (stored / ".env").exists()
    assert not (stored / "certs" / "server.pem").exists()
    # The rest of the package is still installed.
    assert (stored / "plugin.json").is_file()


@pytest.mark.parametrize(
    "content",
    [
        "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----\n",
        "token = 'ghp_" + "a" * 30 + "'\n",
        "api_key = 'sk-" + "b" * 30 + "'\n",
    ],
)
def test_install_refuses_packages_shipping_credentials(tmp_path, content):
    root = _package(tmp_path / "src")
    _write(root / "notes.txt", content)
    home = _home(tmp_path)

    with pytest.raises(ap.AgentPluginError, match="refusing to install"):
        ap.install_package(root, home=home)
    assert not (home / "plugin-packages" / "demo-plugin").exists()


def test_reinstall_requires_force(tmp_path):
    root = _package(tmp_path / "src")
    home = _home(tmp_path)
    ap.install_package(root, home=home)
    with pytest.raises(ap.AgentPluginError, match="already installed"):
        ap.install_package(root, home=home)
    record = ap.install_package(root, home=home, force=True)
    assert record["name"] == "demo-plugin"


def test_list_remove_and_unknown_names(tmp_path):
    root = _package(tmp_path / "src")
    home = _home(tmp_path)
    ap.install_package(root, home=home)

    assert [p["name"] for p in ap.list_packages(home)] == ["demo-plugin"]
    assert ap.get_package("demo-plugin", home=home)["version"] == "1.0.0"
    assert ap.get_package("../escape", home=home) is None
    assert ap.set_enabled("missing", True, home=home) is False
    assert ap.remove_package("demo-plugin", home=home) is True
    assert ap.list_packages(home) == []


def test_packages_root_is_profile_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path / "profile"))
    assert ap.packages_root() == tmp_path / "profile" / "plugin-packages"


def test_install_ignores_traversal_attempts_in_file_tree(tmp_path):
    """A package cannot smuggle files outside its own store via nested paths."""
    root = _package(tmp_path / "src")
    home = _home(tmp_path)
    ap.install_package(root, home=home)
    for path in (home / "plugin-packages").rglob("*"):
        assert path.resolve().is_relative_to((home / "plugin-packages").resolve())
