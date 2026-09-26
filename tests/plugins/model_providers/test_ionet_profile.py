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

    def test_fetch_models_composes_endpoint_auth_and_parse(self, ionet_profile):
        """Live discovery: {base_url}/models with Bearer auth, OpenAI response shape.

        The profile inherits the base implementation, so this pins the contract
        the io.net endpoint relies on: URL composition (no double path join),
        the Authorization header, and org/name id passthrough.
        """
        import io
        import json as _json
        from unittest.mock import patch

        captured = {}

        class _FakeResponse:
            def __init__(self, payload: str):
                self._buf = io.BytesIO(payload.encode())

            def read(self):
                return self._buf.read()

        class _FakeCtx:
            def __init__(self, resp):
                self._resp = resp

            def __enter__(self):
                return self._resp

            def __exit__(self, *exc):
                return False

        def _fake_open(req, timeout=None):
            captured["url"] = req.get_full_url()
            captured["auth"] = req.get_header("Authorization")
            captured["ua"] = req.get_header("User-agent")
            payload = _json.dumps(
                {
                    "data": [
                        {"id": "meta-llama/Llama-3.3-70B-Instruct"},
                        {"id": "deepseek-ai/DeepSeek-V4.1-Flash"},
                        {"object": "model"},  # entries without id are skipped
                    ]
                }
            )
            return _FakeCtx(_FakeResponse(payload))

        with patch(
            "openamer_cli.urllib_security.open_credentialed_url", side_effect=_fake_open
        ):
            models = ionet_profile.fetch_models(
                api_key="test-key",
                base_url="https://example.test/api/v1",
            )

        assert captured["url"] == "https://example.test/api/v1/models"
        assert captured["auth"] == "Bearer test-key"
        assert models == [
            "meta-llama/Llama-3.3-70B-Instruct",
            "deepseek-ai/DeepSeek-V4.1-Flash",
        ]

    def test_fetch_models_trailing_slash_and_failure(self, ionet_profile):
        """A trailing-slash base URL still composes one /models, and fetch
        failures return None so callers fall back to the static list."""
        import json as _json
        from unittest.mock import patch

        class _FakeResponse:
            def __init__(self, payload: str):
                import io

                self._buf = io.BytesIO(payload.encode())

            def read(self):
                return self._buf.read()

        class _FakeCtx:
            def __init__(self, resp):
                self._resp = resp

            def __enter__(self):
                return self._resp

            def __exit__(self, *exc):
                return False

        with patch(
            "openamer_cli.urllib_security.open_credentialed_url",
            side_effect=lambda req, timeout=None: _FakeCtx(
                _FakeResponse(_json.dumps({"data": [{"id": "zai-org/GLM-5.3"}]}))
            ),
        ):
            models = ionet_profile.fetch_models(
                api_key="test-key",
                base_url="https://example.test/api/v1/",
            )
        assert models == ["zai-org/GLM-5.3"]

        with patch(
            "openamer_cli.urllib_security.open_credentialed_url",
            side_effect=RuntimeError("network down"),
        ):
            assert ionet_profile.fetch_models(api_key="k", base_url="https://x.test") is None


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
