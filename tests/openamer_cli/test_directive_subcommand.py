"""``openamer directive`` must stay wired to the constitution audit.

The audit existed as a module with no command, so the constitution had a
status page nobody could open. These tests are the guard that the door
stays attached.
"""

from __future__ import annotations

import json
import re
import sys

import pytest


def _parser_names() -> set[str]:
    """The subcommand names the real top-level parser knows.

    Mirrors the derivation in ``test_startup_plugin_gating``: run
    ``openamer --help`` in-process with plugin discovery disabled, so only
    built-in commands appear.
    """
    import io
    from contextlib import redirect_stdout
    from unittest.mock import patch

    from openamer_cli import main as _main

    argv_backup = sys.argv[:]
    sys.argv = ["openamer", "--help"]
    buf = io.StringIO()
    try:
        with patch.object(_main, "_plugin_cli_discovery_needed", return_value=False):
            with redirect_stdout(buf):
                with pytest.raises(SystemExit):
                    _main.main()
    finally:
        sys.argv = argv_backup
    text = buf.getvalue()
    return {
        m.group(1)
        for m in re.finditer(r"^\s{2,}([a-z][a-z0-9-]*)\s{2,}\S", text, re.MULTILINE)
    }


def test_directive_subcommand_is_registered() -> None:
    assert "directive" in _parser_names()


def test_directive_is_declared_for_the_plugin_gating_fast_path() -> None:
    """An undeclared subcommand forces a needless plugin-discovery pass."""
    from openamer_cli.main import _BUILTIN_SUBCOMMANDS

    assert "directive" in _BUILTIN_SUBCOMMANDS


def test_directive_command_reports_the_constitution(capsys) -> None:
    from openamer_cli.subcommands.directive import directive_command

    class Args:
        json = False
        gaps = False

    assert directive_command(Args()) == 0
    out = capsys.readouterr().out
    assert "Genesis directives: 24" in out
    assert "DIR-01" in out
    assert "No violations" in out


def test_directive_json_is_the_engine_payload(capsys) -> None:
    from agent.directive_engine import audit
    from openamer_cli.subcommands.directive import directive_command

    class Args:
        json = True
        gaps = False

    assert directive_command(Args()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["directives"] == 24
    assert len(payload["rows"]) == 24
    assert payload["violations"] == audit()["violations"]


def test_directive_exits_nonzero_on_a_violation(monkeypatch, capsys) -> None:
    """A failing check has to reach the exit code, or it cannot gate CI."""
    import agent.directive_engine as engine

    real = engine.IMPLEMENTATIONS["DIR-20"]
    broken = engine.Implementation("DIR-20", real.status, real.evidence, real.note, check=lambda: False)
    monkeypatch.setitem(engine.IMPLEMENTATIONS, "DIR-20", broken)

    from openamer_cli.subcommands.directive import directive_command

    class Args:
        json = False
        gaps = False

    assert directive_command(Args()) == 1
    assert "DIR-20: its check fails" in capsys.readouterr().out
