"""After the backfill chain ends: strip contaminated values, then measure.

Order matters. `i18n_strip_all.py --apply` rewrites catalogs, so it must not run
while six translation workers are writing the same files. This waits until both
the chain and any round are gone, then does the cleanup once and writes a final
measurement.

    python scripts/i18n_finish.py [--wait-hours 12]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

REPO = pathlib.Path.home() / "openamer-repo"
HOME = pathlib.Path(os.path.expanduser("~/AppData/Local/openamer-laptop"))
REPORTS = HOME / "reports"
LOG = REPORTS / "i18n-finish.log"
PY = REPO / "venv" / "Scripts" / "python.exe"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


CRON_ID = "34a170dc3892"


def cron(action: str) -> None:
    try:
        subprocess.run(["openamer", "cron", action, CRON_ID],
                       capture_output=True, text=True, timeout=120)
        log(f"cron {action}")
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"cron {action} failed: {exc}")


def busy() -> bool:
    """True while a backfill round or the chain itself is still running.

    Only the backfill processes count. `i18n_translate_locale.py` is deliberately
    NOT matched: the 30-minute cron starts it too, so matching it would make this
    finisher wait forever for a cron tick that keeps restarting.
    """
    cmd = (
        "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*i18n_backfill.py*' -or "
        "$_.CommandLine -like '*i18n_backfill_chain.py*' }).Count"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True, timeout=120)
        return r.stdout.strip() not in ("", "0")
    except (OSError, subprocess.SubprocessError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-hours", type=float, default=12.0)
    ap.add_argument("--poll-seconds", type=int, default=120)
    args = ap.parse_args()

    deadline = time.time() + args.wait_hours * 3600
    log("finisher start: waiting for the backfill to settle")
    while busy():
        if time.time() > deadline:
            log(f"gave up after {args.wait_hours} h")
            return 1
        time.sleep(args.poll_seconds)

    # The cron rewrites the same catalogs; pause it for the duration of the
    # cleanup so strip and cron cannot write over each other.
    cron("pause")
    try:
        log("backfill idle; stripping contaminated values")
        r = subprocess.run([str(PY), str(REPO / "scripts" / "i18n_strip_all.py"), "--apply"],
                           cwd=str(REPO), capture_output=True, text=True)
        tail = (r.stdout or "").strip().splitlines()
        log(f"strip exit {r.returncode}: {tail[-1][:160] if tail else ''}")

        # Second catalog layer: the CLI/agent messages in locales/<code>.yaml.
        # The desktop backfill only touches apps/desktop/src/i18n/*.ts, so a
        # language can be 100 % in the UI and still answer in English on the
        # command line. Measured 2026-11-17: 7 940 of 330 x 185 keys were
        # missing or still English, with eight locales at 330/330.
        log("filling the CLI locale layer (locales/*.yaml)")
        r = subprocess.run([str(PY), str(REPO / "scripts" / "i18n_fill_cli_locales.py")],
                           cwd=str(REPO), capture_output=True, text=True)
        tail = (r.stdout or "").strip().splitlines()
        log(f"cli-fill exit {r.returncode}: {tail[-1][:200] if tail else ''}")

        out = REPORTS / "i18n-final-state.json"
        log("measuring all locales")
        r = subprocess.run([str(PY), str(REPO / "scripts" / "i18n_converge.py"),
                            "--report", "--json", str(out)],
                           cwd=str(REPO), capture_output=True, text=True)
        tail = (r.stdout or "").strip().splitlines()
        log(f"report exit {r.returncode}: {tail[-1][:200] if tail else ''}")

        try:
            data = json.loads(out.read_text(encoding="utf-8"))
            rows = data.get("locales") or []
            done = sum(1 for x in rows if x.get("real_gaps", 1) == 0)
            share = sorted(x.get("share_real", x.get("share", 0)) for x in rows)
            median = share[len(share) // 2] if share else 0
            log(f"final: {done}/{len(rows)} complete, median {median*100:.1f}%")
        except (OSError, ValueError) as exc:
            log(f"could not read the final state: {exc}")
    finally:
        cron("resume")

    log("finisher done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
