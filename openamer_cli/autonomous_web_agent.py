"""Autonomous Web Agent — self-directed internet navigation for OpenAmer.

The WebAgent class wraps OpenAmer's browser_* and web_search tools into a plan-
driven autonomous agent that can set goals, navigate websites, extract data,
search the web, and adapt when things go wrong.

CLI commands:
    openamer web-agent run "<goal>"   — execute a goal autonomously
    openamer web-agent plan "<goal>"  — show the plan (no execution)
    openamer web-agent status         — show running agent status
    openamer web-agent log            — show last action log
"""

from __future__ import annotations

import json
import logging
import re
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Globals — shared mutable state for the CLI commands
# ---------------------------------------------------------------------------
_last_agent: Optional["WebAgent"] = None
_last_plan: Optional["WebPlan"] = None


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class PlanStatus(str, Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# WebPlan dataclass
# ---------------------------------------------------------------------------

@dataclass
class WebPlan:
    """A plan for autonomous web navigation."""

    goal: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    results: Dict[str, Any] = field(default_factory=dict)
    status: PlanStatus = PlanStatus.RUNNING
    log: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": self.steps,
            "current_step": self.current_step,
            "results": self.results,
            "status": self.status.value,
            "log": self.log[-50:],  # keep last 50 entries
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebPlan":
        plan = cls(goal=data["goal"])
        plan.steps = data.get("steps", [])
        plan.current_step = data.get("current_step", 0)
        plan.results = data.get("results", {})
        plan.status = PlanStatus(data.get("status", "running"))
        plan.log = data.get("log", [])
        return plan


# ---------------------------------------------------------------------------
# WebAgent class
# ---------------------------------------------------------------------------

# Default step templates used by _build_plan when no LLM is available
_STEP_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "search": [
        {"action": "search", "params": {"query": "{goal}"},
         "description": "Search the web for information about the goal"},
        {"action": "extract", "params": {},
         "description": "Extract search results content"},
        {"action": "decide", "params": {},
         "description": "Analyse results and decide next step"},
    ],
    "visit_url": [
        {"action": "navigate", "params": {"url": "{url}"},
         "description": "Navigate to the target URL"},
        {"action": "extract", "params": {},
         "description": "Extract page content"},
        {"action": "decide", "params": {},
         "description": "Analyse page and decide next step"},
    ],
    "compare": [
        {"action": "search", "params": {"query": "{goal}"},
         "description": "Search for comparison data"},
        {"action": "extract", "params": {},
         "description": "Extract comparison results"},
        {"action": "decide", "params": {},
         "description": "Analyse comparisons and decide next step"},
    ],
    "form_fill": [
        {"action": "navigate", "params": {"url": "{url}"},
         "description": "Navigate to form page"},
        {"action": "fill_form", "params": {"fields": "{fields}"},
         "description": "Fill in the form fields"},
        {"action": "extract", "params": {},
         "description": "Extract results after form submission"},
    ],
}


