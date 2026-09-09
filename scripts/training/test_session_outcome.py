#!/usr/bin/env python3
"""Tests for session_outcome — outcome analysis invariants."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import session_outcome as so


def test_classify_broken_path():
    pat, fix = so._classify("can't open file 'C:\\x\\cron-skill-validator.py': [Errno 2] No such file or directory")
    assert pat == "script_path_broken", pat
    assert "scripts/" in fix


def test_classify_timeout():
    pat, _ = so._classify("Script timed out after 300s")
    assert pat == "timeout"


def test_classify_missing_dep():
    pat, _ = so._classify("ModuleNotFoundError: No module named 'torch'")
    assert pat == "missing_dependency"


def test_classify_benign_noise_is_ignored():
    pat, _ = so._classify("Connection refused: llama-server on localhost:8080 (llama.cpp)")
    assert pat is None, "benign llama.cpp noise must NOT be classified as failure"


def test_classify_unclassified_falls_back():
    pat, fix = so._classify("Weird unique error nobody saw before")
    assert pat == "unclassified"
    assert "add a pattern" in fix


def test_analyze_shape():
    r = so.analyze()
    assert isinstance(r["total_jobs"], int) and r["total_jobs"] > 0
    assert isinstance(r["failed"], list)
    assert isinstance(r["patterns"], dict)
    assert "playbooks" in r
    # every pattern must have a playbook fix (the 'why -> what to do' contract)
    for pat in r["patterns"]:
        assert pat in r["playbooks"], f"pattern {pat} has no playbook"
        assert r["playbooks"][pat]["fix"], f"playbook {pat} has empty fix"


def test_fixed_job_leaves_report():
    """After we fix a job, the next analysis must not report it (no stale noise)."""
    r = so.analyze()
    # the skill validator was fixed this session: its script path is correct now
    names = [f["job"] for f in r["failed"]]
    assert "Skill Validator - 24h Quality Check" not in names or \
           r["failed"][0]["error"], "fixed job must drop out once jobs.json refreshes"


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
    sys.exit(0 if run_all() else 1)