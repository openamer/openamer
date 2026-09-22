#!/usr/bin/env python3
"""Regression tests for knowledge_to_action dir resolution.

Live bug (16.09.26): a cron env pointing OPENAMER_HOME at a non-existent dir
made every KTA cycle crash with FileNotFoundError on online_buffer.jsonl,
because the module trusted the env blindly (unlike internet_learner).
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

REAL_TRAINING = os.path.join(str(os.path.expanduser("~")),
                             "AppData", "Local", "openamer-laptop", "scripts", "training")


def _import_with_home(home):
    """Import knowledge_to_action in a child process with a given OPENAMER_HOME."""
    env = dict(os.environ)
    if home is None:
        env.pop("OPENAMER_HOME", None)
    else:
        env["OPENAMER_HOME"] = home
    out = subprocess.run(
        [sys.executable, "-c", "import knowledge_to_action as k; print(k.T)"],
        cwd=HERE, env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-400:]
    return out.stdout.strip().splitlines()[-1]


def test_bogus_home_falls_back_to_real_dir():
    for bogus in (r"C:\Users\damir\AppData\Local\openamer", r"C:\nope\throwaway"):
        got = _import_with_home(bogus)
        assert got == REAL_TRAINING, f"{bogus} -> {got}"


def test_no_env_uses_real_dir():
    assert _import_with_home(None) == REAL_TRAINING


def test_valid_env_is_respected():
    assert _import_with_home(REAL_TRAINING.rsplit("\\scripts", 1)[0]) == REAL_TRAINING


def test_cycle_runs_with_bogus_home():
    """The exact cron failure: KTA must exit 0 instead of crashing."""
    env = dict(os.environ, OPENAMER_HOME=r"C:\Users\damir\AppData\Local\openamer")
    out = subprocess.run([sys.executable, "knowledge_to_action.py"],
                         cwd=HERE, env=env, capture_output=True, text=True, timeout=240)
    assert out.returncode == 0, out.stderr[-400:]
    assert "[kta]" in out.stdout, out.stdout
    assert "FileNotFoundError" not in out.stderr


def test_find_latest_insight_skips_blank_lines():
    """Regression (live 21.09.26): blank separator lines aborted every cycle.

    The store carried a blank line between records (149 blanks / 151 records).
    The old loop called json.loads() on every physical line, so it died with
    "Expecting value: line 2 column 1" and NO experiment ever ran. A blank
    separator is not an insight, and one damaged row must not stop the loop.
    """
    import importlib.util, json, tempfile
    spec = importlib.util.spec_from_file_location(
        "kta_blankline_mod", os.path.join(HERE, "knowledge_to_action.py"))
    k = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(k)  # real import path, not just a syntax check

    long_a = "answer text comfortably longer than fifty characters so it counts. " * 2
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "online_buffer.jsonl")
        with open(p, "wb") as f:
            f.write(json.dumps({"u": "first", "a": long_a}).encode() + b"\r\n")
            f.write(b"\r\n")                                  # the blank separator
            f.write(json.dumps({"u": "newest", "a": long_a}).encode() + b"\r\n")
        saved = k.T
        k.T = d
        try:
            got = k.find_latest_insight()
        finally:
            k.T = saved
    assert got is not None, "blank separator line killed the insight lookup"
    assert got["question"] == "newest", got

    # a truncated/damaged row must be skipped too, not fatal
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "online_buffer.jsonl")
        with open(p, "wb") as f:
            f.write(json.dumps({"u": "good", "a": long_a}).encode() + b"\r\n")
            f.write(b'{"u": "broken", "a": \r\n')
            f.write(json.dumps({"u": "newest", "a": long_a}).encode() + b"\r\n")
        saved = k.T
        k.T = d
        try:
            got = k.find_latest_insight()
        finally:
            k.T = saved
    assert got is not None, "damaged row killed the insight lookup"
    assert got["question"] == "newest", got


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASS")
