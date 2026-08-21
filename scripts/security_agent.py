#!/usr/bin/env python3
"""
Security Agent — Automated Security Scanning & Vulnerability Detection.
Scans npm, Python, codebase patterns, and env config for security issues.
Läuft als Cron-Job: openamer cronjob create --schedule 'every 6h' --script scripts/security_agent.py
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
STATE_FILE = REPO_DIR / ".security-agent" / "state.json"
LOG_FILE = REPO_DIR / ".security-agent" / "security.log"
MAX_ALERTS_PER_RUN = 10

# Patterns to scan for in codebase
SECURITY_PATTERNS = {
    "CRITICAL": [
        r'(?i)(?:password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*["\'][^"\']+["\']',
        r'(?i)sk-[a-zA-Z0-9]{20,}',
        r'(?i)ghp_[a-zA-Z0-9]{36,}',
        r'(?i)AKIA[0-9A-Z]{16}',
    ],
    "HIGH": [
        r'(?i)#\s*TODO\s*:\s*SECURITY',
        r'(?i)#\s*FIXME\s*:\s*SECURITY',
        r'(?i)exec\s*\(',
        r'(?i)eval\s*\(',
        r'(?i)subprocess\.(?:Popen|call|run)\s*\([^)]*shell\s*=\s*True',
        r'(?i)os\.system\s*\(',
    ],
    "MEDIUM": [
        r'(?i)#\s*TODO',
        r'(?i)#\s*FIXME',
        r'(?i)#\s*HACK',
        r'(?i)#\s*XXX',
        r'(?i)allow_redirects\s*=\s*True',
        r'(?i)verify\s*=\s*False',
        r'(?i)debug\s*=\s*True',
    ],
}

Path(REPO_DIR / ".security-agent").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE, level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("security-agent")

def run(cmd, **kwargs):
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=kwargs.get("timeout", 120),
        cwd=kwargs.get("cwd", REPO_DIR),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return result

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen_findings": [], "stats": {"total_alerts": 0, "total_fixed": 0}}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def fingerprint(findings: list) -> str:
    """Create a unique fingerprint for a set of findings."""
    return hashlib.sha256(json.dumps(findings, sort_keys=True).encode()).hexdigest()[:16]

def is_duplicate(fp: str, state: dict) -> bool:
    return fp in state.get("seen_findings", [])

# ─── Scanners ─────────────────────────────────────────────────────────────────

def scan_npm() -> list[dict]:
    """Run npm audit and parse results."""
    log.info("Scanning npm dependencies...")
    findings = []
    try:
        result = run(["npx", "npm", "audit", "--json"], timeout=60)
        if result.returncode == 0:
            return findings
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        vulns = data.get("metadata", {}).get("vulnerabilities", {})
        for severity, count in vulns.items():
            if count > 0 and severity in ("critical", "high"):
                findings.append({
                    "type": "npm-vulnerability",
                    "severity": severity.upper(),
                    "title": f"{count} npm {severity} vulnerabilities",
                    "detail": f"Run `npm audit fix` in the repo root",
                    "fix": "npm audit fix",
                })
        log.info(f"npm scan: {len(findings)} findings")
    except Exception as e:
        log.warning(f"npm scan failed: {e}")
    return findings

def scan_python() -> list[dict]:
    """Scan Python dependencies for known vulnerabilities."""
    log.info("Scanning Python dependencies...")
    findings = []
    try:
        result = run(["pip-audit", "--json"], timeout=60)
        if result.returncode == 0:
            return findings
        try:
            data = json.loads(result.stdout)
            for vuln in data.get("vulnerabilities", []):
                findings.append({
                    "type": "python-vulnerability",
                    "severity": "HIGH",
                    "title": vuln.get("description", "Unknown Python vulnerability"),
                    "detail": f"Package: {vuln.get('package', '?')} {vuln.get('version', '?')}",
                    "fix": f"pip install --upgrade {vuln.get('package', '')}",
                })
        except json.JSONDecodeError:
            pass
    except FileNotFoundError:
        log.info("pip-audit not installed, skipping")
    except Exception as e:
        log.warning(f"Python scan failed: {e}")
    return findings

def scan_codebase() -> list[dict]:
    """Scan codebase files for security patterns."""
    log.info("Scanning codebase for security patterns...")
    findings = []
    EXCLUDE_DIRS = {".git", "node_modules", "venv", "__pycache__", ".security-agent", ".bugbot", "out"}

    for severity, patterns in SECURITY_PATTERNS.items():
        for pattern in patterns:
            try:
                result = run([
                    "rg", "--no-heading", "--line-number",
                    "-i", pattern,
                    "-g", "!.git/**", "-g", "!node_modules/**",
                    "-g", "!venv/**", "-g", "!__pycache__/**",
                    "-g", "!*.lock", "-g", "!package-lock.json",
                    str(REPO_DIR),
                ], timeout=30)
                if result.stdout.strip():
                    lines = result.stdout.strip().split("\n")[:5]
                    for line in lines:
                        parts = line.split(":", 2)
                        if len(parts) >= 2:
                            findings.append({
                                "type": f"codebase-{severity.lower()}",
                                "severity": severity,
                                "title": f"Pattern found: {pattern[:50]}",
                                "detail": parts[2][:200] if len(parts) > 2 else parts[1],
                                "file": parts[0],
                                "line": parts[1],
                                "fix": "Review and address the security concern",
                            })
            except Exception as e:
                log.warning(f"Pattern scan failed for {pattern}: {e}")

    log.info(f"Codebase scan: {len(findings)} findings")
    return findings

def scan_doctor() -> list[dict]:
    """Run openamer doctor and parse warnings."""
    log.info("Running openamer doctor...")
    findings = []
    try:
        result = run(["openamer", "doctor"], timeout=60)
        for line in result.stdout.split("\n"):
            if "⚠" in line:
                findings.append({
                    "type": "doctor-warning",
                    "severity": "MEDIUM",
                    "title": line.strip(),
                    "detail": "Found by openamer doctor",
                    "fix": "Run openamer doctor --fix",
                })
        log.info(f"Doctor scan: {len(findings)} findings")
    except Exception as e:
        log.warning(f"Doctor scan failed: {e}")
    return findings

def check_env() -> list[dict]:
    """Check .env.example for potential secret exposure."""
    log.info("Checking .env files...")
    findings = []
    env_file = REPO_DIR / ".env.example"
    if env_file.exists():
        content = env_file.read_text()
        sensitive_keys = ["API_KEY", "SECRET", "PASSWORD", "TOKEN", "AUTH"]
        for key in sensitive_keys:
            if key in content:
                findings.append({
                    "type": "env-exposure",
                    "severity": "MEDIUM",
                    "title": f"Potential sensitive key in .env.example: {key}",
                    "detail": f"Check if {key} contains a real value in .env.example",
                    "fix": "Remove or redact the value in .env.example",
                })
    log.info(f"Env scan: {len(findings)} findings")
    return findings

# ─── Reporting ────────────────────────────────────────────────────────────────

def create_report(findings: list[dict]) -> str:
    """Create a markdown security report."""
    lines = [
        "# 🛡️ Security Agent Report",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Total Findings:** {len(findings)}",
        "",
    ]
    for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        sev_findings = [f for f in findings if f["severity"] == severity]
        if not sev_findings:
            continue
        lines.append(f"## {severity} ({len(sev_findings)})")
        for f in sev_findings:
            lines.append(f"- **{f['title']}**")
            lines.append(f"  - Type: {f['type']}")
            lines.append(f"  - Detail: {f.get('detail', '')[:200]}")
            if f.get("file"):
                lines.append(f"  - File: {f['file']}:{f.get('line', '')}")
            lines.append(f"  - Fix: {f.get('fix', 'Manual review needed')}")
            lines.append("")
    return "\n".join(lines)

def create_issue(findings: list[dict], state: dict):
    """Create a GitHub issue with the security report."""
    report = create_report(findings)
    fp = fingerprint(findings)
    if is_duplicate(fp, state):
        log.info("Duplicate findings, skipping issue creation")
        return

    try:
        result = run([
            "gh", "issue", "create",
            "--title", f"security-agent: {len(findings)} finding(s) detected",
            "--body", report,
            "--label", "security,automated-scan",
        ])
        log.info(f"Security issue created: {result.stdout}")
        state["seen_findings"].append(fp)
        state["stats"]["total_alerts"] = state["stats"].get("total_alerts", 0) + len(findings)
        save_state(state)
    except Exception as e:
        log.error(f"Failed to create issue: {e}")

# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Security Agent run starting")
    state = load_state()

    all_findings = []
    all_findings.extend(scan_npm())
    all_findings.extend(scan_python())
    all_findings.extend(scan_codebase())
    all_findings.extend(scan_doctor())
    all_findings.extend(check_env())

    # Sort by severity
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    all_findings.sort(key=lambda f: severity_order.get(f["severity"], 99))

    # Limit
    all_findings = all_findings[:MAX_ALERTS_PER_RUN]

    if all_findings:
        create_issue(all_findings, state)
        for f in all_findings:
            log.info(f"  [{f['severity']}] {f['title']}")
        print(f"Security Agent: {len(all_findings)} finding(s) reported")
    else:
        print("Security Agent: No findings - all clear ✅")

    log.info("Security Agent run complete")
    return 0

if __name__ == "__main__":
    import hashlib
    sys.exit(main())