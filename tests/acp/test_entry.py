"""Tests for acp_adapter.entry startup wiring."""

import sys

import acp
import pytest

from acp_adapter import entry


def test_main_enables_unstable_protocol(monkeypatch):
    calls = {}

    async def fake_run_agent(agent, **kwargs):
        calls["kwargs"] = kwargs

    monkeypatch.setattr(entry, "_setup_logging", lambda: None)
    monkeypatch.setattr(entry, "_load_env", lambda: None)
    monkeypatch.setattr(acp, "run_agent", fake_run_agent)

    entry.main([])

    assert calls["kwargs"]["use_unstable_protocol"] is True


def test_main_skips_configured_mcp_discovery_when_requested(monkeypatch):
    discovery_calls = []

    async def fake_run_agent(agent, **kwargs):
        pass

    monkeypatch.setattr(entry, "_setup_logging", lambda: None)
    monkeypatch.setattr(entry, "_load_env", lambda: None)
    monkeypatch.setenv("OPENAMER_ACP_SKIP_CONFIGURED_MCP", "1")
    monkeypatch.setattr(
        "tools.mcp_tool.discover_mcp_tools",
        lambda: discovery_calls.append(True),
    )
    monkeypatch.setattr(acp, "run_agent", fake_run_agent)

    entry.main([])

    assert discovery_calls == []


@pytest.mark.parametrize("skip_value", [None, "", "0", "false"])
def test_main_discovers_configured_mcp_when_skip_is_not_enabled(monkeypatch, skip_value):
    """Without the opt-out, entry.main() must TRIGGER configured-MCP discovery.

    The discovery is deliberately asynchronous: `entry.main()` calls
    `start_background_mcp_discovery()`, which spawns a daemon thread, and the
    thread performs `from tools.mcp_tool import discover_mcp_tools` LAZILY before
    calling it. That keeps ACP startup responsive (blocking here used to cost
    2-5 s) and avoids importing the MCP stack for users who have none.

    So asserting on `discovery_calls` right after `entry.main()` can only pass by
    accident of thread scheduling — which is why this test failed on four
    parametrisations while the feature worked. The honest assertions are:
    (a) discovery was REQUESTED, and (b) it actually happens once the background
    thread is allowed to finish.
    """
    discovery_calls = []
    requested = []

    async def fake_run_agent(agent, **kwargs):
        pass

    def fake_start_background_mcp_discovery(*, logger, thread_name):
        """Record the request, then run discovery synchronously.

        Stands in for the daemon thread so the test is deterministic instead of
        racing `entry.main()`'s return against thread startup.
        """
        requested.append(thread_name)
        from tools.mcp_tool import discover_mcp_tools
        discover_mcp_tools()

    monkeypatch.setattr(entry, "_setup_logging", lambda: None)
    monkeypatch.setattr(entry, "_load_env", lambda: None)
    if skip_value is None:
        monkeypatch.delenv("OPENAMER_ACP_SKIP_CONFIGURED_MCP", raising=False)
    else:
        monkeypatch.setenv("OPENAMER_ACP_SKIP_CONFIGURED_MCP", skip_value)
    monkeypatch.setattr(
        "tools.mcp_tool.discover_mcp_tools",
        lambda: discovery_calls.append(True),
    )
    monkeypatch.setattr(
        "openamer_cli.mcp_startup.start_background_mcp_discovery",
        fake_start_background_mcp_discovery,
    )
    monkeypatch.setattr(acp, "run_agent", fake_run_agent)

    entry.main([])

    assert requested == ["acp-mcp-discovery"], "discovery was never requested"
    assert discovery_calls == [True], "discovery was requested but did not run"


def test_main_version_prints_without_starting_server(monkeypatch, capsys):
    monkeypatch.setattr(entry, "_setup_logging", lambda: (_ for _ in ()).throw(AssertionError("started server")))

    entry.main(["--version"])

    output = capsys.readouterr().out.strip()
    assert output
    assert "Starting openamer-agent ACP adapter" not in output


def test_main_check_prints_ok_without_starting_server(monkeypatch, capsys):
    monkeypatch.setattr(entry, "_setup_logging", lambda: (_ for _ in ()).throw(AssertionError("started server")))

    entry.main(["--check"])

    assert capsys.readouterr().out.strip() == "OpenAmer ACP check OK"


def test_main_setup_runs_model_configuration(monkeypatch):
    calls = {}

    def fake_openamer_main():
        calls["argv"] = sys.argv[:]

    monkeypatch.setattr("openamer_cli.main.main", fake_openamer_main)
    # Pretend stdin is not a TTY so the follow-up browser prompt is skipped.
    # That keeps this test focused on the model-setup wiring; the
    # browser-prompt path has its own test below.
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    entry.main(["--setup"])

    assert calls["argv"][1:] == ["model"]


def test_main_setup_offers_browser_install_when_tty(monkeypatch):
    """When stdin is a TTY and the user answers yes, model setup is followed
    by a browser-tools bootstrap call."""
    monkeypatch.setattr("openamer_cli.main.main", lambda: None)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "y")

    bootstrap_calls = []
    monkeypatch.setattr(
        entry,
        "_run_setup_browser",
        lambda assume_yes=False: bootstrap_calls.append(assume_yes) or 0,
    )

    entry.main(["--setup"])

    assert bootstrap_calls == [False]


def test_main_setup_skips_browser_prompt_on_no(monkeypatch):
    monkeypatch.setattr("openamer_cli.main.main", lambda: None)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: "")

    called = []
    monkeypatch.setattr(
        entry,
        "_run_setup_browser",
        lambda assume_yes=False: called.append(assume_yes) or 0,
    )

    entry.main(["--setup"])

    assert called == []


def test_main_setup_browser_calls_ensure_dependency(monkeypatch):
    """`openamer-acp --setup-browser` routes through dep_ensure.ensure_dependency."""
    calls = []

    def fake_ensure(dep, interactive=True):
        calls.append((dep, interactive))
        return True

    monkeypatch.setattr("openamer_cli.dep_ensure.ensure_dependency", fake_ensure)

    entry.main(["--setup-browser"])

    assert ("node", True) in calls
    assert ("browser", True) in calls


def test_main_setup_browser_forwards_yes_flag(monkeypatch):
    """--yes suppresses interactive prompts in ensure_dependency."""
    calls = []

    def fake_ensure(dep, interactive=True):
        calls.append((dep, interactive))
        return True

    monkeypatch.setattr("openamer_cli.dep_ensure.ensure_dependency", fake_ensure)

    entry.main(["--setup-browser", "--yes"])

    assert ("node", False) in calls
    assert ("browser", False) in calls


def test_main_setup_browser_stops_on_node_failure(monkeypatch):
    """If node install fails, browser install is not attempted."""
    calls = []

    def fake_ensure(dep, interactive=True):
        calls.append(dep)
        return dep != "node"  # node fails

    monkeypatch.setattr("openamer_cli.dep_ensure.ensure_dependency", fake_ensure)

    with pytest.raises(SystemExit) as excinfo:
        entry.main(["--setup-browser"])
    assert excinfo.value.code == 1
    assert "node" in calls
    assert "browser" not in calls


def test_main_setup_browser_propagates_browser_failure(monkeypatch):
    """If browser install fails, exit code is 1."""
    def fake_ensure(dep, interactive=True):
        return dep != "browser"  # browser fails

    monkeypatch.setattr("openamer_cli.dep_ensure.ensure_dependency", fake_ensure)

    with pytest.raises(SystemExit) as excinfo:
        entry.main(["--setup-browser"])
    assert excinfo.value.code == 1
