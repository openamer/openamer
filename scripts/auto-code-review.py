#!/usr/bin/env python3
"""
Auto Code Review: Security-Scan + Code-Qualität + Style + Auto-Fix.

Analysiert Git-Diffs (HEAD~N), prüft auf Secrets, SQL-Injection, Code-Qualität,
Style-Probleme und kann Issues automatisch patchen.

CLI:
  --diff HEAD~1         Prüft letzten Commit (Default)
  --diff HEAD~5         Prüft letzte 5 Commits
  --fix                 Automatische Korrektur behebbarer Issues
  --json                Nur JSON-Report auf stdout
  --quiet               Nur Exit-Code, keine Outputs
  --repo PATH           Pfad zum Git-Repo (Default: aktuelles dir)

Exit-Codes:
  0 = Keine Issues
  1 = Warnungen (Code-Qualität / Style)
  2 = Security Issues gefunden
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────
# Pattern-Definitionen
# ──────────────────────────────────────────────────────────────────────

SECRETS_PATTERNS: list[dict] = [
    {
        "id": "HARDCODED_PASSWORD",
        "severity": "critical",
        "pattern": re.compile(
            r'(?:password|passwd|pwd)\s*[=:]\s*[\'"][^\'"]{3,}[\'"]',
            re.IGNORECASE,
        ),
        "message": "Harcoded password/credential in code",
        "category": "secrets",
    },
    {
        "id": "HARDCODED_API_KEY",
        "severity": "critical",
        "pattern": re.compile(
            r'(?:api[_-]?key|apikey|api_key)\s*[=:]\s*[\'"][^\'"]{8,}[\'"]',
            re.IGNORECASE,
        ),
        "message": "Hardcoded API key in code",
        "category": "secrets",
    },
    {
        "id": "HARDCODED_TOKEN",
        "severity": "critical",
        "pattern": re.compile(
            r'(?:token|secret|auth_token|access_token)\s*[=:]\s*[\'"][^\'"]{8,}[\'"]',
            re.IGNORECASE,
        ),
        "message": "Hardcoded token/secret in code",
        "category": "secrets",
    },
    {
        "id": "PRIVATE_KEY",
        "severity": "critical",
        "pattern": re.compile(
            r'-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH|PRIVATE)\s+KEY-----',
            re.IGNORECASE,
        ),
        "message": "Private key embedded in code",
        "category": "secrets",
    },
    {
        "id": "AWS_ACCESS_KEY",
        "severity": "critical",
        "pattern": re.compile(
            r'(?:AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16})',
        ),
        "message": "AWS access key ID in code",
        "category": "secrets",
    },
    {
        "id": "CONNECTION_STRING",
        "severity": "high",
        "pattern": re.compile(
            r'(?:mongodb|postgres(?:ql)?|mysql|redis)://\S+:\S+@',
            re.IGNORECASE,
        ),
        "message": "Database connection string with credentials",
        "category": "secrets",
    },
    {
        "id": "JWT_TOKEN",
        "severity": "high",
        "pattern": re.compile(
            r'(?:eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)',
        ),
        "message": "JWT token in code",
        "category": "secrets",
    },
]

SQL_INJECTION_PATTERNS: list[dict] = [
    {
        "id": "SQL_EXECUTE_FSTRING",
        "severity": "critical",
        "pattern": re.compile(
            r'(?:cursor|execute|executemany)\.\s*execute\s*\(\s*(?:f["\']|f["\'])',
        ),
        "message": "SQL query with f-string formatting — SQL injection risk",
        "category": "sql_injection",
    },
    {
        "id": "SQL_FORMAT_INJECTION",
        "severity": "critical",
        "pattern": re.compile(
            r'execute\s*\(.*\.format\(.*(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)',
            re.IGNORECASE,
        ),
        "message": "SQL query with .format() — SQL injection risk",
        "category": "sql_injection",
    },
    {
        "id": "SQL_CONCATENATION",
        "severity": "critical",
        "pattern": re.compile(
            r'execute\s*\(\s*(?:[\'"][^)]*[\'"]\s*\+|f["\']).*(?:SELECT|INSERT|UPDATE|DELETE)',
            re.IGNORECASE,
        ),
        "message": "SQL query with string concatenation — SQL injection risk",
        "category": "sql_injection",
    },
    {
        "id": "SQL_RAW_QUERY_STRING",
        "severity": "high",
        "pattern": re.compile(
            r'(?:session|conn|db)\.execute\s*\(\s*f["\']',
        ),
        "message": "Database execute with f-string — SQL injection risk",
        "category": "sql_injection",
    },
]

DANGEROUS_PATTERNS: list[dict] = [
    {
        "id": "OS_SYSTEM",
        "severity": "high",
        "pattern": re.compile(r'\bos\.system\s*\('),
        "message": "os.system() — shell injection risk, use subprocess.run()",
        "category": "dangerous",
    },
    {
        "id": "SHELL_TRUE",
        "severity": "high",
        "pattern": re.compile(r'shell\s*=\s*True'),
        "message": "shell=True — shell injection risk",
        "category": "dangerous",
    },
    {
        "id": "EVAL",
        "severity": "critical",
        "pattern": re.compile(r'\beval\s*\('),
        "message": "eval() — arbitrary code execution risk",
        "category": "dangerous",
    },
    {
        "id": "EXEC",
        "severity": "critical",
        "pattern": re.compile(r'\bexec\s*\('),
        "message": "exec() — arbitrary code execution risk",
        "category": "dangerous",
    },
    {
        "id": "PICKLE_LOADS",
        "severity": "high",
        "pattern": re.compile(r'pickle\.loads?\s*\('),
        "message": "pickle.load() — unsafe deserialization risk",
        "category": "dangerous",
    },
    {
        "id": "YAML_LOAD",
        "severity": "medium",
        "pattern": re.compile(r'yaml\.load\s*\(.*[^Loader]'),
        "message": "yaml.load() without SafeLoader — code execution risk",
        "category": "dangerous",
    },
    {
        "id": "MKDIR_SHELL",
        "severity": "medium",
        "pattern": re.compile(r'subprocess\.call\s*\([^,)]*shell\s*=\s*True'),
        "message": "subprocess.call() with shell=True — injection risk",
        "category": "dangerous",
    },
    {
        "id": "REQUEST_VERIFY_FALSE",
        "severity": "medium",
        "pattern": re.compile(r'verify\s*=\s*False|verify\s*=\s*false'),
        "message": "SSL verification disabled (verify=False) — security risk",
        "category": "dangerous",
    },
]

QUALITY_PATTERNS: list[dict] = [
    {
        "id": "EMPTY_EXCEPT",
        "severity": "medium",
        "pattern": re.compile(r'except\s*:'),
        "message": "Bare 'except:' — suppresses all errors, use 'except Exception:'",
        "category": "quality",
    },
    {
        "id": "PASS_IN_EXCEPT",
        "severity": "medium",
        "pattern": re.compile(r'except.*:\s*\n\s+pass'),
        "message": "except block with only 'pass' — error is silently swallowed",
        "category": "quality",
    },
    {
        "id": "TODO",
        "severity": "low",
        "pattern": re.compile(r'#\s*TODO\b'),
        "message": "TODO comment — unfinished work",
        "category": "quality",
    },
    {
        "id": "FIXME",
        "severity": "low",
        "pattern": re.compile(r'#\s*FIXME\b'),
        "message": "FIXME comment — known bug or issue",
        "category": "quality",
    },
    {
        "id": "HACK",
        "severity": "low",
        "pattern": re.compile(r'#\s*HACK\b'),
        "message": "HACK comment — workaround in place",
        "category": "quality",
    },
    {
        "id": "XXX",
        "severity": "low",
        "pattern": re.compile(r'#\s*XXX\b'),
        "message": "XXX comment — problematic code",
        "category": "quality",
    },
    {
        "id": "PRINT_DEBUG",
        "severity": "low",
        "pattern": re.compile(r'^\s*print\s*\(', re.MULTILINE),
        "message": "print() in production code — remove debug output",
        "category": "quality",
    },
    {
        "id": "COMMENTED_CODE",
        "severity": "low",
        "pattern": re.compile(
            r'^\s*#.*(?:def |class |import |from |return |if |for |while )',
            re.MULTILINE,
        ),
        "message": "Commented-out code — remove dead code",
        "category": "quality",
    },
]

STYLE_PATTERNS: list[dict] = [
    {
        "id": "TRAILING_WHITESPACE",
        "severity": "low",
        "pattern": re.compile(r'[ \t]+$', re.MULTILINE),
        "message": "Trailing whitespace",
        "category": "style",
        "fixable": True,
    },
    {
        "id": "TAB_INDENT",
        "severity": "low",
        "pattern": re.compile(r'^\t+', re.MULTILINE),
        "message": "Tab indentation — project uses spaces",
        "category": "style",
        "fixable": True,
    },
    {
        "id": "BOM_MARKER",
        "severity": "low",
        "pattern": re.compile(r'^\xef\xbb\xbf'),
        "message": "BOM marker in file (UTF-8 BOM)",
        "category": "style",
        "fixable": True,
    },
    {
        "id": "MISSING_NEWLINE_EOF",
        "severity": "low",
        "pattern": re.compile(r'(?<!\n)\Z'),
        "message": "No newline at end of file",
        "category": "style",
        "fixable": True,
    },
]


# ──────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ──────────────────────────────────────────────────────────────────────

def run_git(cmd: list[str], repo: Path) -> subprocess.CompletedProcess:
    """Run a git command in the repo directory."""
    return subprocess.run(
        ["git"] + cmd,
        capture_output=True,
        text=True,
        cwd=str(repo),
        timeout=30,
    )


def get_changed_files(diff_ref: str, repo: Path) -> list[str]:
    """Get list of changed files from git diff."""
    result = run_git(
        ["diff", diff_ref, "--name-only", "--diff-filter=ACMR"],
        repo,
    )
    if result.returncode != 0:
        print(f"Warning: git diff failed: {result.stderr.strip()}", file=sys.stderr)
        return []
    files = [f for f in result.stdout.strip().split("\n") if f.strip()]
    return files


def get_file_diff(diff_ref: str, repo: Path) -> str:
    """Get unified diff for the specified ref."""
    result = run_git(["diff", diff_ref], repo)
    return result.stdout


def get_diff_for_file(diff_ref: str, filepath: str, repo: Path) -> str:
    """Get diff for a specific file."""
    result = run_git(["diff", diff_ref, "--", filepath], repo)
    return result.stdout


def get_file_content(filepath: str, repo: Path) -> str | None:
    """Read current file content from working tree."""
    full_path = repo / filepath
    if full_path.exists() and full_path.is_file():
        try:
            return full_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
    return None


def scan_added_lines(diff_text: str, patterns: list[dict]) -> list[dict]:
    """Scan only added lines in a diff for patterns."""
    findings = []
    for line in diff_text.split("\n"):
        if line.startswith("+"):
            added_line = line[1:]  # Strip the '+'
            for pat in patterns:
                if pat["pattern"].search(added_line):
                    findings.append({
                        "line_content": added_line.strip()[:120],
                        "pattern_id": pat["id"],
                        "severity": pat["severity"],
                        "message": pat["message"],
                        "category": pat["category"],
                    })
    return findings


def scan_whole_file(filepath: str, repo: Path, patterns: list[dict]) -> list[dict]:
    """Scan entire file content for patterns (for style / quality checks)."""
    findings = []
    content = get_file_content(filepath, repo)
    if content is None:
        return findings

    for pat in patterns:
        for match in pat["pattern"].finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            findings.append({
                "file": filepath,
                "line": line_num,
                "line_content": content[match.start() : match.end()].strip()[:120],
                "pattern_id": pat["id"],
                "severity": pat["severity"],
                "message": pat["message"],
                "category": pat["category"],
                "fixable": pat.get("fixable", False),
            })
    return findings


def check_long_functions(filepath: str, repo: Path) -> list[dict]:
    """Check for functions > 50 lines."""
    findings = []
    content = get_file_content(filepath, repo)
    if content is None:
        return findings

    # Python function detection
    func_pattern = re.compile(
        r'^\s*(?:async\s+)?def\s+\w+\s*\(', re.MULTILINE
    )
    lines = content.split("\n")

    for match in func_pattern.finditer(content):
        func_start = match.start()
        func_start_line = content[:func_start].count("\n")

        # Find function end by tracking indentation
        func_name = match.group().replace("def ", "").split("(")[0].strip()
        func_indent = len(lines[func_start_line]) - len(lines[func_start_line].lstrip())
        func_end_line = func_start_line + 1

        for i in range(func_start_line + 1, len(lines)):
            stripped = lines[i].rstrip()
            if stripped == "":
                continue
            line_indent = len(lines[i]) - len(lines[i].lstrip())
            if line_indent <= func_indent and stripped not in ("", ")") and not lines[i].lstrip().startswith(("return ", "#", '"""', "'''", "@")):
                break
            func_end_line = i

        func_len = func_end_line - func_start_line + 1

        if func_len > 50:
            findings.append({
                "file": filepath,
                "line": func_start_line + 1,
                "pattern_id": "LONG_FUNCTION",
                "severity": "medium",
                "message": f"Function '{func_name}' is {func_len} lines long (max 50)",
                "category": "quality",
                "line_content": match.group().strip()[:120],
            })

    return findings


