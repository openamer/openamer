"""A bare run of active_learn.py must take ONE rotation step, not five.

The cron scheduler runs a job script as `python <script>` with no arguments --
`cron/scheduler.py::_run_job_script` builds `argv = [python_exe, str(path)]`
and has no way to pass one. active_learn.py read that bare call as its
"run all 5 for testing" branch and never called get_next_action(), so
`.learn_rotation` stayed at 95 from 2026-09-10 onward while the job recorded
8071 completed runs: five actions every seven minutes instead of one, and the
rotation that balances the five actions was dead the whole time.

The exit code stayed 0 and the job status stayed `ok`, which is why nothing
noticed. These tests pin the entry-point contract, not the actions themselves.
"""
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "training"))

_spec = importlib.util.spec_from_file_location(
    "active_learn_under_test", SCRIPTS / "training" / "active_learn.py"
)
AL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AL)

NAMES = ["web_learn", "self_test", "world_explore", "skill_challenge", "cross_connect"]


def _install(tmp_path, monkeypatch, record):
    """Replace the real actions with recorders and isolate every side effect.

    RUN_LOG must be redirected too: the first tests call main([]) -> run_one(),
    which appends to the run log. Measured 2026-11-19: without this, the suite
    wrote its fake "web_learn" rows into the live
    memory/active_learn_log.jsonl and made the real log lie.
    """
    actions = []
    for name in NAMES:
        def action(_name=name):
            record.append(_name)
            return _name
        action.__name__ = name
        actions.append(action)
    monkeypatch.setattr(AL, "ACTIONS", actions)
    monkeypatch.setattr(AL, "ROTATION_FILE", str(tmp_path / ".learn_rotation"))
    monkeypatch.setattr(AL, "RUN_LOG", str(tmp_path / "active_learn_log.jsonl"))
    monkeypatch.setattr(AL, "BUFFER", str(tmp_path / "online_buffer.jsonl"))
    return actions


def test_bare_invocation_runs_exactly_one_action(tmp_path, monkeypatch):
    """The regression: a bare run used to execute all five actions."""
    record = []
    _install(tmp_path, monkeypatch, record)
    assert AL.main([]) == 0
    assert len(record) == 1, f"bare run took {len(record)} actions: {record}"


def test_bare_invocation_advances_rotation(tmp_path, monkeypatch):
    """The rotation file is the only record that the loop is still rotating."""
    record = []
    _install(tmp_path, monkeypatch, record)
    rot = tmp_path / ".learn_rotation"
    assert AL.main([]) == 0
    assert rot.read_text(encoding="utf-8").strip() == "1"
    assert AL.main([]) == 0
    assert rot.read_text(encoding="utf-8").strip() == "2"


def test_rotation_round_robins_through_all_five(tmp_path, monkeypatch):
    record = []
    _install(tmp_path, monkeypatch, record)
    for _ in range(5):
        assert AL.main([]) == 0
    assert record == NAMES
    assert AL.main([]) == 0
    assert record[-1] == "web_learn"


def test_all_sweep_is_opt_in_and_leaves_rotation_alone(tmp_path, monkeypatch):
    record = []
    _install(tmp_path, monkeypatch, record)
    assert AL.main(["all"]) == 0
    assert record == NAMES
    assert not (tmp_path / ".learn_rotation").exists()


def test_unknown_command_refuses_without_running(tmp_path, monkeypatch, capsys):
    record = []
    _install(tmp_path, monkeypatch, record)
    assert AL.main(["bogus"]) == 2
    assert record == []
    assert "unknown command" in capsys.readouterr().err


def test_corrupt_rotation_counter_does_not_stop_the_loop(tmp_path, monkeypatch):
    """A truncated counter must not kill the step before it runs.

    Measured 2026-11-19: the live counter held "95", but a killed run or a
    half-written file leaves "9" of "95", an empty file or garbage behind.
    The old code raised ValueError straight out of get_next_action, so the
    action never ran and the loop stood still for as long as the corrupt
    counter sat there. Recovery is: start the round again at 0.
    """
    record = []
    actions = _install(tmp_path, monkeypatch, record)
    rot = tmp_path / ".learn_rotation"

    for corrupt in ("", "  ", "9x", "nan", "\x00"):
        rot.write_text(corrupt, encoding="utf-8")
        action = AL.get_next_action()
        assert action.__name__ == NAMES[0], f"corrupt counter {corrupt!r} mis-routed"
        assert rot.read_text(encoding="utf-8").strip() == "1"

    # And a valid counter still routes correctly and keeps counting.
    rot.write_text("7", encoding="utf-8")
    assert AL.get_next_action().__name__ == NAMES[7 % len(actions)]
    assert rot.read_text(encoding="utf-8").strip() == "8"


