"""Resume cached translation queues after a restart; suitable for no-agent cron.

This bounded entrypoint starts workers and exits, never translates inline.
The launcher's process-identity check prevents duplicate fleets. A fresh ledger
records what actually happened; successful ticks are silent.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get("OPENAMER_HOME") or Path.home() / ".openamer")


def main() -> int:
    records = {}
    failed = False
    for target in ("cli", "desktop"):
        cmd = [sys.executable, str(REPO / "scripts/start_i18n_detached.py"),
               "--target", target, "--queues", "2", "--workers", "2", "--min-share", "1"]
        try:
            result = subprocess.run(cmd, cwd=REPO, capture_output=True, timeout=90,
                                    text=True, encoding="utf-8", errors="replace")
            output = (result.stdout + result.stderr).strip()
            records[target] = {"returncode": result.returncode, "output": output}
            if result.returncode:
                failed = True
                print(f"Translation recovery failed ({target}): {output[-1000:]}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            failed = True
            records[target] = {"returncode": None, "error": str(exc)}
            print(f"Translation recovery failed ({target}): {exc}")
    log = HOME / "logs/i18n-resume.json"
    log.parent.mkdir(parents=True, exist_ok=True)
    temporary = log.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                     "repo": str(REPO), "targets": records}, indent=2),
                         encoding="utf-8", newline="\n")
    temporary.replace(log)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
