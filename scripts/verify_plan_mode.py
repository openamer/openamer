"""End-to-end proof that plan mode refuses a real mutating tool call.

Drives the REAL agent/tool_executor.py sequential path with a fake-but-permissive
agent, a real write_file tool call, and plan mode enabled. The assertion that
matters is on the filesystem: the file must not exist afterwards.

Run: python scripts/verify_plan_mode.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.plan_mode import PlanModeGate  # noqa: E402


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, name, arguments, call_id="call_1"):
        self.id = call_id
        self.function = _FakeFunction(name, arguments)
        self.type = "function"


class _FakeMessage:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls
        self.content = ""


class _FakeGuardrails:
    def before_call(self, *_args, **_kwargs):
        class _D:
            allows_execution = True
            message = ""

        return _D()

    def after_call(self, *args, **kwargs):
        class _D:
            allows_execution = True

        return _D()


class _Noop:
    """Falsy, callable stand-in for optional collaborators.

    Must be FALSY: a truthy generic attribute made the executor take its
    `agent._interrupt_requested` pre-flight branch, so the run was cancelled
    before the gate was ever consulted — the harness passed a wrong reason and
    would have "proven" nothing. Falsy keeps unrelated branches closed.
    """

    def __call__(self, *_a, **_k):
        return None

    def __bool__(self):
        return False

    def __getattr__(self, _name):
        return _Noop()


class _FakeAgent:
    """Permissive stand-in: anything not set here resolves to a falsy no-op."""

    _plan_mode = None

    def __init__(self):
        self.quiet_mode = True
        self.verbose_logging = False
        self.log_prefix_chars = 100
        self.tool_progress_mode = "off"
        self.tool_progress_callback = None
        self.session_id = "verify"
        self._current_turn_id = "t1"
        self._current_api_request_id = "r1"
        self._current_tool = None
        self._turns_since_memory = 0
        self._iters_since_skill = 0
        self._interrupt_requested = False
        self._tool_guardrails = _FakeGuardrails()
        self._plan_mode = PlanModeGate(enabled=True)
        self.accumulated_cost = 0.0
        self.tool_delay = 0
        self.turns = 0
        self.iteration = 0

    def _touch_activity(self, *_a, **_k):
        pass

    def _wrap_verbose(self, *a, **k):
        return ""

    def __getattr__(self, name):
        return _Noop()


def _drive(tool_executor, agent, message, messages, task_id):
    """Run the real executor, tolerating post-decision teardown errors.

    The executor's final budget/bookkeeping phase expects a fully-populated
    message stream; a fake agent's degenerate stream can make it raise *after*
    the block decision. That must not be confused with "not blocked", so the
    exception is captured and reported rather than swallowed.

    The refusal is emitted through ``logging``, not ``print`` — so capture log
    records too, otherwise the run looks silent even though it blocked.
    """
    import contextlib
    import io
    import logging

    class _Capture(logging.Handler):
        def __init__(self):
            super().__init__()
            self.lines: list[str] = []

        def emit(self, record):
            try:
                self.lines.append(record.getMessage())
            except Exception:  # pragma: no cover
                pass

    capture = _Capture()
    root = logging.getLogger()
    root.addHandler(capture)
    buf = io.StringIO()
    error = None
    try:
        with contextlib.redirect_stdout(buf):
            tool_executor.execute_tool_calls_sequential(agent, message, messages, task_id)
    except Exception as exc:  # noqa: BLE001 - reported, not hidden
        error = f"{type(exc).__name__}: {exc}"
    finally:
        root.removeHandler(capture)
    return buf.getvalue() + "\n".join(capture.lines), error


def main() -> int:
    from agent import tool_executor

    tmp = tempfile.mkdtemp(prefix="planmode-")
    target = os.path.join(tmp, "SHOULD_NOT_EXIST.txt")
    args = json.dumps({"path": target, "content": "written by the agent"})

    print("== plan mode ON: write_file must be refused ==")
    agent = _FakeAgent()  # _plan_mode enabled
    messages = []
    out_on, err_on = _drive(
        tool_executor, agent, _FakeMessage([_FakeToolCall("write_file", args)]), messages, "t1"
    )
    created_on = os.path.exists(target)
    refusal_on = "plan mode is active" in (
        json.dumps(messages, ensure_ascii=False) + out_on
    ).lower()
    print("  file created :", created_on, "->", "LEAKED" if created_on else "not created")
    print("  refusal seen :", refusal_on)
    if err_on:
        print("  teardown note:", err_on, "(after the block decision)")

    print("== plan mode OFF: the same call must reach the tool ==")
    agent_off = _FakeAgent()
    agent_off._plan_mode = PlanModeGate(enabled=False)
    messages2 = []
    out_off, err_off = _drive(
        tool_executor, agent_off, _FakeMessage([_FakeToolCall("write_file", args)]), messages2, "t2"
    )
    created_off = os.path.exists(target)
    refusal_off = "plan mode is active" in (
        json.dumps(messages2, ensure_ascii=False) + out_off
    ).lower()
    print("  file created :", created_off, "->", "EXECUTED" if created_off else "not created")
    print("  refused      :", refusal_off, "(must be False — control)")
    if err_off:
        print("  teardown note:", err_off)

    if created_on and os.path.exists(target):
        os.remove(target)
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)

    refusal_works = (not created_on) and refusal_on
    control_works = (not refusal_off)
    print()
    print("  refusal half :", "PASS" if refusal_works else "FAIL")
    print("  control half :", "PASS" if control_works else "FAIL")
    if not control_works:
        print("  note: the control itself was refused, which would mean the gate")
        print("        leaks even when disabled — treat the whole run as FAIL.")
    ok = refusal_works and control_works
    print("\nRESULT:", "PASS — plan mode blocks and only blocks when enabled" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())