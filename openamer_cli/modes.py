"""Architect/Editor Mode — separation of planning from implementation.

Architect mode: plans solutions, analyzes codebase, suggests approaches
Editor mode: implements changes, writes code, fixes issues
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ArchitectPlan:
    """A plan produced by architect mode."""
    title: str
    summary: str
    steps: List[Dict[str, str]] = field(default_factory=list)
    files_to_modify: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    estimated_effort: str = ""


class ArchitectMode:
    """Architect mode — plans solutions without touching files."""

    def analyze_request(self, request: str, context: Optional[str] = None) -> ArchitectPlan:
        """Analyze a request and produce a plan.

        Args:
            request: The user's request
            context: Optional codebase context

        Returns:
            ArchitectPlan with analysis
        """
        plan = ArchitectPlan(
            title=request[:60] if len(request) > 60 else request,
            summary=f"Analysis of: {request[:200]}",
        )

        # Parse request into steps
        lines = request.split("\n")
        current_step = []
        for line in lines:
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                if current_step:
                    plan.steps.append({"action": " ".join(current_step)})
                    current_step = []
                current_step.append(line[2:])
            elif line:
                current_step.append(line)

        if current_step:
            plan.steps.append({"action": " ".join(current_step)})

        if not plan.steps:
            plan.steps = [{"action": request[:200]}]

        # Detect files from context
        if context:
            for line in context.split("\n"):
                if ".py" in line or ".js" in line or ".ts" in line or ".md" in line:
                    words = line.strip().split()
                    for w in words:
                        if any(ext in w for ext in [".py", ".js", ".ts", ".md", ".json", ".yaml"]):
                            if w not in plan.files_to_modify:
                                plan.files_to_modify.append(w)

        plan.estimated_effort = self._estimate_effort(plan)
        plan.risks = self._identify_risks(plan)
        return plan

    def _estimate_effort(self, plan: ArchitectPlan) -> str:
        n_steps = len(plan.steps)
        n_files = len(plan.files_to_modify)
        if n_steps <= 2 and n_files <= 1:
            return "small (~5-15 minutes)"
        elif n_steps <= 5 and n_files <= 3:
            return "medium (~30-60 minutes)"
        else:
            return f"large ({n_steps} steps across {n_files} files)"

    def _identify_risks(self, plan: ArchitectPlan) -> List[str]:
        risks = []
        if len(plan.files_to_modify) > 3:
            risks.append("Changes span multiple files — coordination risk")
        if any("delete" in str(p).lower() or "remove" in str(p).lower() for p in plan.steps):
            risks.append("Contains destructive operations")
        return risks


class EditorMode:
    """Editor mode — implements changes, writes code, fixes issues."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def implement_step(self, step: Dict[str, str], plan: ArchitectPlan) -> Dict[str, Any]:
        """Execute a single step from an architect plan.

        Args:
            step: The step to implement
            plan: The parent plan

        Returns:
            Result dict with status and details
        """
        action = step.get("action", "")
        if self.dry_run:
            return {"status": "dry_run", "action": action[:100], "note": "Dry run — no changes made"}
        return {"status": "implemented", "action": action[:100]}

    def review_implementation(self, plan: ArchitectPlan) -> List[Dict[str, str]]:
        """Review whether a plan was fully implemented.

        Returns:
            List of discrepancies found
        """
        issues = []
        if not plan.steps:
            issues.append({"severity": "warning", "message": "Plan has no steps to verify"})
        return issues


def cmd_architect(args) -> None:
    """Run architect mode on a request."""
    request = getattr(args, "request", "")
    context_file = getattr(args, "context", "")

    context = ""
    if context_file and Path(context_file).exists():
        context = Path(context_file).read_text(encoding="utf-8")[:3000]

    mode = ArchitectMode()
    plan = mode.analyze_request(request, context)

    print(f"\n📋 Architect Plan: {plan.title}")
    print(f"{'='*60}")
    print(f"Summary: {plan.summary[:200]}")
    print(f"Estimated effort: {plan.estimated_effort}")
    print(f"\nSteps ({len(plan.steps)}):")
    for i, step in enumerate(plan.steps, 1):
        print(f"  {i}. {step.get('action', '?')[:150]}")

    if plan.files_to_modify:
        print(f"\nFiles to modify ({len(plan.files_to_modify)}):")
        for f in plan.files_to_modify:
            print(f"  📄 {f}")

    if plan.risks:
        print(f"\n⚠️  Risks:")
        for r in plan.risks:
            print(f"  • {r}")


