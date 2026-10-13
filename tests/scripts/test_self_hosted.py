"""Tests for scripts/self-hosted.py (provider failover health-check).

Hermetic: no real network, no real Ollama. We cover the offline-testable
contract that matters for hosts: the health-probe must cap the model context
(``num_ctx``), otherwise Ollama loads the model's full context length
(256k for qwen3.5 → ~13 GB of KV cache for a 10-token ping).
"""
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "self_hosted", REPO / "scripts" / "self-hosted.py"
)
SH = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SH)


def test_probe_sends_capped_num_ctx():
    """The generate probe must pin num_ctx so Ollama never loads 256k KV."""
    captured = {}

    class _Resp:
        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode())
        return _Resp()

    with patch.object(SH.urllib.request, "urlopen", side_effect=fake_urlopen):
        result = SH.check_local_health({})

    assert result["available"] is True
    opts = captured["payload"]["options"]
    assert opts["num_predict"] <= 16
    # The budget contract: ctx capped far below model max (256k → 13 GB KV).
    assert 512 <= opts["num_ctx"] <= 8192


def test_num_ctx_regression_guard():
    """If someone removes num_ctx from the probe payload, this must fail.

    Regression for the 2026-08-30 incident: a probe without num_ctx made
    Ollama allocate ~13.3 GB of KV cache (RAM 98%, system unusable).
    """
    captured = {}

    class _Resp:
        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode())
        return _Resp()

    with patch.object(SH.urllib.request, "urlopen", side_effect=fake_urlopen):
        SH.check_local_health({})

    assert "num_ctx" in captured["payload"]["options"], (
        "health probe lost its num_ctx cap — this re-opens the 13 GB RAM bug"
    )