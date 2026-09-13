"""Enforced plan mode — read-only tool gating, not a prompt-level suggestion.

Why a gate and not a skill
--------------------------
``/plan`` already exists as a bundled *skill* that writes a markdown plan. That
is a behaviour the model can ignore: the write tools stay available the whole
time, so "plan first" is a request, not a property of the session. Every serious
competitor enforces it instead — Claude Code's plan mode ("auto-allow does not
widen approvals in plan mode"), omp's Plan + Goal modes, Cline's Plan/Act toggle,
Codex's ``read-only`` permission profile, Qwen's parity table.

This module is the enforcement: while the gate is active, tools that change
state are refused before they run, and the refusal tells the model exactly what
to do instead (present the plan, ask for approval to act).

Design (AGENTS.md: capability at the edges, core is a narrow waist)
------------------------------------------------------------------
The gate is a plain object consulted next to the existing tool guardrails. It
adds no model tool, mutates no system prompt, and is inert when disabled — the
default. It is deliberately *fail-closed in the safe direction*: an unknown tool
name is treated as non-mutating only if it is absent from a curated deny set, and
that set is the single place to extend.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "MUTATING_TOOLS",
    "READ_ONLY_SAFE_TOOLS",
    "PlanModeGate",
    "is_mutating",
]

#: Tools that change state outside the conversation. Anything here is refused
#: while plan mode is active. Extend this set — never a per-call special case.
MUTATING_TOOLS: frozenset[str] = frozenset(
    {
        # Files and shell
        "write_file",
        "patch",
        "terminal",
        "process",  # write/kill/submit into a running process
        "execute_code",
        "code_execution",
        # Desktop / UI automation
        "computer_use",
        # Self-modification of the agent's own knowledge
        "skill_manage",
        "memory",
        # Scheduling and delegation (a subagent can write on our behalf)
        "cronjob",
        "delegate_task",
        # Browser: navigation is read-only, but forms/keys are not, and the
        # distinction is not per-call decidable — so the whole tool is gated.
        "browser_click",
        "browser_type",
        "browser_press",
        "browser_navigate",
        # Project / workspace mutation
        "project_create",
        "project_switch",
        # Connected devices and services
        "homeassistant",
        "kanban",
        "discord",
        "discord_admin",
        "spotify",
        "yuanbao",
        # Generation has side effects (cost, external state) and is never needed
        # to produce a plan.
        "image_generate",
        "video_generate",
    }
)

#: Tools that are explicitly fine in plan mode. Listed so the intent is legible
#: and so a reviewer can see the read side was considered, not just the deny side.
READ_ONLY_SAFE_TOOLS: frozenset[str] = frozenset(
    {
        "read_file",
        "search_files",
        "skills_list",
        "skill_view",
        "session_search",
        "web_search",
        "web_extract",
        "browser_snapshot",
        "browser_get_images",
        "browser_console",
        "browser_vision",
        "browser_scroll",
        "browser_back",
        "read_terminal",
        "vision_analyze",
        "todo",
        "clarify",
        "list_apps",
        "list_windows",
    }
)


def is_mutating(tool_name: str) -> bool:
    """True when ``tool_name`` must be refused while plan mode is active.

    Unknown tools are treated as **mutating** — a new tool defaults to safe
    (blocked) rather than silently opening a write path in plan mode. That is the
    §"fail closed" choice, and it is why this is a function and not a set lookup
    at the call sites.
    """
    name = (tool_name or "").strip()
    if name in READ_ONLY_SAFE_TOOLS:
        return False
    # Anything not explicitly known to be read-only — including a tool added
    # after this list was written — is treated as mutating.
    return True


@dataclass
class PlanModeGate:
    """Session-scoped read-only gate."""

    enabled: bool = False

    def check(self, tool_name: str) -> tuple[bool, str]:
        """Return ``(allowed, refusal_reason)``.

        The reason is written to be *actionable for the model* rather than a
        generic denial: it names the tool, states the rule, and says what to do
        next, because a refusal the model cannot act on just burns a turn.
        """
        if not self.enabled:
            return True, ""
        if not is_mutating(tool_name):
            return True, ""
        return False, self.refusal_message(tool_name)

    @staticmethod
    def refusal_message(tool_name: str) -> str:
        return (
            f"Plan mode is active: `{tool_name}` changes state and was not run.\n"
            "In plan mode you may only read and investigate. Do this instead:\n"
            "  1. finish exploring with read-only tools,\n"
            "  2. present the plan you intend to execute (files to touch, steps,\n"
            "     risks), and\n"
            "  3. ask the user to approve, which leaves plan mode.\n"
            "Do not retry this tool — it will be refused again."
        )

    def status(self) -> dict[str, object]:
        """Small status payload for a `/plan-mode` style surface."""
        return {
            "enabled": self.enabled,
            "refused_tools": sorted(MUTATING_TOOLS),
            "allowed_tools_explicit": sorted(READ_ONLY_SAFE_TOOLS),
        }