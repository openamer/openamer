"""Fallback-chain resilience for auxiliary tasks.

Two behaviors, both from a live Windows case (2026-11-06):

1. **A dead candidate must not kill the chain.** A fallback candidate that
   fails for a CAPACITY reason (402/429/unreachable/5xx) or a capability
   mismatch ("this route cannot serve this model") used to re-raise out of
   ``_call_fallback_candidate_sync`` / ``_call_fallback_candidate_async`` and
   abort the whole auxiliary task, even though later candidates were healthy.
   Only a genuinely malformed request (a 400 no candidate could satisfy) may
   still raise.

2. **Vision requests only walk to vision-capable candidates.** A text-only
   candidate answers an image request with a provider-side 500
   ("unknown variant `image_url`") rather than a clean error, which used to
   abort the call. ``_try_configured_fallback_chain`` /
   ``_try_main_fallback_chain`` must skip such a candidate and keep walking.

The non-vision path must stay permissive: a text-only model is perfectly
valid for ``title_generation``/``compression``, so the filter is gated on
``task == "vision"``.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _APIStatusError(Exception):
    """Stand-in for an SDK error carrying an HTTP status."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _client_raising(exc: Exception, *, is_async: bool) -> MagicMock:
    """A fake OpenAI client whose create() raises ``exc``."""
    client = MagicMock()
    client.base_url = "https://example.invalid/api/v1"
    if is_async:
        client.chat.completions.create = AsyncMock(side_effect=exc)
    else:
        client.chat.completions.create = MagicMock(side_effect=exc)
    return client


def _call_sync(client, *, task):
    from agent.auxiliary_client import _call_fallback_candidate_sync

    return _call_fallback_candidate_sync(
        client,
        "candidate-model",
        "fallback_chain[0](openrouter)",
        task=task,
        messages=[{"role": "user", "content": "hi"}],
        temperature=None,
        max_tokens=None,
        tools=None,
        effective_timeout=30.0,
        effective_extra_body={},
        reasoning_config=None,
    )


def _call_async(client, *, task):
    from agent.auxiliary_client import _call_fallback_candidate_async

    return asyncio.run(
        _call_fallback_candidate_async(
            client,
            "candidate-model",
            "fallback_chain[0](openrouter)",
            task=task,
            messages=[{"role": "user", "content": "hi"}],
            temperature=None,
            max_tokens=None,
            tools=None,
            effective_timeout=30.0,
            effective_extra_body={},
            reasoning_config=None,
        )
    )


@pytest.fixture(autouse=True)
def _no_configured_timeout():
    """Keep the helper from reading a per-entry timeout out of config."""
    with patch(
        "agent.auxiliary_client._fallback_entry_timeout", return_value=None
    ):
        yield


class TestDeadCandidateDoesNotAbortSyncChain:
    def test_provider_500_is_skipped_not_raised(self):
        """The live case: a text-only candidate 500s on an image request."""
        exc = _APIStatusError("unknown variant `image_url`", 500)
        client = _client_raising(exc, is_async=False)
        assert _call_sync(client, task="vision") is None

    def test_rate_limit_is_skipped_not_raised(self):
        exc = _APIStatusError("429 rate limit exceeded", 429)
        client = _client_raising(exc, is_async=False)
        assert _call_sync(client, task="compression") is None

    def test_payment_error_is_skipped_not_raised(self):
        exc = _APIStatusError("402 insufficient credits", 402)
        client = _client_raising(exc, is_async=False)
        assert _call_sync(client, task="compression") is None

    def test_malformed_request_still_raises(self):
        """A 400 no later candidate could satisfy must not be swallowed."""
        exc = _APIStatusError(
            "invalid_request_error: messages.0.content is required", 400
        )
        client = _client_raising(exc, is_async=False)
        with pytest.raises(_APIStatusError):
            _call_sync(client, task="compression")


class TestDeadCandidateDoesNotAbortAsyncChain:
    def test_provider_500_is_skipped_not_raised(self):
        exc = _APIStatusError("unknown variant `image_url`", 500)
        client = _client_raising(exc, is_async=True)
        assert _call_async(client, task="vision") is None

    def test_malformed_request_still_raises(self):
        exc = _APIStatusError(
            "invalid_request_error: messages.0.content is required", 400
        )
        client = _client_raising(exc, is_async=True)
        with pytest.raises(_APIStatusError):
            _call_async(client, task="compression")


class TestVisionCandidatesAreScreened:
    """_try_configured_fallback_chain must skip text-only candidates for vision."""

    def _chain(self, *models):
        return {
            "fallback_chain": [
                {"provider": f"provider{i}", "model": m}
                for i, m in enumerate(models)
            ]
        }

    def test_text_only_candidate_is_skipped_and_next_one_serves(self):
        from agent import auxiliary_client as ac

        text_client = MagicMock(name="text-client")
        vision_client = MagicMock(name="vision-client")

        def _resolve(entry):
            model = entry.get("model")
            if model == "text-only-model":
                return text_client, model
            return vision_client, model

        with patch.object(
            ac, "_get_auxiliary_task_config", return_value=self._chain(
                "text-only-model", "vision-model"
            )
        ), patch.object(ac, "_resolve_fallback_entry", side_effect=_resolve), \
           patch.object(
               ac,
               "_main_model_supports_vision",
               side_effect=lambda provider, model: model == "vision-model",
           ):
            client, model, label = ac._try_configured_fallback_chain(
                "vision", "openai-api"
            )

        assert client is vision_client
        assert model == "vision-model"
        assert "fallback_chain[1]" in label

    def test_non_vision_task_accepts_a_text_only_model(self):
        """The screen is vision-only; compression must still accept text models."""
        from agent import auxiliary_client as ac

        text_client = MagicMock(name="text-client")

        with patch.object(
            ac, "_get_auxiliary_task_config",
            return_value=self._chain("text-only-model"),
        ), patch.object(
            ac, "_resolve_fallback_entry",
            side_effect=lambda entry: (text_client, entry.get("model")),
        ), patch.object(
            ac, "_main_model_supports_vision", return_value=False
        ) as vision_probe:
            client, model, label = ac._try_configured_fallback_chain(
                "compression", "openai-api"
            )

        assert client is text_client
        assert model == "text-only-model"
        vision_probe.assert_not_called()

    def test_all_candidates_text_only_yields_no_fallback(self):
        from agent import auxiliary_client as ac

        with patch.object(
            ac, "_get_auxiliary_task_config",
            return_value=self._chain("text-a", "text-b"),
        ), patch.object(
            ac, "_resolve_fallback_entry",
            side_effect=lambda entry: (MagicMock(), entry.get("model")),
        ), patch.object(
            ac, "_main_model_supports_vision", return_value=False
        ):
            result = ac._try_configured_fallback_chain("vision", "openai-api")

        assert result == (None, None, "")