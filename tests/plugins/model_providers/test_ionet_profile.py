"""Unit tests for the IO Intelligence (io.net) provider profile."""

from __future__ import annotations

import pytest


@pytest.fixture
def ionet_profile():
    """Resolve the registered IO Intelligence profile via the provider registry.

    Importing ``model_tools`` triggers plugin discovery, which registers the
    profile. Going through ``get_provider_profile`` keeps the test honest: if
    the registered class is ever swapped for a plain ``ProviderProfile`` the
    ``build_extra_body`` assertion below collapses.
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

    def test_tool_choice_auto_on_every_request(self, ionet_profile):
        """The profile pins tool_choice=auto because the endpoint default is none."""
        assert ionet_profile.build_extra_body() == {"tool_choice": "auto"}

    def test_aliases_resolve(self, ionet_profile):
        import providers

        assert providers.get_provider_profile("io-net") is ionet_profile
        assert providers.get_provider_profile("io-intelligence") is ionet_profile
