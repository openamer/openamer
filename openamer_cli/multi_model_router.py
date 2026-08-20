"""Multi-Model Routing — route tasks to the best model for each job.

Routes different task types to different models:
- Coding tasks → fast coding model
- Creative tasks → creative model  
- Analysis → deep reasoning model
- Quick chats → cheap/fast model
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelRoute:
    """A routing rule for a model."""
    name: str
    model: str
    provider: str = ""
    task_types: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    priority: int = 10
    description: str = ""


@dataclass
class RoutingResult:
    """Result of a routing decision."""
    model: str
    provider: str
    route_name: str
    confidence: float


class MultiModelRouter:
    """Route tasks to the best model based on task type."""

    def __init__(self, config_path: Optional[str] = None):
        self._routes: List[ModelRoute] = self._default_routes()
        if config_path:
            self._load_config(config_path)

    def _default_routes(self) -> List[ModelRoute]:
        return [
            ModelRoute("coding", "deepseek/deepseek-v4-flash:0731", "openrouter",
                      task_types=["code", "debug", "refactor"],
                      keywords=["code", "fix", "bug", "implement", "function", "class", "test"],
                      priority=1, description="Fast model for coding tasks"),
            ModelRoute("creative", "anthropic/claude-sonnet-4", "openrouter",
                      task_types=["write", "creative", "design"],
                      keywords=["write", "create", "design", "draft", "poem", "story"],
                      priority=2, description="Creative model for writing tasks"),
            ModelRoute("analysis", "openai/o3-mini", "openrouter",
                      task_types=["analyze", "research", "reason"],
                      keywords=["analyze", "research", "compare", "evaluate", "explain"],
                      priority=3, description="Deep reasoning model"),
            ModelRoute("quick", "deepseek/deepseek-chat", "openrouter",
                      task_types=["chat", "quick", "simple"],
                      keywords=["hello", "hi", "thanks", "yes", "no", "simple"],
                      priority=4, description="Cheap/fast model for simple queries"),
            ModelRoute("default", "deepseek/deepseek-v4-flash:0731", "openrouter",
                      task_types=["default"],
                      keywords=[],
                      priority=999, description="Default fallback model"),
        ]

    def _load_config(self, path: str) -> None:
        try:
            with open(path) as f:
                data = json.load(f)
            for route_data in data.get("routes", []):
                self._routes.append(ModelRoute(**route_data))
        except Exception as exc:
            logger.warning("Failed to load routing config: %s", exc)

    def route(self, task: str, task_type: str = "") -> RoutingResult:
        """Route a task to the best model.

        Args:
            task: The task description or user message
            task_type: Optional explicit task type

        Returns:
            RoutingResult with model, provider, and confidence
        """
        task_lower = task.lower()

        # First: try to match by explicit task type
        if task_type:
            for route in sorted(self._routes, key=lambda r: r.priority):
                if task_type in route.task_types:
                    return RoutingResult(
                        model=route.model,
                        provider=route.provider,
                        route_name=route.name,
                        confidence=0.9,
                    )

        # Second: try keyword matching
        best_route = None
        best_matches = 0
        for route in sorted(self._routes, key=lambda r: r.priority):
            if not route.keywords:
                continue
            matches = sum(1 for kw in route.keywords if kw in task_lower)
            if matches > best_matches:
                best_matches = matches
                best_route = route

        if best_route and best_matches > 0:
            confidence = min(0.5 + (best_matches * 0.1), 0.95)
            return RoutingResult(
                model=best_route.model,
                provider=best_route.provider,
                route_name=best_route.name,
                confidence=confidence,
            )

        # Fallback: default route
        default = next((r for r in self._routes if "default" in r.task_types), self._routes[0])
        return RoutingResult(
            model=default.model,
            provider=default.provider,
            route_name=default.name,
            confidence=0.3,
        )

    def list_routes(self) -> List[ModelRoute]:
        return self._routes.copy()


def cmd_route(args) -> None:
    """Route a task to the best model."""
    router = MultiModelRouter()
    action = getattr(args, "route_action", None)

    if action == "list":
        routes = router.list_routes()
        print(f"Model Routes ({len(routes)}):")
        print(f"{'Name':<15} {'Model':<40} {'Priority':<10}")
        print("-" * 65)
        for r in routes:
            print(f"{r.name:<15} {r.model:<40} {r.priority:<10}")

    elif action == "check":
        task = getattr(args, "task", "")
        task_type = getattr(args, "type", "")
        result = router.route(task, task_type)
        print(f"Task: {task[:60]}")
        print(f"Routed to: {result.model}")
        print(f"Provider: {result.provider}")
        print(f"Route: {result.route_name} (confidence: {result.confidence:.0%})")

    else:
        print("Usage: openamer route <list|check> [args]")


def build_route_parser(subparsers) -> None:
    """Add ``openamer route`` subcommand."""
    parser = subparsers.add_parser(
        "route",
        help="Route tasks to the best model",
        description="Route different task types to different models automatically.",
    )
    sub = parser.add_subparsers(dest="route_action")

    sub.add_parser("list", help="List all routing rules")

    check_p = sub.add_parser("check", help="Check which model a task would route to")
    check_p.add_argument("task", help="The task description")
    check_p.add_argument("--type", "-t", default="", help="Explicit task type")

    parser.set_defaults(func=cmd_route)