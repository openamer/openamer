#!/usr/bin/env python3
"""Cron watchdog: Skill Safety Scan (daily).

Motivation: the 2026-09-16 competitor scan surfaced China's CVERC "skill
poisoning" advisory — counterfeit agent skill packs whose hidden prompt text
made the agent fetch a trojan. This laptop holds 800+ skills and imports them
from external repos (skill-discovery, skills-hub-cache, darwin harvesting), and
nothing in the toolchain read a skill for hostile content:
  scan_untracked_secrets.py -> credentials only
  security-cve-scan.py      -> pip CVEs only
  skill-validator.py        -> quality/format score only
This wrapper closes that gap and runs the read on a schedule.

Watchdog contract (same shape as competitor_scan.py):
  - exit 0 always for a normal run; findings are reported in the output, and
    only HIGH findings become an alert line the cron runner delivers.
  - exit 1 ONLY if the scanner itself could not run (missing script, crash) —
    a genuinely quiet/clean day must never look like a broken watchdog.

Silent when clean and when only medium/low findings exist.
"""
import json
import os
import subprocess
import sys

_HOME = os.environ.get("OPENAMER_HOME") or os.path.join(
    os.path.expanduser("~"), "AppData", "Local", "openamer-laptop")
SCANNER = os.path.join(_HOME, "scripts", "scan_skill_safety.py")
SKILLS = os.path.join(_HOME, "skills")
REPORT = os.path.join(_HOME, "reports", "skill-safety-latest.json")

# Findings we have already reviewed and accepted. Without this the daily job
# re-alerts on the same known items forever and the user stops reading it.
# Each entry is "file::detector" — keyed on file+class, not line, so the note
# survives unrelated edits above it.
KNOWN_REVIEWED = {
    # the project's own installer one-liner in our own skill docs: expected
    "autonomous-ai-agents/openamer-agent/SKILL.md::egress-or-exec",
    # a 62-char zero-width sequence inside a downloaded hub index cache file:
    # third-party metadata, not agent instructions; regenerated on re-download
    ".hub/index-cache/lobehub_index.json::invisible-unicode",
}


def main() -> int:
    if not os.path.isdir(_HOME) or not os.path.isfile(SCANNER):
        print(f"[skill-safety] scan failed: scanner missing at {SCANNER}")
        return 1
    if not os.path.isdir(SKILLS):
        print(f"[skill-safety] scan failed: skills dir missing at {SKILLS}")
        return 1

    try:
        out = subprocess.run(
            [sys.executable, SCANNER, "--json", "--severity", "low",
             "--fail-level", "none"],
            capture_output=True, text=True, encoding="utf-8", timeout=240)
    except subprocess.TimeoutExpired:
        print("[skill-safety] scan failed: timed out after 240s")
        return 1
    except Exception as e:
        print(f"[skill-safety] scan failed: {type(e).__name__}: {e}")
        return 1

    if not out.stdout or not out.stdout.strip():
        print(f"[skill-safety] scan failed: no output (rc={out.returncode}) "
              f"{out.stderr[:200]}")
        return 1
    try:
        res = json.loads(out.stdout)
    except json.JSONDecodeError as e:
        print(f"[skill-safety] scan failed: bad JSON ({e})")
        return 1

    findings = res.get("findings", [])
    # persist the full report for the dashboard / human triage
    try:
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
    except OSError:
        pass

    def key(f):
        return f"{f['file']}::{f['detector']}"

    high = [f for f in findings if f["severity"] == "high"]
    fresh = [f for f in high if key(f) not in KNOWN_REVIEWED]

    if fresh:
        lines = [f"🛡️ SKILL-SAFETY ALERT ({len(fresh)} neue HIGH-Funde "
                 f"in {res.get('files_scanned', '?')} Dateien):"]
        for f in fresh[:6]:
            lines.append(f"- {f['file']}:{f['line']} [{f['detector']}] "
                         f"{f['detail'][:90]}")
        lines.append("(Report: reports/skill-safety-latest.json)")
        print("\n".join(lines))
        return 0

    if high:
        # only known/reviewed items — stay quiet but leave a breadcrumb
        print(f"[skill-safety] {len(high)} bekannte HIGH-Funde (reviewed), "
              f"keine neuen. scanned={res.get('files_scanned')}")
        return 0

    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
