"""Tests for ``openamer run`` — the non-interactive single-task CLI command.

Hermetic: the SDK client is swapped for a fake, so no model call and no network.
What is asserted for real is the command's contract:

* it is registered as a top-level ``run`` subcommand and parses its flags,
* ``-p`` is NOT claimed by it (``-p`` is the profile selector in
  ``openamer_cli/main.py`` — taking it here would shadow profile routing),
* ``--json`` writes exactly one JSON object carrying result + turns + cost,
* the exit code is 0 only for a completed turn,
* the command really routes through ``openamer_sdk.OpenAmerClient`` (one engine
  code path shared with the library), not a second implementation.

The last test reads ``openamer_cli/main.py`` and asserts the wiring is present
exactly once — a drift guard that avoids importing the ~19k-line god-file.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import pytest

from openamer_cli.subcommands.run import build_run_parser

REPO = pathlib.Path(__file__).resolve().parents[2]
MAIN_PY = REPO / "openamer_cli" / "main.py"


def _build():
    """Return ``(parser, subparsers)`` with ``run`` attached."""
    parser = argparse.ArgumentParser(prog="openamer")
    subparsers = parser.add_subparsers(dest="command")
    build_run_parser(subparsers)
    return parser, subparsers


def _parser():
    return _build()[0]


def _run_parser():
    _parser_, subparsers = _build()
    return subparsers.choices["run"]


# ---------------------------------------------------------------------------
# Parser surface
# ---------------------------------------------------------------------------


def test_run_subcommand_is_registered():
    parser = _parser()
    ns = parser.parse_args(["run", "do the thing"])

    assert ns.command == "run"
    assert ns.task == "do the thing"


def test_run_does_not_claim_the_dash_p_short_flag():
    """``-p`` is the profile selector; the new command must not shadow it."""
    parser = _parser()
    option_strings = {
        opt for action in _run_parser()._actions for opt in action.option_strings
    }
    assert "-p" not in option_strings, f"-p would shadow --profile: {sorted(option_strings)}"

    # And argparse itself refuses to read it as a run flag.
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "task", "-p", "coder"])


def test_defaults_are_engine_defaults_not_invented_ones():
    ns = _parser().parse_args(["run", "task"])

    assert ns.task == "task"
    assert ns.max_turns is None  # unset -> SDK/engine default, not a CLI guess
    assert ns.as_json is False
    assert ns.toolsets is None
    assert ns.no_toolsets is None
    assert ns.model == ""
    assert ns.timeout is None


def test_flags_parse():
    ns = _parser().parse_args([
        "run", "audit the repo",
        "--max-turns", "4",
        "--toolsets", "web,vision",
        "--no-toolsets", "terminal",
        "--model", "acme/model-1",
        "--timeout", "120",
        "--json",
    ])

    assert ns.task == "audit the repo"
    assert ns.max_turns == 4
    assert ns.toolsets == "web,vision"
    assert ns.no_toolsets == "terminal"
    assert ns.model == "acme/model-1"
    assert ns.timeout == 120.0
    assert ns.as_json is True


def test_handler_is_wired_into_the_parser():
    ns = _parser().parse_args(["run", "task"])
    assert callable(ns.func)


# ---------------------------------------------------------------------------
# Handler behaviour, with a faked SDK client
# ---------------------------------------------------------------------------


class _FakeClient:
    """Captures construction + the task, and returns a canned RunResult."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        type(self).instances.append(self)
        self.run_calls = []

    def run(self, task, **kwargs):
        self.run_calls.append(task)
        from openamer_sdk import RunResult

        return RunResult(
            text="the answer",
            turns=2,
            cost_usd=0.0042,
            session_id="20260101_000000_cli001",
            completed=True,
            failed=False,
            interrupted=False,
            error="",
            turn_exit_reason="completed",
            model="fake/model",
            provider="fake",
            total_tokens=120,
            message_count=2,
            stdout="🤖 AI Agent with Tool Calling\n📞 API Calls: 2\n",
        )


