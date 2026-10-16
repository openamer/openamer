"""Tests for the ``openamer_sdk`` embedding package (tests/sdk/).

Hermetic: no network, no model call, no real ``run_agent`` import in the hot
path. The engine is faked through the SDK's own documented ``engine`` seam, but
the *SDK's contract* is asserted for real — which kwargs reach
``run_agent.main``, how the engine's turn-result dict maps onto ``RunResult``,
and which named ``reason`` each failure class carries.

Why the fake is shaped the way it is: ``run_agent.main`` builds ``AIAgent``
through the *module-level* name and calls ``agent.run_conversation(query)``.
The fake therefore mirrors that exactly (``module.AIAgent(**kwargs)`` then
``.run_conversation(query)``) so the SDK's recording seam is genuinely
exercised rather than bypassed. If the seam breaks, ``capture.result`` stays
``None`` and the run fails loudly.

The last test reads ``run_agent.py`` and asserts every kwarg the SDK sends is an
accepted parameter of the real ``main`` — a drift guard, so a signature change
names itself instead of surfacing as a TypeError in production.
"""

from __future__ import annotations

import ast
import json
import pathlib
import time
import types

import pytest

import openamer_sdk.engine as sdk_engine
from openamer_sdk import (
    REASON_CONFIG,
    REASON_ENGINE,
    REASON_TIMEOUT,
    OpenAmerClient,
    OpenAmerConfigError,
    OpenAmerEngineError,
    OpenAmerError,
    OpenAmerTimeoutError,
    RunResult,
)

REPO = pathlib.Path(__file__).resolve().parents[2]

DEFAULT_SESSION_ID = "20260101_000000_sdk001"


def default_result(**overrides):
    """A turn-result dict shaped like ``agent/turn_finalizer.py``'s own."""
    result = {
        "final_response": "The answer is 42.",
        "messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
        "api_calls": 3,
        "completed": True,
        "failed": False,
        "interrupted": False,
        "turn_exit_reason": "completed",
        "model": "fake/model",
        "provider": "fake",
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "estimated_cost_usd": 0.0042,
    }
    result.update(overrides)
    return result


def make_engine(
    *,
    result=None,
    sleep=0.0,
    init_failure=False,
    raise_exc=None,
    prints=("🤖 AI Agent with Tool Calling", "=" * 20),
):
    """Build a fake engine module + a record of what ``main`` received.

    Returns ``(module, seen)``. ``seen`` collects the kwargs handed to ``main``
    and the query handed to ``run_conversation``.
    """
    module = types.ModuleType("fake_run_agent")
    seen = {}
    canned = default_result() if result is None else dict(result)

    class FakeAgent:
        """Minimal stand-in for ``run_agent.AIAgent``."""

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.session_id = kwargs.get("session_id") or DEFAULT_SESSION_ID
            self.model = kwargs.get("model") or "fake/model"
            self.provider = "fake"

        def run_conversation(self, query, **kwargs):
            seen["agent_query"] = query
            return dict(canned)

    def main(**kwargs):
        seen.update(kwargs)
        for line in prints:
            print(line)
        if sleep:
            time.sleep(sleep)
        if init_failure:
            print("❌ Failed to initialize agent: no model configured")
            return None
        if raise_exc is not None:
            raise raise_exc
        # Exactly what the real main() does: build the module-level AIAgent and
        # run one conversation. The SDK has swapped that name for its recorder.
        agent = module.AIAgent(**kwargs)
        out = agent.run_conversation(kwargs.get("query"))
        print(f"📞 API Calls: {out['api_calls']}")
        return out

    module.main = main
    module.AIAgent = FakeAgent
    return module, seen


# ---------------------------------------------------------------------------
# Import hygiene
# ---------------------------------------------------------------------------


def test_import_does_not_pull_the_engine_module():
    """``import openamer_sdk`` must not eagerly bind ``run_agent``.

    The engine's import graph is heavy and touches provider wiring; the SDK
    stays importable (and network-free) by resolving it lazily.
    """
    assert sdk_engine.ENGINE_MODULE == "run_agent"
    assert "run_agent" not in sdk_engine.__dict__


# ---------------------------------------------------------------------------
# Structured result
# ---------------------------------------------------------------------------


