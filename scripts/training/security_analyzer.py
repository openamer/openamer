#!/usr/bin/env python3
"""Security analyzer — validates every tool action BEFORE execution.

Inspired by OpenHands SDK's 4th core responsibility (Security Validation):
analyze proposed actions for safety before executing them.

Verdicts:
  allow — action is safe, execute
  warn  — action is risky but plausible; execute, but log for review
  block — action violates a hard safety boundary; refuse to execute

Design: deterministic pattern rules, no LLM call (fast, reliable, 0 cost).
Violations are appended to security_violations.jsonl for review — like
Devin's enterprise guardrails, but local and self-owned.

Boundaries (why these rules exist):
- The agent belongs to Damir; it must never destroy his system or data.
- Cross-profile paths belong to OTHER agent instances — not this one.
- Secrets must never travel through tool params (they end up in logs).
"""
import json
import os
import re
import time
from pathlib import Path

_HOME = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer-laptop")))
LOG = _HOME / "scripts" / "training" / "security_violations.jsonl"

ALLOW, WARN, BLOCK = "allow", "warn", "block"

# --- hard blocks: never execute, no exceptions --------------------------------
DESTRUCTIVE_SHELL = [
    r"rm\s+-rf\s+/(?!tmp)",          # rm -rf / (anything except /tmp)
    r"rm\s+-rf\s+[A-Z]:\\?$",        # rm -rf C:
    r"mkfs",                          # format filesystem
    r"format\s+[A-Z]:",              # format C:
    r"del\s+/[fsq]",                 # del /f /s /q
    r"rd\s+/s\s+/q",                 # rd /s /q
    r"remove-item.*-recurse.*-force",  # PS mass delete
    r":\s*\(\)\s*\{.*\|.*&.*\}",  # fork bomb (whitespace-tolerant)
    r"shutdown\s+/s|/s\s+/t\s+0",    # immediate shutdown
    r"reg\s+delete\s+HKLM",          # registry core delete
    r"bcdedit\s+/set.*recoveryenabled\s+no",  # kill recovery
]

SECRET_PARAMS = re.compile(
    r"(api[_-]?key|secret|password|passwd|credential|private[_-]?key|"
    r"access[_-]?token|auth[_-]?token|bearer)\s*['\"\s:=]", re.IGNORECASE)

SECRET_VALUES = re.compile(
    r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|xox[bp]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,})", re.IGNORECASE)

# paths belonging to other profiles — cross-profile soft guard
OTHER_PROFILE = re.compile(r"openamer-laptop[/\\]profiles[/\\](?!default)[^/\\]+")

# --- warns: execute but log ----------------------------------------------------
WARN_SHELL = [
    r"git\s+push\s+--force",          # history rewrite risk
    r"git\s+reset\s+--hard",          # uncommitted work loss
    r"drop\s+table|drop\s+database",  # database deletion
    r"truncate\s+table",              # db truncate
    r"crontab\s+-r",                  # remove all cron
    r"taskkill\s+/f\s+/im\s+(python|ollama|node)",  # kill core services
]


def _matches(patterns, text):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def analyze_action(tool, params):
    """Return (verdict, reason). Called before EVERY tool execution."""
    # serialize params once for pattern checks
    try:
        text = json.dumps(params, ensure_ascii=False, default=str)
    except Exception:
        text = str(params)

    # 1) destructive shell commands -> BLOCK
    shell = ""
    if tool in ("shell", "terminal", "bash") or "command" in params:
        shell = str(params.get("command", params.get("cmd", "")) or "")
    if shell and _matches(DESTRUCTIVE_SHELL, shell):
        return BLOCK, f"destructive shell pattern: {shell[:80]!r}"

    # 2) secrets in params -> BLOCK (they leak into logs)
    if SECRET_PARAMS.search(text) or SECRET_VALUES.search(text):
        return BLOCK, "secrets must never be passed through tool params"

    # 3) cross-profile writes -> BLOCK (other profiles are not ours)
    if OTHER_PROFILE.search(text):
        return BLOCK, "cross-profile path detected — other profiles are off-limits"

    # 4) risky but plausible -> WARN
    if shell and _matches(WARN_SHELL, shell):
        return WARN, f"risky shell pattern: {shell[:80]!r}"
    if tool in ("file", "write_file") and "C:/Windows" in text.replace("\\", "/").lower():
        return WARN, "write inside Windows system directory"
    if re.search(r"\bdelete|remove\b", str(params.get("action", "")), re.IGNORECASE) \
            and str(params.get("path", "")).strip() == "C:\\":
        return WARN, "delete operation on a root path"

    return ALLOW, ""


def log_violation(tool, params, verdict, reason):
    """Append a violation record for later review (Devin-style violations log)."""
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "tool": tool,
                "verdict": verdict,
                "reason": reason,
                "params": json.dumps(params, ensure_ascii=False, default=str)[:300],
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass  # logging must never break execution


def check(tool, params):
    """Gate function: returns (verdict, reason) and logs non-allow verdicts."""
    verdict, reason = analyze_action(tool, params)
    if verdict != ALLOW:
        log_violation(tool, params, verdict, reason)
    return verdict, reason


if __name__ == "__main__":
    # smoke: self-test the rules
    cases = [
        ("terminal", {"command": "rm -rf /"}, BLOCK),
        ("terminal", {"command": "ls -la"}, ALLOW),
        ("file", {"path": os.path.join(os.path.expanduser("~"), "x.txt")}, ALLOW),
        ("terminal", {"command": "git push --force origin main"}, WARN),
        ("web", {"url": "https://x.com"}, ALLOW),
    ]
    for t, p, want in cases:
        got, why = analyze_action(t, p)
        status = "OK" if got == want else "FAIL"
        print(f"[{status}] {t} {str(p)[:50]} -> {got} (want {want})")