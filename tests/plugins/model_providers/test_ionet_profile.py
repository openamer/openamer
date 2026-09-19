"""Unit tests for the IO Intelligence (io.net) provider profile."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def ionet_profile():
    """Resolve the registered IO Intelligence profile via the provider registry.

    Importing ``model_tools`` triggers plugin discovery, which registers the
    profile. Going through ``get_provider_profile`` keeps the test honest: if
    the registered class is ever swapped for a plain ``ProviderProfile`` the
    ``build_extra_body`` assertions below collapse.
    """
    import model_tools  # noqa: F401
    import providers

    profile = providers.get_provider_profile("ionet")
    assert profile is not None, "ionet provider profile must be registered"
    return profile


class TestIonetProfile:
    def test_wire_shape(self, ionet_profile):
        """Chat Completions dialect, OpenAI-compatible endpoint, key env var."""
        assert ionet_profile.api_mode == "chat_completions"
        assert ionet_profile.base_url == "https://api.intelligence.io.solutions/api/v1"
        assert "IONET_API_KEY" in ionet_profile.env_vars

    def test_tool_choice_auto_only_when_tools_present(self, ionet_profile):
        """The profile pins tool_choice=auto because the endpoint default is none.

        Strict OpenAI-compatible backends reject tool_choice without a tools
        list, so the override is emitted only for requests that carry tools —
        the auxiliary no-tools call sites (title generation, compression)
        must stay clean.
        """
        assert ionet_profile.build_extra_body(tools=[{"type": "function", "function": {}}]) == {
            "tool_choice": "auto"
        }
        assert ionet_profile.build_extra_body(tools=[]) == {}
        assert ionet_profile.build_extra_body() == {}

    def test_aliases_resolve(self, ionet_profile):
        import providers

        assert providers.get_provider_profile("io-net") is ionet_profile
        assert providers.get_provider_profile("io-intelligence") is ionet_profile

    def test_fetch_models_passthrough(self, ionet_profile):
        """Live discovery returns the endpoint's org/name ids unchanged."""
        from providers.base import ProviderProfile

        with patch.object(
            ProviderProfile,
            "fetch_models",
            return_value=["meta-llama/Llama-3.3-70B-Instruct", "deepseek-ai/DeepSeek-V4.1-Flash"],
        ):
            models = ionet_profile.fetch_models(
                api_key="test-key",
                base_url="https://api.intelligence.io.solutions/api/v1",
            )

        assert models == ["meta-llama/Llama-3.3-70B-Instruct", "deepseek-ai/DeepSeek-V4.1-Flash"]


class TestIonetTransportIntegration:
    """The tool_choice override rides the transport's extra_body path."""

    def _build(self, ionet_profile, tools):
        from agent.transports.chat_completions import ChatCompletionsTransport

        return ChatCompletionsTransport().build_kwargs(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[{"role": "user", "content": "ping"}],
            tools=tools,
            provider_profile=ionet_profile,
            base_url="https://api.intelligence.io.solutions/api/v1",
            provider_name="ionet",
        )

    def test_kwargs_carry_tool_choice_when_tools_offered(self, ionet_profile):
        tool = {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }
        kwargs = self._build(ionet_profile, [tool])

        assert kwargs["extra_body"] == {"tool_choice": "auto"}
        assert kwargs["tools"] == [tool]

    def test_kwargs_stay_clean_without_tools(self, ionet_profile):
        """Aux no-tools calls must not ship tool_choice (strict backends 400)."""
        kwargs = self._build(ionet_profile, None)

        assert "tool_choice" not in kwargs.get("extra_body", {})
        assert "tools" not in kwargs
