"""Tests for the Nous-OpenAmer-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"openamer"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``openamer-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "openamer" tag namespace.

``is_nous_openamer_non_agentic`` should only match the actual Nous Research
OpenAmer-3 / OpenAmer-4 chat family.
"""

from __future__ import annotations

import pytest

from openamer_cli.model_switch import (
    _OPENAMER_MODEL_WARNING,
    _check_openamer_model_warning,
    is_nous_openamer_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/OpenAmer-3-Llama-3.1-70B",
        "NousResearch/OpenAmer-3-Llama-3.1-405B",
        "openamer-3",
        "OpenAmer-3",
        "openamer-4",
        "openamer-4-405b",
        "openamer_4_70b",
        "openrouter/openamer3:70b",
        "openrouter/nousresearch/openamer-4-405b",
        "NousResearch/OpenAmer3",
        "openamer-3.1",
    ],
)
def test_matches_real_nous_openamer_chat_models(model_name: str) -> None:
    assert is_nous_openamer_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous OpenAmer 3/4"
    )
    assert _check_openamer_model_warning(model_name) == _OPENAMER_MODEL_WARNING


@pytest.mark.parametrize(
    "model_name",
    [
        # Kyle's local Modelfile — qwen3:14b under a custom tag
        "openamer-brain:qwen3-14b-ctx16k",
        "openamer-brain:qwen3-14b-ctx32k",
        "openamer-honcho:qwen3-8b-ctx8k",
        # Plain unrelated models
        "qwen3:14b",
        "qwen3-coder:30b",
        "qwen2.5:14b",
        "claude-opus-4-6",
        "anthropic/claude-sonnet-4.5",
        "gpt-5",
        "openai/gpt-4o",
        "google/gemini-2.5-flash",
        "deepseek-chat",
        # Non-chat OpenAmer models we don't warn about
        "openamer-llm-2",
        "openamer2-pro",
        "nous-openamer-2-mistral",
        # Edge cases
        "",
        "openamer",  # bare "openamer" isn't the 3/4 family
        "openamer-brain",
        "brain-openamer-3-impostor",  # "3" not preceded by /: boundary
    ],
)
def test_does_not_match_unrelated_models(model_name: str) -> None:
    assert not is_nous_openamer_non_agentic(model_name), (
        f"expected {model_name!r} NOT to be flagged as Nous OpenAmer 3/4"
    )
    assert _check_openamer_model_warning(model_name) == ""


def test_none_like_inputs_are_safe() -> None:
    assert is_nous_openamer_non_agentic("") is False
    # Defensive: the helper shouldn't crash on None-ish falsy input either.
    assert _check_openamer_model_warning("") == ""