def check_missing_type_hints(filepath: str, repo: Path) -> list[dict]:
    """Check for functions missing return type hints."""
    findings = []
    content = get_file_content(filepath, repo)
    if content is None:
        return findings

    func_pattern = re.compile(
        r'^\s*(?:async\s+)?def\s+\w+\s*\([^)]*\)\s*:', re.MULTILINE
    )
    for match in func_pattern.finditer(content):
        # Check if there's a return type hint
        line = match.group()
        # Look for -> before the colon
        before_colon = line.rsplit(":", 1)[0]
        if "->" not in before_colon:
            line_num = content[: match.start()].count("\n") + 1
            findings.append({
                "file": filepath,
                "line": line_num,
                "pattern_id": "MISSING_RETURN_HINT",
                "severity": "low",
                "message": "Function missing return type hint",
                "category": "quality",
                "line_content": line.strip()[:120],
            })

    return findings


def check_python_file(filepath: str, repo: Path) -> list[dict]:
    """Run Python-specific checks on a file."""
    if not filepath.endswith(".py"):
        return []
    findings = []
    findings.extend(check_long_functions(filepath, repo))
    findings.extend(check_missing_type_hints(filepath, repo))
    findings.extend(scan_whole_file(filepath, repo, QUALITY_PATTERNS))
    findings.extend(scan_whole_file(filepath, repo, STYLE_PATTERNS))
    return findings


