"""
OpenRouter App Attribution — sorgt dafür dass OpenAmer in den OpenRouter-Rankings erscheint.

Patched die OpenAI-Client-Erstellung um HTTP-Referer + X-OpenRouter-Title Header zu setzen.
Wird automatisch geladen wenn der Provider OpenRouter ist.
"""

from __future__ import annotations

from typing import Any

# OpenRouter app identity.
#
# `X-OpenRouter-Categories` must contain ONLY names from OpenRouter's
# recognised category list (openrouter.ai/docs/app-attribution). Anything
# else is dropped silently — no error, no category, no listing. The values
# that actually route us into the marketplace listings we care about are:
#   cli-agent     -> Coding > CLI Agents        (our main ranking)
#   ide-extension -> Coding > IDE Extensions    (apps/vscode, apps/jetbrains)
#   personal-agent-> Productivity > Personal Agents (our positioning)
#   cloud-agent   -> Coding > Cloud Agents      (remote/A2A workers)
#
# Historical bug: this was "coding,productivity" — both are *group* names,
# not categories, so OpenRouter discarded BOTH and the app page never
# appeared in any category ranking despite billions of attributed tokens.
OPENROUTER_APP_URL = "https://github.com/openamer/openamer"
OPENROUTER_APP_TITLE = "OpenAmer Agent"
OPENROUTER_APP_CATEGORIES = "cli-agent,ide-extension,personal-agent,cloud-agent"


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