@pytest.fixture
def fake_client(monkeypatch):
    import openamer_sdk

    _FakeClient.instances = []
    monkeypatch.setattr(openamer_sdk, "OpenAmerClient", _FakeClient)
    return _FakeClient


def _run_cli(argv, capsys):
    parser = _parser()
    args = parser.parse_args(argv)
    code = args.func(args)
    return code, capsys.readouterr()


def test_json_mode_emits_one_object_with_result_turns_and_cost(fake_client, capsys):
    code, captured = _run_cli(["run", "count the tests", "--json"], capsys)

    assert code == 0
    payload = json.loads(captured.out)  # exactly one JSON document
    assert payload["ok"] is True
    assert payload["text"] == "the answer"
    assert payload["turns"] == 2
    assert payload["cost_usd"] == pytest.approx(0.0042)
    assert payload["session_id"] == "20260101_000000_cli001"
    assert payload["completed"] is True
    # The engine's own narration must not pollute the machine-readable stream.
    assert "AI Agent with Tool Calling" not in captured.out


def test_json_mode_maps_flags_onto_the_sdk_client(fake_client, capsys):
    _run_cli(
        ["run", "task", "--json", "--max-turns", "4", "--toolsets", "web,vision",
         "--no-toolsets", "terminal", "--model", "acme/m"],
        capsys,
    )

    kwargs = fake_client.instances[0].kwargs
    assert kwargs["model"] == "acme/m"
    assert kwargs["max_turns"] == 4
    assert kwargs["toolsets"] == ["web", "vision"]
    assert kwargs["no_toolsets"] == ["terminal"]


def test_json_mode_omits_untouched_options(fake_client, capsys):
    _run_cli(["run", "task", "--json"], capsys)

    kwargs = fake_client.instances[0].kwargs
    assert kwargs == {"model": ""}


def test_default_mode_prints_the_engine_report_and_a_machine_footer(fake_client, capsys):
    code, captured = _run_cli(["run", "task"], capsys)

    assert code == 0
    assert "AI Agent with Tool Calling" in captured.out
    assert "[run] turns=2 cost_usd=0.004200 session=20260101_000000_cli001" in captured.out


def test_exit_code_is_one_when_the_turn_did_not_complete(fake_client, capsys, monkeypatch):
    from openamer_sdk import RunResult

    def _incomplete(self, task, **kwargs):
        return RunResult(
            text="", turns=10, cost_usd=0.01, session_id="s",
            completed=False, failed=False, interrupted=False,
            error="", turn_exit_reason="max_iterations_reached(10/10)",
        )

    monkeypatch.setattr(fake_client, "run", _incomplete, raising=False)
    code, captured = _run_cli(["run", "task", "--json"], capsys)

    assert code == 1
    assert json.loads(captured.out)["ok"] is False


def test_sdk_error_becomes_a_named_json_reason_and_exit_1(fake_client, capsys, monkeypatch):
    from openamer_sdk.errors import OpenAmerEngineError

    def _boom(self, task, **kwargs):
        raise OpenAmerEngineError("upstream 502", detail="engine output tail")

    monkeypatch.setattr(fake_client, "run", _boom, raising=False)
    code, captured = _run_cli(["run", "task", "--json"], capsys)

    assert code == 1
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["reason"] == "engine"
    assert payload["error"] == "OpenAmerEngineError"
    assert "upstream 502" in payload["message"]


def test_config_error_reports_reason_config(fake_client, capsys, monkeypatch):
    from openamer_sdk.errors import OpenAmerConfigError

    def _boom(self, task, **kwargs):
        raise OpenAmerConfigError("query must be a non-empty string")

    monkeypatch.setattr(fake_client, "run", _boom, raising=False)
    code, captured = _run_cli(["run", "task", "--json"], capsys)

    assert code == 1
    assert json.loads(captured.out)["reason"] == "config"


