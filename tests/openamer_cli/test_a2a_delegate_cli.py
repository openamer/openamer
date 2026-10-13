"""Tests for the `openamer a2a delegate` CLI module (openamer_cli/a2a/delegate_cli.py).

These are offline/offline-safe: they do NOT hit GitHub. They validate the new
surface wiring without network — the real live delegation is exercised via a
separate E2E script (laptop -> GitHub Actions runner -> verified reply).
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli.a2a import delegate_cli as D  # noqa: E402


def test_latest_reply_skips_stale_and_filters_mailbox(tmp_path):
    # fresh reply addressed to our fingerprint, returned
    ours = {"recipient": "1234567890abcdef@openamer",
            "envelope": {"kind": "task.result", "ts": 1000}, "x": 1}
    older = {"recipient": "1234567890abcdef@openamer",
             "envelope": {"kind": "task.result", "ts": 500}}
    other = {"recipient": "zzz@openamer", "envelope": {"kind": "task.result", "ts": 9000}}
    for i, obj in enumerate((ours, older, other)):
        (tmp_path / f"f{i}.json").write_text(json.dumps(obj))
    r = D._latest_reply(tmp_path, "1234567890abcdef")
    assert r["x"] == 1                              # newest for our mailbox
    # after_ts filter
    r2 = D._latest_reply(tmp_path, "1234567890abcdef", after_ts=1000)
    assert r2 is None


def test_base64_upload_path(tmp_path):
    # just confirm _upload_via_api url construction & b64 content (no net)
    import base64
    import re
    # cannot call (network) — assert the JSON/headers logic via a tiny helper check:
    # the function builds a PUT to /contents/{path}
    # (covered better by live E2E; here we only sanity the module import surface)
    assert callable(D._upload_via_api)
    assert D.DEFAULT_GH_REPO == "openamer/openamer"
    assert D.DEFAULT_LABEL == "nodeworker"


def test_cred_token_parses_expected_layout(tmp_path, monkeypatch):
    gf = tmp_path / ".git-credentials"
    gf.write_text("https://x-access-token:ghp_FAKETOKEN@github.com")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    D._cred_cache = ""
    assert D._cred_token() == "ghp_FAKETOKEN"


class _FakeStore:
    """IdentityStore stand-in that signs with a real Ed25519 key (offline)."""

    def __init__(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        self._key = Ed25519PrivateKey.generate()

    def ensure_identity(self):
        pub = self._key.public_key().public_bytes_raw().hex()
        return type("I", (), {"fingerprint": "f" * 16, "public_key": pub})()

    def private_key(self):
        return self._key


def test_delegate_sum_carries_addends_to_the_worker(tmp_path, monkeypatch):
    """Regression: the CLI never sent a/b, so the remote worker computed 0+0.

    Live-verified 2026-10-06: a real `sum` delegation returned `sum: 0` from the
    GitHub Actions worker. The worker executes
    `int(payload["a"]) + int(payload["b"])`, so the delegate payload MUST carry
    both keys and delegate_cmd must forward args["a"]/args["b"].
    """
    uploaded: dict = {}

    def _fake_upload(repo, tok, path, content):
        uploaded["content"] = content
        return "sha"

    monkeypatch.setattr(D, "_cred_token", lambda: "gho_faketoken")
    monkeypatch.setattr(D, "_upload_via_api", _fake_upload)
    monkeypatch.setattr(D, "_dispatch", lambda *a, **k: None)
    monkeypatch.setattr(D, "IdentityStore", lambda *a, **k: _FakeStore())
    # keep the poll loop from running: shrink the wait window to zero
    monkeypatch.setattr(D.time, "time", lambda: 10_000)

    args = {"msg": "", "text": "", "a": 20, "b": 22, "model": "",
            "wait": 0, "repo": str(tmp_path), "gh_repo": "openamer/openamer"}
    D.delegate_cmd("sum", args)

    assert "content" in uploaded, "nothing was uploaded"
    note = json.loads(uploaded["content"])
    payload = note["envelope"]["payload"]
    # the relay stringifies payload values; the worker coerces with int()
    assert int(payload["a"]) == 20 and int(payload["b"]) == 22, payload
    # the worker's arithmetic is int(a)+int(b) -> must be 42, not 0
    assert int(payload["a"]) + int(payload["b"]) == 42


def test_delegate_sum_payload_shape_matches_worker():
    """Lock the a/b contract the worker's _task_executor relies on.

    Also documents the exact pre-fix symptom: an empty payload yields 0.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    import a2a_worker

    assert a2a_worker._task_executor("sum", {"a": 20, "b": 22}) == {"ok": True, "sum": 42}
    assert a2a_worker._task_executor("sum", {}) == {"ok": True, "sum": 0}
