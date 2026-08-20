"""Guardrails — configurable safety rules for agent actions.

Extends the existing HITL system with pre-defined safety policies.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GuardrailRule:
    """A single guardrail rule."""
    name: str
    description: str
    action_type: str  # terminal_command, file_write, network_request, etc.
    pattern: str = ""  # regex pattern to check against
    allow: bool = False  # True = allow, False = block
    severity: str = "warning"  # warning, error, critical


class GuardrailEngine:
    """Configurable guardrail engine for agent safety."""

    def __init__(self, config_path: Optional[str] = None):
        self._rules: List[GuardrailRule] = self._load_defaults()
        if config_path:
            self._load_config(config_path)

    def _load_defaults(self) -> List[GuardrailRule]:
        return [
            GuardrailRule("no-rm-rf", "Prevent recursive deletion", "terminal_command",
                         r"rm\s+-rf\s*/", allow=False, severity="critical"),
            GuardrailRule("no-chmod-777", "Prevent world-writable permissions", "terminal_command",
                         r"chmod\s+777", allow=False, severity="error"),
            GuardrailRule("no-curl-pipe-bash", "Prevent curl-to-bash", "terminal_command",
                         r"curl.*\|.*bash", allow=False, severity="error"),
            GuardrailRule("no-wget-pipe-sh", "Prevent wget-to-sh", "terminal_command",
                         r"wget.*\|.*sh", allow=False, severity="error"),
            GuardrailRule("no-etc-password", "Prevent reading /etc/passwd", "terminal_command",
                         r"cat\s+/etc/passwd", allow=False, severity="warning"),
            GuardrailRule("no-docker-exec", "Prevent docker exec without approval", "terminal_command",
                         r"docker\s+exec", allow=False, severity="warning"),
            GuardrailRule("no-curl-external", "Flag external curl requests", "terminal_command",
                         r"curl\s+https?://", allow=True, severity="warning"),
            GuardrailRule("no-write-sensitive", "Prevent writing to sensitive paths", "file_write",
                         r"/(etc|boot|sys|proc)/", allow=False, severity="critical"),
        ]

    def _load_config(self, path: str) -> None:
        """Load custom rules from a JSON config file."""
        try:
            import json
            with open(path) as f:
                data = json.load(f)
            for rule_data in data.get("rules", []):
                self._rules.append(GuardrailRule(**rule_data))
        except Exception as exc:
            logger.warning("Failed to load guardrail config: %s", exc)

    def check(self, action_type: str, content: str) -> List[GuardrailRule]:
        """Check an action against all guardrail rules.

        Args:
            action_type: Type of action (terminal_command, file_write, etc.)
            content: The command or content to check

        Returns:
            List of violated rules
        """
        violations = []
        for rule in self._rules:
            if rule.action_type != action_type:
                continue
            if rule.pattern and re.search(rule.pattern, content, re.IGNORECASE):
                if not rule.allow:
                    violations.append(rule)
        return violations

    def is_allowed(self, action_type: str, content: str) -> tuple[bool, list]:
        """Check if an action is allowed.

        Returns:
            (allowed: bool, violated_rules: list)
        """
        violations = self.check(action_type, content)
        critical = [v for v in violations if v.severity == "critical"]
        if critical:
            return False, violations
        errors = [v for v in violations if v.severity == "error"]
        if errors:
            return False, violations
        return True, violations

    def add_rule(self, rule: GuardrailRule) -> None:
        """Add a custom guardrail rule."""
        self._rules.append(rule)

    def list_rules(self, action_type: Optional[str] = None) -> List[GuardrailRule]:
        """List all rules, optionally filtered by action type."""
        if action_type:
            return [r for r in self._rules if r.action_type == action_type]
        return self._rules.copy()


def cmd_guardrails(args) -> None:
    """Manage guardrails."""
    engine = GuardrailEngine()
    action = getattr(args, "guardrails_action", None)

    if action == "list":
        rules = engine.list_rules()
        if rules:
            print(f"Guardrail Rules ({len(rules)}):")
            print(f"{'Name':<30} {'Type':<20} {'Severity':<10} {'Allow':<6}")
            print("-" * 70)
            for r in rules:
                print(f"{r.name:<30} {r.action_type:<20} {r.severity:<10} {str(r.allow):<6}")
        else:
            print("No guardrail rules configured.")

    elif action == "check":
        action_type = getattr(args, "action_type", "terminal_command")
        content = getattr(args, "content", "")
        allowed, violations = engine.is_allowed(action_type, content)
        if allowed:
            print(f"✅ Action allowed: {content[:80]}")
        else:
            print(f"❌ Action blocked by {len(violations)} rule(s):")
            for v in violations:
                print(f"   - {v.name}: {v.description}")

    else:
        print("Usage: openamer guardrails <list|check> [args]")


def build_guardrails_parser(subparsers) -> None:
    """Add ``openamer guardrails`` subcommand."""
    parser = subparsers.add_parser(
        "guardrails",
        help="Manage safety guardrails for agent actions",
        description="List and check guardrail rules that prevent dangerous actions.",
    )
    sub = parser.add_subparsers(dest="guardrails_action")

    sub.add_parser("list", help="List all guardrail rules")

    check_p = sub.add_parser("check", help="Check if an action is allowed")
    check_p.add_argument("action_type", nargs="?", default="terminal_command",
                        help="Action type (terminal_command, file_write, network_request)")
    check_p.add_argument("content", nargs="?", default="", help="Command or content to check")

    parser.set_defaults(func=cmd_guardrails)