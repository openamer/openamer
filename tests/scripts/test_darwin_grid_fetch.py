"""Regression tests for the Darwin grid genome fetch (scripts/darwin_grid_github.py).

Live 2026-09-17: the daily grid duel (`autonomous_loop.py --loop` step 6) crashed
before it could duel anything:

    File "scripts/darwin_grid_github.py", line 113, in _fetch_genome
        data = json.loads(base64.b64decode(resp["content"]))
    json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

Cause: the GitHub Contents API inlines `content` only for blobs under ~1 MB.
The foreign genome crossed that line in normal operation (damir-desktop.json is
now ~2.8 MB with a 137-skill population), so the API answered 200 with
`"encoding": "none"` and an EMPTY `content` field. `b64decode("")` returns b"",
and `json.loads(b"")` raises JSONDecodeError -- so the duel died at the fetch,
every day, silently, because `challenge_grid_daily()` records `last_duel` and
swallows the child's exit code.

The 16.09.2026 duel still printed a line because that genome was still under the
1 MB inline limit; the failure only appears once the population is real, which
is exactly the case the grid exists for.

Contract pinned here: a Contents API response with an inline payload decodes from
base64, and one without falls back to `download_url`. Both paths must produce the
same dict, and an unparseable response must return None (not raise) so the caller
can report "machine not found" instead of dying.
"""
from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO / "scripts" / "darwin_grid_github.py"

# darwin_engine.py resolves OPENAMER_HOME at import time and scans the real
# skills tree if pointed at it (~2 min). Point it at a temp home so the module
# load stays a fast unit import. Set before exec_module, hence not a fixture.
os.environ["OPENAMER_HOME"] = tempfile.mkdtemp(prefix="darwin-grid-test-")

_spec = importlib.util.spec_from_file_location("darwin_grid_github", SCRIPT)
DG = importlib.util.module_from_spec(_spec)
sys.modules["darwin_grid_github"] = DG
_spec.loader.exec_module(DG)


class _Resp(io.BytesIO):
    """Minimal urlopen() context manager over raw bytes."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def test_inline_content_still_decodes_from_base64():
    """Small blobs: the API inlines base64 -- unchanged behaviour."""
    payload = {"machine_id": "damir-desktop", "population": {"a": 1}}
    resp = {
        "encoding": "base64",
        "content": base64.b64encode(json.dumps(payload).encode()).decode(),
    }
    assert DG._decode_contents(resp) == payload


def test_oversized_blob_falls_back_to_download_url():
    """The live failure: encoding 'none' + empty content, 2.8 MB genome.

    This is the exact shape GitHub returned for damir-desktop.json on
    17.09.2026. It must NOT raise -- it must fetch via download_url.
    """
    # Sized like the real file: 137 skills, each with a SKILL.md body.
    payload = {"machine_id": "damir-desktop",
               "population": {f"skill-{i}": {"wins": i, "body": "x" * 20000}
                              for i in range(137)}}
    raw = json.dumps(payload).encode()
    assert len(raw) > 1_000_000  # really is over the inline limit
    resp = {
        "encoding": "none",
        "content": "",
        "size": len(raw),
        "download_url": "https://raw.githubusercontent.com/openamer/"
                        "darwin-grid/main/damir-desktop.json",
    }
    calls: list[str] = []

    def _fake_urlopen(url, **kw):
        calls.append(url)
        return _Resp(raw)

    with patch("urllib.request.urlopen", _fake_urlopen):
        out = DG._decode_contents(resp)
    assert out == payload
    assert calls == [resp["download_url"]]  # fell back to the URL, no b64 attempt


def test_missing_content_key_falls_back_to_download_url():
    """Older/partial API shapes omit `content` entirely."""
    payload = {"machine_id": "x"}
    raw = json.dumps(payload).encode()
    resp = {"download_url": "https://example.invalid/x.json"}
    with patch("urllib.request.urlopen", lambda url, **kw: _Resp(raw)):
        assert DG._decode_contents(resp) == payload


def test_unparseable_response_returns_none_not_raises():
    """A dead/HTML download_url must not take the duel down with it.

    `challenge_grid_daily()` reports on the child's stdout only, so an exception
    here is invisible except as a missing duel. Returning None degrades to the
    existing "machine not found" branch.
    """
    resp = {"encoding": "none", "content": "",
            "download_url": "https://example.invalid/x.json"}
    with patch("urllib.request.urlopen",
               lambda url, **kw: _Resp(b"<html>404 not found</html>")):
        assert DG._decode_contents(resp) is None

    # no download_url AND no inline content -> nothing to decode
    assert DG._decode_contents({"encoding": "none", "content": ""}) is None