def scan_file_for_security(filepath: str, repo: Path) -> list[dict]:
    """Run security scans on a file."""
    findings = []
    content = get_file_content(filepath, repo)
    if content is None:
        return findings
    # Security patterns scan whole file
    for patterns in [SECRETS_PATTERNS, SQL_INJECTION_PATTERNS, DANGEROUS_PATTERNS]:
        for pat in patterns:
            for match in pat["pattern"].finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                findings.append({
                    "file": filepath,
                    "line": line_num,
                    "pattern_id": pat["id"],
                    "severity": pat["severity"],
                    "message": pat["message"],
                    "category": pat["category"],
                    "line_content": content[match.start() : match.end()].strip()[:120],
                })
    return findings


# ──────────────────────────────────────────────────────────────────────
# Auto-Fix
# ──────────────────────────────────────────────────────────────────────

def auto_fix_issues(files: list[str], issues: list[dict], repo: Path) -> list[dict]:
    """Automatically fix fixable style issues."""
    fixed = []
    modified_files: dict[str, str] = {}

    for issue in issues:
        if not issue.get("fixable"):
            continue
        filepath = issue["file"]
        if filepath not in modified_files:
            content = get_file_content(filepath, repo)
            if content is None:
                continue
            modified_files[filepath] = content

    for filepath, content in modified_files.items():
        original = content
        lines = content.split("\n")

        # Fix trailing whitespace
        content = re.sub(r'[ \t]+$', "", content, flags=re.MULTILINE)

        # Fix missing newline at EOF
        if not content.endswith("\n"):
            content += "\n"

        # Fix BOM
        if content.startswith("\ufeff"):
            content = content.lstrip("\ufeff")

        if content != original:
            fixed.append({
                "file": filepath,
                "fixes": [],
            })
            # Write fixed content
            full_path = repo / filepath
            full_path.write_text(content, encoding="utf-8")
            fixed[-1]["fixes"].append("trailing_whitespace+bom+eol")

    return fixed


