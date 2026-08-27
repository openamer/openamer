"""Tests for the remotely-hosted a2a worker node (scripts/a2a_worker.py).

Offline-safe: run the worker with no_push=True against a temp checkout. It
must read a signed task-note, execute a whitelisted task, and write a signed
reply back addressed to the task sender; unknown tasks are skipped.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from openamer_cli.a2a.core import IdentityStore, Envelope          # noqa: E402
from openamer_cli.a2a import relay as R                              # noqa: E402
from openamer_cli.a2a.relay import verify_note                       # noqa: E402
import a2a_worker                                                     # noqa: E402


def _seed_task(tmp_path, task, **kw):
    store = IdentityStore(tmp_path / "laptop-ident")
    li    = store.ensure_identity()
    env = Envelope.create(
        private_key=store.private_key(), sender=f"{li.fingerprint}@openamer",
        recipient=a2a_worker.WORKER_MAILBOX, kind="task.ask",
        payload={"task": task, **kw})
    note = R.relay_note(identity_store=store, envelope=env)
    inbox = tmp_path / R.RELAY_PREFIX
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / R.sort_relay_filename("nodeworker")).write_text(
        json.dumps(note, ensure_ascii=False))
    return li


def test_worker_executes_sum_and_replies(tmp_path):
    li = _seed_task(tmp_path, "sum", a=20, b=22)
    handled = a2a_worker.run(tmp_path, no_push=True)
    assert handled == 1

    inbox = tmp_path / R.RELAY_PREFIX
    replies = [json.loads(p.read_text()) for p in inbox.glob("*.json")
               if p.name.startswith(li.fingerprint)]
    assert replies, "no reply for laptop mailbox"
    ver = verify_note(replies[0])
    assert ver["ok"], ver.get("reason")
    assert ver["env"].payload.get("sum") == "42"   # relay redacts -> string


def test_worker_skips_unknown_task(tmp_path):
    _seed_task(tmp_path, "rm_rf", cmd="rm -rf /")
    handled = a2a_worker.run(tmp_path, no_push=True)
    assert handled == 0


def test_worker_rejects_stale_note(tmp_path):
    li = _seed_task(tmp_path, "ping")
    # age the note beyond the replay tolerance
    inbox = tmp_path / R.RELAY_PREFIX
    pf = next(inbox.glob("*.json"))
    note = json.loads(pf.read_text())
    note["envelope"]["ts"] = 0
    pf.write_text(json.dumps(note))
    handled = a2a_worker.run(tmp_path, no_push=True)
    assert handled == 0