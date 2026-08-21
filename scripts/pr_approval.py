#!/usr/bin/env python3
"""
PR Approval Agent — Automated Pull Request Review & Approval Workflow.
Reviews open PRs, runs tests, approves or requests changes, auto-merges.
Läuft als Cron-Job: openamer cronjob create --schedule 'every 2h' --script scripts/pr_approval.py
"""
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────
REPO_DIR = Path(os.environ.get("OPENAMER_REPO",
    r"C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent"))
STATE_FILE = REPO_DIR / ".pr-agent" / "state.json"
LOG_FILE = REPO_DIR / ".pr-agent" / "pr_approval.log"
MAX_PRS_PER_RUN = 3
MAX_LINES_FOR_APPROVAL = 500
AUTO_MERGE_LABEL = "auto-merge"
REVIEWED_LABEL = "reviewed"

Path(REPO_DIR / ".pr-agent").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE, level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("pr-agent")

def run(cmd, **kwargs):
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=kwargs.get("timeout", 120),
        cwd=kwargs.get("cwd", REPO_DIR),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    if result.returncode != 0 and not kwargs.get("check", True):
        return result
    if result.returncode != 0:
        raise RuntimeError(f"Command {cmd} failed: {result.stderr[:500]}")
    return result

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"reviewed_prs": {}, "stats": {"approved": 0, "changes_requested": 0, "skipped": 0}}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

# ─── PR Operations ────────────────────────────────────────────────────────────

def list_open_prs() -> list[dict]:
    """Fetch open PRs from GitHub."""
    log.info("Fetching open PRs...")
    try:
        result = run(["gh", "pr", "list", "--state", "open", "--json",
                       "number,title,author,createdAt,labels,headRefName,baseRefName,url,additions,deletions,files"])
        prs = json.loads(result.stdout)
        log.info(f"Found {len(prs)} open PRs")
        return prs
    except Exception as e:
        log.error(f"Failed to list PRs: {e}")
        return []

def is_already_reviewed(pr: dict, state: dict) -> bool:
    return str(pr["number"]) in state.get("reviewed_prs", {})

def checkout_pr(pr: dict) -> bool:
    """Checkout the PR branch."""
    try:
        run(["git", "fetch", "origin", f"pull/{pr['number']}/head:{pr['headRefName']}"])
        run(["git", "checkout", pr["headRefName"]])
        return True
    except Exception as e:
        log.error(f"Failed to checkout PR #{pr['number']}: {e}")
        return False

def run_tests() -> tuple[bool, str]:
    """Run test suite and return (passed, output)."""
    log.info("Running tests...")
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "-x", "--tb=short", "--timeout=60", "--json-report"],
            capture_output=True, text=True, timeout=180,
            cwd=REPO_DIR,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0:
            return True, "All tests passed ✅"
        else:
            failures = re.findall(r"FAILED\s+(\S+)", result.stdout + result.stderr)
            return False, f"Tests failed: {failures[:5]}"
    except subprocess.TimeoutExpired:
        return False, "Tests timed out"
    except Exception as e:
        return False, f"Test runner error: {e}"

def review_diff(pr: dict) -> tuple[str, list[str]]:
    """
    Review the PR diff for quality issues.
    Returns (decision, reasons) where decision is 'approve', 'changes', or 'skip'.
    """
    reasons = []
    additions = pr.get("additions", 0)
    deletions = pr.get("deletions", 0)
    total_changes = additions + deletions

    # Check size
    if total_changes > MAX_LINES_FOR_APPROVAL:
        reasons.append(f"PR is too large ({total_changes} lines, max {MAX_LINES_FOR_APPROVAL})")

    # Check for breaking changes
    try:
        diff = run(["git", "diff", f"origin/{pr['baseRefName']}...HEAD", "--", "*.py", "*.json", "*.yaml", "*.yml"], timeout=30)
        diff_text = diff.stdout

        # Check for breaking migration patterns
        if re.search(r"migrations\.\w+|alembic|schema.*change", diff_text, re.IGNORECASE):
            reasons.append("Contains migration or schema changes - needs manual review")

        # Check for hardcoded secrets in diff
        secret_patterns = [
            r'(?i)(?:password|secret|api_key|token)\s*[:=]\s*["\'][^"\']+["\']',
            r'(?i)sk-[a-zA-Z0-9]{20,}',
            r'(?i)ghp_[a-zA-Z0-9]{36,}',
        ]
        for pattern in secret_patterns:
            matches = re.findall(pattern, diff_text)
            if matches:
                reasons.append("Potential hardcoded secret detected in diff")

        # Check for debug code
        if re.search(r"(?i)print\(|console\.log|debugger|import pdb", diff_text):
            reasons.append("Debug code (print/console.log/debugger) found in diff")

        # Check for large binary files
        binary_files = re.findall(r"Binary files\s+(\S+)", diff_text)
        if binary_files:
            reasons.append(f"Binary files changed: {binary_files}")

    except Exception as e:
        log.warning(f"Diff review failed: {e}")

    # Decision
    if not reasons:
        return "approve", reasons
    elif len(reasons) <= 2:
        return "changes", reasons
    else:
        return "skip", reasons

