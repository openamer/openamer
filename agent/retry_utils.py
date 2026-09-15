"""Retry utilities — jittered backoff for decorrelated retries.

Replaces fixed exponential backoff with jittered delays to prevent
thundering-herd retry spikes when multiple sessions hit the same
rate-limited provider concurrently.
"""

import random
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Optional

# Monotonic counter for jitter seed uniqueness within the same process.
# Protected by a lock to avoid race conditions in concurrent retry paths
# (e.g. multiple gateway sessions retrying simultaneously).
_jitter_counter = 0
_jitter_lock = threading.Lock()

# Z.AI Coding Plan's GLM-5.2 endpoint often returns HTTP 429 code 1305
# ("The service may be temporarily overloaded...") for otherwise valid
# OpenAmer requests. Short retries tend to hammer the same overloaded window;
# after a few normal retries, progressively widen the wait window. Keep the
# cap interactive-friendly: a simple TUI message should fail visibly in minutes,
# not sit silent for 20+ minutes.
_ZAI_CODING_OVERLOAD_LONG_BACKOFF = (30.0, 60.0, 90.0, 120.0)

# Number of initial short retries before the adaptive long-backoff tier kicks
# in. Shared by ``adaptive_rate_limit_backoff`` (which walks the long table
# starting at attempt ``short_attempts + 1``) and
# ``zai_coding_overload_retry_ceiling`` (which sizes the retry loop so every
# long-tier entry is reachable). Keeping it a single module constant prevents
# the two from silently desyncing if the short-retry count is ever tuned.
_ZAI_CODING_OVERLOAD_SHORT_ATTEMPTS = 3


def jittered_backoff(
    attempt: int,
    *,
    base_delay: float = 5.0,
    max_delay: float = 120.0,
    jitter_ratio: float = 0.5,
) -> float:
    """Compute a jittered exponential backoff delay.

    Args:
        attempt: 1-based retry attempt number.
        base_delay: Base delay in seconds for attempt 1.
        max_delay: Maximum delay cap in seconds.
        jitter_ratio: Fraction of computed delay to use as random jitter
            range.  0.5 means jitter is uniform in [0, 0.5 * delay].

    Returns:
        Delay in seconds: min(base * 2^(attempt-1), max_delay) + jitter.

    The jitter decorrelates concurrent retries so multiple sessions
    hitting the same provider don't all retry at the same instant.
    """
    global _jitter_counter
    with _jitter_lock:
        _jitter_counter += 1
        tick = _jitter_counter

    exponent = max(0, attempt - 1)
    if exponent >= 63 or base_delay <= 0:
        delay = max_delay
    else:
        delay = min(base_delay * (2 ** exponent), max_delay)

    # Seed from time + counter for decorrelation even with coarse clocks.
    seed = (time.time_ns() ^ (tick * 0x9E3779B9)) & 0xFFFFFFFF
    rng = random.Random(seed)
    jitter = rng.uniform(0, jitter_ratio * delay)

    return delay + jitter


def _error_text(error: Any) -> str:
    """Best-effort flattened provider error text for retry classification."""
    parts = [
        error,
        getattr(error, "message", None),
        getattr(error, "body", None),
        getattr(error, "response", None),
    ]
    return " ".join(str(part) for part in parts if part is not None).lower()


def is_zai_coding_overload_error(*, base_url: str | None, model: str | None, error: Any) -> bool:
    """Return True for Z.AI Coding Plan transient overload 429s.

    The coding-plan endpoint reports overload as HTTP 429 with body code 1305
    and message "The service may be temporarily overloaded...". Treat only
    that narrow shape specially so ordinary quota/billing 429s still fail fast
    through the existing classifier.
    """
    base = (base_url or "").lower()
    model_name = (model or "").lower()
    status = getattr(error, "status_code", None)
    text = _error_text(error)
    return (
        status == 429
        and "api.z.ai/api/coding/paas/v4" in base
        and "glm-5.2" in model_name
        and ("1305" in text or "temporarily overloaded" in text)
    )


