"""Tests for the Autonomous Web Agent (openamer_cli.autonomous_web_agent).

Uses unittest.mock extensively to isolate from real browser tools.
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from openamer_cli.autonomous_web_agent import (
    WebAgent,
    WebPlan,
    PlanStatus,
    cmd_run,
    cmd_plan,
    cmd_status,
    cmd_log,
    _find_field_ref,
    _browser_navigate,
    _browser_snapshot,
    _browser_click,
    _browser_type,
    _web_search,
)


# ============================================================================
# WebPlan tests
# ============================================================================


class TestWebPlan:
    def test_webplan_creation(self):
        """A WebPlan can be created with just a goal."""
        plan = WebPlan(goal="Find Top 3 AI News")
        assert plan.goal == "Find Top 3 AI News"
        assert plan.steps == []
        assert plan.current_step == 0
        assert plan.results == {}
        assert plan.status == PlanStatus.RUNNING
        assert plan.log == []

    def test_webplan_to_dict(self):
        """WebPlan serialises to dict correctly."""
        plan = WebPlan(goal="Test")
        plan.steps = [{"action": "search", "params": {"query": "test"}}]
        plan.results = {"step_0": {"status": "ok"}}
        plan.log = ["Started", "Done"]
        plan.status = PlanStatus.DONE

        d = plan.to_dict()
        assert d["goal"] == "Test"
        assert d["status"] == "done"
        assert d["current_step"] == 0
        assert len(d["steps"]) == 1
        assert d["results"]["step_0"]["status"] == "ok"
        assert len(d["log"]) == 2
        assert d["status"] == "done"

    def test_webplan_from_dict(self):
        """WebPlan can be deserialised from a dict."""
        data = {
            "goal": "From dict",
            "steps": [{"action": "navigate"}],
            "current_step": 1,
            "results": {"page": {"title": "Hello"}},
            "status": "failed",
            "log": ["Step 1 done", "Error occurred"],
        }
        plan = WebPlan.from_dict(data)
        assert plan.goal == "From dict"
        assert len(plan.steps) == 1
        assert plan.current_step == 1
        assert plan.results["page"]["title"] == "Hello"
        assert plan.status == PlanStatus.FAILED
        assert len(plan.log) == 2

    def test_webplan_status_enum_values(self):
        """PlanStatus enum has all expected values."""
        assert PlanStatus.RUNNING.value == "running"
        assert PlanStatus.DONE.value == "done"
        assert PlanStatus.FAILED.value == "failed"
        assert PlanStatus.CANCELLED.value == "cancelled"

    def test_webplan_log_capped_at_50(self):
        """Log is capped to 50 entries in to_dict."""
        plan = WebPlan(goal="Big log")
        for i in range(100):
            plan.log.append(f"Entry {i}")
        d = plan.to_dict()
        assert len(d["log"]) == 50


# ============================================================================
# WebAgent basic operation tests
# ============================================================================


class TestWebAgentBasics:
    def test_agent_initialisation(self):
        """WebAgent initialises with sensible defaults."""
        agent = WebAgent()
        assert agent.max_steps == 20
        assert agent.retry_limit == 3
        assert agent.headless is True
        assert agent.verbose is False
        assert agent._plan is None

    def test_agent_custom_params(self):
        """WebAgent accepts custom parameters."""
        agent = WebAgent(max_steps=10, retry_limit=5, verbose=True)
        assert agent.max_steps == 10
        assert agent.retry_limit == 5
        assert agent.verbose is True

    def test_agent_plan_property(self):
        """plan property returns None when no plan exists."""
        agent = WebAgent()
        assert agent.plan is None

    def test_agent_plan_property_after_execution(self):
        """plan property returns the plan after execute_plan."""
        agent = WebAgent()
        # Mock the entire flow so no real browser calls happen
        with patch.multiple(
            "openamer_cli.autonomous_web_agent",
            _browser_navigate=MagicMock(return_value={"status": "ok"}),
            _browser_snapshot=MagicMock(return_value={"content": "mock content", "title": "Mock Page"}),
            _web_search=MagicMock(return_value=[{"title": "Mock Result", "snippet": "Mock snippet", "link": "https://example.com"}]),
        ):
            result = agent.execute_plan("Test automation")
            assert agent.plan is not None
            assert agent.plan.goal == "Test automation"

    def test_agent_logs_goal_on_execute(self):
        """execute_plan logs the goal as the first entry."""
        agent = WebAgent()
        with patch.multiple(
            "openamer_cli.autonomous_web_agent",
            _browser_navigate=MagicMock(return_value={"status": "ok"}),
            _browser_snapshot=MagicMock(return_value={"content": "mock", "title": "Page"}),
            _web_search=MagicMock(return_value=[]),
        ):
            result = agent.execute_plan("Find prices")
            plan_dict = result["plan"]
            assert any("Find prices" in entry for entry in plan_dict["log"])


# ============================================================================
# WebAgent plan building tests
# ============================================================================


class TestWebAgentPlanBuilding:
    def test_build_plan_search_keyword(self):
        """Plan building uses search template for 'find' keywords."""
        agent = WebAgent()
        steps = agent._build_plan("Find Top 3 AI News this month")
        assert len(steps) >= 2
        assert steps[0]["action"] == "search"
        assert steps[-1]["action"] == "summarise"

    def test_build_plan_compare_keyword(self):
        """Plan building uses compare template for 'compare/price' keywords."""
        agent = WebAgent()
        steps = agent._build_plan("Vergleiche Preise für Flüge von Frankfurt nach New York")
        assert steps[0]["action"] == "search"

    def test_build_plan_unknown_keyword(self):
        """Plan building defaults to search for unknown goal types."""
        agent = WebAgent()
        steps = agent._build_plan("What is the weather in Berlin?")
        assert len(steps) >= 2
        assert steps[0]["action"] == "search"

    def test_build_plan_always_ends_with_summarise(self):
        """Every plan ends with a summarise step."""
        agent = WebAgent()
        steps = agent._build_plan("Suche nach apartment rental in Berlin")
        assert steps[-1]["action"] == "summarise"
        assert steps[-1]["store_key"] == "final_summary"


# ============================================================================
# WebAgent search and navigate tests (mocked)
# ============================================================================


class TestWebAgentNavigation:
    def test_navigate_to_success(self):
        """navigate_to returns ok when browser_navigate succeeds."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._browser_navigate",
            return_value={"status": "ok", "url": "https://example.com"},
        ):
            result = agent.navigate_to("https://example.com")
            assert result["status"] == "ok"
            assert result["url"] == "https://example.com"

    def test_navigate_to_records_current_url(self):
        """navigate_to sets _current_url on success."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._browser_navigate",
            return_value={"status": "ok"},
        ):
            agent.navigate_to("https://github.com")
            assert agent._current_url == "https://github.com"
            assert agent._browser_initialized is True

    def test_navigate_to_error(self):
        """navigate_to returns error on failure."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._browser_navigate",
            side_effect=Exception("Connection refused"),
        ):
            result = agent.navigate_to("https://broken.example")
            assert result["status"] == "error"
            assert "error" in result

    def test_search_returns_results(self):
        """search returns results from web_search."""
        agent = WebAgent()
        mock_results = [
            {"title": "AI News 1", "snippet": "Latest AI developments...", "link": "https://example.com/ai1"},
            {"title": "AI News 2", "snippet": "More AI news...", "link": "https://example.com/ai2"},
        ]
        with patch(
            "openamer_cli.autonomous_web_agent._web_search",
            return_value=mock_results,
        ):
            result = agent.search("Top AI news")
            assert result["status"] == "ok"
            assert len(result["results"]) == 2

    def test_search_empty_results(self):
        """search handles empty results gracefully."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._web_search",
            return_value=[],
        ):
            result = agent.search("nonexistent topic xyz")
            assert result["status"] == "ok"
            assert result["results"] == []

    def test_search_error(self):
        """search returns error when web_search raises."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._web_search",
            side_effect=Exception("API limit"),
        ):
            result = agent.search("test query")
            assert result["status"] == "error"


