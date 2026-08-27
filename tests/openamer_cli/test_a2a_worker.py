"""Tests for the remotely-hosted a2a worker node (scripts/a2a_worker.py).

Offline-safe: run the worker with no_push=True against a temp checkout. The
worker must read a signed task-note, execute a whitelisted task, and write a
signed reply addressed back to the sender; unknown tasks are skipped. The a2a
_ask_llm resolver + prompt→answer extractors are also covered.
"""
import json
import sys
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from openamer_cli.a2a.core import IdentityStore, Envelope          # noqa: E402
from openamer_cli.a2a import relay as R                              # noqa: E402
from openamer_cli.a2a.relay import verify_note                       # noqa: E402
import a2a_worker                                                     # noqa: E402

_KEY_ENVS = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY",
             "DEEPSEEK_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
             "OPENAI_BASE_URL")


@pytest.fixture
def blank_cloud_keys(monkeypatch, tmp_path):
    """Remove every cloud-key env so _ask_llm only sees local/HF backends."""
    saved = {k: os.environ.get(k) for k in _KEY_ENVS}
    for k in _KEY_ENVS:
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture
def blanked_worker_ask(monkeypatch):
    """Route every network adapter to a deterministic no-op to keep tests hermetic."""
    def _noop(*a, **k):
        return {"ok": False, "error": "mocked-away"}
    for fn in ("_ask_openrouter", "_ask_openai_compat", "_ask_anthropic",
               "_ask_ollama", "_ask_huggingface"):
        monkeypatch.setattr(a2a_worker, fn, _noop)


def _seed_task(tmp_path, task, **kw):
    store = IdentityStore(tmp_path / "laptop-ident")
    li = store.ensure_identity()
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
    inbox = tmp_path / R.RELAY_PREFIX
    pf = next(inbox.glob("*.json"))
    note = json.loads(pf.read_text())
    note["envelope"]["ts"] = 0
    pf.write_text(json.dumps(note))
    handled = a2a_worker.run(tmp_path, no_push=True)
    assert handled == 0


def test_extract_answer_strips_cot():
    noisy = ("Let me think.\nStep 1: consider X.\nReasoning: ...\n"
             "Ein KI-Agent trifft eigenständig Entscheidungen.")
    out = a2a_worker._extract_answer(noisy)
    assert "trifft" in out
    assert "Let me" not in out
    assert "Step 1" not in out
    assert "Reasoning" not in out


def test_ask_llm_handles_no_keys_without_crash(blank_cloud_keys, blanked_worker_ask):
    res = a2a_worker._ask_llm("hi")
    # with every backend mocked away it must return a structured dict, no raise
    assert isinstance(res, dict) and "ok" in res


def test_ask_llm_tries_openrouter_when_key_present(monkeypatch, blank_cloud_keys):
    os.environ["OPENROUTER_API_KEY"] = "sk-test-xs"
    used = {"n": 0}

    def fake_or(prompt, model, key):
        used["n"] += 1
        return {"ok": True, "text": "x", "model": model}

    monkeypatch.setattr(a2a_worker, "_ask_openrouter", fake_or)
    res = a2a_worker._ask_llm("hi")
    assert used["n"] == 1 and res["ok"] is True


def test_load_model_default_reads_declared_standard(tmp_path, monkeypatch):
    # A config.yaml with model: {provider, default} is the DECLARED standard.
    (tmp_path / "config.yaml").write_text(
        "model:\n  provider: ollama\n  default: qwen3.5:9b\n",
        encoding="utf-8")
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    std = a2a_worker._load_model_default()
    assert std
    assert std["provider"] == "ollama"
    assert std["model"] == "qwen3.5:9b"


def test_ask_llm_uses_declared_standard_first(monkeypatch, tmp_path):
    # Declared standard provider+model must be the FIRST candidate tried.
    (tmp_path / "config.yaml").write_text(
        "model:\n  provider: ollama\n  default: qwen3.5:9b\n",
        encoding="utf-8")
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    # force no cloud keys
    for k in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY",
              "DEEPSEEK_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
              "OPENAI_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    used = []
    monkeypatch.setattr(a2a_worker, "_ask_ollama",
                        lambda p: used.append("ollama") or {"ok": True, "text": "x", "model": "ollama:qwen3.5:9b"})
    res = a2a_worker._ask_llm("hi")
    assert used and "ollama" in str(used[0])   # declared standard (ollama) was tried