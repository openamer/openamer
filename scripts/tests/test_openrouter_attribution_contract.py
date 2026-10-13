"""The App Attribution contract, pinned to the vendor's own numbers.

OpenRouter's documentation states, verbatim:

    MAX_CATEGORIES_PER_REQUEST = 2
    MAX_CATEGORIES_PER_APP = 10
    "Pass a comma-separated list of up to {MAX_CATEGORIES_PER_REQUEST}
     categories per request."
    "Only recognized categories from the list below are accepted; OpenRouter
     drops unrecognized ones without an error."

A four-value header therefore looked correct in code review while half of it
never reached the ranking. Excess is dropped WITHOUT an error, which is exactly
the class of silent failure that reads as "it works" in every log.
"""

from __future__ import annotations

import re
from pathlib import Path

MAX_CATEGORIES_PER_REQUEST = 2
SRC = (Path(__file__).resolve().parents[2]
       / "openamer_cli" / "openrouter_attribution.py")


def _headers() -> dict:
    ns: dict = {}
    src = SRC.read_text(encoding="utf-8")
    # the module imports optional runtime deps; take only the constant + builder
    m = re.search(r"^OPENROUTER_APP_CATEGORIES\s*=\s*[\"']([^\"']+)[\"']", src, re.M)
    assert m, "OPENROUTER_APP_CATEGORIES must exist as a literal constant"
    ns["OPENROUTER_APP_CATEGORIES"] = m.group(1)
    return ns


def test_categories_never_exceed_the_documented_request_limit():
    cats = [c for c in _headers()["OPENROUTER_APP_CATEGORIES"].split(",") if c.strip()]
    assert len(cats) <= MAX_CATEGORIES_PER_REQUEST, (
        f"{len(cats)} categories in one request; OpenRouter accepts "
        f"{MAX_CATEGORIES_PER_REQUEST} and drops the rest without an error")


def test_categories_are_lowercase_hyphen_separated_and_short():
    """The documented format: lowercase, hyphen-separated, each <= 30 chars."""
    for c in _headers()["OPENROUTER_APP_CATEGORIES"].split(","):
        c = c.strip()
        assert c == c.lower(), f"{c!r} is not lowercase"
        assert " " not in c, f"{c!r} contains a space (must be hyphen-separated)"
        assert len(c) <= 30, f"{c!r} exceeds 30 characters"
        assert re.fullmatch(r"[a-z0-9-]+", c), f"{c!r} has characters outside [a-z0-9-]"


def test_the_identifier_header_is_still_present():
    """HTTP-Referer is the required identifier: without it no app page is created."""
    src = SRC.read_text(encoding="utf-8")
    assert "HTTP-Referer" in src, "the required ranking identifier disappeared"
