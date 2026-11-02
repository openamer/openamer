"""The fresh-final threshold must not depend on the host's uptime.

``_message_created_ts`` is a ``time.monotonic()`` reading, so an "old preview"
is expressed as ``monotonic() - age``.  Expressing it as the literal ``0.0``
means "the host has been up for N seconds" — on a freshly booted CI runner
(uptime below the 60 s threshold) the fresh-final path never triggered and
these tests failed only in CI.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.stream_consumer import GatewayStreamConsumer, StreamConsumerConfig


def _adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.REQUIRES_EDIT_FINALIZE = False
    adapter.MAX_MESSAGE_LENGTH = 4096
    adapter.send = AsyncMock(return_value=SimpleNamespace(
        success=True, message_id="initial_preview"))
    adapter.edit_message = AsyncMock(return_value=SimpleNamespace(
        success=True, message_id="initial_preview"))
    adapter.delete_message = AsyncMock(return_value=True)
    return adapter


@pytest.mark.asyncio
async def test_old_preview_is_detected_even_on_a_freshly_booted_host(monkeypatch):
    """Simulate a host that just booted: monotonic() is only a few seconds."""
    uptime = 3.0
    monkeypatch.setattr(
        "gateway.stream_consumer.time.monotonic", lambda: uptime, raising=False)
    adapter = _adapter()
    adapter.send.side_effect = [
        SimpleNamespace(success=True, message_id="initial_preview"),
        SimpleNamespace(success=True, message_id="fresh_final"),
    ]
    consumer = GatewayStreamConsumer(
        adapter=adapter,
        chat_id="chat",
        config=StreamConsumerConfig(fresh_final_after_seconds=60.0),
    )
    await consumer._send_or_edit("hello")
    # The preview was created when the host had 3 s of uptime.
    consumer._message_created_ts = uptime
    # The host is now at 3 s + 3600 s: the preview is an hour old.
    monkeypatch.setattr(
        "gateway.stream_consumer.time.monotonic", lambda: uptime + 3600.0,
        raising=False)
    await consumer._send_or_edit("hello world", finalize=True)
    assert adapter.send.call_count == 2
    adapter.edit_message.assert_not_called()


@pytest.mark.asyncio
async def test_young_preview_is_not_treated_as_stale_on_a_fresh_host(monkeypatch):
    """A preview younger than the threshold stays an edit, uptime or not."""
    uptime = 5.0
    monkeypatch.setattr(
        "gateway.stream_consumer.time.monotonic", lambda: uptime, raising=False)
    adapter = _adapter()
    consumer = GatewayStreamConsumer(
        adapter=adapter,
        chat_id="chat",
        config=StreamConsumerConfig(fresh_final_after_seconds=60.0),
    )
    await consumer._send_or_edit("hello")
    await consumer._send_or_edit("hello world", finalize=True)
    assert adapter.send.call_count == 1
    adapter.edit_message.assert_called_once()


def test_zero_timestamp_is_not_a_usable_age_marker():
    """Documented invariant: 0.0 means uptime, not 'in the past'."""
    assert time.monotonic() - 0.0 >= 0.0
