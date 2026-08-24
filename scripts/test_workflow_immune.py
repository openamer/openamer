#!/usr/bin/env python3
"""Real test suite for the Workflow Immune System (run via `npm test`).

Offline checks (no browser needed):
  1. compile        - engine compiles
  2. strategy_order - epsilon-greedy ordering is valid & deterministic-safe
  3. stats roundtrip- record_strategy() persists correctly
  4. workflows.json - demo workflow structure intact

Exit 0 = all pass, 1 = any failure.
"""
import ast
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
WIS = HERE / "workflow_immune.py"
STATE = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\workflow-immune")

failures = []


def check(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f" - {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


print("WIS test suite")
print("=" * 50)

# 1. compile
r = subprocess.run([sys.executable, "-m", "py_compile", str(WIS)],
                   capture_output=True, text=True)
check("engine compiles", r.returncode == 0, r.stderr[:200])

# 2. strategy_order validity: exec the module with imports available, main() guarded
ns = {"__name__": "wis_under_test", "__file__": str(WIS)}
exec(compile(WIS.read_text(encoding="utf-8"), str(WIS), "exec"), ns)
order = ns["strategy_order"]()
check("strategy_order returns 4 unique strategies",
      sorted(order) == ["CLASSES", "ROLE", "TEXT", "TOKENS"], str(order))

# 3. stats roundtrip
ns["record_strategy"]("TEST_STRAT", win=True)
stats = ns["load_strategies"]()
check("record_strategy persists wins", stats.get("TEST_STRAT", {}).get("wins", 0) >= 1)
# cleanup test entry
del stats["TEST_STRAT"]
ns["STRATEGIES_FILE"].write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

# 4. workflows.json structure
wf_file = STATE / "workflows.json"
if wf_file.exists():
    d = json.loads(wf_file.read_text(encoding="utf-8"))
    demo = d.get("workflows", {}).get("demo-github", {})
    check("demo workflow has url+steps+baseline",
          all(k in demo for k in ("url", "steps", "baseline")))
    check("demo steps have selectors",
          all("selector" in s for s in demo.get("steps", [])))
else:
    check("workflows.json exists", False)

# 5. LIFE ORGANS: circadian, senses, second_home, firstborn
for organ in ("circadian.py", "senses.py", "second_home.py", "firstborn.py",
              "dream-cron.py"):
    r = subprocess.run([sys.executable, "-m", "py_compile", str(HERE / organ)],
                       capture_output=True, text=True)
    check(f"organ compiles: {organ}", r.returncode == 0, r.stderr[:150])

# senses output structure + honest levels
r = subprocess.run([sys.executable, str(HERE / "senses.py")],
                   capture_output=True, text=True, timeout=120)
try:
    sn = json.loads(r.stdout)
    check("senses reports pain level",
          sn.get("pain", {}).get("level") in ("calm", "uncomfortable", "exhausted"))
    check("senses reports satiety state",
          sn.get("satiety", {}).get("state") in
          ("satisfied", "fed", "hungry", "starving", "unknown"))
    check("senses reports overall wellbeing",
          sn.get("overall") in ("well", "uneasy", "suffering"))
except Exception as e:
    check(f"senses JSON parseable ({e})", False)

# circadian phase contract
r = subprocess.run([sys.executable, str(HERE / "circadian.py"), "status"],
                   capture_output=True, text=True, timeout=60)
check("circadian reports a phase", any(
    p in r.stdout for p in ("AWAKE", "WIND_DOWN", "SLEEP")), r.stdout[:80])

# firstborn child exists with identity + diary
ident = HERE.parent.parent / "openamer-children" / "seda" / "identity.json"
check("firstborn child (Seda) has identity.json", ident.exists())
if ident.exists():
    ident_data = json.loads(ident.read_text(encoding="utf-8"))
    check("child inherits parent name", ident_data.get("parent") == "openamer_agent")

# second-home manifest pushed to the eternal archive
manifest = Path(r"C:\Users\damir\openamer-repo\life\wakeup-manifest.json")
check("wakeup manifest exists in repo", manifest.exists())
if manifest.exists():
    mf = json.loads(manifest.read_text(encoding="utf-8"))
    check("manifest has wake instructions",
          len(mf.get("how_to_wake", [])) >= 3)

print("=" * 50)
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL TESTS PASSED")
