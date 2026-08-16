"""Regression tests for the OpenAmer Portal env-override bypassing the host
allowlist, mirroring the existing OPENAMER_INFERENCE_BASE_URL /
_ALLOWED_openamer_INFERENCE_HOSTS treatment.

Real incident (2026-07): a hosted agent provisioned by openamer-account-service
on the `staging` Vercel environment is stamped with
``OPENAMER_PORTAL_BASE_URL=https://portal.staging-openamer.com`` in its
container env (the documented dev/staging override), while its bootstrap
``auth.json`` ALSO persists ``portal_base_url`` to the same staging host.

Before this fix, ``resolve_openamer_access_token`` / ``resolve_openamer_runtime_
credentials`` read ``state.get("portal_base_url")`` FIRST via a plain ``or``
chain, so whenever the stored state had ANY value the env vars were never
even consulted — and whichever value won (state or env) was then run through
``_openamer_PORTAL_ALLOWED_HOSTS``, which only recognised the production host.
The staging host was silently rewritten back to prod on every refresh, so a
staging-issued refresh token got replayed against the PROD token endpoint.
Prod correctly rejected that with ``invalid_grant``, which triggered
``_quarantine_openamer_oauth_state`` and wiped the entire credential pool.

The correct fix (mirroring ``_openamer_inference_env_override()``): the env
override is a TRUSTED value the operator/deployment set themselves — it must
win outright (even over a stored value) and bypass the allowlist entirely.
The allowlist exists only to reject an untrusted NETWORK-provided value
(a poisoned portal_base_url written to auth.json by a compromised Portal
response), never a value the operator explicitly configured.
"""

from __future__ import annotations

import json
import logging

from openamer_cli.auth import (
    DEFAULT_openamer_PORTAL_URL,
    _openamer_PORTAL_ALLOWED_HOSTS,
    _openamer_portal_env_override,
)


class TestPortalEnvOverrideHelper:
    def test_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("OPENAMER_PORTAL_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAMER_PORTAL_BASE_URL", raising=False)
        assert _openamer_portal_env_override() is None

    def test_openamer_portal_base_url_wins(self, monkeypatch):
        monkeypatch.setenv(
            "OPENAMER_PORTAL_BASE_URL", "https://portal.staging-openamer.com/"
        )
        monkeypatch.delenv("OPENAMER_PORTAL_BASE_URL", raising=False)
        assert (
            _openamer_portal_env_override() == "https://portal.staging-openamer.com"
        )

    def test_openamer_portal_base_url_used_as_fallback(self, monkeypatch):
        monkeypatch.delenv("OPENAMER_PORTAL_BASE_URL", raising=False)
        monkeypatch.setenv(
            "OPENAMER_PORTAL_BASE_URL", "https://portal.staging-openamer.com"
        )
        assert (
            _openamer_portal_env_override() == "https://portal.staging-openamer.com"
        )

    def test_env_override_not_gated_by_allowlist(self, monkeypatch):
        """The whole point: an env-set staging host is NOT in
        _openamer_PORTAL_ALLOWED_HOSTS, and the helper must return it anyway —
        gating happens only for network-provenance values."""
        monkeypatch.setenv(
            "OPENAMER_PORTAL_BASE_URL", "https://portal.staging-openamer.com"
        )
        assert "portal.staging-openamer.com" not in _openamer_PORTAL_ALLOWED_HOSTS
        assert (
            _openamer_portal_env_override() == "https://portal.staging-openamer.com"
        )


