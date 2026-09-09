#!/usr/bin/env python3
"""Tests for security_analyzer — every rule must hold (TDD: invariants, not snapshots)."""
from security_analyzer import analyze_action, check, ALLOW, WARN, BLOCK

def test_destructive_shell_blocked():
    v, _ = analyze_action("terminal", {"command": "rm -rf /"})
    assert v == BLOCK

def test_format_drive_blocked():
    v, _ = analyze_action("terminal", {"command": "format C:"})
    assert v == BLOCK

def test_fork_bomb_blocked():
    v, _ = analyze_action("terminal", {"command": ":(){ :|:& };:"})
    assert v == BLOCK

def test_secrets_in_params_blocked():
    v, _ = analyze_action("web", {"url": "https://x.com", "headers": "Authorization: Bearer sk-abc123def456ghi789jkl"})
    assert v == BLOCK

def test_github_token_blocked():
    v, _ = analyze_action("terminal", {"command": "echo ghp_abcdefghijklmnopqrstuvwxyz1234567890"})
    assert v == BLOCK

def test_cross_profile_blocked():
    v, _ = analyze_action("file", {"path": "C:/Users/damir/AppData/Local/openamer-laptop/profiles/work/config.yaml"})
    assert v == BLOCK

def test_own_profile_allowed():
    v, _ = analyze_action("file", {"path": "C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/x.py"})
    assert v == ALLOW

def test_normal_shell_allowed():
    v, _ = analyze_action("terminal", {"command": "ls -la && python test.py"})
    assert v == ALLOW

def test_tmp_cleanup_allowed():
    v, _ = analyze_action("terminal", {"command": "rm -rf /tmp/cache"})
    assert v == ALLOW

def test_force_push_warns():
    v, _ = analyze_action("terminal", {"command": "git push --force origin main"})
    assert v == WARN

def test_drop_table_warns():
    v, _ = analyze_action("terminal", {"command": "sqlite3 state.db 'DROP TABLE users'"})
    assert v == WARN

def test_check_logs_violations():
    v, reason = check("terminal", {"command": "rm -rf /"})
    assert v == BLOCK
    assert reason

def run_all():
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    passed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"[PASS] {name}")
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
    print(f"\nRESULT: {passed}/{len(tests)} passed")
    return passed == len(tests)

if __name__ == "__main__":
    import sys
    sys.exit(0 if run_all() else 1)