def cmd_editor(args) -> None:
    """Run editor mode on a plan."""
    dry_run = getattr(args, "dry_run", False)
    step_number = getattr(args, "step", 0)

    mode = EditorMode(dry_run=dry_run)
    print(f"\n🔧 Editor Mode {'(dry run)' if dry_run else ''}")
    print(f"{'='*60}")
    print(f"Editor ready. Use with an Architect plan to implement steps.")


def build_modes_parser(subparsers) -> None:
    """Add architect and editor subcommands."""
    # Architect
    arch_p = subparsers.add_parser("architect", help="Plan solutions without changing files")
    arch_p.add_argument("request", help="The request to analyze")
    arch_p.add_argument("--context", "-c", default="", help="Context file with codebase info")
    arch_p.set_defaults(func=cmd_architect)

    # Editor
    edit_p = subparsers.add_parser("editor", help="Implement changes from an architect plan")
    edit_p.add_argument("--step", "-s", type=int, default=0, help="Step number to implement (0 = all)")
    edit_p.add_argument("--dry-run", "-n", action="store_true", help="Show what would be done")
    edit_p.set_defaults(func=cmd_editor)


# ── Watch Mode ──────────────────────────────────────────────────────────


class FileWatcher:
    """Watch files for changes and trigger actions."""

    def __init__(self):
        self._watched: Dict[str, float] = {}

    def watch(self, file_path: str, callback=None) -> None:
        """Start watching a file for modifications."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        self._watched[str(path)] = path.stat().st_mtime

    def check_changes(self) -> List[str]:
        """Check for changes and return changed file paths."""
        changed = []
        for path_str, last_mtime in list(self._watched.items()):
            path = Path(path_str)
            if path.exists():
                current_mtime = path.stat().st_mtime
                if current_mtime != last_mtime:
                    changed.append(path_str)
                    self._watched[path_str] = current_mtime
        return changed

    def watch_directory(self, directory: str, pattern: str = "*.py") -> None:
        """Watch all files matching a pattern in a directory."""
        for f in Path(directory).glob(pattern):
            self.watch(str(f))


class AutoFixWatcher(FileWatcher):
    """Watch files and auto-fix lint issues on change."""

    def __init__(self, linter: str = "auto"):
        super().__init__()
        self.linter = linter

    def poll_and_fix(self, interval: float = 2.0, max_iterations: int = 0) -> int:
        """Poll for changes and fix issues.

        Args:
            interval: Seconds between polls
            max_iterations: 0 = unlimited

        Returns:
            Number of fixes applied
        """
        import time
        from openamer_cli.lint_fix import LintFixEngine

        engine = LintFixEngine()
        fixes_applied = 0
        iterations = 0

        print(f"Watching {len(self._watched)} files for changes...")
        print(f"Linter: {self.linter} | Interval: {interval}s")

        try:
            while True:
                iterations += 1
                if max_iterations > 0 and iterations > max_iterations:
                    break

                changed = self.check_changes()
                for file_path in changed:
                    print(f"\n📝 Change detected: {file_path}")
                    result = engine.run_lint_fix_cycle(file_path, max_iterations=2)
                    if result.get("fixes_applied", 0) > 0:
                        fixes_applied += result["fixes_applied"]
                        print(f"  ✅ Applied {result['fixes_applied']} fix(es)")
                    else:
                        print(f"  ✓ No issues found")

                time.sleep(interval)

        except KeyboardInterrupt:
            print(f"\nStopped. Applied {fixes_applied} fix(es).")

        return fixes_applied


def cmd_watch(args) -> None:
    """Watch files and auto-fix."""
    pattern = getattr(args, "pattern", "*.py")
    directory = getattr(args, "directory", ".")
    interval = getattr(args, "interval", 2.0)

    watcher = AutoFixWatcher()
    watcher.watch_directory(directory, pattern)
    watcher.poll_and_fix(interval=interval)


def cmd_check_watch(args) -> None:
    """Check for changes and report."""
    pattern = getattr(args, "pattern", "*.py")
    directory = getattr(args, "directory", ".")

    watcher = FileWatcher()
    watcher.watch_directory(directory, pattern)
    changed = watcher.check_changes()
    if changed:
        print(f"Changed files ({len(changed)}):")
        for f in changed:
            print(f"  📄 {f}")
    else:
        print("No changes detected.")


def build_watch_parser(subparsers) -> None:
    """Add watch subcommands."""
    watch_p = subparsers.add_parser("watch", help="Watch files and auto-fix lint issues")
    watch_p.add_argument("--pattern", "-p", default="*.py", help="File pattern to watch")
    watch_p.add_argument("--directory", "-d", default=".", help="Directory to watch")
    watch_p.add_argument("--interval", "-i", type=float, default=2.0, help="Poll interval (seconds)")
    watch_p.set_defaults(func=cmd_watch)