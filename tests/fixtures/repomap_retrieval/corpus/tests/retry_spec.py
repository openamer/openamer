"""Unit tests for the retry policy backoff computation."""

from __future__ import annotations

from app.retry import RetryPolicy


def test_backoff_grows() -> None:
    policy = RetryPolicy(base_delay=0.5, max_delay=8.0)
    delays = [policy.compute_backoff(attempt) for attempt in range(5)]
    assert delays == sorted(delays)


def test_retry_stops_at_max_attempts() -> None:
    policy = RetryPolicy(max_attempts=2)
    assert policy.should_retry(1, 503)
    assert not policy.should_retry(2, 503)


def test_non_retryable_status_is_rejected() -> None:
    policy = RetryPolicy()
    assert not policy.should_retry(0, 404)