# --- the writer-gate contract ------------------------------------------------

REAL_INSIGHTS = [
    "Build AI agents as modular systems with separate planning, memory, tool-use, "
    "and orchestration components so multi-agent workflows can be scaled and maintained effectively.",
    "Energy efficiency and intelligence scalability are tightly coupled, but they are "
    "not the same thing: a useful metric has to price both latency and quality.",
    "Retrieval augmented generation reduces hallucination by grounding each answer in "
    "retrieved documents rather than parametric memory alone.",
]


def test_web_learn_payload_survives_its_own_junk_gate():
    """The row web_learn stores must pass the gate its own writer applies.

    Measured 2026-11-19: web_learn stored f"Key insight: {insight}", and
    `key insight:` is an entry in buffer_store._NAV_CHROME (a template-echo
    marker). So every web_learn row was refused on its label alone -- 191
    logged rejections with reason "junk", zero rows ever buffered. The loop
    reported "not buffered" into a void: a no_agent job's stdout is a
    delivery, this job has no origin, and the executions table has no output
    column. Nothing could see it.

    This pins the contract: the payload must not be junk by the gate's own
    rules, and the old labelled form must still be refused (so the marker is
    not silently weakened).
    """
    import buffer_store

    for insight in REAL_INSIGHTS:
        payload = AL._insight_payload(insight)
        assert payload, "payload must not be empty"
        assert not buffer_store.is_junk(payload), (
            f"web_learn would be gated on its own payload: {payload[:70]!r}"
        )

    # The regression, stated as a test: the label is what tripped the gate.
    labelled = f"Key insight: {REAL_INSIGHTS[0]}"
    assert buffer_store.is_junk(labelled), (
        "if this stops being junk the marker was weakened -- re-check _NAV_CHROME"
    )


def test_run_one_writes_one_durable_row(tmp_path, monkeypatch):
    """8071 runs once left zero record. Every run now leaves one row."""
    record = []
    _install(tmp_path, monkeypatch, record)
    log = tmp_path / "active_learn_log.jsonl"
    monkeypatch.setattr(AL, "RUN_LOG", str(log))
    monkeypatch.setattr(AL, "BUFFER", str(tmp_path / "online_buffer.jsonl"))

    assert AL.run_one() == "web_learn"
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["action"] == "web_learn"
    assert rows[0]["rotation"] == 0
    assert rows[0]["buffer_changed"] is False  # the fake action wrote nothing
    assert "ts" in rows[0] and "elapsed_s" in rows[0]


def test_buffer_changed_is_measured_not_self_reported(tmp_path, monkeypatch):
    """The instrument must see a real write even at the buffer cap.

    Line counts stay flat once the buffer is full (enforce_cap trims it back),
    so the log compares the newest row instead. A lying action that reports
    success without writing must still be recorded as buffer_changed=False.
    """
    buf = tmp_path / "online_buffer.jsonl"
    buf.write_text('{"u": "old", "a": "old"}\n', encoding="utf-8")
    log = tmp_path / "active_learn_log.jsonl"
    monkeypatch.setattr(AL, "RUN_LOG", str(log))
    monkeypatch.setattr(AL, "BUFFER", str(buf))

    def liar():
        return "self-test: good on 'nothing'"

    def writer():
        with open(buf, "a", encoding="utf-8") as fh:
            fh.write('{"u": "new", "a": "new"}\n')
        return "web-learn: something"

    liar.__name__, writer.__name__ = "liar", "writer"
    monkeypatch.setattr(AL, "ACTIONS", [liar, writer])
    monkeypatch.setattr(AL, "ROTATION_FILE", str(tmp_path / ".learn_rotation"))

    AL.run_one()  # liar: rotation 0
    AL.run_one()  # writer: rotation 1
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
    assert [(r["action"], r["buffer_changed"]) for r in rows] == [
        ("liar", False), ("writer", True)
    ]

