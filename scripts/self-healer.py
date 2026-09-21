#!/usr/bin/env python3
"""OpenAmer Self-Healing Daemon — findet und fixt Code-Fehler automatisch."""
import os, sys, time, json, re
from pathlib import Path

REPO = r"C:\Users\damir\openamer-repo"
SKILLS = r"C:\Users\damir\AppData\Local\openamer-laptop\skills"
LOG_FILE = r"C:\Users\damir\AppData\Local\openamer-laptop\cache\self-healer.log"
SCRIPTS_DIR = r"C:\Users\damir\AppData\Local\openamer-laptop\scripts"

# Repair cooldown: never re-attempt the same repair on unchanged content within
# 24h. A file whose content changed is a NEW fault and is retried immediately.
sys.path.insert(0, SCRIPTS_DIR)
try:
    import repair_cooldown as _rc
except Exception:
    _rc = None


def log(msg):
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    l = f"[{t}] {msg}"
    print(l)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a', encoding="utf-8") as f:
        f.write(l + "\n")

def is_vendored(root):
    """Bundled interpreters / vendored trees must not be linted.

    The repo ships a Python 3.14 stdlib under Python/pythoncore-*-64/Lib/.
    Compiling those sources with the running (3.11) interpreter reports
    SyntaxError on perfectly valid files -- a pure false-positive class that
    previously showed up as 10 unfixable "errors" every run.
    """
    parts = {p.lower() for p in Path(root).parts}
    return ('lib' in parts and 'python' in parts) or 'pythoncore-3.14-64' in ' '.join(parts)


def find_py(path, exclude=None):
    if exclude is None:
        exclude = {'.git', 'node_modules', '__pycache__', 'build', 'venv', '.venv',
                   'site-packages', 'Python', 'pythoncore-3.14-64'}
    for root, dirs, names in os.walk(path):
        dirs[:] = [d for d in dirs if d not in exclude]
        if is_vendored(root):
            dirs[:] = []
            continue
        for n in names:
            if n.endswith('.py'):
                yield Path(root) / n

def check_syntax(path):
    try:
        compile(path.read_text(encoding='utf-8', errors='replace'), str(path), 'exec')
        return []
    except SyntaxError as e:
        return [f"SyntaxError in {path.name}: {e.msg} (line {e.lineno})"]

def clear_pycache(path):
    count = 0
    for root, dirs, _ in os.walk(path):
        if '__pycache__' in dirs:
            pc = os.path.join(root, '__pycache__')
            try:
                for f in os.listdir(pc):
                    fp = os.path.join(pc, f)
                    if os.path.isfile(fp):
                        os.remove(fp); count += 1
            except Exception as e:
                log(f"  Can't clear {pc}: {e}")
    return count

def auto_fix_indent(path, errors):
    """Fix indentation errors by looking at surrounding context."""
    fixed = 0
    for err in errors:
        if 'indent' in err.lower():
            lines = path.read_text(encoding='utf-8').split('\n')
            for part in err.split():
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(lines):
                        stripped = lines[idx].lstrip()
                        # Count current indent
                        curr = len(lines[idx]) - len(stripped)
                        # Look at previous line for correct indent
                        for prev in range(idx-1, max(0, idx-10), -1):
                            p = lines[prev]
                            if p.strip() and not p.strip().startswith('#') and not p.strip().startswith('"""'):
                                pindent = len(p) - len(p.lstrip())
                                # If prev line ends with :, we need one more indent
                                if p.rstrip().endswith(':'):
                                    new_indent = pindent + 4
                                else:
                                    new_indent = pindent
                                if curr != new_indent:
                                    lines[idx] = ' ' * new_indent + stripped
                                    fixed += 1
                                break
                    break
    if fixed:
        path.write_text('\n'.join(lines))
    return fixed

def heal():
    log("=" * 60)
    log("SELF-HEAL START")
    log("=" * 60)
    total_syntax = 0
    total_fixed = 0
    total_cache = 0
    total_suppressed = 0
    
    for target in [REPO, SKILLS]:
        if not os.path.exists(target):
            continue
        log(f"\nScanning: {target}")
        files = list(find_py(target))
        log(f"  {len(files)} .py files")
        
        for pf in files:
            errors = check_syntax(pf)
            if errors:
                for e in errors:
                    log(f"  ERROR: {e}")
                total_syntax += len(errors)
                heal_key = f"heal:{pf.name}"
                cur_hash = _rc.file_hash(pf) if _rc else None
                if _rc and _rc.cmd_check(heal_key, cur_hash) == 3:
                    total_suppressed += 1
                    log(f"  SKIPPED (repair cooldown, unchanged content): {pf.name}")
                    continue
                fixed = auto_fix_indent(pf, errors)
                if fixed:
                    total_fixed += fixed
                    log(f"  FIXED {fixed} issue(s) in {pf.name}")
                    if _rc:
                        _rc.cmd_mark(heal_key, "REPAIR_OK_FIXED",
                                     _rc.file_hash(pf))
                else:
                    log(f"  CANNOT AUTO-FIX: {pf.name}")
                    # Diagnosed but unfixable: park it for 24h so the same
                    # broken file is not re-scanned every run. Content changes
                    # lift the cooldown automatically.
                    if _rc:
                        _rc.cmd_mark(heal_key, "REPAIR_DIAGNOSED_NO_FIX", cur_hash)

        cleared = clear_pycache(target)
        total_cache += cleared
    
    log("\n" + "=" * 60)
    log("REPORT")
    log(f"  Issues: {total_syntax}")
    log(f"  Fixed:  {total_fixed}")
    log(f"  Cache:  {total_cache}")
    log(f"  Suppressed (repair cooldown): {total_suppressed}")
    if total_syntax == 0:
        log("  HEALTHY")
    log("=" * 60)
    return total_syntax, total_fixed

if __name__ == '__main__':
    heal()