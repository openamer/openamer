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