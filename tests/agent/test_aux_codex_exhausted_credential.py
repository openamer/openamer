"""Regression: an exhausted Codex credential must not be reported as missing.

The credential pool marks a Codex credential ``exhausted`` after an HTTP 429
usage-limit response and then refuses to select it.  ``_read_codex_access_token``
saw no selectable entry, fell through to the singleton store (which
``manual:device_code`` entries intentionally do not mirror), and returned
``None``.  The caller then logged "no Codex OAuth token found (run: openamer
model)" — advice that cannot help, because the token is valid and only the
account's quota window is spent.

These tests pin the corrected behaviour:
  1. the exhaustion detail is discoverable from the pool,
  2. the log message names the quota state instead of a missing token,
  3. a genuinely absent credential still reports the old "no token" wording.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest


def _entry(
    *,
    last_status: str = "exhausted",
    last_error_reason: Optional[str] = "usage_limit_reached",
    last_error_code: Optional[int] = 429,
    last_error_reset_at: Optional[float] = 1_793_645_325.0,
    last_error_message: Optional[str] = "The usage limit has been reached",
) -> SimpleNamespace:
    return SimpleNamespace(
        id="f72cf4",
        label="openai-codex-oauth-1",
        auth_type="oauth",
        source="manual:device_code",
        access_token="eyJhbGciOi.test.token",
        refresh_token="rt.1.test",
        last_status=last_status,
        last_status_at=1_793_638_926.0,
        last_error_code=last_error_code,
        last_error_reason=last_error_reason,
        last_error_message=last_error_message,
        last_error_reset_at=last_error_reset_at,
    )


class _FakePool:
    def __init__(self, entries: List[Any]) -> None:
        self._entries = entries

    def entries(self) -> List[Any]:
        return list(self._entries)

    def has_credentials(self) -> bool:
        return bool(self._entries)


@pytest.fixture
def aux(monkeypatch: pytest.MonkeyPatch):
    from agent import auxiliary_client

    return auxiliary_client


def _patch_pool(monkeypatch: pytest.MonkeyPatch, aux, entries: List[Any]) -> None:
    monkeypatch.setattr(aux, "load_pool", lambda provider: _FakePool(entries))


def test_pool_exhaustion_is_reported(aux, monkeypatch: pytest.MonkeyPatch) -> None:
    """An exhausted pool entry yields its quota detail."""
    _patch_pool(monkeypatch, aux, [_entry()])

    detail = aux._codex_pool_exhaustion()

    assert detail is not None
    assert detail["reason"] == "usage_limit_reached"
    assert detail["code"] == 429
    assert detail["reset_at"] == 1_793_645_325.0


def test_pool_exhaustion_none_when_credential_is_healthy(
    aux, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A healthy credential is not reported as exhausted."""
    _patch_pool(monkeypatch, aux, [_entry(last_status="ok", last_error_reason=None,
                                          last_error_code=None, last_error_reset_at=None)])

    assert aux._codex_pool_exhaustion() is None


def test_pool_exhaustion_none_when_pool_empty(
    aux, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty pool is not exhaustion."""
    _patch_pool(monkeypatch, aux, [])

    assert aux._codex_pool_exhaustion() is None


def test_exhausted_credential_logs_quota_not_missing_token(
    aux, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The warning names the quota state, not a missing token."""
    _patch_pool(monkeypatch, aux, [_entry()])

    with caplog.at_level(logging.WARNING, logger="agent.auxiliary_client"):
        aux._log_codex_token_unavailable()

    text = caplog.text
    assert "exhausted" in text
    assert "usage_limit_reached" in text
    # The old wording pointed the user at a re-login that cannot fix a quota.
    assert "no Codex OAuth token found" not in text


def test_missing_credential_still_reports_no_token(
    aux, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A genuinely absent credential keeps the original wording."""
    _patch_pool(monkeypatch, aux, [])

    with caplog.at_level(logging.WARNING, logger="agent.auxiliary_client"):
        aux._log_codex_token_unavailable()

    assert "no Codex OAuth token found" in caplog.text


def test_read_token_falls_back_to_singleton_when_pool_exhausted(
    aux, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exhausted pool entry still yields the stored token via the singleton.

    ``manual:device_code`` credentials do not mirror into the singleton store,
    so this path normally stays empty.  When a singleton token *does* exist it
    must be used rather than reporting "no token" — the token is valid.
    """
    _patch_pool(monkeypatch, aux, [_entry()])
    monkeypatch.setattr(aux, "_select_pool_entry", lambda provider: (True, None))

    singleton = {"tokens": {"access_token": "eyJhbGciOi.singleton.token"}}
    import openamer_cli.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_read_codex_tokens", lambda **_: singleton)

    token = aux._read_codex_access_token()

    assert token == "eyJhbGciOi.singleton.token"
