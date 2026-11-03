"""HTTP transport that composes the retry policy with the response cache."""

from __future__ import annotations

import time
from typing import Any

from app.cache import CacheStore
from app.retry import RetryPolicy


class HttpClient:
    """Minimal HTTP client: cache lookup first, then retrying dispatch."""

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        cache: CacheStore | None = None,
    ) -> None:
        self.policy = policy or RetryPolicy()
        self.cache = cache or CacheStore()
        self.requests_sent = 0

    def send_request(self, url: str, attempt: int = 0) -> dict[str, Any]:
        """Fetch *url*, sleeping between transient failures."""
        cached = self.cache.lookup(url)
        if cached is not None:
            return cached

        self.requests_sent += 1
        status_code, body = self._dispatch(url)

        if self.policy.should_retry(attempt, status_code):
            delay = self.policy.compute_backoff(attempt)
            time.sleep(delay)
            return self.send_request(url, attempt + 1)

        payload = {"url": url, "status": status_code, "body": body}
        self.cache.store(url, payload)
        return payload

    def _dispatch(self, url: str) -> tuple[int, str]:
        return 200, f"body for {url}"
