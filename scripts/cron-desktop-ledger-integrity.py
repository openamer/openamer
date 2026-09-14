#!/usr/bin/env python3
"""Nightly integrity watchdog for the desktop evidence ledger.

Cron contract: SILENT when the evidence is intact (empty stdout = nothing to
say). It speaks only when the chain is broken.

Why a watchdog and not a report: the ledger's value is that it can be *trusted*
later. Evidence that can be silently altered is not evidence, so what needs
watching is not how many actions happened but whether the stored frames still
hash to what was recorded. A modified or missing frame means the proof of what
the agent did on the desktop is no longer sound — that is the thing worth a
notification, and it is the only thing this job reports.
"""
import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("desktop_ledger.py")


def _load():
    spec = importlib.util.spec_from_file_location("desktop_ledger", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["desktop_ledger"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = _load()
    ledger = mod.Ledger()
    report = ledger.verify()

    if report["checked"] == 0:
        return 0  # nothing recorded yet: silence is correct, not a failure

    if report["intact"]:
        return 0

    print("⚠️ Desktop evidence ledger: integrity check FAILED")
    if report["modified"]:
        print(f"  altered frames ({len(report['modified'])}):")
        for p in report["modified"][:10]:
            print(f"    - {p}")
    if report["missing"]:
        print(f"  missing frames ({len(report['missing'])}):")
        for p in report["missing"][:10]:
            print(f"    - {p}")
    print(f"  checked={report['checked']} ok={report['ok']}")
    print("  The record of what the agent did on the desktop can no longer be "
          "trusted — a frame was changed or lost after it was written.")
    return 1


if __name__ == "__main__":
    sys.exit(main())