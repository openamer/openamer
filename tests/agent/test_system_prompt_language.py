"""The response-language block in the stable system prompt.

``build_system_prompt_parts`` injects the user's chosen language (config
``display.language``, resolved through ``agent.i18n.get_language``) so the agent
answers in that language while code, commits and docs stay English.

Pinned here:

- the block appears with the human-readable language name for a configured
  locale, and stays inside the *stable* tier (it must not move into the volatile
  tier, which would invalidate the prompt cache mid-conversation),
- ``en`` injects nothing (English is already the default; an instruction would
  only add noise),
- a locale with no display name falls back to its raw code rather than dropping
  the instruction,
- a failure inside the resolver never blocks prompt assembly.

These run against the real prompt builders — mocking the resolver would hide
exactly the wiring bug this test exists to catch.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent.system_prompt import build_system_prompt_parts


def _stable_prompt(language: str | None):
    agent = SimpleNamespace(
        load_soul_identity=False,
        skip_context_files=False,
        valid_tool_names=[],
        _task_completion_guidance=False,
        _tool_use_enforcement=False,
        _environment_probe=False,
        _kanban_worker_guidance="",
        _memory_store=None,
        _memory_manager=None,
        _platform_hint_overrides={},
        model="",
        provider="",
        pass_session_id=False,
        session_id="",
        platform="",
    )
    with (
        patch("run_agent.load_soul_md", return_value=""),
        patch("run_agent.build_openamer_subscription_prompt", return_value=""),
        patch("run_agent.build_environment_hints", return_value=""),
        patch("run_agent.build_context_files_prompt", return_value=""),
        patch("agent.i18n.get_language", return_value=language),
    ):
        parts = build_system_prompt_parts(agent)
    return parts


class TestResponseLanguageBlock:
    def test_german_locale_injects_the_german_instruction(self):
        stable = _stable_prompt("de")["stable"]
        assert "## Response Language" in stable
        assert "Respond to the user in **German**" in stable
        # English stays mandatory for the artifacts of the work.
        assert "must remain in English" in stable

    def test_english_injects_nothing(self):
        stable = _stable_prompt("en")["stable"]
        assert "## Response Language" not in stable

    def test_no_language_configured_injects_nothing(self):
        stable = _stable_prompt(None)["stable"]
        assert "## Response Language" not in stable

    def test_traditional_chinese_uses_its_full_name(self):
        stable = _stable_prompt("zh-hant")["stable"]
        assert "**Chinese (Traditional)**" in stable

    def test_unknown_locale_falls_back_to_the_raw_code(self):
        stable = _stable_prompt("tlh")["stable"]
        assert "**tlh**" in stable

    def test_block_lives_in_the_stable_tier(self):
        """A volatile-tier language block would break prompt caching."""
        parts = _stable_prompt("ja")
        assert "## Response Language" in parts["stable"]
        for name, value in parts.items():
            if name == "stable":
                continue
            assert "## Response Language" not in value

    def test_resolver_failure_does_not_block_prompt_assembly(self):
        agent = SimpleNamespace(
            load_soul_identity=False,
            skip_context_files=False,
            valid_tool_names=[],
            _task_completion_guidance=False,
            _tool_use_enforcement=False,
            _environment_probe=False,
            _kanban_worker_guidance="",
            _memory_store=None,
            _memory_manager=None,
            _platform_hint_overrides={},
            model="",
            provider="",
            pass_session_id=False,
            session_id="",
            platform="",
        )
        with (
            patch("run_agent.load_soul_md", return_value=""),
            patch("run_agent.build_openamer_subscription_prompt", return_value=""),
            patch("run_agent.build_environment_hints", return_value=""),
            patch("run_agent.build_context_files_prompt", return_value=""),
            patch("agent.i18n.get_language", side_effect=RuntimeError("boom")),
        ):
            parts = build_system_prompt_parts(agent)
        assert parts["stable"]  # assembled anyway
        assert "## Response Language" not in parts["stable"]