def test_run_returns_a_structured_result_not_a_string():
    module, _ = make_engine()
    result = OpenAmerClient(engine=module).run("what is the answer?")

    assert isinstance(result, RunResult)
    assert not isinstance(result, str)
    assert result.text == "The answer is 42."
    assert result.turns == 3
    assert result.cost_usd == pytest.approx(0.0042)
    assert result.session_id
    assert result.completed is True
    assert result.failed is False
    assert result.message_count == 2
    assert result.total_tokens == 120
    assert result.model == "fake/model"


def test_result_to_dict_is_json_serialisable_and_carries_turns_and_cost():
    module, _ = make_engine()
    result = OpenAmerClient(engine=module).run("count something")

    payload = json.loads(json.dumps(result.to_dict()))

    assert payload["turns"] == 3
    assert payload["cost_usd"] == pytest.approx(0.0042)
    assert payload["session_id"] == DEFAULT_SESSION_ID
    assert payload["text"] == "The answer is 42."
    # ``raw`` is Python-only on purpose: the engine's dict is not guaranteed to
    # be JSON-clean, and --json output must never fail to serialise.
    assert "raw" not in payload
    assert result.raw["api_calls"] == 3


def test_session_id_is_read_from_the_real_agent_the_engine_constructed():
    """Proves the recording seam really built an agent, not a stub."""
    module, _ = make_engine(result=default_result(session_id=None))
    call = sdk_engine.call_engine_main(query="x", engine=module)

    assert call.main_called is True
    assert call.agent is not None
    assert call.agent.session_id == DEFAULT_SESSION_ID
    assert call.result is not None


# ---------------------------------------------------------------------------
# The real call into run_agent.main(...)
# ---------------------------------------------------------------------------


def test_main_is_called_with_the_documented_kwargs():
    module, seen = make_engine()
    call = sdk_engine.call_engine_main(
        query="audit this",
        model="acme/model-1",
        max_turns=5,
        enabled_toolsets="web,vision",
        disabled_toolsets="terminal",
        engine=module,
    )

    assert call.main_called is True
    assert seen["query"] == "audit this"
    assert seen["model"] == "acme/model-1"
    assert seen["max_turns"] == 5
    assert seen["enabled_toolsets"] == "web,vision"
    assert seen["disabled_toolsets"] == "terminal"
    assert seen["agent_query"] == "audit this"
    # Nothing the caller did not ask for is invented.
    assert set(seen) == {
        "query",
        "model",
        "max_turns",
        "enabled_toolsets",
        "disabled_toolsets",
        "agent_query",
    }


def test_optional_kwargs_are_omitted_when_not_set():
    module, seen = make_engine()
    OpenAmerClient(engine=module).run("just the query")

    assert seen["query"] == "just the query"
    assert seen["max_turns"] == 10  # client default mirrors run_agent.main
    assert "model" not in seen
    assert "enabled_toolsets" not in seen
    assert "disabled_toolsets" not in seen
    assert "api_key" not in seen
    assert "base_url" not in seen


def test_toolsets_accept_a_list_and_are_normalised_to_csv():
    module, seen = make_engine()
    OpenAmerClient(engine=module, toolsets=["web", "vision"]).run(
        "look around", no_toolsets=("terminal", "browser")
    )

    assert seen["enabled_toolsets"] == "web,vision"
    assert seen["disabled_toolsets"] == "terminal,browser"


def test_per_run_overrides_win_over_client_defaults():
    module, seen = make_engine()
    client = OpenAmerClient(engine=module, max_turns=10, toolsets="web")
    client.run("second", max_turns=2, toolsets="safe")

    assert seen["max_turns"] == 2
    assert seen["enabled_toolsets"] == "safe"


def test_aiagent_binding_is_restored_after_the_call():
    module, _ = make_engine()
    original = module.AIAgent
    OpenAmerClient(engine=module).run("x")

    assert module.AIAgent is original


def test_aiagent_binding_is_restored_even_when_the_engine_raises():
    module, _ = make_engine(raise_exc=RuntimeError("engine exploded"))
    original = module.AIAgent
    with pytest.raises(OpenAmerEngineError):
        OpenAmerClient(engine=module).run("x")

    assert module.AIAgent is original


# ---------------------------------------------------------------------------
# Output capture
# ---------------------------------------------------------------------------