def adaptive_rate_limit_backoff(
    attempt: int,
    *,
    base_url: str | None,
    model: str | None,
    error: Any,
    default_wait: float,
    short_attempts: int = _ZAI_CODING_OVERLOAD_SHORT_ATTEMPTS,
) -> tuple[float, str | None]:
    """Provider-aware rate-limit backoff.

    For most providers this returns ``default_wait`` unchanged. For Z.AI
    Coding Plan GLM-5.2 overloads, keep the first ``short_attempts`` retries on
    the normal short exponential schedule, then switch to progressively longer
    waits (30s → 60s → 90s → 120s, capped) plus light jitter.

    ``attempt`` is 1-based, matching the retry loop's logged attempt number.
    Returns ``(wait_seconds, reason_label)`` where ``reason_label`` is suitable
    for status/log decoration when a provider-specific policy fired.
    """
    if not is_zai_coding_overload_error(base_url=base_url, model=model, error=error):
        return default_wait, None
    if attempt <= short_attempts:
        return default_wait, "zai_coding_overload_short"

    idx = min(attempt - short_attempts - 1, len(_ZAI_CODING_OVERLOAD_LONG_BACKOFF) - 1)
    base_delay = _ZAI_CODING_OVERLOAD_LONG_BACKOFF[idx]
    # A smaller jitter ratio keeps long waits readable while still avoiding
    # synchronized retry storms across concurrent OpenAmer sessions.
    return jittered_backoff(1, base_delay=base_delay, max_delay=base_delay, jitter_ratio=0.2), "zai_coding_overload_long"


def zai_coding_overload_retry_ceiling(short_attempts: int = _ZAI_CODING_OVERLOAD_SHORT_ATTEMPTS) -> int:
    """Retry-loop ceiling needed for the full Z.AI overload backoff schedule.

    The adaptive policy runs ``short_attempts`` short retries, then walks the
    long-backoff table one entry per subsequent attempt. The retry loop gives
    up as soon as ``retry_count >= ceiling`` — and that check runs *before* the
    attempt's backoff is computed — so the ceiling must sit one past the final
    long-backoff entry for every long tier to actually execute.

    With the default ``api_max_retries`` (3) equal to ``short_attempts`` (3),
    the loop always gave up before reaching the long tier, leaving the whole
    long-backoff schedule as dead code. Callers extend the ceiling to this
    value for Z.AI Coding overload 429s so the 30/60/90/120s waits run.
    """
    return short_attempts + len(_ZAI_CODING_OVERLOAD_LONG_BACKOFF) + 1


# ---------------------------------------------------------------------------
# Provider "retry after / resets in" message parsing
# ---------------------------------------------------------------------------

# "4.5s", "30 sec", "2 minutes", "1h30m", "1 hour 30 min"
_DURATION_UNIT_SECONDS = {
    "ms": 0.001,
    "millisecond": 0.001,
    "milliseconds": 0.001,
    "s": 1.0,
    "sec": 1.0,
    "secs": 1.0,
    "second": 1.0,
    "seconds": 1.0,
    "m": 60.0,
    "min": 60.0,
    "mins": 60.0,
    "minute": 60.0,
    "minutes": 60.0,
    "h": 3600.0,
    "hr": 3600.0,
    "hrs": 3600.0,
    "hour": 3600.0,
    "hours": 3600.0,
    "d": 86400.0,
    "day": 86400.0,
    "days": 86400.0,
}

# Provider phrasings that introduce a relative delay. Kept narrow on purpose so
# an unrelated number in the message body (a token count, a request id) can't
# be mistaken for a reset delay. The trailing ``\b`` matters: without it the
# bare ``in`` alternative matches inside ordinary words ("invalid", "input").
_DURATION_ANCHOR_RE = re.compile(
    r"\b(?:retry|try again|resets?|reset|available|come back|wait|in)\b\D{0,20}?"
    r"(\d+(?:\.\d+)?)\s*"
    r"(milliseconds?|ms|seconds?|secs?|sec|s|minutes?|mins?|min|m|hours?|hrs?|hr|h|days?|d)\b",
    re.IGNORECASE,
)

# "1h30m", "1 hour 30 min", "2m30s", "2 min 30 sec" — no anchor word needed,
# the digits+unit shape is unambiguous. Hours and minutes/seconds are separate
# patterns because "2m30s" has no hour component at all.
_COMPOUND_HMS_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)\s*"
    r"(?:(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes))?\s*"
    r"(?:(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds))?\b",
    re.IGNORECASE,
)
_COMPOUND_MS_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes)\s*"
    r"(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds)\b",
    re.IGNORECASE,
)


# "resets at 14:30:00Z", "available after 2026-09-15T23:10:00Z"
_CLOCK_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)
_ISO_TIMESTAMP_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b"
)


def _unit_to_seconds(unit: str) -> Optional[float]:
    return _DURATION_UNIT_SECONDS.get(unit.lower())


