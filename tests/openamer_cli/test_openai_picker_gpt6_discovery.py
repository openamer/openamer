"""Regression tests: the OpenAI picker must surface models OpenAI released
after the curated snapshot was written.

Bug — GPT-6 family invisible to /model
    ``provider_model_ids("openai-api")`` intersected the live
    ``api.openai.com/v1/models`` catalog with a hardcoded curated list.
    Every model OpenAI shipped after that snapshot was written was silently
    dropped, so the whole GPT-6 family (gpt-6-astra, gpt-6.1-sol, gpt-6-sol,
    gpt-6-luna) never appeared in the picker.

Fix — merge, don't intersect
    The live catalog is the source of truth for what the account can call.
    The curated list keeps the ordering and the always-visible baseline.
    Live models at least as new as the newest curated generation are
    appended, so a new generation appears without an OpenAmer release while
    legacy generations stay out of the picker.
"""

from unittest.mock import patch

import pytest

from openamer_cli import models as M


# --- helpers ---------------------------------------------------------------

def _version(model_id: str):
    return M._openai_model_version(model_id)


def _is_agentic(model_id: str) -> bool:
    return M._is_agentic_openai_model(model_id)


# --- version parsing -------------------------------------------------------

@pytest.mark.parametrize("model_id,expected", [
    ("gpt-6-astra", (6, 0)),
    ("gpt-6.1-sol", (6, 1)),
    ("gpt-5.6-sol", (5, 6)),
    ("gpt-5-mini", (5, 0)),
    ("gpt-4o", None),
    ("o3", None),
    ("chat-latest", None),
    ("gpt-5-codex", (5, 0)),       # suffix variant, same generation
    ("gpt-5.3-codex", (5, 3)),
    ("gpt-6.2-future", (6, 2)),
])
def test_openai_model_version_parses_generation(model_id, expected):
    assert _version(model_id) == expected


# --- agentic filter --------------------------------------------------------

@pytest.mark.parametrize("model_id", [
    "gpt-6-astra", "gpt-6.1-sol", "gpt-5.6-sol", "gpt-5-mini",
    "gpt-4.1", "gpt-4o", "o3", "o4-mini", "gpt-5.3-codex",
])
def test_agentic_models_pass_filter(model_id):
    assert _is_agentic(model_id) is True


@pytest.mark.parametrize("model_id", [
    "text-embedding-3-large",
    "text-embedding-ada-002",
    "whisper-1",
    "tts-1",
    "tts-1-hd",
    "gpt-4o-mini-tts",
    "gpt-4o-mini-transcribe",
    "gpt-4o-transcribe-diarize",
    "gpt-transcribe",
    "gpt-audio",
    "gpt-audio-mini",
    "gpt-image-1",
    "gpt-image-2.5-flare",
    "chatgpt-image-latest",
    "gpt-realtime",
    "gpt-realtime-2.1-mini",
    "gpt-live-1",
    "omni-moderation-latest",
    "sora-2",
    "sora-2-pro",
    "davinci-002",
    "babbage-002",
    "gpt-3.5-turbo-instruct",
])
def test_non_chat_models_are_excluded(model_id):
    assert _is_agentic(model_id) is False


# --- merge behaviour -------------------------------------------------------

def test_merge_appends_newer_generation_from_live():
    """A model newer than the curated frontier is added to the picker."""
    curated = ["gpt-5.6-sol", "gpt-5.5"]
    live = ["gpt-6-astra", "gpt-6.1-sol", "gpt-5.6-sol", "gpt-5.5"]

    result = M._split_openai_picker_models(live, curated)

    assert result == ["gpt-5.6-sol", "gpt-5.5", "gpt-6-astra", "gpt-6.1-sol"]


def test_merge_keeps_legacy_generations_out():
    """Older generations present in the live catalog stay out of the picker."""
    curated = ["gpt-5.6-sol", "gpt-5.5"]
    live = ["gpt-5.6-sol", "gpt-5.5", "gpt-4o", "gpt-3.5-turbo", "o1", "gpt-4.1"]

    result = M._split_openai_picker_models(live, curated)

    assert "gpt-4o" not in result
    assert "gpt-3.5-turbo" not in result
    assert "o1" not in result
    assert "gpt-4.1" not in result
    assert "gpt-5.6-sol" in result
    assert "gpt-5.5" in result


def test_merge_drops_curated_models_account_cannot_call():
    """Curated models the account does not serve are not offered."""
    curated = ["gpt-5.6-sol", "gpt-5.5"]
    live = ["gpt-5.5", "gpt-6-astra"]

    result = M._split_openai_picker_models(live, curated)

    assert "gpt-5.6-sol" not in result
    assert "gpt-5.5" in result
    assert "gpt-6-astra" in result


def test_merge_never_duplicates():
    curated = ["gpt-5.6-sol"]
    live = ["gpt-5.6-sol", "gpt-6-astra", "gpt-6-astra"]

    result = M._split_openai_picker_models(live, curated)

    assert result.count("gpt-5.6-sol") == 1
    assert result.count("gpt-6-astra") == 1


def test_merge_excludes_non_chat_live_entries():
    curated = ["gpt-5.6-sol"]
    live = ["gpt-5.6-sol", "gpt-6-astra", "text-embedding-3-large", "sora-2"]

    result = M._split_openai_picker_models(live, curated)

    assert "text-embedding-3-large" not in result
    assert "sora-2" not in result
    assert "gpt-6-astra" in result


# --- end-to-end through provider_model_ids ---------------------------------

def test_provider_model_ids_surfaces_gpt6_family(monkeypatch):
    """The picker exposes GPT-6 models the account serves."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    live = [
        "gpt-6-astra", "gpt-6.1-sol", "gpt-6-sol", "gpt-6-luna",
        "gpt-5.6-sol", "gpt-5.5", "gpt-4o", "gpt-3.5-turbo",
        "text-embedding-3-large", "whisper-1", "sora-2",
    ]
    with patch.object(M, "fetch_api_models", return_value=live):
        result = M.provider_model_ids("openai-api", force_refresh=True)

    assert "gpt-6-astra" in result
    assert "gpt-6.1-sol" in result
    assert "gpt-6-sol" in result
    assert "gpt-6-luna" in result
    assert "text-embedding-3-large" not in result
    assert "whisper-1" not in result
    assert "sora-2" not in result
    assert "gpt-3.5-turbo" not in result


def test_curated_catalog_contains_gpt6_family():
    """The curated snapshot lists the current OpenAI flagship generation."""
    curated = M._PROVIDER_MODELS["openai-api"]
    for model_id in ("gpt-6-astra", "gpt-6.1-sol", "gpt-6-sol", "gpt-6-luna"):
        assert model_id in curated
