#!/usr/bin/env python3
"""Weekly ASI capability audit — silent unless a capability went dark.

Cron contract: empty stdout = nothing to say. This job speaks only when a
building block that used to be PROVEN is no longer running (a cron went red or
missing), because that is the regression worth a notification — a capability
that quietly stopped running while still being advertised.

The full table is written to memory/asi_audit.json every run, so the history
exists even when the job stays silent.
"""
import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("asi_audit.py")


def _load():
    spec = importlib.util.spec_from_file_location("asi_audit", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["asi_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = _load()
    result = mod.audit()

    out = mod.HOME / "memory" / "asi_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    import json

    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    gaps = [r for r in result["capabilities"] if r["status"] != "PROVEN"]
    if not gaps:
        return 0  # every building block is implemented AND running

    print(f"⚠️ ASI capability audit: {len(gaps)} building block(s) not proven to run")
    for r in gaps:
        if r["status"] == "ABSENT":
            print(f"  ❌ {r['name']} — missing {', '.join(r['evidence_missing'])}")
        else:
            why = r["runtime_dark"][0] if r["runtime_dark"] else "no runtime signal"
            print(f"  🟡 {r['name']} — built, not running ({why})")
    c = result["counts"]
    print(f"  totals: PROVEN {c['PROVEN']} · PARTIAL {c['PARTIAL']} · ABSENT {c['ABSENT']}")
    print("  A capability on a shelf is not a capability.")
    return 1


if __name__ == "__main__":
    sys.exit(main())