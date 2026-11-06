"""Regression test: auxiliary tasks must forward per-provider ``extra_headers``.

A named custom provider may declare ``extra_headers`` in config.yaml (e.g. an
empty ``Authorization`` for a keyless gateway, or a Cloudflare Access service
token).  The main-agent path already forwards them via
``apply_custom_provider_extra_headers_to_client_kwargs``; the auxiliary
resolution path did not, so an aux task routed to such a provider sent the
SDK's own auth header instead and got HTTP 401.

The custom provider resolution in ``resolve_provider_client`` must therefore
merge ``custom_entry["extra_headers"]`` into the client's ``default_headers``.
"""

from unittest.mock import MagicMock, patch

import logging

import pytest


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    openamer_home = tmp_path / ".openamer"
    openamer_home.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(openamer_home))
    (openamer_home / "config.yaml").write_text("model:\n  default: test-model\n")


def _write_config(tmp_path, config_dict):
    import yaml
    (tmp_path / ".openamer" / "config.yaml").write_text(yaml.dump(config_dict))


class TestAuxiliaryNamedCustomProviderExtraHeaders:
    """``extra_headers`` must reach the client built for a named custom provider."""

    def test_extra_headers_are_forwarded_to_client(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "custom:kilo-gateway"},
            "custom_providers": [{
                "name": "Kilo Gateway",
                "base_url": "https://ai-gateway.kilo.ai/api/v1",
                "model": "kilo-auto/free",
                "extra_headers": {"Authorization": ""},
            }],
        })

        from agent.auxiliary_client import resolve_provider_client

        captured = {}

        def _fake_client(*, api_key, base_url, **kwargs):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            captured.update(kwargs)
            return MagicMock()

        with patch("agent.auxiliary_client._create_openai_client", side_effect=_fake_client):
            client, model = resolve_provider_client(
                "custom:kilo-gateway", model="kilo-auto/free"
            )

        assert client is not None
        assert model == "kilo-auto/free"
        headers = captured.get("default_headers") or {}
        assert "Authorization" in headers, (
            "per-provider extra_headers must be forwarded to the aux client"
        )
        assert headers["Authorization"] == ""

    def test_extra_headers_merge_with_existing_default_headers(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "custom:beans"},
            "custom_providers": [{
                "name": "beans",
                "base_url": "http://localhost:9999/v1",
                "extra_headers": {"X-Provider": "yes"},
            }],
        })

        from agent.auxiliary_client import resolve_provider_client

        captured = {}

        def _fake_client(*, api_key, base_url, **kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch("agent.auxiliary_client._create_openai_client", side_effect=_fake_client):
            resolve_provider_client("custom:beans", model="beans-model")

        headers = captured.get("default_headers") or {}
        assert headers.get("X-Provider") == "yes"

    def test_provider_without_extra_headers_is_unchanged(self, tmp_path):
        """A provider declaring no extra_headers must not gain any."""
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "custom:beans"},
            "custom_providers": [{
                "name": "beans",
                "base_url": "http://localhost:9999/v1",
            }],
        })

        from agent.auxiliary_client import resolve_provider_client

        captured = {}

        def _fake_client(*, api_key, base_url, **kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch("agent.auxiliary_client._create_openai_client", side_effect=_fake_client):
            resolve_provider_client("custom:beans", model="beans-model")

        assert not (captured.get("default_headers") or {})

    def test_keyless_provider_does_not_warn_about_401(self, tmp_path, caplog):
        """A provider whose extra_headers override Authorization must not be
        warned about as if it were going to 401 — the override replaces the
        placeholder token, so the request is valid."""
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "custom:kilo-gateway"},
            "custom_providers": [{
                "name": "Kilo Gateway",
                "base_url": "https://ai-gateway.kilo.ai/api/v1",
                "extra_headers": {"Authorization": ""},
            }],
        })

        from agent.auxiliary_client import resolve_provider_client

        with patch("agent.auxiliary_client._create_openai_client", return_value=MagicMock()):
            with caplog.at_level(logging.WARNING, logger="agent.auxiliary_client"):
                resolve_provider_client("custom:kilo-gateway", model="kilo-auto/free")

        assert not [
            rec for rec in caplog.records
            if rec.levelno >= logging.WARNING and "no resolvable" in rec.getMessage()
        ]

    def test_keyless_provider_without_auth_override_still_warns(self, tmp_path, caplog):
        """Without an Authorization override the placeholder token is sent and
        the provider really would 401 — the warning must stay."""
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "custom:beans"},
            "custom_providers": [{
                "name": "beans",
                "base_url": "http://localhost:9999/v1",
                "extra_headers": {"X-Custom": "v"},
            }],
        })

        from agent.auxiliary_client import resolve_provider_client

        with patch("agent.auxiliary_client._create_openai_client", return_value=MagicMock()):
            with caplog.at_level(logging.WARNING, logger="agent.auxiliary_client"):
                resolve_provider_client("custom:beans", model="beans-model")

        assert [
            rec for rec in caplog.records
            if rec.levelno >= logging.WARNING and "no resolvable" in rec.getMessage()
        ]
