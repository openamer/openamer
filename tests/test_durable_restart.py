"""Separate-process crash/restart fixtures for durable execution.

The acceptance contract is physical: a really killed process is restarted in a
disposable profile and must not repeat completed work, must keep its previous
checkpoint when a write was interrupted, and must refuse to replay an external
effect whose outcome is unknown.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from openamer_cli import durable_execution as de
from openamer_cli.graph_workflow import WorkflowGraph, WorkflowNode, WorkflowStore

REPO_ROOT = Path(__file__).resolve().parents[1]

# Child process used by the crash/restart fixtures. It only uses the public
# durable-execution API — no test-only hooks.
_CHILD = '''
import os
import sys
import time
from pathlib import Path

from openamer_cli import durable_execution as de

mode, counter_path, ready_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])


def mark(label):
    with counter_path.open("a", encoding="utf-8") as fh:
        fh.write(label + "\\n")
        fh.flush()
        os.fsync(fh.fileno())


if mode == "crash":
    run = de.open_run("restart-run")
    run.run_step("prepare", lambda: mark("prepare"), effect=de.EffectClass.NONE)

    def deploy():
        mark("deploy")
        ready_path.write_text("effect-started", encoding="utf-8")
        time.sleep(120)

    run.run_step("deploy", deploy, effect=de.EffectClass.EXTERNAL)

elif mode == "resume":
    run = de.open_run("restart-run")
    run.run_step("prepare", lambda: mark("prepare-AGAIN"), effect=de.EffectClass.NONE)
    try:
        run.run_step("deploy", lambda: mark("deploy-AGAIN"), effect=de.EffectClass.EXTERNAL)
    except de.AmbiguousExternalEffect:
        print("AMBIGUOUS", flush=True)
        sys.exit(0)
    print("REPLAYED", flush=True)
    sys.exit(1)

elif mode == "writer":
    payload = "x" * 200_000
    for index in range(2000):
        de.save_checkpoint("crash-session", [{"role": "user", "content": f"{index}:{payload}"}])

elif mode == "write":
    de.save_checkpoint("iso", [{"role": "user", "content": sys.argv[4]}])
    print("WROTE", flush=True)

elif mode == "read":
    checkpoint = de.load_latest_checkpoint("iso")
    if checkpoint is None:
        print("NONE", flush=True)
    else:
        print(f"FOUND:{checkpoint.messages[0]['content']}", flush=True)

else:
    raise SystemExit(f"unknown mode {mode}")
'''


def _child_script(tmp_path: Path) -> Path:
    path = tmp_path / "durable_child.py"
    path.write_text(_CHILD, encoding="utf-8")
    return path


def _env(home: Path) -> dict:
    env = dict(os.environ)
    env["OPENAMER_HOME"] = str(home)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env.pop("OPENAMER_KANBAN_TASK", None)
    return env


def _wait_for(predicate, timeout: float, interval: float = 0.05) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _run_child(script: Path, home: Path, *args: str, timeout: float = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(REPO_ROOT),
        env=_env(home),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _journal(home: Path, run_id: str) -> Path:
    return home / "checkpoints" / "runs" / run_id / "run.json"


# ---------------------------------------------------------------------------
# 1. Kill mid external effect, restart, resume
# ---------------------------------------------------------------------------


def test_killed_process_does_not_repeat_completed_work_and_halts_on_ambiguity(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    counter = tmp_path / "counter.txt"
    ready = tmp_path / "ready.txt"
    script = _child_script(tmp_path)

    proc = subprocess.Popen(
        [sys.executable, str(script), "crash", str(counter), str(ready)],
        cwd=str(REPO_ROOT),
        env=_env(home),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert _wait_for(ready.exists, timeout=120), "child never reached the external effect"
        # The intent record must already be durable while the effect is running.
        journal = _journal(home, "restart-run")
        assert journal.exists()
        assert '"in_flight"' in journal.read_text(encoding="utf-8")
    finally:
        proc.kill()
        proc.wait(timeout=60)

    assert counter.read_text(encoding="utf-8").split() == ["prepare", "deploy"]

    resumed = _run_child(script, home, "resume", str(counter), str(ready))

    assert resumed.returncode == 0, resumed.stderr
    assert "AMBIGUOUS" in resumed.stdout
    assert "prepare-AGAIN" not in counter.read_text(encoding="utf-8")
    assert "deploy-AGAIN" not in counter.read_text(encoding="utf-8")
    assert counter.read_text(encoding="utf-8").split() == ["prepare", "deploy"]

    snapshot = json.loads(_journal(home, "restart-run").read_text(encoding="utf-8"))
    assert snapshot["steps"]["prepare"]["status"] == "completed"
    assert snapshot["steps"]["prepare"]["attempts"] == 1
    assert snapshot["steps"]["deploy"]["status"] == "in_flight"


# ---------------------------------------------------------------------------
# 2. Interrupted checkpoint write must not corrupt the previous checkpoint
# ---------------------------------------------------------------------------


def test_kill_during_checkpoint_writes_keeps_a_valid_prior_checkpoint(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(home))
    script = _child_script(tmp_path)
    session_dir = home / "checkpoints" / "crash-session"

    for delay in (0.05, 0.2, 0.4):
        proc = subprocess.Popen(
            [sys.executable, str(script), "writer", "unused", "unused"],
            cwd=str(REPO_ROOT),
            env=_env(home),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wrote_any = _wait_for(
                lambda: session_dir.exists() and len(list(session_dir.glob("*.json"))) >= 2,
                timeout=120,
            )
            assert wrote_any, "child never wrote checkpoints"
            time.sleep(delay)
        finally:
            proc.kill()
            proc.wait(timeout=60)

        restored = de.load_latest_checkpoint("crash-session")
        assert restored is not None, "a killed write must leave the store resumable"
        index, _, payload = restored.messages[0]["content"].partition(":")
        assert index.isdigit()
        assert int(index) == restored.number - 1
        assert payload == "x" * 200_000, "the surviving payload must be complete"

        for path in session_dir.glob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))  # every retained file parses


# ---------------------------------------------------------------------------
# 3. Profiles stay isolated across processes
# ---------------------------------------------------------------------------


def test_two_profiles_do_not_see_each_other(tmp_path):
    script = _child_script(tmp_path)
    home_a = tmp_path / "profiles" / "alpha"
    home_b = tmp_path / "profiles" / "beta"
    home_a.mkdir(parents=True)
    home_b.mkdir(parents=True)

    assert _run_child(script, home_a, "write", "unused", "unused", "alpha-state").returncode == 0

    other = _run_child(script, home_b, "read", "unused", "unused")
    assert other.returncode == 0
    assert other.stdout.strip() == "NONE"

    same = _run_child(script, home_a, "read", "unused", "unused")
    assert same.stdout.strip() == "FOUND:alpha-state"


# ---------------------------------------------------------------------------
# 4. Real production CLI: durable run + resume + status
# ---------------------------------------------------------------------------


def _cli(env: dict, *args: str, timeout: float = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "openamer_cli.main", *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_cli_durable_run_resumes_from_journal(tmp_path):
    home = tmp_path / "cli-home"
    home.mkdir()
    env = _env(home)

    created = _cli(env, "workflow", "create")
    assert created.returncode == 0, created.stderr

    first = _cli(env, "workflow", "run", "demo-workflow", "valid",
                 "--durable", "--run-id", "cli-durable")
    assert first.returncode == 0, first.stderr
    assert "Durable steps executed now: ['parse'" in first.stdout

    second = _cli(env, "workflow", "run", "demo-workflow", "valid",
                  "--durable", "--run-id", "cli-durable")
    assert second.returncode == 0, second.stderr
    assert "Durable steps restored from journal: ['parse'" in second.stdout
    assert "Durable steps executed now: (none)" in second.stdout

    status = _cli(env, "workflow", "status", "cli-durable")
    assert status.returncode == 0, status.stderr
    assert "completed  parse  attempts=1" in status.stdout

    listed = _cli(env, "checkpoint", "runs")
    assert listed.returncode == 0, listed.stderr
    assert "cli-durable" in listed.stdout


def test_cli_refuses_to_replay_an_ambiguous_external_step(tmp_path, monkeypatch):
    home = tmp_path / "cli-home"
    home.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(home))
    env = _env(home)

    # A workflow whose first task node is `parse`, matching the seeded journal.
    WorkflowStore().save(
        "external-demo",
        WorkflowGraph(
            nodes={
                "parse": WorkflowNode(id="parse", type="task", name="Parse",
                                      config={"durable_effect": "external"}),
            },
            entry_node_id="parse",
        ),
    )
    run = de.open_run("cli-ambiguous")
    with pytest.raises(KeyboardInterrupt):
        run.run_step(
            "parse",
            lambda: (_ for _ in ()).throw(KeyboardInterrupt("killed in flight")),
            effect=de.EffectClass.EXTERNAL,
        )

    halted = _cli(env, "workflow", "run", "external-demo", "--durable",
                  "--run-id", "cli-ambiguous")

    assert halted.returncode == 3
    assert "HALTED" in halted.stderr
    status = _cli(env, "workflow", "status", "cli-ambiguous")
    assert "Ambiguous external effects" in status.stdout