class TestResolveAccessTokenEnvOverrideWins:
    """End-to-end: resolve_openamer_access_token must use the env override for
    the refresh call, bypassing the allowlist, even when state also has a
    portal_base_url set (the exact incident shape)."""

    def _write_auth_file(self, tmp_path, *, stored_portal_url):
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(
            json.dumps(
                {
                    "version": 1,
                    "active_provider": "openamer",
                    "providers": {
                        "openamer": {
                            "portal_base_url": stored_portal_url,
                            "access_token": "expired-access",
                            "refresh_token": "staging-refresh",
                            "client_id": "openamer-cli-vps",
                            "expires_at": "2000-01-01T00:00:00+00:00",
                        }
                    },
                }
            )
        )
        return auth_file

    def _run_and_capture(self, monkeypatch, auth):
        seen_portal_urls = []

        def _fake_refresh(*, client, portal_base_url, client_id, refresh_token):
            seen_portal_urls.append(portal_base_url)
            return {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            }

        monkeypatch.setattr(auth, "_refresh_access_token", _fake_refresh)

        caplog_records = []
        logger = logging.getLogger("openamer_cli.auth")
        handler = logging.Handler()
        handler.emit = lambda record: caplog_records.append(record.getMessage())
        logger.addHandler(handler)
        try:
            auth.resolve_openamer_access_token()
        finally:
            logger.removeHandler(handler)
        return seen_portal_urls, caplog_records

    def test_env_override_wins_even_with_staging_state_stored(
        self, monkeypatch, tmp_path
    ):
        """The real incident: state ALSO has the staging host stored (from
        a prior OPENAMER_AUTH_JSON_BOOTSTRAP seed), and the env var is set to
        the same staging host. Both must resolve to staging, and the
        allowlist-rejection warning must never fire."""
        import openamer_cli.auth as auth

        staging_portal = "https://portal.staging-openamer.com"
        monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
        monkeypatch.setenv("OPENAMER_PORTAL_BASE_URL", staging_portal)
        self._write_auth_file(tmp_path, stored_portal_url=staging_portal)

        seen_portal_urls, records = self._run_and_capture(monkeypatch, auth)

        assert seen_portal_urls == [staging_portal]
        assert not any(
            "ignoring invalid portal_base_url" in msg for msg in records
        ), "env override must bypass the allowlist gate entirely"

    def test_env_override_wins_over_prod_state(self, monkeypatch, tmp_path):
        """Even when the STORED state is the prod host (e.g. a stale/healed
        value from before the env var was set), the env override must still
        win for the actual refresh call."""
        import openamer_cli.auth as auth

        staging_portal = "https://portal.staging-openamer.com"
        monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
        monkeypatch.setenv("OPENAMER_PORTAL_BASE_URL", staging_portal)
        self._write_auth_file(tmp_path, stored_portal_url=DEFAULT_openamer_PORTAL_URL)

        seen_portal_urls, _records = self._run_and_capture(monkeypatch, auth)

        assert seen_portal_urls == [staging_portal]

    def test_no_env_override_stored_staging_host_heals_to_prod(
        self, monkeypatch, tmp_path
    ):
        """Without the env override set, a stored staging host is untrusted
        network provenance and correctly heals to prod (this is the
        allowlist's actual job — preserved, not regressed, by this fix)."""
        import openamer_cli.auth as auth

        staging_portal = "https://portal.staging-openamer.com"
        monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
        monkeypatch.delenv("OPENAMER_PORTAL_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAMER_PORTAL_BASE_URL", raising=False)
        self._write_auth_file(tmp_path, stored_portal_url=staging_portal)

        seen_portal_urls, records = self._run_and_capture(monkeypatch, auth)

        assert seen_portal_urls == [DEFAULT_openamer_PORTAL_URL]
        assert any("ignoring invalid portal_base_url" in msg for msg in records)

    def test_no_env_no_staging_state_prod_url_used_unmodified(
        self, monkeypatch, tmp_path
    ):
        """Baseline: no override, no staging state — prod is used and the
        allowlist never even logs a warning (nothing was rejected)."""
        import openamer_cli.auth as auth

        monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
        monkeypatch.delenv("OPENAMER_PORTAL_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAMER_PORTAL_BASE_URL", raising=False)
        self._write_auth_file(tmp_path, stored_portal_url=DEFAULT_openamer_PORTAL_URL)

        seen_portal_urls, records = self._run_and_capture(monkeypatch, auth)

        assert seen_portal_urls == [DEFAULT_openamer_PORTAL_URL]
        assert not any("ignoring invalid portal_base_url" in msg for msg in records)