def commit_fixes(repo: Path) -> bool:
    """Commit auto-fixes."""
    result = run_git(["add", "-u"], repo)
    if result.returncode != 0:
        return False
    result = run_git(
        [
            "commit", "-m",
            "[auto-code-review] Auto-fix: trailing whitespace, BOM, EOL",
            "--no-verify",
        ],
        repo,
    )
    return result.returncode == 0


# ───────────────────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────────────────

def build_report(
    files: list[str],
    diff_text: str,
    added_findings: list[dict],
    file_findings: list[dict],
    fixed: list[dict],
    repo: Path,
    diff_ref: str = "HEAD~1",
) -> dict:
    """Build structured JSON report."""
    all_issues = added_findings + file_findings

    security_issues = [i for i in all_issues if i.get("category") in ("secrets", "sql_injection", "dangerous")]
    quality_issues = [i for i in all_issues if i.get("category") == "quality"]
    style_issues = [i for i in all_issues if i.get("category") == "style"]
    fixable_count = sum(1 for i in all_issues if i.get("fixable"))

    def severity_score(s: str) -> int:
        return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(s, 0)

    max_severity = max((severity_score(i["severity"]) for i in all_issues), default=0)
    severity_label = {4: "critical", 3: "high", 2: "medium", 1: "low", 0: "none"}[max_severity]

    has_critical = any(i["severity"] == "critical" for i in security_issues)
    has_high = any(i["severity"] == "high" for i in security_issues)

    severity_to_num = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    top_severity = max(
        (severity_to_num.get(i.get("severity", "low"), 0) for i in all_issues),
        default=0,
    )

    return {
        "scan_timestamp": datetime.now().isoformat(),
        "repository": str(repo.resolve()),
        "diff_ref": diff_ref,
        "stats": {
            "files_analyzed": len(files),
            "total_issues": len(all_issues),
            "security_issues": len(security_issues),
            "quality_issues": len(quality_issues),
            "style_issues": len(style_issues),
            "fixable_issues": fixable_count,
            "auto_fixed": len(fixed),
            "max_severity": severity_label,
        },
        "files": sorted(set(f["file"] for f in all_issues)) if all_issues else files,
        "issues_by_severity": {
            "critical": [i for i in all_issues if i["severity"] == "critical"],
            "high": [i for i in all_issues if i["severity"] == "high"],
            "medium": [i for i in all_issues if i["severity"] == "medium"],
            "low": [i for i in all_issues if i["severity"] == "low"],
        },
        "issues": all_issues,
        "security_issues": security_issues,
        "quality_issues": quality_issues,
        "style_issues": style_issues,
        "auto_fixes_applied": fixed,
        "suggestions": [
            "Use parameterized queries instead of string formatting in SQL",
            "Use subprocess.run() with list arguments instead of os.system()",
            "Use environment variables or a secrets manager for credentials",
            "Add type hints to function signatures",
            "Remove commented-out code and debug print() statements",
            "Use logging instead of print() for production code",
        ],
        "has_security_issues": len(security_issues) > 0,
        "exit_code": 2 if has_critical or has_high else (1 if all_issues else 0),
    }