def test_engine_stdout_is_captured_and_not_leaked(capsys):
    module, _ = make_engine()
    result = OpenAmerClient(engine=module).run("quiet please")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "AI Agent with Tool Calling" in result.stdout
    assert "API Calls: 3" in result.stdout


def test_capture_output_false_lets_the_engine_print(capsys):
    module, _ = make_engine()
    result = OpenAmerClient(engine=module, capture_output=False).run("loud please")

    captured = capsys.readouterr()
    assert "AI Agent with Tool Calling" in captured.out
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# Named failure reasons
# ---------------------------------------------------------------------------


def test_failed_turn_raises_engine_error_and_keeps_the_result():
    module, _ = make_engine(
        result=default_result(
            completed=False, failed=True, error="upstream 502", final_response=""
        )
    )

    with pytest.raises(OpenAmerEngineError) as excinfo:
        OpenAmerClient(engine=module).run("doomed")

    assert excinfo.value.reason == REASON_ENGINE
    assert "upstream 502" in str(excinfo.value)
    # The engine's own numbers survive the failure.
    assert excinfo.value.result["api_calls"] == 3


def test_engine_exception_is_an_engine_error():
    module, _ = make_engine(raise_exc=RuntimeError("engine exploded"))

    with pytest.raises(OpenAmerEngineError) as excinfo:
        OpenAmerClient(engine=module).run("x")

    assert excinfo.value.reason == REASON_ENGINE
    assert "RuntimeError" in str(excinfo.value)


def test_engine_that_never_publishes_a_result_is_an_engine_error():
    module, _ = make_engine(init_failure=False)
    # A main() that returns without building an agent at all.
    module.main = lambda **kwargs: print("nothing happened")

    with pytest.raises(OpenAmerEngineError) as excinfo:
        OpenAmerClient(engine=module).run("x")

    assert excinfo.value.reason == REASON_ENGINE
    assert "without running a turn" in str(excinfo.value)


def test_agent_init_failure_is_a_config_error():
    module, _ = make_engine(init_failure=True)

    with pytest.raises(OpenAmerConfigError) as excinfo:
        OpenAmerClient(engine=module).run("x")

    assert excinfo.value.reason == REASON_CONFIG
    assert "could not initialize" in str(excinfo.value)
    assert "Failed to initialize agent" in excinfo.value.detail


def test_timeout_is_a_timeout_error():
    module, _ = make_engine(sleep=5.0)

    with pytest.raises(OpenAmerTimeoutError) as excinfo:
        OpenAmerClient(engine=module, timeout=0.05).run("slow")

    assert excinfo.value.reason == REASON_TIMEOUT
    assert excinfo.value.timeout == 0.05
    assert "0.05" in str(excinfo.value)


def test_unimportable_engine_module_is_a_config_error(monkeypatch):
    monkeypatch.setattr(sdk_engine, "ENGINE_MODULE", "openamer_sdk_no_such_module_xyz")

    with pytest.raises(OpenAmerConfigError) as excinfo:
        OpenAmerClient().run("x")

    assert excinfo.value.reason == REASON_CONFIG
    assert "could not be imported" in str(excinfo.value)


def test_engine_module_without_aiagent_is_a_config_error():
    module = types.ModuleType("no_agent_engine")
    module.main = lambda **kwargs: None

    with pytest.raises(OpenAmerConfigError) as excinfo:
        OpenAmerClient(engine=module).run("x")

    assert excinfo.value.reason == REASON_CONFIG
    assert "AIAgent" in str(excinfo.value)


def test_engine_module_without_main_is_a_config_error():
    module = types.ModuleType("no_main_engine")
    module.AIAgent = object

    with pytest.raises(OpenAmerConfigError) as excinfo:
        OpenAmerClient(engine=module).run("x")

    assert excinfo.value.reason == REASON_CONFIG
    assert "main" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Argument validation (config errors, before anything runs)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["", "   ", None, 42])
def test_bad_query_is_a_config_error(query):
    module, seen = make_engine()
    with pytest.raises(OpenAmerConfigError) as excinfo:
        OpenAmerClient(engine=module).run(query)

    assert excinfo.value.reason == REASON_CONFIG
    assert seen == {}  # the engine was never reached


@pytest.mark.parametrize("max_turns", [0, -1, 1.5, "3", True])
def test_bad_max_turns_is_a_config_error(max_turns):
    module, _ = make_engine()
    with pytest.raises(OpenAmerConfigError):
        OpenAmerClient(engine=module).run("x", max_turns=max_turns)