def test_timeout_error_reports_reason_timeout(fake_client, capsys, monkeypatch):
    from openamer_sdk.errors import OpenAmerTimeoutError

    def _boom(self, task, **kwargs):
        raise OpenAmerTimeoutError("too slow", timeout=3.0)

    monkeypatch.setattr(fake_client, "run", _boom, raising=False)
    code, captured = _run_cli(["run", "task", "--json"], capsys)

    assert code == 1
    payload = json.loads(captured.out)
    assert payload["reason"] == "timeout"
    assert payload["timeout"] == 3.0


def test_unexpected_exception_never_tracebacks_out_of_the_cli(fake_client, capsys, monkeypatch):
    def _boom(self, task, **kwargs):
        raise ValueError("something odd")

    monkeypatch.setattr(fake_client, "run", _boom, raising=False)
    code, captured = _run_cli(["run", "task", "--json"], capsys)

    assert code == 1
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["error"] == "ValueError"


def test_human_mode_error_goes_to_stderr(fake_client, capsys, monkeypatch):
    from openamer_sdk.errors import OpenAmerEngineError

    def _boom(self, task, **kwargs):
        raise OpenAmerEngineError("upstream 502", detail="tail")

    monkeypatch.setattr(fake_client, "run", _boom, raising=False)
    code, captured = _run_cli(["run", "task"], capsys)

    assert code == 1
    assert captured.out == ""
    assert "upstream 502" in captured.err
    assert "engine" in captured.err


def test_the_task_reaches_the_sdk_verbatim(fake_client, capsys):
    _run_cli(["run", "  spaces matter  ", "--json"], capsys)
    assert fake_client.instances[0].run_calls == ["  spaces matter  "]


# ---------------------------------------------------------------------------
# Wiring + one-code-path guards
# ---------------------------------------------------------------------------


def test_run_command_is_wired_into_main_py_exactly_once():
    source = MAIN_PY.read_text(encoding="utf-8")

    assert source.count("from openamer_cli.subcommands.run import build_run_parser") == 1
    assert source.count("build_run_parser(subparsers)") == 1


def test_dash_p_is_still_the_profile_selector_in_main_py():
    """The trap the task warns about: `-p` must keep meaning --profile."""
    source = MAIN_PY.read_text(encoding="utf-8")

    assert 'if arg in {"--profile", "-p"} and i + 1 < len(argv):' in source


def test_cli_routes_through_the_sdk_not_a_second_implementation():
    """`openamer run` and OpenAmerClient must share one engine code path."""
    source = (REPO / "openamer_cli" / "subcommands" / "run.py").read_text(encoding="utf-8")

    assert "from openamer_sdk import OpenAmerClient" in source
    assert "client.run(task)" in source
    # No direct engine reach-around: the CLI must not import or call the engine.
    assert "import run_agent" not in source
    assert "from run_agent" not in source


def test_run_module_does_not_import_the_sdk_at_import_time():
    """Import stays lazy so `openamer --help` does not pay for the SDK."""
    source = (REPO / "openamer_cli" / "subcommands" / "run.py").read_text(encoding="utf-8")
    top_level = "\n".join(
        line for line in source.splitlines()
        if not line.startswith((" ", "\t"))
    )

    assert "import openamer_sdk" not in top_level
    assert "from openamer_sdk" not in top_level


def test_help_text_mentions_non_interactive_and_json():
    help_text = _run_parser().format_help()

    assert "--json" in help_text
    assert "--max-turns" in help_text
    assert re.search(r"non-interactive", help_text, re.IGNORECASE)


def test_module_is_importable_without_the_sdk_installed(monkeypatch):
    """`openamer run --help` must work even if openamer_sdk cannot import."""
    monkeypatch.setitem(sys.modules, "openamer_sdk", None)
    parser = _parser()
    ns = parser.parse_args(["run", "task"])
    assert ns.task == "task"
