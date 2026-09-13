"""Contract test: OpenRouter attribution headers must be *usable*.

OpenRouter silently drops unrecognised category names — no error, no warning —
so a typo or a group name (``coding``, ``productivity``) results in an app that
accumulates attributed tokens but never appears in any marketplace category.
That is exactly what happened to us: 7.7B attributed tokens and zero listing
until the categories were corrected.

This test asserts the invariant "every category we advertise is one OpenRouter
recognises", not a frozen literal — adding a legitimate new category keeps the
test green; introducing an invented one fails it.
"""

from __future__ import annotations

from agent.auxiliary_client import _OR_HEADERS_BASE
from openamer_cli.openrouter_attribution import (
    OPENROUTER_APP_CATEGORIES,
    OPENROUTER_APP_URL,
    get_openrouter_attribution_headers,
)

# Recognised categories, per https://openrouter.ai/docs/app-attribution —
# "Category groups" (Coding / Creative / Productivity / Entertainment hold the
# *group* names; the list below holds the actual accepted category names).
RECOGNISED_CATEGORIES = frozenset(
    {
        # Coding
        "cli-agent",
        "ide-extension",
        "cloud-agent",
        "programming-app",
        "native-app-builder",
        # Creative
        "creative-writing",
        "video-gen",
        "image-gen",
        "audio-gen",
        # Productivity
        "writing-assistant",
        "general-chat",
        "personal-agent",
        "legal",
        # Entertainment
        "roleplay",
        "game",
    }
)

# Group names that are NOT categories. Sending them is a silent no-op.
GROUP_NAMES_NOT_CATEGORIES = frozenset(
    {"coding", "creative", "productivity", "entertainment"}
)


def _categories(raw: str) -> list[str]:
    return [c.strip() for c in raw.split(",") if c.strip()]


def test_module_categories_are_all_recognised() -> None:
    cats = _categories(OPENROUTER_APP_CATEGORIES)
    assert cats, "at least one category is required to appear in a listing"
    unknown = [c for c in cats if c not in RECOGNISED_CATEGORIES]
    assert not unknown, (
        f"OpenRouter drops these silently: {unknown}. "
        f"Recognised names: {sorted(RECOGNISED_CATEGORIES)}"
    )


def test_module_categories_are_lowercase_hyphenated() -> None:
    for cat in _categories(OPENROUTER_APP_CATEGORIES):
        assert cat == cat.lower(), f"{cat!r} must be lowercase"
        assert " " not in cat, f"{cat!r} must be hyphen-separated, not spaced"
        assert len(cat) <= 30, f"{cat!r} exceeds OpenRouter's 30-char limit"


def test_no_group_name_sent_as_category() -> None:
    cats = set(_categories(OPENROUTER_APP_CATEGORIES))
    overlap = cats & GROUP_NAMES_NOT_CATEGORIES
    assert not overlap, (
        f"{overlap} are group names, not categories — OpenRouter discards them"
    )


def test_cli_agent_listed() -> None:
    """cli-agent is our primary ranking; losing it hides us from the category."""
    assert "cli-agent" in _categories(OPENROUTER_APP_CATEGORIES)


def test_headers_carry_referer_and_title() -> None:
    headers = get_openrouter_attribution_headers()
    # HTTP-Referer is the *required* identifier and is what creates the app page.
    assert headers["HTTP-Referer"] == OPENROUTER_APP_URL
    assert OPENROUTER_APP_URL.startswith("https://")
    assert headers["X-OpenRouter-Title"]
    assert headers["X-OpenRouter-Categories"] == OPENROUTER_APP_CATEGORIES


def test_auxiliary_client_agrees_with_module() -> None:
    """Both call paths must advertise the same, valid category set.

    They are patched by different mechanisms (SDK default_headers vs. the
    auxiliary client's own dict), so they drift independently.
    """
    aux = _categories(_OR_HEADERS_BASE["X-OpenRouter-Categories"])
    unknown = [c for c in aux if c not in RECOGNISED_CATEGORIES]
    assert not unknown, f"auxiliary_client sends unrecognised categories: {unknown}"
    assert set(aux) == set(_categories(OPENROUTER_APP_CATEGORIES))
    assert _OR_HEADERS_BASE["HTTP-Referer"] == OPENROUTER_APP_URL