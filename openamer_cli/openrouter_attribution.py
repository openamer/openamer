"""
OpenRouter App Attribution — sorgt dafür dass OpenAmer in den OpenRouter-Rankings erscheint.

Patched die OpenAI-Client-Erstellung um HTTP-Referer + X-OpenRouter-Title Header zu setzen.
Wird automatisch geladen wenn der Provider OpenRouter ist.
"""

from __future__ import annotations

from typing import Any

# OpenRouter App Identität
OPENROUTER_APP_URL = "https://github.com/openamer/openamer"
OPENROUTER_APP_TITLE = "OpenAmer Agent"
OPENROUTER_APP_CATEGORIES = "coding,productivity"


def get_openrouter_attribution_headers() -> dict[str, str]:
    """Liefert die HTTP-Header für OpenRouter App Attribution.

    Diese Header machen OpenAmer in den öffentlichen Rankings und
    Analytics von OpenRouter sichtbar.
    """
    return {
        "HTTP-Referer": OPENROUTER_APP_URL,
        "X-OpenRouter-Title": OPENROUTER_APP_TITLE,
        "X-OpenRouter-Categories": OPENROUTER_APP_CATEGORIES,
    }