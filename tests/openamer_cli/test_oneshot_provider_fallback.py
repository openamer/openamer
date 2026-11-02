"""The one-shot path must fall back when the primary provider is unusable.

A rate-limited OAuth provider raises ``AuthError`` from
``resolve_runtime_provider()`` — before the agent exists. The agent's own
fallback chain is built during ``AIAgent`` construction, so it cannot help
there: without an explicit fallback resolution in the one-shot path, every
``openamer -z`` run failed with "Codex provider quota exhausted (429)" even
though a working fallback chain was configured.
"""
from __future__ import annotations

import pytest

from openamer_cli.auth import AuthError


@pytest.fixture
def oneshot(monkeypatch):
    """Import the oneshot module with its provider resolution stubbed out."""
    import openamer_cli.config as config_mod
    import openamer_cli.runtime_provider as runtime_mod
    import run_agent as run_agent_mod
    import openamer_cli.oneshot as oneshot_mod

    monkeypatch.setattr(
        config_mod,
        "load_config",
        lambda: {
            "model": {"default": "gpt-6.1-sol", "provider": "openai-codex"},
            "fallback_providers": [
                {"provider": "ollama-cloud", "model": "minimax-m3.1-flash"},
            ],
        },
    )
    return oneshot_mod, runtime_mod, run_agent_mod


def _install_fake_agent(monkeypatch, run_agent_mod, captured):
    class _FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            raise RuntimeError("agent-construction-stop")

    monkeypatch.setattr(run_agent_mod, "AIAgent", _FakeAgent)


def test_oneshot_falls_back_when_primary_quota_is_exhausted(monkeypatch, oneshot):
    oneshot_mod, runtime_mod, run_agent_mod = oneshot

    calls: list[str] = []

    def _fake_resolve(requested=None, **kwargs):
        calls.append(str(requested))
        if requested in (None, "openai-codex"):
            raise AuthError(
                "Codex provider quota exhausted (429); retry after 600s. "
                "Credentials are still valid.",
                provider="openai-codex",
                code="codex_rate_limited",
                relogin_required=False,
            )
        return {
            "provider": "ollama-cloud",
            "requested_provider": "ollama-cloud",
            "api_mode": "chat_completions",
            "base_url": "https://ollama.com",
            "api_key": "test-key",
        }

    monkeypatch.setattr(runtime_mod, "resolve_runtime_provider", _fake_resolve)

    captured: dict = {}
    _install_fake_agent(monkeypatch, run_agent_mod, captured)

    with pytest.raises(RuntimeError, match="agent-construction-stop"):
        oneshot_mod._run_agent(
            "hello",
            model=None,
            provider=None,
            toolsets=None,
            use_config_toolsets=False,
        )

    assert captured.get("provider") == "ollama-cloud"
    assert captured.get("model") == "minimax-m3.1-flash"
    assert "ollama-cloud" in calls


def test_oneshot_reraises_when_no_fallback_is_configured(monkeypatch, oneshot):
    oneshot_mod, runtime_mod, run_agent_mod = oneshot

    monkeypatch.setattr(
        runtime_mod,
        "resolve_runtime_provider",
        lambda requested=None, **kwargs: (_ for _ in ()).throw(
            AuthError(
                "Codex provider quota exhausted (429).",
                provider="openai-codex",
                code="codex_rate_limited",
                relogin_required=False,
            )
        ),
    )

    captured: dict = {}
    _install_fake_agent(monkeypatch, run_agent_mod, captured)

    with pytest.raises(AuthError):
        oneshot_mod._run_agent(
            "hello",
            model=None,
            provider=None,
            toolsets=None,
            use_config_toolsets=False,
        )

    assert captured == {}, "no agent may be built when no fallback resolves"


def test_oneshot_reraises_non_auth_errors(monkeypatch, oneshot):
    """A non-auth failure must not be silently converted into a fallback."""
    oneshot_mod, runtime_mod, run_agent_mod = oneshot

    def _fake_resolve(requested=None, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(runtime_mod, "resolve_runtime_provider", _fake_resolve)

    captured: dict = {}
    _install_fake_agent(monkeypatch, run_agent_mod, captured)

    with pytest.raises(RuntimeError, match="boom"):
        oneshot_mod._run_agent(
            "hello",
            model=None,
            provider=None,
            toolsets=None,
            use_config_toolsets=False,
        )

    assert captured == {}
