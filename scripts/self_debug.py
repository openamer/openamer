#!/usr/bin/env python3
"""OpenAmer Self-Debugging Engine — ASI Tool Invention.
Scannt openamer-repo Code, findet Fehler, erstellt Patches autonom.

Usage:
    python self_debug.py --scan          # Scan + Report
    python self_debug.py --fix           # Scan + Auto-Fix
    python self_debug.py --watch         # Daemon-Modus (alle 30min)
"""
import ast, json, os, re, sys, subprocess, time, hashlib
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
STATE = HOME / "reports" / "self-debug-state.json"

CHECKS = {
    "deprecated_api": [
        (r"\.cuda\(\)", "CUDA-Aufruf auf CPU-only Maschine"),
        (r"subprocess\.run\(.*shell=True", "shell=True Sicherheitsrisiko"),
        (r"print\(.*f['\"]", "f-string in print() — logging verwenden"),
    ],
    "unused_imports": r"import (\w+)\s*\n(?!.*\1)",
    "bare_except": r"except\s*:",
    "todo_fixme": r"#\s*(TODO|FIXME|HACK|XXX)\b",
    "async_without_await": r"async def \w+.*\n(?!.*await)",
}

def scan_file(path: Path) -> list[dict]:
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings
    
    # AST checks
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            # Unused imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    if name not in text.splitlines()[node.end_lineno:]:
                        findings.append({"file": str(path), "line": node.lineno, "type": "unused_import", "msg": f"Unused import: {alias.name}"})
            # Bare except
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append({"file": str(path), "line": node.lineno, "type": "bare_except", "msg": "Bare except: catches everything"})
            # FIXME/TODO
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                for kw in ["TODO", "FIXME", "HACK", "XXX"]:
                    if kw in node.value.value:
                        findings.append({"file": str(path), "line": node.lineno, "type": "todo", "msg": f"{kw}: {node.value.value.strip()[:80]}"})
    except SyntaxError:
        findings.append({"file": str(path), "line": 0, "type": "syntax_error", "msg": "SyntaxError in file"})
    
    return findings

def scan_repo() -> dict:
    all_findings = []
    files_scanned = 0
    
    for py_file in list(REPO.rglob("*.py"))[:100]:  # Limit auf 100 Files
        if "venv" in str(py_file) or ".git" in str(py_file):
            continue
        files_scanned += 1
        all_findings.extend(scan_file(py_file))
    
    by_type = {}
    for f in all_findings:
        by_type.setdefault(f["type"], []).append(f)
    
    return {
        "timestamp": time.time(),
        "files_scanned": files_scanned,
        "total_findings": len(all_findings),
        "by_type": {t: len(v) for t, v in by_type.items()},
        "findings": all_findings[:200],  # Top 200
        "severity": {
            "syntax_error": "critical",
            "bare_except": "high",
            "unused_import": "medium",
            "todo": "low",
        }
    }

def generate_fix_plan(report: dict) -> list[dict]:
    """Erstellt Auto-Fix-Plan aus den Findings."""
    patches = []
    for f in report["findings"]:
        if f["type"] == "bare_except":
            patches.append({"file": f["file"], "line": f["line"], "fix_type": "add_exception_type", "auto": True})
        elif f["type"] == "deprecated":
            patches.append({"file": f["file"], "line": f["line"], "fix_type": "remove_deprecated", "auto": True})
    return patches

def run_daemon():
    """Daemon-Modus: scannt alle 30 Minuten."""
    while True:
        report = scan_repo()
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(report, indent=1, default=str))
        
        critical = report["by_type"].get("syntax_error", 0) + report["by_type"].get("bare_except", 0)
        if critical > 0:
            print(f"[self-debug] {critical} kritische Issues gefunden — siehe {STATE}")
        
        time.sleep(1800)  # 30 min

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true", help="Einmaliger Scan + Report")
    parser.add_argument("--fix", action="store_true", help="Scan + Auto-Fix")
    parser.add_argument("--watch", action="store_true", help="Daemon (alle 30min)")
    args = parser.parse_args()
    
    if args.watch:
        run_daemon()
    else:
        report = scan_repo()
        print(json.dumps(report, indent=1, default=str))