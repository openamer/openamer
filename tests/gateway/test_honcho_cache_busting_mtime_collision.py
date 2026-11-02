"""The gateway agent cache must bust on every real change to honcho.json.

The cache-busting memo was keyed on the file's mtime alone. NTFS timestamps
are coarser than the wall clock, so two edits inside the same tick can share
an mtime — the memo then returned the previous alias map and the cached agent
was reused although the identity mapping had changed.

The collision is reproduced here deterministically: the second write is
forced back onto the first write's mtime, which is exactly what the measured
Windows failure produced.
"""

from __future__ import annotations

import json
import os

import pytest

from gateway.run import GatewayRunner


@pytest.fixture(autouse=True)
def clear_memo():
    GatewayRunner._HONCHO_CACHE_BUSTING_MEMO = {}
    yield
    GatewayRunner._HONCHO_CACHE_BUSTING_MEMO = {}


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_alias_change_with_identical_mtime_still_busts_the_cache(tmp_path, monkeypatch):
    """The regression: the same mtime must not reuse the memo."""
    cfg = tmp_path / "honcho.json"
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    _write(cfg, {"apiKey": "k", "peerName": "Igor"})
    base_stamp = cfg.stat().st_mtime_ns

    first = GatewayRunner._extract_cache_busting_config({"memory": {"provider": "honcho"}})
    assert first["honcho.user_peer_aliases"] == []

    # A second edit inside the same filesystem timestamp tick: the content
    # changes, the mtime does not.
    _write(cfg, {"apiKey": "k", "peerName": "Igor", "userPeerAliases": {"7": "Igor"}})
    os.utime(cfg, ns=(base_stamp, base_stamp))
    assert cfg.stat().st_mtime_ns == base_stamp

    second = GatewayRunner._extract_cache_busting_config({"memory": {"provider": "honcho"}})
    assert second["honcho.user_peer_aliases"] != first["honcho.user_peer_aliases"], (
        "a changed alias map must bust the cached agent even when the file's "
        "mtime did not move"
    )


def test_unchanged_file_reuses_the_memo(tmp_path, monkeypatch):
    cfg = tmp_path / "honcho.json"
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    _write(cfg, {"apiKey": "k", "peerName": "Igor"})
    first = GatewayRunner._extract_cache_busting_config({"memory": {"provider": "honcho"}})
    second = GatewayRunner._extract_cache_busting_config({"memory": {"provider": "honcho"}})
    assert first == second
    assert len(GatewayRunner._HONCHO_CACHE_BUSTING_MEMO) == 1
