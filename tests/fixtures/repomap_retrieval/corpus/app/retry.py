"""Retry policy primitives for the HTTP transport.

The policy is intentionally free of I/O so the backoff curve can be unit
tested without sleeping.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_ATTEMPTS = 5
BASE_DELAY_SECONDS = 0.25
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass
class RetryPolicy:
    """Exponential backoff with a hard ceiling."""

    max_attempts: int = MAX_ATTEMPTS
    base_delay: float = BASE_DELAY_SECONDS
    max_delay: float = 30.0

    def compute_backoff(self, attempt: int) -> float:
        """Return the delay in seconds before the next attempt."""
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)

    def should_retry(self, attempt: int, status_code: int) -> bool:
        """True when the caller may schedule another attempt."""
        if attempt >= self.max_attempts:
            return False
        return status_code in RETRYABLE_STATUS
