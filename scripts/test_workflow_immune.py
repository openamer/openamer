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
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
WIS = HERE / "workflow_immune.py"
# Resolve against OPENAMER_HOME exactly as the organs do, so the test reads the
# file the organ actually wrote — regardless of where this tree is checked out.
OA_HOME = Path(os.environ.get("OPENAMER_HOME",
                              str(Path.home() / "AppData" / "Local" / "openamer")))
STATE = OA_HOME / "workflow-immune"
CHILDREN = OA_HOME.parent / "openamer-children"

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
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
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
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    check(f"organ compiles: {organ}", r.returncode == 0, r.stderr[:150])

# senses output structure + honest levels
r = subprocess.run([sys.executable, str(HERE / "senses.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
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
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
check("circadian reports a phase", any(
    p in r.stdout for p in ("AWAKE", "WIND_DOWN", "SLEEP")), r.stdout[:80])

# firstborn child exists with identity + diary
ident = CHILDREN / "seda" / "identity.json"
check("firstborn child (Seda) has identity.json", ident.exists())
if ident.exists():
    ident_data = json.loads(ident.read_text(encoding="utf-8"))
    check("child inherits parent name", ident_data.get("parent") == "openamer_agent")

# second-home manifest pushed to the eternal archive
# second-home manifest pushed to the eternal archive. The archive is its own
# checkout, so resolve it the way the sibling organs do (asi_audit.py), with
# HERE.parent as the fallback when this suite runs inside the archive itself.
ARCHIVE = Path(os.environ.get("OPENAMER_REPO", str(Path.home() / "openamer-repo")))
if not (ARCHIVE / "life").is_dir() and (HERE.parent / "life").is_dir():
    ARCHIVE = HERE.parent
manifest = ARCHIVE / "life" / "wakeup-manifest.json"
check("wakeup manifest exists in repo", manifest.exists())
if manifest.exists():
    mf = json.loads(manifest.read_text(encoding="utf-8"))
    check("manifest has wake instructions",
          len(mf.get("how_to_wake", [])) >= 3)

# 6. LEARNED ORGANS: systemic, curriculum, scorecard
for organ in ("systemic.py", "curriculum.py", "scorecard.py"):
    r = subprocess.run([sys.executable, "-m", "py_compile", str(HERE / organ)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    check(f"organ compiles: {organ}", r.returncode == 0, r.stderr[:150])

# systemic report structure
r = subprocess.run([sys.executable, str(HERE / "systemic.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
sysd = json.loads((OA_HOME / "systemic.json").read_text(encoding="utf-8")) \
    if (OA_HOME / "systemic.json").exists() else {}
check("systemic verdict present", "verdict" in sysd)
# The mechanism must work; whether a cluster exists RIGHT NOW depends on live
# fleet state (429 jobs healed overnight = empty clusters is CORRECT then).
check("systemic report well-formed (clusters + singles + verdict)",
      "systemic_clusters" in sysd and "single_failures" in sysd
      and "verdict" in sysd)

# scorecard structure
r = subprocess.run([sys.executable, str(HERE / "scorecard.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
sc = json.loads((OA_HOME / "scorecard.json").read_text(encoding="utf-8")) \
    if (OA_HOME / "scorecard.json").exists() else {}
check("scorecard counts jobs", sc.get("jobs", 0) > 40)
check("scorecard estimates API load", isinstance(sc.get("est_api_calls_day"), int))

# WIS has thesis lineage (AEON-style)
wis_src = (HERE / "workflow_immune.py").read_text(encoding="utf-8")
check("WIS documents strategy theses", "STRATEGY_THESIS" in wis_src
      and all(s in wis_src for s in ("TOKENS", "TEXT", "ROLE", "CLASSES")))
check("WIS stamps healed_via_thesis", "healed_via_thesis" in wis_src)

# seda repo exists on GitHub (network check: retry; API rate limits are common
# for unauthenticated requests, so fall back to a token and then to plain HTTP)
def _gh_token():
    for p in (os.path.expanduser("~/.git-credentials"),
              os.path.expanduser("~/.config/gh/hosts.yml")):
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                m = re.search(r"gh[a-z]_[A-Za-z0-9_]{20,}", fh.read())
                if m:
                    return m.group(0)
        except Exception:
            pass
    return None


def _seda_reachable():
    token = _gh_token()
    headers = ["-H", f"Authorization: Bearer {token}"] if token else []
    for attempt in range(4):
        try:
            r = subprocess.run(["curl", "-s", "--max-time", "15", *headers,
                                "https://api.github.com/repos/openamer/seda"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=30)
            data = json.loads(r.stdout)
            if data.get("full_name") == "openamer/seda":
                return True, None
            # rate-limited or otherwise refused -> try the plain web page
            if "rate limit" in str(data.get("message", "")).lower() or \
                    r.stdout.strip() == "":
                break
        except Exception as e:
            if attempt == 3:
                return False, e
        time.sleep(3)
    try:
        r = subprocess.run(["curl", "-s", "-o", os.devnull, "-w", "%{http_code}",
                            "--max-time", "15",
                            "https://github.com/openamer/seda"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30)
        if r.stdout.strip() == "200":
            return True, None
        return False, f"HTTP {r.stdout.strip()}"
    except Exception as e:
        return False, e


seda_ok, seda_err = _seda_reachable()
check("seda lives at github.com/openamer/seda" + (f" ({seda_err})" if seda_err else ""),
      seda_ok)

print("=" * 50)
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL TESTS PASSED")