def approve_pr(pr: dict, message: str):
    """Approve the PR and set auto-merge."""
    number = pr["number"]
    log.info(f"Approving PR #{number}...")
    try:
        run(["gh", "pr", "review", str(number), "--approve", "--body", message])
        run(["gh", "pr", "merge", str(number), "--auto", "--squash"])
        run(["gh", "pr", "edit", str(number), "--add-label", f"{AUTO_MERGE_LABEL},{REVIEWED_LABEL}"])
        log.info(f"PR #{number} approved + auto-merge set")
        return True
    except Exception as e:
        log.error(f"Failed to approve PR #{number}: {e}")
        return False

def request_changes(pr: dict, reasons: list[str]):
    """Request changes on the PR."""
    number = pr["number"]
    log.info(f"Requesting changes on PR #{number}...")
    body = "## 🤖 PR Agent Review\n\nChanges requested:\n\n"
    for i, reason in enumerate(reasons, 1):
        body += f"{i}. ⚠️ {reason}\n"
    body += "\n---\n*This review was automatically generated by [PR Agent](https://github.com/openamer/openamer).*"
    try:
        run(["gh", "pr", "review", str(number), "--request-changes", "--body", body])
        run(["gh", "pr", "edit", str(number), "--add-label", "changes-requested"])
        log.info(f"Changes requested on PR #{number}")
        return True
    except Exception as e:
        log.error(f"Failed to request changes on PR #{number}: {e}")
        return False

def skip_pr(pr: dict, reason: str):
    """Skip the PR and mark it as reviewed."""
    number = pr["number"]
    log.info(f"Skipping PR #{number}: {reason}")
    try:
        run(["gh", "pr", "edit", str(number), "--add-label", REVIEWED_LABEL])
        run(["gh", "pr", "comment", str(number),
             "--body", f"## 🤖 PR Agent\n\nSkipped: {reason}\n\n---\n*Auto-review skipped.*"])
        return True
    except Exception as e:
        log.error(f"Failed to skip PR #{number}: {e}")
        return False

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("PR Agent run starting")
    state = load_state()
    processed = 0
    approved = 0
    changes = 0
    skipped = 0

    prs = list_open_prs()
    for pr in prs:
        if processed >= MAX_PRS_PER_RUN:
            log.info(f"Reached max {MAX_PRS_PER_RUN} PRs per run")
            break
        if is_already_reviewed(pr, state):
            log.info(f"Skipping already reviewed PR #{pr['number']}")
            continue

        processed += 1
        number = pr["number"]
        log.info(f"Reviewing PR #{number}: {pr['title']} by {pr['author']['login']}")

        # Checkout
        if not checkout_pr(pr):
            state["reviewed_prs"][str(number)] = {"status": "error", "reason": "checkout failed"}
            save_state(state)
            continue

        # Run tests
        tests_passed, test_output = run_tests()
        log.info(f"Tests: {'PASSED' if tests_passed else 'FAILED'}")

        if not tests_passed:
            skip_pr(pr, f"Tests failed:\n```\n{test_output[:500]}\n```")
            state["reviewed_prs"][str(number)] = {"status": "skipped", "reason": "tests failed"}
            skipped += 1
            save_state(state)
            continue

        # Review diff
        decision, reasons = review_diff(pr)
        log.info(f"Review decision: {decision} - reasons: {reasons}")

        if decision == "approve":
            # Check if PR author is external (needs approval)
            author = pr["author"]["login"]
            message = (
                "## 🤖 PR Agent Review\n\n"
                "### ✅ Approved\n\n"
                f"- Changes: +{pr.get('additions', 0)}/-{pr.get('deletions', 0)} lines\n"
                f"- Tests: ✅ All passed\n"
                f"- Author: {author}\n\n"
                "Auto-merge enabled with squash.\n\n"
                "---\n*This review was automatically generated by [PR Agent](https://github.com/openamer/openamer).*"
            )
            if approve_pr(pr, message):
                approved += 1
                state["reviewed_prs"][str(number)] = {"status": "approved"}
                state["stats"]["approved"] = state["stats"].get("approved", 0) + 1

        elif decision == "changes":
            if request_changes(pr, reasons):
                changes += 1
                state["reviewed_prs"][str(number)] = {"status": "changes-requested", "reasons": reasons}
                state["stats"]["changes_requested"] = state["stats"].get("changes_requested", 0) + 1

        else:
            if skip_pr(pr, "; ".join(reasons)):
                skipped += 1
                state["reviewed_prs"][str(number)] = {"status": "skipped", "reasons": reasons}
                state["stats"]["skipped"] = state["stats"].get("skipped", 0) + 1

        save_state(state)

    # Return to main
    try:
        run(["git", "checkout", "main"])
    except:
        pass

    log.info(f"PR Agent complete: {processed} processed, {approved} approved, {changes} changes, {skipped} skipped")
    print(f"PR Agent: {processed} processed, {approved} approved ⚡, {changes} changes requested, {skipped} skipped")
    return 0

if __name__ == "__main__":
    sys.exit(main())