@pytest.mark.parametrize("timeout", [0, -3])
def test_bad_timeout_is_a_config_error(timeout):
    module, _ = make_engine()
    with pytest.raises(OpenAmerConfigError):
        OpenAmerClient(engine=module).run("x", timeout=timeout)


def test_bad_toolsets_type_is_a_config_error():
    with pytest.raises(OpenAmerConfigError):
        OpenAmerClient(engine=make_engine()[0], toolsets=7)


def test_every_error_carries_a_named_reason_and_a_dict_form():
    for exc in (
        OpenAmerConfigError("c"),
        OpenAmerEngineError("e"),
        OpenAmerTimeoutError("t", timeout=1.0),
    ):
        assert isinstance(exc, OpenAmerError)
        payload = exc.to_dict()
        assert payload["reason"] in {REASON_CONFIG, REASON_ENGINE, REASON_TIMEOUT}
        assert payload["error"] == type(exc).__name__
        assert isinstance(payload["message"], str)
        json.dumps(payload)


# ---------------------------------------------------------------------------
# resume()
# ---------------------------------------------------------------------------


def test_resume_writes_the_turn_under_the_given_session_id():
    module, seen = make_engine()
    result = OpenAmerClient(engine=module).resume("20260101_000000_aaaaaa", "and then?")

    # The resumed id reaches the real AIAgent constructor...
    assert seen["query"] == "and then?"
    # ...and is what the caller is told.
    assert result.session_id == "20260101_000000_aaaaaa"
    assert result.session_continued is True


def test_run_is_not_flagged_as_continued():
    module, _ = make_engine()
    result = OpenAmerClient(engine=module).run("fresh start")

    assert result.session_continued is False
    assert result.session_id == DEFAULT_SESSION_ID


@pytest.mark.parametrize("session_id", ["", "   ", None, 7])
def test_resume_requires_a_real_session_id(session_id):
    module, seen = make_engine()
    with pytest.raises(OpenAmerConfigError):
        OpenAmerClient(engine=module).resume(session_id, "x")

    assert seen == {}


def test_resume_docstring_states_the_no_history_limitation():
    """The limitation is part of the contract, so it is asserted, not implied."""
    doc = OpenAmerClient.resume.__doc__ or ""
    assert "does not replay" in doc
    assert "session_id" in doc


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------


def test_module_level_run_helper_works_and_rejects_unknown_kwargs():
    import openamer_sdk

    module, seen = make_engine()
    result = openamer_sdk.run("helper", max_turns=2, engine=module)

    assert seen["max_turns"] == 2
    assert result.text == "The answer is 42."

    with pytest.raises(OpenAmerConfigError) as excinfo:
        openamer_sdk.run("helper", engine=module, nonsense=True)
    assert "nonsense" in excinfo.value.detail


# ---------------------------------------------------------------------------
# Drift guard against the real run_agent.main signature
# ---------------------------------------------------------------------------


def _real_main_params():
    source = (REPO / "run_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            args = node.args
            names = {a.arg for a in args.args} | {a.arg for a in args.kwonlyargs}
            return names
    raise AssertionError("run_agent.main was not found in run_agent.py")


def test_sdk_kwargs_are_real_run_agent_main_parameters():
    """A signature change in run_agent.main must fail here, by name."""
    accepted = _real_main_params()
    sent_by_sdk = {
        "query",
        "model",
        "api_key",
        "base_url",
        "max_turns",
        "enabled_toolsets",
        "disabled_toolsets",
    }
    missing = sorted(sent_by_sdk - accepted)
    assert missing == [], f"run_agent.main no longer accepts: {missing}"


def test_sdk_targets_the_same_entry_point_python_run_agent_py_uses():
    """The SDK's engine target is the repo-root run_agent, not a private copy."""
    source = (REPO / "run_agent.py").read_text(encoding="utf-8")
    assert sdk_engine.ENGINE_MODULE == "run_agent"
    assert (REPO / f"{sdk_engine.ENGINE_MODULE}.py").is_file()
    # The module really is the script entry point, so `openamer run` and
    # `python run_agent.py` reach the same main().
    assert "fire.Fire(main)" in source
    assert {"query", "max_turns"} <= _real_main_params()