class WebAgent:
    """Autonomous web agent that can plan and execute multi-step web tasks.

    Wraps the OpenAmer browser_* tools (navigate, click, type, snapshot) and
    web_search into a plan-driven loop with retry and adaptation logic.

    Typical workflow::

        agent = WebAgent(max_steps=10)
        result = agent.execute_plan(
            "Find the Top 3 AI news this month and summarise them"
        )
        print(result["summary"])
    """

    def __init__(
        self,
        max_steps: int = 20,
        retry_limit: int = 3,
        headless: bool = True,
        verbose: bool = False,
    ):
        self.max_steps = max_steps
        self.retry_limit = retry_limit
        self.headless = headless
        self.verbose = verbose
        self._plan: Optional[WebPlan] = None
        self._browser_initialized = False
        self._current_url: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API — browser actions (thin wrappers around OpenAmer tools)
    # ------------------------------------------------------------------

    def navigate_to(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL and wait for the page to load.

        Returns the page snapshot or error dict.
        """
        self._log(f"🌐 Navigating to: {url}")
        try:
            result = _browser_navigate(url)
            self._current_url = url
            self._browser_initialized = True
            self._log(f"✅ Navigated to {url}")
            return {"status": "ok", "url": url, "result": result}
        except Exception as exc:
            self._log(f"❌ Navigation failed: {exc}")
            return {"status": "error", "error": str(exc)}

    def search(self, query: str) -> Dict[str, Any]:
        """Perform a web search and collect results.

        Uses the configured search tool (web_search or a fallback).
        Returns a dict with 'results' list.
        """
        self._log(f"🔍 Searching: {query}")
        try:
            results = _web_search(query)
            self._log(f"✅ Search returned {len(results)} results")
            return {"status": "ok", "query": query, "results": results}
        except Exception as exc:
            self._log(f"❌ Search failed: {exc}")
            return {"status": "error", "error": str(exc), "results": []}

    def click_element(self, ref: str) -> Dict[str, Any]:
        """Click on an element identified by its snapshot ref (e.g. '@e5')."""
        self._log(f"🖱️ Clicking element: {ref}")
        try:
            result = _browser_click(ref)
            self._log(f"✅ Clicked {ref}")
            return {"status": "ok", "ref": ref, "result": result}
        except Exception as exc:
            self._log(f"❌ Click failed: {exc}")
            return {"status": "error", "error": str(exc)}

    def type_text(self, ref: str, text: str) -> Dict[str, Any]:
        """Type text into an input field identified by snapshot ref."""
        self._log(f"⌨️ Typing '{text[:30]}...' into {ref}")
        try:
            result = _browser_type(ref, text)
            self._log(f"✅ Typed into {ref}")
            return {"status": "ok", "ref": ref, "result": result}
        except Exception as exc:
            self._log(f"❌ Type failed: {exc}")
            return {"status": "error", "error": str(exc)}

    def extract_content(self) -> Dict[str, Any]:
        """Extract text content from the current page.

        Returns a dict with 'content' (plain text) and 'title'.
        """
        self._log("📄 Extracting page content")
        try:
            snapshot = _browser_snapshot(full=True)
            self._log(f"✅ Extracted {len(snapshot.get('content', ''))} chars")
            return {
                "status": "ok",
                "content": snapshot.get("content", ""),
                "title": snapshot.get("title", ""),
            }
        except Exception as exc:
            self._log(f"❌ Extraction failed: {exc}")
            return {"status": "error", "error": str(exc), "content": ""}

    def fill_form(self, fields_dict: Dict[str, str]) -> Dict[str, Any]:
        """Fill a form with field_name -> value mappings.

        Takes a snapshot, finds each field by label/placeholder, and types
        the corresponding value.
        """
        self._log(f"📝 Filling form with {len(fields_dict)} fields")
        results = {}
        try:
            snapshot = _browser_snapshot()
            for field_name, value in fields_dict.items():
                ref = _find_field_ref(snapshot, field_name)
                if ref:
                    self.type_text(ref, value)
                    results[field_name] = "filled"
                else:
                    self._log(f"⚠️ Field '{field_name}' not found on page")
                    results[field_name] = "not_found"
            return {"status": "ok", "fields": results}
        except Exception as exc:
            self._log(f"❌ Form fill failed: {exc}")
            return {"status": "error", "error": str(exc)}

    def take_screenshot(self) -> Dict[str, Any]:
        """Capture a screenshot of the current page.

        Returns the path to the screenshot file or error.
        """
        self._log("📸 Taking screenshot")
        try:
            path = _browser_screenshot()
            self._log(f"✅ Screenshot saved: {path}")
            return {"status": "ok", "path": path}
        except Exception as exc:
            self._log(f"❌ Screenshot failed: {exc}")
            return {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Plan execution
    # ------------------------------------------------------------------

    def execute_plan(self, goal: str) -> Dict[str, Any]:
        """Execute an autonomous web search/navigation plan for the given goal.

        This is the main entry point. It:
        1. Builds a step-by-step plan from the goal
        2. Executes each step in order
        3. On failure, retries with adaptive alternatives up to retry_limit
        4. Returns the collected results as a structured dict

        Args:
            goal: A natural-language goal like "Find the cheapest flight
                  from Berlin to Tokyo next week"

        Returns:
            Dict with keys: status, summary, results, plan (WebPlan dict)
        """
        global _last_agent, _last_plan

        _last_agent = self
        self._plan = WebPlan(goal=goal)
        _last_plan = self._plan
        self._plan.log.append(f"🚀 Starting goal: {goal}")

        # Step 1: build the plan
        self._plan.steps = self._build_plan(goal)
        self._plan.log.append(f"📋 Plan has {len(self._plan.steps)} steps")

        # Step 2: execute steps
        step_results: List[Dict[str, Any]] = []

        for step_idx, step in enumerate(self._plan.steps):
            if self._plan.status == PlanStatus.CANCELLED:
                break
            if step_idx >= self.max_steps:
                self._plan.log.append("⚠️ Max steps reached, stopping")
                break

            self._plan.current_step = step_idx
            self._plan.log.append(
                f"▶️ Step {step_idx + 1}/{len(self._plan.steps)}: "
                f"{step.get('description', step['action'])}"
            )

            result = self._execute_step_with_retry(step, step_idx)
            step_results.append(result)

            # Store result keyed by a meaningful name
            result_key = step.get("store_key") or f"step_{step_idx}"
            self._plan.results[result_key] = result

            # If a step fails critically, adapt the plan
            if result.get("status") == "error" and not result.get("recovered"):
                adapted = self._adapt_plan(step, result, step_idx)
                if adapted:
                    self._plan.log.append(f"🔄 Plan adapted — {len(adapted)} new steps")
                    # Insert new steps after current position
                    self._plan.steps[step_idx + 1:step_idx + 1] = adapted
                else:
                    self._plan.log.append("⛔ No recovery possible, failing")
                    self._plan.status = PlanStatus.FAILED
                    break

        # Step 3: summarise
        if self._plan.status == PlanStatus.RUNNING:
            self._plan.status = PlanStatus.DONE

        summary = self._summarise_results(goal, step_results)
        self._plan.log.append(f"✅ Goal complete. Summary: {summary[:200]}")

        return {
            "status": self._plan.status.value,
            "summary": summary,
            "results": self._plan.results,
            "plan": self._plan.to_dict(),
            "steps_executed": len(step_results),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_plan(self, goal: str) -> List[Dict[str, Any]]:
        """Build a step-by-step plan from the goal using templates.

        Uses rule-based heuristics to determine the right plan template
        based on keywords in the goal.
        """
        goal_lower = goal.lower()

        # Detect goal type and pick appropriate steps
        if any(w in goal_lower for w in ["vergleich", "compare", "cheapest",
                                          "günstig", "price", "preis",
                                          "cost", "kosten", "billig"]):
            base = self._clone_steps("compare")
        elif any(w in goal_lower for w in ["suche", "search", "find", "finde",
                                           "top", "best", "beste"]):
            base = self._clone_steps("search")
        elif any(w in goal_lower for w in ["form", "fill", "register",
                                           "signup", "anmelden", "buchung"]):
            base = self._clone_steps("form_fill")
        else:
            base = self._clone_steps("search")

        # Fill in template variables
        for step in base:
            for key, value in list(step.get("params", {}).items()):
                if isinstance(value, str) and "{goal}" in value:
                    step["params"][key] = value.replace("{goal}", goal)
            if "description" in step and "{goal}" in step["description"]:
                step["description"] = step["description"].replace("{goal}", goal)

        # Add a final summarise step
        base.append({
            "action": "summarise",
            "params": {"goal": goal},
            "description": "Summarise collected results into final answer",
            "store_key": "final_summary",
        })

        return base

    def _clone_steps(self, template_name: str) -> List[Dict[str, Any]]:
        """Deep-clone a step template."""
        import copy
        template = _STEP_TEMPLATES.get(template_name, _STEP_TEMPLATES["search"])
        steps = []
        for step in template:
            s = copy.deepcopy(step)
            s["attempts"] = 0
            s["max_attempts"] = self.retry_limit
            steps.append(s)
        return steps

    def _execute_step_with_retry(
        self, step: Dict[str, Any], step_idx: int
    ) -> Dict[str, Any]:
        """Execute a single step with retry logic."""
        action = step["action"]
        params = step.get("params", {})
        attempt = 0
        last_error = ""

        while attempt < self.retry_limit:
            attempt += 1
            step["attempts"] = attempt
            try:
                if action == "navigate":
                    url = params.get("url", "")
                    result = self.navigate_to(url)
                elif action == "search":
                    query = params.get("query", "")
                    result = self.search(query)
                elif action == "click":
                    ref = params.get("ref", "")
                    result = self.click_element(ref)
                elif action == "type":
                    ref = params.get("ref", "")
                    text = params.get("text", "")
                    result = self.type_text(ref, text)
                elif action == "extract":
                    result = self.extract_content()
                elif action == "fill_form":
                    fields = params.get("fields", {})
                    result = self.fill_form(fields)
                elif action == "screenshot":
                    result = self.take_screenshot()
                elif action == "decide":
                    result = self._decide_next(step_idx)
                else:
                    result = {"status": "error", "error": f"Unknown action: {action}"}

                if result.get("status") != "error":
                    return result

                last_error = result.get("error", "Unknown error")
            except Exception as exc:
                last_error = str(exc)

            if attempt < self.retry_limit:
                self._log(f"🔄 Retry {attempt}/{self.retry_limit}: {last_error}")

        return {"status": "error", "error": last_error, "attempts": attempt}

    def _decide_next(self, current_step_idx: int) -> Dict[str, Any]:
        """Analyse current results and decide the next action.

        This is the agent's 'reasoning' step. It looks at what we've
        collected so far and formulates the next navigation or extraction.
        """
        results = self._plan.results
        steps = self._plan.steps
        goal = self._plan.goal

        # Check if we already have enough information
        content_keys = [k for k, v in results.items() if isinstance(v, dict)
                        and v.get("status") == "ok"
                        and v.get("content", "")]
        if len(content_keys) >= 2:
            # We've collected content from 2+ pages — proceed to summarise
            return {"status": "ok", "decision": "summarise", "reason": "Sufficient data collected"}

        # If the last step extracted content, look for links to follow
        last_result = results.get(f"step_{current_step_idx}", {})
        content = last_result.get("content", "")

        # Detect URLs in extracted content
        urls = re.findall(r'https?://[^\s"\'<>]+', content)
        if urls and len(steps) - current_step_idx < 3:
            next_url = urls[0]
            new_step = {
                "action": "navigate",
                "params": {"url": next_url},
                "description": f"Follow link: {next_url[:60]}",
                "attempts": 0,
                "max_attempts": self.retry_limit,
            }
            # Insert after current position
            steps.insert(current_step_idx + 1, new_step)
            return {"status": "ok", "decision": "follow_link",
                    "url": next_url}

        # Default — do another search with refined terms
        refined_query = self._refine_query(goal, results)
        new_step = {
            "action": "search",
            "params": {"query": refined_query},
            "description": f"Refined search: {refined_query}",
            "attempts": 0,
            "max_attempts": self.retry_limit,
        }
        steps.insert(current_step_idx + 1, new_step)
        return {"status": "ok", "decision": "refine_search",
                "query": refined_query}

    def _refine_query(self, goal: str, results: Dict[str, Any]) -> str:
        """Create a refined search query based on goal and partial results."""
        # Extract any result snippets to inform the refined query
        snippets = []
        for key, result in results.items():
            if isinstance(result, dict):
                for r in result.get("results", []):
                    if isinstance(r, dict):
                        snippets.append(r.get("title", ""))
                        snippets.append(r.get("snippet", ""))

        combined = " ".join(snippets)[:200]
        if "preis" in goal.lower() or "price" in goal.lower() or "cost" in goal.lower():
            return f"{goal} — pricing details 2025"
        elif "github" in goal.lower():
            return f"{goal} stars:>100"
        elif "news" in goal.lower():
            return f"{goal} 2025 monthly roundup"

        if combined:
            return f"{goal} — detailed information"
        return goal

    def _adapt_plan(
        self, failed_step: Dict[str, Any], result: Dict[str, Any], step_idx: int
    ) -> List[Dict[str, Any]]:
        """When a step fails, try to generate alternative steps."""
        action = failed_step["action"]
        alternatives: List[Dict[str, Any]] = []
        goal = self._plan.goal if self._plan else "complete the task"

        if action == "navigate":
            # Try searching instead
            alternatives.append({
                "action": "search",
                "params": {"query": goal},
                "description": "Fallback: search for the information",
                "attempts": 0,
                "max_attempts": self.retry_limit,
                "store_key": f"fallback_search_{step_idx}",
            })
        elif action == "search":
            # Try with different search terms
            alternatives.append({
                "action": "search",
                "params": {"query": goal + " overview"},
                "description": "Fallback: broader search",
                "attempts": 0,
                "max_attempts": self.retry_limit,
                "store_key": f"fallback_broad_{step_idx}",
            })
        elif action == "extract":
            # Try screenshot + OCR fallback
            alternatives.append({
                "action": "screenshot",
                "params": {},
                "description": "Fallback: screenshot the page",
                "attempts": 0,
                "max_attempts": self.retry_limit,
                "store_key": f"fallback_screenshot_{step_idx}",
            })

        return alternatives

    def _summarise_results(
        self, goal: str, step_results: List[Dict[str, Any]]
    ) -> str:
        """Build a human-readable summary from all collected results."""
        lines = [f"## Ergebnis für: {goal}", ""]

        for i, result in enumerate(step_results):
            if not isinstance(result, dict):
                continue
            status = result.get("status", "?")
            if status == "ok":
                # Extract meaningful content
                content = result.get("content", "")
                title = result.get("title", "")
                results_list = result.get("results", [])

                if title:
                    lines.append(f"**Seite {i + 1}**: {title}")
                if content:
                    # Take first 500 chars
                    preview = content[:500].strip()
                    lines.append(f"```\n{preview}\n```")
                if results_list:
                    for item in results_list[:5]:
                        if isinstance(item, dict):
                            t = item.get("title", "")
                            s = item.get("snippet", "")
                            link = item.get("link", "")
                            if t:
                                lines.append(f"- **{t}**")
                            if s:
                                lines.append(f"  {s[:200]}")
                            if link:
                                lines.append(f"  🔗 {link}")
                lines.append("")
            elif status == "error":
                lines.append(f"  ⚠️ Schritt {i + 1} fehlgeschlagen: {result.get('error', '')}")
                lines.append("")

        if not any(r.get("status") == "ok" for r in step_results if isinstance(r, dict)):
            lines.append("Keine erfolgreichen Ergebnisse. Mögliche Probleme:")
            lines.append("- Die Website hat sich geändert oder ist nicht erreichbar")
            lines.append("- Der Suchdienst hat keine relevanten Ergebnisse geliefert")
            lines.append("- Es wurde kein passender Inhalt gefunden")
            lines.append("")

        return "\n".join(lines).strip()

    def _log(self, message: str) -> None:
        """Add a message to the plan log and optionally print it."""
        if self._plan:
            self._plan.log.append(message)
        if self.verbose:
            print(f"[WebAgent] {message}")

    # ------------------------------------------------------------------
    # Status / log access
    # ------------------------------------------------------------------

    @property
    def plan(self) -> Optional[WebPlan]:
        return self._plan


# ---------------------------------------------------------------------------
# CLI command functions
# ---------------------------------------------------------------------------

def cmd_run(args: Any) -> None:
    """Execute ``openamer web-agent run <goal>``."""
    goal = args.goal
    verbose = getattr(args, "verbose", False)

    agent = WebAgent(max_steps=20, verbose=verbose)
    print(f"🚀 Autonomous Web Agent — Ziel: {goal}")
    print(f"   Max Schritte: {agent.max_steps}\n")

    try:
        result = agent.execute_plan(goal)
        print("\n" + "=" * 60)
        print("📋 ERGEBNIS")
        print("=" * 60)
        status = result.get("status", "?")
        summary = result.get("summary", "Keine Zusammenfassung.")
        steps = result.get("steps_executed", 0)

        print(f"Status: {status}")
        print(f"Schritte ausgeführt: {steps}")
        print(f"\n{summary}")

        if status == "failed":
            plan_dict = result.get("plan", {})
            logs = plan_dict.get("log", [])
            error_logs = [l for l in logs if "❌" in l or "⛔" in l]
            if error_logs:
                print("\n⚠️ Fehler:")
                for err in error_logs[-5:]:
                    print(f"  {err}")

    except KeyboardInterrupt:
        if agent.plan:
            agent.plan.status = PlanStatus.CANCELLED
        print("\n⏹️  Abgebrochen.")
    except Exception as exc:
        print(f"\n❌ Fehler: {exc}")
        traceback.print_exc()


def cmd_plan(args: Any) -> None:
    """Show the plan for a goal without executing it (``openamer web-agent plan``)."""
    goal = args.goal
    agent = WebAgent()
    steps = agent._build_plan(goal)

    print(f"\n📋 PLAN für: {goal}")
    print("=" * 60)
    for i, step in enumerate(steps):
        action = step["action"]
        desc = step.get("description", action)
        params = step.get("params", {})
        print(f"\n  {i + 1}. [{action}] {desc}")
        for k, v in params.items():
            if isinstance(v, str) and len(v) > 80:
                v = v[:77] + "..."
            if v:
                print(f"     {k}: {v}")
    print(f"\nTotal: {len(steps)} Schritte")
    print("(Use 'web-agent run' to execute this plan)\n")


def cmd_status(args: Any) -> None:
    """Show the status of the last web-agent run (``openamer web-agent status``)."""
    global _last_plan
    if _last_plan is None:
        print("Kein vorheriger Web-Agenten-Lauf gefunden.")
        print("Führe zuerst 'openamer web-agent run \"<ziel>\"' aus.")
        return

    plan = _last_plan
    print(f"\n📊 STATUS")
    print("=" * 60)
    print(f"Ziel:     {plan.goal}")
    print(f"Status:   {plan.status.value}")
    print(f"Schritt:  {plan.current_step + 1}/{len(plan.steps)}")
    print(f"Ergebnisse: {len(plan.results)}")
    print(f"Log-Einträge: {len(plan.log)}")

    if plan.status == PlanStatus.DONE:
        print("\n✅ Abgeschlossen.")
    elif plan.status == PlanStatus.FAILED:
        print("\n❌ Fehlgeschlagen.")
        errors = [l for l in plan.log if "❌" in l or "⛔" in l]
        if errors:
            print("Letzte Fehler:")
            for e in errors[-3:]:
                print(f"  {e}")
    elif plan.status == PlanStatus.RUNNING:
        print("\n⏳ Läuft noch...")
        current_step = plan.steps[plan.current_step] if plan.current_step < len(plan.steps) else {}
        print(f"Aktuelle Aktion: {current_step.get('description', '?')}")
    print()


def cmd_log(args: Any) -> None:
    """Show the full log of the last web-agent run (``openamer web-agent log``)."""
    global _last_plan
    if _last_plan is None:
        print("Kein vorheriger Web-Agenten-Lauf gefunden.")
        return

    log = _last_plan.log
    show_all = getattr(args, "all", False)

    print(f"\n📜 LOG ({len(log)} Einträge)")
    print("=" * 60)

    entries = log if show_all else log[-30:]

    for entry in entries:
        # Colour-code by prefix emoji
        if entry.startswith("❌") or entry.startswith("⛔"):
            print(f"  ⛔ {entry[2:].strip()}")
        elif entry.startswith("✅"):
            print(f"  ✓ {entry[2:].strip()}")
        elif entry.startswith("🔄"):
            print(f"  ⟳ {entry[2:].strip()}")
        elif entry.startswith("🚀"):
            print(f"  ▶ {entry[2:].strip()}")
        else:
            print(f"  {entry}")

    if not show_all and len(log) > 30:
        print(f"\n... und {len(log) - 30} weitere Einträge (use --all)\n")
    else:
        print()


# ---------------------------------------------------------------------------
# Parser builder — called from main.py
# ---------------------------------------------------------------------------

def build_web_agent_parser(subparsers) -> None:
    """Add ``openamer web-agent`` subcommand tree.

    Subcommands:
        run     — execute a goal autonomously
        plan    — show plan without executing
        status  — show status of the last run
        log     — show the action log of the last run
    """
    parser = subparsers.add_parser(
        "web-agent",
        help="Autonomous Web Agent — plan and execute web tasks",
        description=(
            "Autonomous Web Agent that can navigate websites, search the web, "
            "extract data, and fill forms to accomplish complex multi-step goals."
        ),
    )
    # Register sub-subparsers
    wsub = parser.add_subparsers(dest="web_subcommand", required=True)

    # --- web-agent run ---
    run_parser = wsub.add_parser(
        "run",
        help="Execute a goal autonomously",
        description="Run the autonomous web agent with a natural-language goal.",
    )
    run_parser.add_argument("goal", help="The goal to accomplish (e.g. 'Find the cheapest flight from Berlin to Tokyo')")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Print verbose output during execution")
    run_parser.set_defaults(func=cmd_run)

    # --- web-agent plan ---
    plan_parser = wsub.add_parser(
        "plan",
        help="Show the execution plan for a goal (no execution)",
        description="Preview the step-by-step plan the agent would execute for a given goal.",
    )
    plan_parser.add_argument("goal", help="The goal to plan for")
    plan_parser.set_defaults(func=cmd_plan)

    # --- web-agent status ---
    status_parser = wsub.add_parser(
        "status",
        help="Show status of the last web-agent run",
        description="Display the current status of the most recent autonomous web-agent execution.",
    )
    status_parser.set_defaults(func=cmd_status)

    # --- web-agent log ---
    log_parser = wsub.add_parser(
        "log",
        help="Show the action log of the last run",
        description="Display the full action log from the most recent web-agent execution.",
    )
    log_parser.add_argument("--all", "-a", action="store_true", help="Show all log entries (default: last 30)")
    log_parser.set_defaults(func=cmd_log)


# =========================================================================
# Tool wrappers — these call the actual OpenAmer browser/web tools
# The module-level functions below are real wrappers; they get monkey-
# patched by tests.
# =========================================================================

def _browser_navigate(url: str) -> Dict[str, Any]:
    """Real wrapper for the browser_navigate tool."""
    # In production, this calls the actual tool via the runtime.
    # For now, we try the available browser tool directly.
    from openamer_tools import browser_navigate as _bn
    result = _bn(url=url)
    return result


def _browser_snapshot(full: bool = False) -> Dict[str, Any]:
    """Real wrapper for browser_snapshot."""
    try:
        from openamer_tools import browser_snapshot as _bs
        return _bs(full=full)
    except (ImportError, AttributeError):
        return {"content": "", "title": "Unknown"}


def _browser_click(ref: str) -> Dict[str, Any]:
    """Real wrapper for browser_click."""
    from openamer_tools import browser_click as _bc
    return _bc(ref=ref)


def _browser_type(ref: str, text: str) -> Dict[str, Any]:
    """Real wrapper for browser_type."""
    from openamer_tools import browser_type as _bt
    return _bt(ref=ref, text=text)


def _browser_screenshot() -> str:
    """Real wrapper — returns path to screenshot file."""
    # Use the computer_use tool with capture mode
    from openamer_tools import computer_use as _cu
    result = _cu(action="capture", mode="vision")
    if isinstance(result, dict):
        return result.get("path", "")
    return ""


def _web_search(query: str) -> List[Dict[str, Any]]:
    """Real wrapper for web search."""
    try:
        from openamer_tools import web_search as _ws
        result = _ws(query=query)
        # Normalise: web_search returns varied shapes
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("results", result.get("items", []))
        return []
    except (ImportError, AttributeError):
        return [{"title": "No search tool available", "snippet": "",
                 "link": ""}]


def _find_field_ref(snapshot: Dict[str, Any], field_name: str) -> Optional[str]:
    """Find the ref of a form field by name/label in a snapshot."""
    content = snapshot.get("content", "") or ""
    elements = snapshot.get("elements", []) or []

    field_lower = field_name.lower()

    # Try to find by label in elements
    for elem in elements:
        label = (elem.get("label", "") or "").lower()
        role = elem.get("role", "") or ""
        ref = elem.get("ref", "") or ""
        if field_lower in label and "textbox" in role:
            return ref
        if field_lower in label and "input" in role:
            return ref

    # Regex fallback: look for aria-label or placeholder in content
    for pattern in [
        rf'aria-label="[^"]*{re.escape(field_name)}[^"]*"\s+(ref="[^"]+")',
        rf'placeholder="[^"]*{re.escape(field_name)}[^"]*"\s+(ref="[^"]+")',
    ]:
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            ref_match = re.search(r'ref="([^"]+)"', m.group(0))
            if ref_match:
                return ref_match.group(1)

    return None