def print_report(report: dict, quiet: bool = False):
    """Print human-readable report."""
    if quiet:
        return

    s = report["stats"]
    print(f"\n{'='*60}")
    print(f"  Auto Code Review Report")
    print(f"  {report['scan_timestamp']}")
    print(f"  Repo: {report['repository']}")
    print(f"{'='*60}")

    print(f"\n  Files analyzed:    {s['files_analyzed']}")
    print(f"  Total issues:      {s['total_issues']}")
    print(f"  Security issues:   {s['security_issues']}")
    print(f"  Quality issues:    {s['quality_issues']}")
    print(f"  Style issues:      {s['style_issues']}")
    print(f"  Auto-fixed:        {s['auto_fixed']}")
    print(f"  Max severity:      {s['max_severity']}")
    print()

    if report["security_issues"]:
        print(f"  {'─'*50}")
        print(f"  ⚠  CRITICAL / HIGH SECURITY ISSUES")
        print(f"  {'─'*50}")
        for issue in report["security_issues"]:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}
            print(f"  {icon.get(issue['severity'], '•')} [{issue['severity'].upper()}] "
                  f"{issue.get('file', '')}:L{issue.get('line', '?')}")
            print(f"    {issue['message']}")
            print(f"    → {issue.get('line_content', '')}")
            print()

    if report["quality_issues"]:
        print(f"  {'─'*50}")
        print(f"  📋 QUALITY ISSUES")
        print(f"  {'─'*50}")
        for issue in report["quality_issues"]:
            print(f"  • [{issue['severity'].upper()}] {issue.get('file', '')}:L{issue.get('line', '?')}")
            print(f"    {issue['message']}")
            print(f"    → {issue.get('line_content', '')}")
            print()

    if report["style_issues"]:
        print(f"  {'─'*50}")
        print(f"  🎨 STYLE ISSUES")
        print(f"  {'─'*50}")
        for issue in report["style_issues"]:
            print(f"  • [{issue['severity'].upper()}] {issue.get('file', '')}:L{issue.get('line', '?')}")
            print(f"    {issue['message']}")
            print()

    if report["auto_fixes_applied"]:
        print(f"  ✅ Auto-fixes applied:")
        for fix in report["auto_fixes_applied"]:
            print(f"    • {fix['file']}: {', '.join(fix.get('fixes', ['fixes']))}")

    print(f"\n  {'='*60}")
    if report["has_security_issues"]:
        print(f"  ❌ FAILED: Security issues found — exit code 2")
    elif s["total_issues"] > 0:
        print(f"  ⚠  WARNINGS: {s['total_issues']} issues found — exit code 1")
    else:
        print(f"  ✅ PASSED: No issues found — exit code 0")
    print(f"  {'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Auto Code Review — Security, Quality, Style & Auto-Fix"
    )
    parser.add_argument(
        "--diff",
        default="HEAD~1",
        help="Git diff ref (default: HEAD~1)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix fixable issues (trailing whitespace, BOM, EOL)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON report only",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output except exit code",
    )
    parser.add_argument(
        "--repo",
        default=os.getcwd(),
        help="Path to git repository (default: cwd)",
    )

    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"Error: Not a git repository: {repo}", file=sys.stderr)
        sys.exit(2)

    # Step 1: Get changed files and diff
    files = get_changed_files(args.diff, repo)
    if not files:
        result = run_git(["log", "--oneline", "-1"], repo)
        if result.returncode == 0:
            # Check if there are uncommitted changes
            status = run_git(["status", "--porcelain"], repo)
            if status.stdout.strip():
                files = []
                for line in status.stdout.strip().split("\n"):
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) >= 2:
                        files.append(parts[1])
        if not files:
            if not args.quiet and not args.json:
                print("No changes to analyze.")
            sys.exit(0)

    diff_text = get_file_diff(args.diff, repo)

    # Step 2: Security scan on added lines in diff
    added_findings = []
    added_findings += scan_added_lines(diff_text, SECRETS_PATTERNS)
    added_findings += scan_added_lines(diff_text, SQL_INJECTION_PATTERNS)
    added_findings += scan_added_lines(diff_text, DANGEROUS_PATTERNS)

    # Step 3: Scan full files for security (catches all occurrences)
    file_security_findings = []
    for f in files:
        if not os.path.exists(repo / f):
            continue
        file_security_findings += scan_file_for_security(f, repo)

    # Step 4: Code quality & style checks on full files
    file_quality_findings = []
    for f in files:
        fd = check_python_file(f, repo)
        file_quality_findings += fd

    # Determine type for each finding
    for f in file_security_findings:
        f["type"] = f["category"]
    for f in file_quality_findings:
        f["type"] = f["category"]

    # Step 5: Auto-fix if requested
    fixed = []
    if args.fix:
        all_file_issues = file_security_findings + file_quality_findings
        fixed = auto_fix_issues(files, all_file_issues, repo)
        if fixed:
            committed = commit_fixes(repo)
            if committed and not args.quiet:
                print(f"✅ Auto-fix committed {len(fixed)} file(s)")

    # Step 6: Build and output report
    report = build_report(
        files,
        diff_text,
        [],
        file_security_findings + file_quality_findings,
        fixed,
        repo,
        diff_ref=args.diff,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report, args.quiet)

    sys.exit(report["exit_code"])


if __name__ == "__main__":
    main()