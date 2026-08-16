"""openamer_cli.a2a.privacy — redact private/sensitive data before storing.

Privacy is non-negotiable for the OpenAmer brain: raw activity and shared
knowledge must never contain phone numbers, passwords/secrets, emails, credit
cards, or private document markers. This module scrubs those patterns with
conservative regexes and a length-aware heuristic for credential values.

Everything here is offline, stdlib-only, and unit-testable.
"""
from __future__ import annotations

import re

# --- patterns (order matters: run cards/leaks before generic) --------------
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # credit / bank card numbers (13-19 digits)
    (re.compile(r"(?<!\d)\d{13,19}(?!\d)"), "[REDACTED:NUMBER]"),
    # IBAN
    (re.compile(r"(?<![A-Za-z])[A-Z]{2}\d{2}[A-Z0-9]{11,30}(?![A-Z0-9])"), "[REDACTED:IBAN]"),
    # email addresses
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[REDACTED:EMAIL]"),
    # common secret/password/token keys INSIDE text (e.g. password=..., api_key: "x")
    (re.compile(r'(?i)(pass(?:word|wd)?|passwd|api[_-]?key|secret|token|auth|bearer|cookie|private[_-]?key)\s*[=:]\s*["\']?[^\s,"\'`]{4,}'),
     lambda m: f"{m.group(1).split('=')[0].split(':')[0].strip()}=[REDACTED]"),
    # bearer / authorization header values
    (re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{16,}"), "[REDACTED:CREDENTIAL]"),
    # SSH private key blocks
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED:PRIVATE_KEY]"),
    # passwords passed as CLI flag values (--password X, -p X)
    (re.compile(r"(?i)(--?passw[a-z]*|-p)\s+(\S+)"), r"\1 [REDACTED:PASSWORD]"),
]

# Phone numbers: keep last (national) and international patterns; require a digit
# run that looks like a phone (>=7 digits) to avoid falsing on years/ids.
_PHONE = re.compile(r"(?<![\d])(?:\+?\d{1,3}[\s\-.]*)?(?:\(?\d{2,4}\)?[\s\-.]*)?\d{3,4}[\s\-.]*\d{3,4}(?!\d)")


def _kind(phone: re.Match) -> str:
    return "[REDACTED:PHONE]"


def redact(text: str) -> str:
    """Return text with private data replaced by safe placeholders."""
    if not text:
        return text
    out = text
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    # phones after patterns (they contain digits but also +/()/-)
    out = _PHONE.sub(lambda m: "[REDACTED:PHONE]", out)
    return out


def contains_private(text: str) -> bool:
    """True if any private/sensitive pattern is present (for scoring)."""
    if not text:
        return False
    for pat, _ in _PATTERNS:
        if pat.search(text):
            return True
    return _PHONE.search(text) is not None


_HEADER = re.compile(r"^\s*(To|Cc|Bcc|From|Subject|Reply-To)\s*:\s*", re.M)

def redact_message(text: str, *, header_mode: bool = False) -> str:
    """Redact, and if header_mode also masks email mail headers."""
    out = redact(text)
    if header_mode:
        out = _HEADER.sub(lambda m: f"{m.group(1)}: [REDACTED]", out)
    return out