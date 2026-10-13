"""Tests for openamer_cli/a2a/catalog_serve.py (ARD .well-known HTTP server).

Hermetic: we start the stdlib HTTP server on an ephemeral port in a thread and
hit it with urllib — no external network. Verifies the three ARD discovery
routes serve the catalog (including the dotfile .well-known path that GitHub
Pages cannot), and that health works.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli.a2a import catalog_serve        # noqa: E402


@pytest.fixture
def catalog_host(tmp_path):
    """Start the server on an ephemeral port serving the repo catalog."""
    cat = REPO / "docs" / ".well-known" / "ai-catalog.json"
    if not cat.exists():
        cat = REPO / "docs" / "ai-catalog.json"
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    # start in background thread using the real serve() (daemon so it dies)
    t = threading.Thread(target=catalog_serve.serve,
                         args=("127.0.0.1", port, str(cat)), daemon=True)
    t.start()
    # wait until bound
    import time
    for _ in range(20):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    yield port


def _get(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def test_health(catalog_host):
    code, body = _get(catalog_host, "/health")
    assert code == 200
    assert json.loads(body)["status"] == "ok"


def test_dotwellknown_serves_catalog(catalog_host):
    code, body = _get(catalog_host, "/.well-known/ai-catalog.json")
    assert code == 200
    d = json.loads(body)
    assert d["entries"][0]["identifier"].startswith("urn:air:")


def test_root_catalog_serves(catalog_host):
    code, body = _get(catalog_host, "/ai-catalog.json")
    assert code == 200
    assert "urn:air:" in body


def test_unknown_404(catalog_host):
    code, _ = _get(catalog_host, "/nope")
    assert code == 404