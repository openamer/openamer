"""Regression test: an auto-routed VISION aux call must reach the fallback chain.

Live failure (2026-11-06, this Windows host)
----------------------------------------------
The OpenAI primary was out of credits (HTTP 429 "no credits remaining").
An auxiliary VISION call was routed by auto-detection, which resolves the
main provider (openai-api) and then narrows ``resolved_provider`` from the
``"auto"`` sentinel to that concrete backend.

The fallback gate computes::

    is_auto = resolved_provider in {"auto", "", None}

so after the narrowing ``is_auto`` was False. An auto-routed vision call that
hit a payment error therefore SKIPPED the configured fallback chain and only
tried the "main agent model" safety net — which returns nothing precisely
when the main provider IS the failed one. The auxiliary task then died with::

    Auxiliary vision (async): payment error on openai-api and all fallbacks
    exhausted (fallback_chain + main agent model). Raising original error.

even though a healthy, reachable fallback was configured.

The fix keeps the auto-ness as a separate flag (``vision_auto_requested``) so
the fallback layers behave the same for auto-routed vision calls as for every
other auxiliary task.

These tests pin the contract behaviourally: an auto-routed vision call that
hits a capacity error MUST consult the fallback chain. They deliberately do
not assert on internal variable names, so a future refactor that keeps the
behaviour passes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class _PaymentError(Exception):
    """Stand-in for an HTTP 402/429 "out of credits" provider error."""


def _make_payment_error() -> Exception:
    """Build an error the payment detector recognises.

    ``_is_payment_error`` inspects the exception class name and message, so
    the stand-in has to look like a real OpenAI quota error.
    """
    err = _PaymentError(
        "Error code: 429 - {'error': {'message': "
        "\"You have no credits remaining. Add credits to continue using the "
        "API at https://platform.openai.com/settings/organization/billing/.\", "
        "'type': 'insufficient_quota', 'param': None, "
        "'code': 'credit_balance_exhausted'}}"
    )
    return err


@pytest.fixture(autouse=True)
def _clear_unhealthy_cache():
    """The unhealthy-provider cache is process-global; keep tests isolated."""
    from agent import auxiliary_client as ac

    ac._aux_unhealthy_until.clear()
    ac._aux_unhealthy_logged_at.clear()
    yield
    ac._aux_unhealthy_until.clear()
    ac._aux_unhealthy_logged_at.clear()


def _vision_messages() -> list:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this picture?"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,iVBORw0KGgo="},
                },
            ],
        }
    ]


def _fake_response(text: str = "a red pixel") -> MagicMock:
    resp = MagicMock()
    msg = MagicMock()
    msg.content = text
    resp.choices = [MagicMock(message=msg)]
    return resp


# ── The contract ────────────────────────────────────────────────────────────


def test_auto_vision_payment_error_reaches_main_fallback_chain():
    """Auto-routed vision + payment error -> the TOP-LEVEL fallback chain runs.

    This is the live bug. The fallback order is:

      1. user-configured per-task ``fallback_chain``
      2. (auto only) top-level ``fallback_providers`` / ``fallback_model``
      3. (auto only) built-in auxiliary discovery chain
      4. (explicit providers only) main-agent-model safety net

    Because the vision resolver narrows ``resolved_provider`` from the
    ``"auto"`` sentinel to the concrete backend, the gate evaluated
    ``is_auto`` as False — so an auto-routed vision call skipped layers 2 and
    3 and jumped to layer 4, which is empty precisely when the main provider
    IS the failed one. The auxiliary call then died with "all fallbacks
    exhausted" even though the user's own ``fallback_providers`` were
    configured and reachable.

    Layer 2 is therefore the discriminating observation: it must run for an
    auto-routed vision call, and it must NOT run for an explicitly pinned
    one.
    """
    from agent import auxiliary_client as ac

    primary_client = MagicMock()
    primary_client.base_url = "https://api.openai.com/v1"
    primary_client.chat.completions.create.side_effect = _make_payment_error()

    fallback_client = MagicMock()
    fallback_client.base_url = "https://ollama.com/v1"
    fallback_client.chat.completions.create.return_value = _fake_response()

    with patch.object(ac, "_resolve_task_provider_model",
                      return_value=("auto", None, None, None, None)), \
         patch.object(ac, "resolve_vision_provider_client",
                      return_value=("openai-api", primary_client, "gpt-6.1-sol")), \
         patch.object(ac, "_try_configured_fallback_chain",
                      return_value=(None, None, "")), \
         patch.object(ac, "_try_main_fallback_chain",
                      return_value=(fallback_client, "fb-model", "ollama-cloud")) as main_chain, \
         patch.object(ac, "_try_payment_fallback",
                      return_value=(None, None, "")), \
         patch.object(ac, "_try_main_agent_model_fallback",
                      return_value=(None, None, "")) as main_net, \
         patch.object(ac, "_get_auxiliary_task_config", return_value={}), \
         patch.object(ac, "_get_task_extra_body", return_value={}), \
         patch.object(ac, "_build_call_kwargs",
                      return_value={"model": "gpt-6.1-sol", "messages": []}):
        result = ac.call_llm(task="vision", messages=_vision_messages())

    # Layer 2 ran — the regression guard.
    main_chain.assert_called_once()
    # The auto path does not use the explicit-provider-only safety net.
    main_net.assert_not_called()
    # The fallback's response is what the caller receives.
    assert result.choices[0].message.content == "a red pixel"


def test_auto_vision_reaches_builtin_discovery_chain():
    """Layer 3 (built-in discovery) is also auto-only and must be reachable."""
    from agent import auxiliary_client as ac

    primary_client = MagicMock()
    primary_client.base_url = "https://api.openai.com/v1"
    primary_client.chat.completions.create.side_effect = _make_payment_error()

    fallback_client = MagicMock()
    fallback_client.base_url = "https://openrouter.ai/api/v1"
    fallback_client.chat.completions.create.return_value = _fake_response("or ok")

    with patch.object(ac, "_resolve_task_provider_model",
                      return_value=("auto", None, None, None, None)), \
         patch.object(ac, "resolve_vision_provider_client",
                      return_value=("openai-api", primary_client, "gpt-6.1-sol")), \
         patch.object(ac, "_try_configured_fallback_chain",
                      return_value=(None, None, "")), \
         patch.object(ac, "_try_main_fallback_chain",
                      return_value=(None, None, "")), \
         patch.object(ac, "_try_payment_fallback",
                      return_value=(fallback_client, "or-model", "openrouter")) as discovery, \
         patch.object(ac, "_get_auxiliary_task_config", return_value={}), \
         patch.object(ac, "_get_task_extra_body", return_value={}), \
         patch.object(ac, "_build_call_kwargs",
                      return_value={"model": "gpt-6.1-sol", "messages": []}):
        result = ac.call_llm(task="vision", messages=_vision_messages())

    discovery.assert_called_once()
    assert result.choices[0].message.content == "or ok"


def test_explicit_vision_provider_still_respects_explicit_choice():
    """An EXPLICIT vision provider keeps its own (non-auto) fallback order.

    The fix must not widen the behaviour for users who pinned a provider:
    for an explicit provider the main-agent net is the right last resort,
    and the auto-only layers must not silently take over.
    """
    from agent import auxiliary_client as ac

    primary_client = MagicMock()
    primary_client.base_url = "https://api.openai.com/v1"
    primary_client.chat.completions.create.side_effect = _make_payment_error()

    with patch.object(ac, "_resolve_task_provider_model",
                      return_value=("openai-api", "gpt-6.1-sol", None, None, None)), \
         patch.object(ac, "resolve_vision_provider_client",
                      return_value=("openai-api", primary_client, "gpt-6.1-sol")), \
         patch.object(ac, "_try_configured_fallback_chain",
                      return_value=(None, None, "")) as configured_chain, \
         patch.object(ac, "_try_main_agent_model_fallback",
                      return_value=(None, None, "")) as main_net, \
         patch.object(ac, "_try_main_fallback_chain",
                      return_value=(None, None, "")) as main_chain, \
         patch.object(ac, "_try_payment_fallback",
                      return_value=(None, None, "")) as discovery, \
         patch.object(ac, "_get_auxiliary_task_config", return_value={}), \
         patch.object(ac, "_get_task_extra_body", return_value={}), \
         patch.object(ac, "_build_call_kwargs",
                      return_value={"model": "gpt-6.1-sol", "messages": []}):
        with pytest.raises(Exception):
            ac.call_llm(task="vision", messages=_vision_messages())

    # Explicit provider: the main-agent net is consulted (last resort),
    # the auto-only layers are NOT.
    main_net.assert_called_once()
    main_chain.assert_not_called()
    discovery.assert_not_called()
    configured_chain.assert_called_once()


# ── A failing candidate must not abort the chain ───────────────────────────


def test_fallback_candidate_failure_does_not_abort_chain():
    """A candidate that fails with a capacity error is SKIPPED, not fatal.

    Live case (2026-11-06): the first fallback candidate was a text-only
    model that answered the image request with a provider-side 500. That
    error propagated out of the chain and killed the auxiliary task, even
    though the next candidate was vision-capable and healthy.

    A 5xx from one candidate is a property of THAT candidate, not of the
    request — the next candidate may serve it fine.
    """
    from agent import auxiliary_client as ac

    class _ServerError(Exception):
        pass

    err = _ServerError(
        "Error code: 500 - {'error': {'message': 'Internal Server Error'}}"
    )
    err.status_code = 500

    failing_client = MagicMock()
    failing_client.base_url = "https://ollama.com/v1"
    failing_client.chat.completions.create.side_effect = err

    with patch.object(ac, "_build_call_kwargs",
                      return_value={"model": "m", "messages": []}):
        resp = ac._call_fallback_candidate_sync(
            failing_client, "m", "fallback_chain[0](ollama-cloud)",
            task="vision", messages=[], temperature=None, max_tokens=None,
            tools=None, effective_timeout=30.0, effective_extra_body={},
            reasoning_config=None,
        )

    # None means "skip this candidate, continue the chain" — NOT an exception.
    assert resp is None


def test_fallback_candidate_malformed_request_still_raises():
    """A 400 no candidate can satisfy stays fatal.

    A malformed request fails identically on every candidate, so aborting
    early is correct — silently walking the whole chain would waste a
    request per candidate for the same outcome.
    """
    from agent import auxiliary_client as ac

    class _BadRequest(Exception):
        pass

    err = _BadRequest("Error code: 400 - invalid request")
    err.status_code = 400

    failing_client = MagicMock()
    failing_client.base_url = "https://ollama.com/v1"
    failing_client.chat.completions.create.side_effect = err

    with patch.object(ac, "_build_call_kwargs",
                      return_value={"model": "m", "messages": []}):
        with pytest.raises(_BadRequest):
            ac._call_fallback_candidate_sync(
                failing_client, "m", "fallback_chain[0](ollama-cloud)",
                task="vision", messages=[], temperature=None, max_tokens=None,
                tools=None, effective_timeout=30.0, effective_extra_body={},
                reasoning_config=None,
            )


def test_vision_main_fallback_chain_skips_text_only_candidate():
    """The TOP-LEVEL fallback chain must apply the same vision-capability screen.

    Without it, the main chain can select a text-only model for a vision
    request; that model answers with a provider-side 500 and — before the
    candidate-failure guard — killed the whole auxiliary task.
    """
    from agent import auxiliary_client as ac

    text_only_client = MagicMock()
    vision_client = MagicMock()

    chain = [
        {"provider": "ollama-cloud", "model": "text-only-model"},
        {"provider": "openrouter", "model": "vision-model"},
    ]

    def _fake_resolve(entry):
        if entry["model"] == "text-only-model":
            return text_only_client, "text-only-model"
        return vision_client, "vision-model"

    with patch("openamer_cli.config.load_config", return_value={}), \
         patch("openamer_cli.fallback_config.get_fallback_chain",
               return_value=chain), \
         patch.object(ac, "_resolve_fallback_entry", side_effect=_fake_resolve), \
         patch.object(ac, "_main_model_supports_vision",
                      side_effect=lambda p, m: m == "vision-model"):
        client, model, label = ac._try_main_fallback_chain(
            "vision", "openai-api", reason="payment error")

    assert client is vision_client
    assert model == "vision-model"
    assert "openrouter" in label


# ── Vision-capability screening of fallback candidates ─────────────────────


def test_vision_fallback_skips_text_only_candidate():
    """A text-only fallback candidate must be skipped, not called.

    A text-only model answers a vision request with a provider-side 500
    ("unknown variant `image_url`") instead of a clean error, which aborts
    the whole auxiliary call. The chain must walk past it.
    """
    from agent import auxiliary_client as ac

    text_only_client = MagicMock()
    vision_client = MagicMock()
    vision_client.chat.completions.create.return_value = _fake_response("vision ok")

    entries = [
        {"provider": "ollama-cloud", "model": "text-only-model"},
        {"provider": "openrouter", "model": "vision-model"},
    ]

    def _fake_resolve(entry):
        if entry["model"] == "text-only-model":
            return text_only_client, "text-only-model"
        return vision_client, "vision-model"

    with patch.object(ac, "_get_auxiliary_task_config",
                      return_value={"fallback_chain": entries}), \
         patch.object(ac, "_resolve_fallback_entry",
                      side_effect=_fake_resolve), \
         patch.object(ac, "_main_model_supports_vision",
                      side_effect=lambda p, m: m == "vision-model"):
        client, model, label = ac._try_configured_fallback_chain(
            "vision", "openai-api", reason="payment error")

    assert client is vision_client
    assert model == "vision-model"
    assert label == "fallback_chain[1](openrouter)"
    # The text-only candidate was never called.
    text_only_client.chat.completions.create.assert_not_called()
