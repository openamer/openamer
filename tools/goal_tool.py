"""Model-facing ``goal`` tool: let the agent see and steer its own goal.

Adapted from deepseek-ai/deepseek-harness ``packages/goal`` (which
exposes ``get_goal`` / ``create_goal`` / ``update_goal`` as model tools
on top of the same goal service the ``/goal`` command drives).

The gap this closes in OpenAmer
-------------------------------
OpenAmer already has the most powerful autonomous mechanism it owns: a
durable goal with an auto-continuation loop. But the goal is a **black
box** to the model. The model cannot:

* read what the goal actually is (it only sees a continuation prompt),
* report that it is blocked,
* narrow or amend the objective when it turns out to be wrong,
* use the turn budget knowingly.

Worse, every turn costs an **extra LLM call** — the judge decides
"done" or "continue". A model that can judge its own progress in the
same turn is both cheaper and better informed than one that guesses and
waits for a verdict.

The tool is deliberately thin: it wraps the existing ``GoalManager``
rather than reimplementing the domain. Every existing guarantee —
persistence, revision, continuation loop, wait barriers — keeps working.

Scope
-----
The tool reads and mutates the goal for the *current session*. It does
not replace the judge: the judge still runs and can still end the loop.
What the tool adds is the model's ability to participate.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)


GOAL_SCHEMA = {
    "name": "goal",
    "description": (
        "Read or steer the durable goal of this session. Use 'read' to see "
        "the objective, the contract, the turn budget and the last verdict; "
        "use 'set' to define the goal; use 'amend' to narrow it or add a "
        "sub-goal; use 'report' to declare the goal done or blocked; use "
        "'pause'/'resume' to stop or restart the auto-continuation loop. "
        "The goal survives turns and is the thing the auto-continuation "
        "loop works toward."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "set", "amend", "report", "pause", "resume"],
                "description": "What to do with the goal.",
            },
            "goal": {
                "type": "string",
                "description": (
                    "For 'set': the objective, phrased as a completion "
                    "criterion. For 'amend': extra criteria appended to the "
                    "existing goal."
                ),
            },
            "max_turns": {
                "type": "integer",
                "description": (
                    "For 'set': how many auto-continuation turns the goal may "
                    "use. Omit for the default."
                ),
            },
            "status": {
                "type": "string",
                "enum": ["done", "blocked"],
                "description": (
                    "For 'report': whether the goal is complete or blocked. "
                    "'blocked' needs a reason in 'reason'."
                ),
            },
            "reason": {
                "type": "string",
                "description": "For 'report'/'pause': why.",
            },
        },
        "required": ["action"],
    },
}


def _manager_for(parent_agent):
    """Return a GoalManager bound to the agent's session, or None."""
    if parent_agent is None:
        return None
    try:
        from openamer_cli.goals import GoalManager
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("goal manager unavailable: %s", exc)
        return None

    session_id = getattr(parent_agent, "session_id", None) or ""
    if not session_id:
        return None

    # Reuse the agent's manager when it already has one (the CLI binds
    # one per session); otherwise bind a fresh one to the same session.
    existing = getattr(parent_agent, "_goal_manager", None)
    if existing is not None:
        return existing
    try:
        return GoalManager(session_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("could not bind goal manager: %s", exc)
        return None


def _state_payload(manager) -> Dict[str, Any]:
    """Render the goal state for the model."""
    if not manager.has_goal():
        return {"goal": None, "status": "none"}

    payload: Dict[str, Any] = {}
    try:
        state = manager.state
    except Exception:
        state = None

    if state is not None:
        payload.update(
            {
                "goal": state.goal,
                "status": state.status,
                "turns_used": state.turns_used,
                "max_turns": state.max_turns,
                "last_verdict": state.last_verdict,
                "last_reason": state.last_reason,
                "paused_reason": state.paused_reason,
                "subgoals": list(state.subgoals),
            }
        )
        if state.waiting_on_pid or state.waiting_on_session or state.waiting_until:
            payload["waiting"] = {
                "pid": state.waiting_on_pid,
                "session_id": state.waiting_on_session,
                "until": state.waiting_until,
                "reason": state.waiting_reason,
            }
    else:
        payload["goal"] = manager.status_line()

    try:
        if manager.has_contract():
            payload["contract"] = manager.render_contract()
    except Exception:
        pass

    return payload


def goal_tool(
    action: Optional[str] = None,
    goal: Optional[str] = None,
    max_turns: Optional[int] = None,
    status: Optional[str] = None,
    reason: Optional[str] = None,
    parent_agent=None,
    **_kwargs,
) -> str:
    """Read or steer the session goal."""
    manager = _manager_for(parent_agent)
    if manager is None:
        return tool_error(
            "goal requires a session-bound agent context."
        )

    action = (action or "read").strip().lower()

    try:
        if action == "read":
            payload = _state_payload(manager)
            return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

        if action == "set":
            if not goal or not goal.strip():
                return tool_error("'set' requires a non-empty 'goal'.")
            manager.set(goal.strip(), max_turns=max_turns)
            return json.dumps(
                {"ok": True, **_state_payload(manager)},
                ensure_ascii=False, indent=2, default=str,
            )

        if action == "amend":
            if not goal or not goal.strip():
                return tool_error("'amend' requires a non-empty 'goal'.")
            manager.add_subgoal(goal.strip())
            return json.dumps(
                {"ok": True, **_state_payload(manager)},
                ensure_ascii=False, indent=2, default=str,
            )

        if action == "report":
            if status == "done":
                manager.mark_done(reason or "reported done by the agent")
                return json.dumps(
                    {"ok": True, **_state_payload(manager)},
                    ensure_ascii=False, indent=2, default=str,
                )
            if status == "blocked":
                if not reason:
                    return tool_error(
                        "Reporting 'blocked' requires a 'reason' so the loop "
                        "knows what to unblock."
                    )
                manager.pause(reason=f"blocked: {reason}")
                return json.dumps(
                    {"ok": True, **_state_payload(manager)},
                    ensure_ascii=False, indent=2, default=str,
                )
            return tool_error("'report' requires status 'done' or 'blocked'.")

        if action == "pause":
            state = manager.pause(reason or "paused by the agent")
            if state is None:
                return tool_error("No active goal to pause.")
            return json.dumps(
                {"ok": True, **_state_payload(manager)},
                ensure_ascii=False, indent=2, default=str,
            )

        if action == "resume":
            state = manager.resume()
            if state is None:
                return tool_error("No goal to resume.")
            return json.dumps(
                {"ok": True, **_state_payload(manager)},
                ensure_ascii=False, indent=2, default=str,
            )

    except Exception as exc:
        logger.warning("goal tool failed: %s", exc)
        return tool_error(f"goal '{action}' failed: {exc}")

    return tool_error(f"Unknown goal action: {action}")


def check_goal_requirements() -> bool:
    """The tool needs the goal service to be importable."""
    try:
        from openamer_cli.goals import GoalManager  # noqa: F401

        return True
    except Exception:
        return False


registry.register(
    name="goal",
    toolset="goal",
    schema=GOAL_SCHEMA,
    handler=lambda args, **kw: goal_tool(
        action=args.get("action"),
        goal=args.get("goal"),
        max_turns=args.get("max_turns"),
        status=args.get("status"),
        reason=args.get("reason"),
        parent_agent=kw.get("parent_agent"),
    ),
    check_fn=check_goal_requirements,
    emoji="🎯",
)