# Upper bound on a parsed reset delay. Generous enough for multi-day quota
# windows, small enough that a misparsed number can never park a credential
# (or a scheduled retry) for weeks.
_MAX_RESET_DELAY_SECONDS = 7 * 86400.0


def _clamp_delay(seconds: float) -> float:
    return max(0.0, min(float(seconds), _MAX_RESET_DELAY_SECONDS))


def _clock_offset_seconds(match: "re.Match[str]", *, now: Optional[float] = None) -> Optional[float]:
    """Seconds from now until a wall-clock time appearing in the text.

    Only used as a fallback when no relative delay is present. Sub-day precision
    only — provider messages that mean "tomorrow at 09:00" are indistinguishable
    from "today at 09:00" without a date, so the result is clamped to 24h.
    """
    now_dt = datetime.fromtimestamp(now if now is not None else time.time())
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or 0)
    meridiem = (match.group(4) or "").lower()
    if meridiem:
        if hour == 12:
            hour = 0
        if meridiem == "pm":
            hour += 12
    if hour > 23 or minute > 59 or second > 59:
        return None
    target = now_dt.replace(hour=hour, minute=minute, second=second, microsecond=0)
    if target <= now_dt:
        target += timedelta(days=1)
    offset = (target - now_dt).total_seconds()
    return max(0.0, min(offset, 86400.0))


def reset_delay_from_message(message: Any, *, now: Optional[float] = None) -> Optional[float]:
    """Extract a relative retry delay in seconds from a provider error message.

    Credential-pool entries record provider errors as free text (``error_context``
    / ``last_error``); this recovers the reset delay the provider stated in prose
    ("Please retry after 4 seconds", "Rate limit reached, resets in 2 minutes",
    "try again in 1h30m") so a depleted credential can be parked for the right
    amount of time instead of a blanket TTL. Absolute ISO timestamps embedded in
    the message are honoured as well, since several providers report ``resets_at``
    inline.

    Args:
        message: Raw provider error text. Non-strings return ``None``.
        now: Optional epoch-seconds reference point (injectable for tests).

    Returns:
        Non-negative seconds to wait, or ``None`` when the message states no
        parseable reset time. Values are clamped to 24h so a misparsed clock
        reading can never park a credential indefinitely.
    """
    if not isinstance(message, str):
        return None
    raw = message.strip()
    if not raw:
        return None
    now_ts = now if now is not None else time.time()

    lowered = raw.lower()
    if any(
        marker in lowered
        for marker in ("weekly", "monthly", "daily limit", "billing period", "next month")
    ):
        # Period-scale messages carry no precise delay we should act on.
        return None

    # 1. Compound shapes ("1h30m", "2m30s") — unambiguous, no anchor required.
    best: Optional[float] = None
    for match in _COMPOUND_HMS_RE.finditer(raw):
        if match.group(2) is None:
            continue
        total = float(match.group(1)) * 3600.0
        if match.group(3) is not None:
            total += float(match.group(3)) * 60.0
        if match.group(5) is not None:
            total += float(match.group(5))
        best = total if best is None else min(best, total)
    for match in _COMPOUND_MS_RE.finditer(raw):
        total = float(match.group(1)) * 60.0 + float(match.group(3))
        best = total if best is None else min(best, total)
    if best is not None:
        return _clamp_delay(best)

    # 2. Single anchored unit ("retry after 4 seconds", "resets in 2 min").
    best = None
    for match in _DURATION_ANCHOR_RE.finditer(raw):
        seconds = _unit_to_seconds(match.group(2))
        if seconds is None:
            continue
        total = float(match.group(1)) * seconds
        best = total if best is None else min(best, total)
    if best is not None:
        return _clamp_delay(best)

    # 3. Absolute ISO-8601 reset timestamp ("resets_at 2026-09-15T23:10:00Z").
    for match in _ISO_TIMESTAMP_RE.finditer(raw):
        stamp = match.group(1).replace(" ", "T")
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is not None:
            delta = parsed.timestamp() - now_ts
        else:
            delta = (
                parsed - datetime.fromtimestamp(now_ts)
            ).total_seconds()
        if delta > 0:
            return _clamp_delay(delta)

    # 4. Bare wall-clock time ("resets at 23:10"). Weakest signal, last resort.
    if "reset" in lowered or "available" in lowered or "try again" in lowered:
        for match in _CLOCK_TIME_RE.finditer(raw):
            offset = _clock_offset_seconds(match, now=now_ts)
            if offset:
                return offset

    return None