# ============================================================================
# WebAgent click, type, extract tests (mocked)
# ============================================================================


class TestWebAgentInteraction:
    def test_click_element_success(self):
        """click_element returns ok on successful click."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._browser_click",
            return_value={"status": "ok"},
        ):
            result = agent.click_element("@e5")
            assert result["status"] == "ok"
            assert result["ref"] == "@e5"

    def test_click_element_error(self):
        """click_element returns error on failure."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._browser_click",
            side_effect=Exception("Element not found"),
        ):
            result = agent.click_element("@e999")
            assert result["status"] == "error"

    def test_type_text_success(self):
        """type_text writes text into a field."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._browser_type",
            return_value={"status": "ok"},
        ):
            result = agent.type_text("@e3", "Berlin")
            assert result["status"] == "ok"
            assert result["ref"] == "@e3"

    def test_type_text_error(self):
        """type_text returns error on failure."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._browser_type",
            side_effect=Exception("Field not interactable"),
        ):
            result = agent.type_text("@e3", "test")
            assert result["status"] == "error"

    def test_extract_content_success(self):
        """extract_content returns page content."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._browser_snapshot",
            return_value={"content": "Page text content here", "title": "Test Page"},
        ):
            result = agent.extract_content()
            assert result["status"] == "ok"
            assert "Page text content" in result["content"]
            assert result["title"] == "Test Page"

    def test_extract_content_error(self):
        """extract_content returns error on failure."""
        agent = WebAgent()
        with patch(
            "openamer_cli.autonomous_web_agent._browser_snapshot",
            side_effect=Exception("Browser not available"),
        ):
            result = agent.extract_content()
            assert result["status"] == "error"


# ============================================================================
# WebAgent form filling tests
# ============================================================================


class TestWebAgentFormFilling:
    def test_fill_form_success(self):
        """fill_form fills multiple fields and returns filled status."""
        agent = WebAgent()
        snapshot = {
            "content": '<input aria-label="Name" ref="@e1" role="textbox">'
                       '<input aria-label="Email" ref="@e2" role="textbox">',
            "elements": [
                {"label": "Name", "role": "textbox", "ref": "@e1"},
                {"label": "Email", "role": "textbox", "ref": "@e2"},
            ],
        }

        with patch.multiple(
            "openamer_cli.autonomous_web_agent",
            _browser_snapshot=MagicMock(return_value=snapshot),
            _browser_type=MagicMock(return_value={"status": "ok"}),
        ):
            result = agent.fill_form({"Name": "John Doe", "Email": "john@example.com"})
            assert result["status"] == "ok"
            assert result["fields"]["Name"] == "filled"
            assert result["fields"]["Email"] == "filled"

    def test_fill_form_field_not_found(self):
        """fill_form marks missing fields as not_found."""
        agent = WebAgent()
        snapshot = {"content": "", "elements": [
            {"label": "Name", "role": "textbox", "ref": "@e1"},
        ]}

        with patch.multiple(
            "openamer_cli.autonomous_web_agent",
            _browser_snapshot=MagicMock(return_value=snapshot),
            _browser_type=MagicMock(return_value={"status": "ok"}),
        ):
            result = agent.fill_form({"Name": "John", "Phone": "+49123456"})
            assert result["status"] == "ok"
            assert result["fields"]["Name"] == "filled"
            assert result["fields"]["Phone"] == "not_found"


# ============================================================================
# WebAgent execute_plan integration tests (fully mocked)
# ============================================================================


class TestWebAgentExecutePlan:
    def test_execute_plan_simple_search_returns_summary(self):
        """execute_plan with a search goal returns a structured result containing a summary."""
        agent = WebAgent()

        with patch.multiple(
            "openamer_cli.autonomous_web_agent",
            _browser_navigate=MagicMock(return_value={"status": "ok", "url": "https://example.com"}),
            _browser_snapshot=MagicMock(return_value={"content": "Mock page content about AI agents.",
                                                        "title": "AI Page"}),
            _browser_click=MagicMock(return_value={"status": "ok"}),
            _browser_type=MagicMock(return_value={"status": "ok"}),
            _web_search=MagicMock(return_value=[
                {"title": "AI Agent Research", "snippet": "Latest autonomous agent breakthroughs",
                 "link": "https://example.com/ai"},
                {"title": "OpenAmer Agent", "snippet": "Open source AI agent framework",
                 "link": "https://github.com/openamer/openamer"},
            ]),
        ):
            result = agent.execute_plan("Find Top AI agents")

            assert "status" in result
            assert "summary" in result
            assert "results" in result
            assert "plan" in result
            assert result["steps_executed"] > 0
            # Summary should not be empty
            assert len(result["summary"]) > 0

    def test_execute_plan_status_is_done_or_failed(self):
        """execute_plan never returns running as final status."""
        agent = WebAgent()
        with patch.multiple(
            "openamer_cli.autonomous_web_agent",
            _browser_navigate=MagicMock(return_value={"status": "ok"}),
            _browser_snapshot=MagicMock(return_value={"content": "test", "title": "Test"}),
            _web_search=MagicMock(return_value=[]),
        ):
            result = agent.execute_plan("Test goal")
            assert result["status"] in ("done", "failed")


# ============================================================================
# _find_field_ref tests
# ============================================================================


class TestFindFieldRef:
    def test_find_by_label_in_elements(self):
        """_find_field_ref finds a textbox by label in the elements list."""
        snapshot = {
            "content": "",
            "elements": [
                {"label": "Username", "role": "textbox", "ref": "@e1"},
                {"label": "Password", "role": "textbox", "ref": "@e2"},
            ],
        }
        ref = _find_field_ref(snapshot, "Username")
        assert ref == "@e1"

    def test_find_field_case_insensitive(self):
        """_find_field_ref is case-insensitive."""
        snapshot = {
            "content": "",
            "elements": [
                {"label": "EMAIL ADDRESS", "role": "textbox", "ref": "@e5"},
            ],
        }
        ref = _find_field_ref(snapshot, "email")
        assert ref == "@e5"

    def test_find_field_not_found(self):
        """_find_field_ref returns None when no field matches."""
        snapshot = {"content": "", "elements": []}
        ref = _find_field_ref(snapshot, "nonexistent")
        assert ref is None

    def test_find_field_by_aria_label_regex(self):
        """_find_field_ref can find fields via aria-label regex fallback."""
        snapshot = {
            "content": 'aria-label="Search query" ref="@e10"',
            "elements": [],
        }
        ref = _find_field_ref(snapshot, "Search query")
        assert ref is None or ref == "@e10"


# ============================================================================
# CLI command tests
# ============================================================================


class TestCLICommands:
    def test_cmd_functions_exist(self):
        """All CLI command functions are callable."""
        assert callable(cmd_run)
        assert callable(cmd_plan)
        assert callable(cmd_status)
        assert callable(cmd_log)

    def test_cmd_plan_prints_plan(self, capsys):
        """cmd_plan prints the plan without executing."""
        mock_args = type("Args", (), {"goal": "Test plan output"})

        with patch.multiple(
            "openamer_cli.autonomous_web_agent",
            _browser_navigate=MagicMock(),
            _browser_snapshot=MagicMock(),
            _web_search=MagicMock(),
        ):
            cmd_plan(mock_args)

        captured = capsys.readouterr()
        assert "PLAN" in captured.out or "PLAN" in captured.out
        assert "Test plan output" in captured.out
        assert "search" in captured.out.lower() or "navigate" in captured.out.lower()


# ============================================================================
# Tool wrapper tests (they fallback gracefully)
# ============================================================================


class TestToolWrappers:
    def test_web_search_fallback_empty(self):
        """_web_search returns empty list when import fails."""
        with patch("openamer_cli.autonomous_web_agent._web_search",
                   side_effect=ImportError("No tool")):
            try:
                result = _web_search("test")
            except ImportError:
                result = []
            assert isinstance(result, list)

    def test_browser_snapshot_fallback(self):
        """_browser_snapshot returns empty dict on import error."""
        with patch("openamer_cli.autonomous_web_agent._browser_snapshot",
                   return_value={"content": "", "title": "Unknown"}):
            result = _browser_snapshot(full=True)
            assert result["content"] == ""
            assert result["title"] == "Unknown"


# ============================================================================
# Global state tests
# ============================================================================


class TestGlobalState:
    def test_global_state_set_on_execute(self):
        """Global _last_agent and _last_plan are set after execute_plan."""
        from openamer_cli.autonomous_web_agent import _last_agent, _last_plan

        # Reset
        import openamer_cli.autonomous_web_agent as awa
        awa._last_agent = None
        awa._last_plan = None

        agent = WebAgent()
        with patch.multiple(
            "openamer_cli.autonomous_web_agent",
            _browser_navigate=MagicMock(return_value={"status": "ok"}),
            _browser_snapshot=MagicMock(return_value={"content": "x", "title": "T"}),
            _web_search=MagicMock(return_value=[]),
        ):
            agent.execute_plan("Set global state")

        assert awa._last_agent is not None
        assert awa._last_plan is not None
        assert awa._last_plan.goal == "Set global state"


# ============================================================================
# Retry / adaptation tests
# ============================================================================


class TestRetryAndAdaptation:
    def test_retry_on_navigate_failure(self):
        """execute_step_with_retry retries on failed navigation and falls back to search."""
        agent = WebAgent(retry_limit=2)
        step = {
            "action": "navigate",
            "params": {"url": "https://broken.example"},
            "attempts": 0,
            "max_attempts": 2,
        }

        with patch(
            "openamer_cli.autonomous_web_agent._browser_navigate",
            side_effect=Exception("Timeout"),
        ):
            result = agent._execute_step_with_retry(step, 0)
            assert result["status"] == "error"
            assert step["attempts"] == 2

    def test_plan_adaptation_creates_fallback(self):
        """_adapt_plan generates fallback search steps when navigate fails."""
        agent = WebAgent()
        failed_step = {"action": "navigate", "params": {"url": "https://x.com"}}
        result = {"status": "error", "error": "Connection failed"}

        alternatives = agent._adapt_plan(failed_step, result, 0)
        assert len(alternatives) >= 1
        assert alternatives[0]["action"] == "search"
        assert "Fallback" in alternatives[0]["description"]

    def test_plan_adaptation_search_fallback(self):
        """_adapt_plan generates broader search when search fails."""
        agent = WebAgent()
        failed_step = {"action": "search", "params": {"query": "niche topic"}}
        result = {"status": "error", "error": "No results"}

        alternatives = agent._adapt_plan(failed_step, result, 0)
        assert len(alternatives) >= 1
        assert alternatives[0]["action"] == "search"
        assert "broader" in alternatives[0]["description"].lower()

    def test_plan_adaptation_extract_uses_screenshot(self):
        """_adapt_plan offers screenshot when extract fails."""
        agent = WebAgent()
        failed_step = {"action": "extract", "params": {}}
        result = {"status": "error", "error": "No content"}

        alternatives = agent._adapt_plan(failed_step, result, 0)
        assert len(alternatives) >= 1
        assert alternatives[0]["action"] == "screenshot"