#!/usr/bin/env python3
"""Nightly RSI pass — one entry point for the whole prediction loop.

Runs both halves and prints a compact report (this script is wired to a
`no_agent` cron job, whose stdout is delivered verbatim — so it must stay
short and must say "nothing to report" in one line when nothing happened).

  predict_validate.py   the legacy template predictor's scorer (world-model
                        semantic matching).  Kept because it still owns the
                        historical 282-sample record that predates rsi_cycle.
  rsi_cycle.py          falsifiable predictions + Select + Evaluate + Learn:
                        the part that can record a MISS.

Exit code is 0 even when a half fails, so a broken sub-loop cannot mask the
other one; the failure is printed instead.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
HOME = os.environ.get("OPENAMER_HOME") or os.path.dirname(os.path.dirname(HERE))


def run(script, *args, want=None):
    path = os.path.join(HERE, script)
    if not os.path.exists(path):
        return f"{script}: MISSING"
    try:
        proc = subprocess.run([PY, path, *args], capture_output=True, text=True,
                              timeout=300, encoding="utf-8", errors="replace",
                              env={**os.environ, "PYTHONUTF8": "1", "OPENAMER_HOME": HOME})
    except subprocess.TimeoutExpired:
        return f"{script}: TIMEOUT 300s"
    out = (proc.stdout or "").strip().splitlines()
    err = (proc.stderr or "").strip().splitlines()
    if want:
        for line in out:
            if want in line:
                return line.strip()
    tail = out[-1] if out else (err[-1] if err else f"exit {proc.returncode}, no output")
    return tail


def main():
    legacy = run("predict_validate.py", want="predictions checked")
    cycle = run("rsi_cycle.py", "once", want="predictions:")
    print(f"RSI: {cycle}")
    print(f"legacy: {legacy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
