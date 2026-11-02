"""Tests for Ollama Cloud cost pricing (DIR: cost visibility).

Measured 2026-11-02 on the live install: 95.6 % of all Ollama Cloud spend was
booked as ``cost_status='unknown'`` because ``resolve_billing_route()`` had no
branch for the ``ollama-cloud`` provider, so every such session was priced at
``$0.00``.  These tests pin the two halves of the fix:

1. ``resolve_billing_route()`` recognises ``ollama-cloud`` (and its
   ``custom:ollama-cloud`` custom-provider spelling) as a billable route with
   its own billing mode instead of falling through to ``unknown``.
2. The Ollama Cloud price table resolves real rates — from the live
   models.dev catalog, with the official-docs snapshot as the offline
   fallback — so a token count turns into a non-zero cost.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agent.usage_pricing import (
    CanonicalUsage,
    estimate_usage_cost,
    get_pricing_entry,
    has_known_pricing,
    resolve_billing_route,
)


@pytest.fixture(autouse=True)
def offline_catalog(monkeypatch):
    from agent.usage_pricing import _ollama_cloud_catalog
    _ollama_cloud_catalog.cache_clear()
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    yield
    _ollama_cloud_catalog.cache_clear()


# =============================================================================
# Route resolution
# =============================================================================


class TestOllamaCloudRouteResolution:
    """``ollama-cloud`` must not fall through to the ``unknown`` billing mode."""

    def test_ollama_cloud_provider_is_billable(self) -> None:
        route = resolve_billing_route("deepseek-v4.1-flash", provider="ollama-cloud")
        assert route.provider == "ollama-cloud"
        assert route.billing_mode != "unknown", (
            "ollama-cloud is a metered provider — its billing mode must be a "
            "priced mode, not 'unknown'"
        )
        assert route.model == "deepseek-v4.1-flash"

    def test_custom_ollama_cloud_provider_is_billable(self) -> None:
        """The custom-provider spelling used by the model picker."""
        route = resolve_billing_route(
            "deepseek-v4.1-flash", provider="custom:ollama-cloud"
        )
        assert route.billing_mode != "unknown"

    def test_ollama_cloud_base_url_is_recognised(self) -> None:
        """A route identified only by its base URL must still be priced."""
        route = resolve_billing_route(
            "deepseek-v4.1-flash",
            provider=None,
            base_url="https://ollama.com/v1",
        )
        assert route.provider == "ollama-cloud"
        assert route.billing_mode != "unknown"

    def test_local_ollama_stays_free(self) -> None:
        """Regression guard: local Ollama must NOT become a billable route."""
        route = resolve_billing_route(
            "qwen3:8b",
            provider="custom",
            base_url="http://127.0.0.1:11434",
        )
        assert route.billing_mode != "ollama_cloud_pricing"


# =============================================================================
# Price table
# =============================================================================


class TestOllamaCloudPricingEntry:
    """A known Ollama Cloud model must resolve to a price entry."""

    def test_known_model_has_pricing(self) -> None:
        assert has_known_pricing(
            "deepseek-v4.1-flash", provider="ollama-cloud"
        ), "deepseek-v4.1-flash is an Ollama Cloud model with published rates"

    def test_entry_has_input_and_output_rates(self) -> None:
        entry = get_pricing_entry("deepseek-v4.1-flash", provider="ollama-cloud")
        assert entry is not None
        assert entry.input_cost_per_million is not None
        assert entry.output_cost_per_million is not None
        assert entry.input_cost_per_million > 0
        assert entry.output_cost_per_million > 0

    def test_tagged_model_id_resolves(self) -> None:
        """Ollama Cloud model ids carry a date tag (``deepseek-v4.1-flash:1017``)."""
        entry = get_pricing_entry(
            "deepseek-v4.1-flash:1017", provider="ollama-cloud"
        )
        assert entry is not None
        assert entry.input_cost_per_million is not None
        assert entry.output_cost_per_million is not None

    def test_unknown_model_has_no_pricing(self) -> None:
        """A model nobody publishes rates for must not invent a price."""
        entry = get_pricing_entry(
            "definitely-not-a-real-model-xyz", provider="ollama-cloud"
        )
        assert entry is None or entry.input_cost_per_million is None


# =============================================================================
# Cost estimation
# =============================================================================


class TestOllamaCloudCostEstimation:
    """The end-to-end path: usage in, USD out."""

    def test_usage_yields_nonzero_cost(self) -> None:
        usage = CanonicalUsage(input_tokens=1_000_000, output_tokens=100_000)
        result = estimate_usage_cost(
            "deepseek-v4.1-flash", usage, provider="ollama-cloud"
        )
        assert result.status != "unknown", (
            "Ollama Cloud usage must not be booked as unknown — that is what "
            "made the real spend invisible"
        )
        assert result.amount_usd is not None
        assert result.amount_usd > 0

    def test_cost_matches_published_rate(self) -> None:
        """Off-peak published rate: $0.15/M in, $0.60/M out."""
        usage = CanonicalUsage(input_tokens=1_000_000, output_tokens=1_000_000)
        result = estimate_usage_cost(
            "deepseek-v4.1-flash", usage, provider="ollama-cloud"
        )
        assert result.amount_usd is not None
        # Accept either the off-peak (0.15/0.60) or the peak (0.30/1.20)
        # published rate — both are legitimate, the point is that a rate is
        # applied instead of zero.
        assert result.amount_usd in (
            Decimal("0.75"),
            Decimal("1.50"),
        ), f"unexpected cost {result.amount_usd}"

    def test_cache_read_tokens_are_not_charged_as_input(self) -> None:
        """Cached input is billed at the cache rate, not the input rate."""
        usage = CanonicalUsage(
            input_tokens=0,
            output_tokens=1_000_000,
            cache_read_tokens=1_000_000,
        )
        result = estimate_usage_cost(
            "deepseek-v4.1-flash", usage, provider="ollama-cloud"
        )
        assert result.amount_usd is not None
        # Off-peak: 0.60 (output) + 0.003 (cache read) = 0.603
        # Peak:     1.20 (output) + 0.006 (cache read) = 1.206
        assert result.amount_usd in (
            Decimal("0.603"),
            Decimal("1.206"),
        ), f"unexpected cost {result.amount_usd}"

    def test_zero_usage_is_zero_cost(self) -> None:
        result = estimate_usage_cost(
            "deepseek-v4.1-flash",
            CanonicalUsage(input_tokens=0, output_tokens=0),
            provider="ollama-cloud",
        )
        assert result.amount_usd == Decimal("0")

    def test_minimax_m3_1_flash_is_priced(self) -> None:
        """The other model this install actually ran: minimax-m3.1-flash."""
        usage = CanonicalUsage(input_tokens=1_000_000, output_tokens=1_000_000)
        result = estimate_usage_cost(
            "minimax-m3.1-flash", usage, provider="ollama-cloud"
        )
        assert result.status != "unknown"
        assert result.amount_usd is not None
        assert result.amount_usd > 0


# =============================================================================
# Provider isolation
# =============================================================================


class TestOllamaCloudPricingIsolation:
    """Pricing one provider must not leak into another's accounting."""

    def test_local_ollama_remains_unknown_not_billed(self) -> None:
        """Local Ollama is free — it must not be priced as a cloud route."""
        usage = CanonicalUsage(input_tokens=1_000_000, output_tokens=1_000_000)
        result = estimate_usage_cost(
            "qwen3:8b",
            usage,
            provider="custom",
            base_url="http://127.0.0.1:11434",
        )
        assert result.amount_usd is None or result.amount_usd == Decimal("0")

    def test_openai_codex_stays_subscription_included(self) -> None:
        result = estimate_usage_cost(
            "gpt-6.1-sol",
            CanonicalUsage(input_tokens=1_000_000, output_tokens=1_000_000),
            provider="openai-codex",
        )
        assert result.status == "included"
        assert result.amount_usd == Decimal("0")


