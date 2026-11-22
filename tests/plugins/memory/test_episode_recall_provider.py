"""Privacy canaries for the EpisodeRecall memory provider.

The provider injects private episodic memory into a turn, so every canary has
to hold BEFORE any text reaches the model: unknown identity, a shared channel,
a non-primary agent context, and an explicit disable must each return an empty
string. A regression here is a privacy leak, not a UI bug — hence a test that
pins the refusal, not the retrieval quality (that lives in
``tests/scripts/test_self_instruments.py``).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PLUGIN_PATH = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "memory"
    / "episode_recall"
    / "__init__.py"
)

PRIVATE = {"chat_type": "private", "agent_context": "primary", "user_id": "user-1"}


@pytest.fixture(scope="module")
def provider_cls():
    spec = importlib.util.spec_from_file_location(
        "episode_recall_plugin", PLUGIN_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EpisodeRecallProvider


def _initialized(provider_cls, **overrides):
    provider = provider_cls()
    kwargs = {**PRIVATE, **overrides}
    provider.initialize("canary-session", **kwargs)
    return provider


def test_prefetch_denies_unknown_identity(provider_cls):
    provider = _initialized(provider_cls, user_id="")
    assert provider.prefetch("deployment rollback") == ""


def test_prefetch_denies_shared_channel(provider_cls):
    provider = _initialized(provider_cls, chat_type="group")
    assert provider.prefetch("deployment rollback") == ""


def test_prefetch_denies_non_primary_context(provider_cls):
    for context in ("worker", "cron", "subagent"):
        provider = _initialized(provider_cls, agent_context=context)
        assert provider.prefetch("deployment rollback") == "", context


def test_prefetch_denies_when_disabled(provider_cls, monkeypatch):
    monkeypatch.setenv("EPISODE_RECALL_ENABLED", "0")
    provider = _initialized(provider_cls)
    assert provider.is_available() is False
    assert provider.prefetch("deployment rollback") == ""


def test_prefetch_denies_before_initialize(provider_cls):
    provider = provider_cls()
    assert provider.prefetch("deployment rollback") == ""


def test_system_prompt_block_marks_recall_private(provider_cls):
    block = provider_cls().system_prompt_block()
    assert "never quote them verbatim" in block
    assert "private" in block.lower()


def test_provider_exposes_no_tools(provider_cls):
    """Context-only provider: adding tools would widen the core tool schema."""
    assert provider_cls().get_tool_schemas() == []
