"""Phase-30 tests: swarm communication - workers talk to each other."""
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "swarm_communication", REPO / "scripts" / "swarm_communication.py")
comm = importlib.util.module_from_spec(spec)
sys.modules["swarm_communication"] = comm
spec.loader.exec_module(comm)


@pytest.fixture
def fake_world(tmp_path, monkeypatch):
    monkeypatch.setattr(comm, "MESSAGES_FILE",
                        tmp_path / "darwin" / "messages.json")
    (tmp_path / "darwin").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_send_and_receive_direct(fake_world):
    comm.send_message("alice", "bob", "ALERT", "gap in security detected")
    msgs = comm.receive_messages("bob")
    assert len(msgs) == 1
    assert msgs[0]["sender"] == "alice"
    assert msgs[0]["type"] == "ALERT"
    assert "security" in msgs[0]["content"]


def test_broadcast_reaches_all(fake_world):
    comm.send_message("core", "*", "ALERT", "stagnation detected")
    alice_msgs = comm.receive_messages("alice")
    bob_msgs = comm.receive_messages("bob")
    assert len(alice_msgs) == 1
    assert len(bob_msgs) == 1
    # sender doesn't receive own broadcast
    core_msgs = comm.receive_messages("core")
    assert len(core_msgs) == 0


def test_messages_marked_read(fake_world):
    comm.send_message("a", "b", "INFO", "hello")
    first = comm.receive_messages("b")
    assert len(first) == 1
    second = comm.receive_messages("b")
    assert len(second) == 0  # already read


def test_sender_no_receive_own(fake_world):
    comm.send_message("alice", "alice", "INFO", "talking to myself")
    msgs = comm.receive_messages("alice")
    assert len(msgs) == 0  # sender never receives own message


def test_message_types(fake_world):
    comm.send_message("a", "b", "ALERT", "gap found")
    comm.send_message("a", "b", "REQUEST", "help me")
    comm.send_message("a", "b", "INSIGHT", "learned something")
    msgs = comm.receive_messages("b")
    types = [m["type"] for m in msgs]
    assert types == ["ALERT", "REQUEST", "INSIGHT"]


def test_llm_respond_in_character(fake_world):
    ident = {"name": "Gaia the Deep", "personality": ["brave"],
             "mood": "thriving"}
    msg = {"sender": "darwin-core", "type": "ALERT",
           "content": "Gap detected: weak-population"}
    context = {"stats": {"population": 42}, "gaps": [{"type": "weak-population"}]}
    r = comm.llm_respond("Gaia the Deep", msg, ident, context)
    if not r or "could not" in r:
        pytest.skip("Ollama not responding (integration test)")
    assert len(r) > 0


def test_swarm_conversation_generates_coordination(fake_world, fake_world2=None):
    # broadcast an alert, then have a worker respond
    comm.send_message("darwin-core", "*", "ALERT",
                      "Gap detected: weak-population. Mutate now.")
    # create a worker identity
    ident = {"name": "Boris the Bold", "personality": ["brave", "curious"],
             "mood": "thriving"}
    organisms = [{"id": "boris", "type": "worker", "identity": ident}]
    context = {"stats": {"population": 42},
               "gaps": [{"type": "weak-population"}]}
    with patch.object(comm, "llm_respond",
                      return_value="I will mutate the weak skills immediately."):
        results = comm.swarm_conversation(organisms, context)
    assert len(results) >= 1
    assert results[0]["type"] == "RESPONSE"
    assert "Boris" in results[0]["from"]


def test_conversation_creates_coordination_tasks(fake_world):
    from swarm_os import submit_task, load_swarm
    results = [{"from": "boris", "to": "darwin-core", "type": "RESPONSE",
                "content": "I will mutate and help with the gap",
                "responding_to": "ALERT"}]
    tids = comm.generate_communication_tasks(results)
    assert len(tids) == 1  # "I will" triggers task creation