@pytest.mark.parametrize("provider,url", [
    ("custom:ollama-cloud-lookalike", None),
    ("custom", "https://ollama.com.attacker.invalid/v1"),
])
def test_non_cloud_routes_do_not_match(provider, url):
    assert resolve_billing_route("deepseek-v4.1-flash", provider, url).provider != "ollama-cloud"


def test_live_catalog_units_cache_and_cloud_suffix(monkeypatch):
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {
        "ollama-cloud": {"models": {"example:cloud": {
            "cost": {"input": 2, "output": 8, "cache_read": 0}}}}})
    result = estimate_usage_cost("example", CanonicalUsage(
        input_tokens=1_000_000, output_tokens=1_000_000, cache_read_tokens=1_000_000),
        provider="ollama-cloud")
    assert result.amount_usd == Decimal("10")
    assert result.source == "provider_models_api"


def test_offline_failure_is_negatively_cached(monkeypatch):
    calls = []
    def offline():
        calls.append(1)
        raise OSError("offline")
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", offline)
    for model in ("deepseek-v4.1-flash", "minimax-m3.1-flash", "unknown"):
        get_pricing_entry(model, provider="ollama-cloud")
    assert len(calls) == 1


@pytest.mark.parametrize("model", ["gpt-oss:120b", "gpt-oss:20b"])
def test_size_tags_remain_part_of_model_id(model):
    entry = get_pricing_entry(model, provider="ollama-cloud")
    assert entry is not None
    assert entry.input_cost_per_million > 0

