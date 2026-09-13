#!/usr/bin/env python3
"""World State Model (SEAgent idea, adapted): assess each workflow STEP
BEFORE running it, so drift is predicted instead of only healed after the fact.

WIS heals reactively (run -> detect drift -> repair). This predicts.

Inputs (all local, real data):
  workflow-immune/workflows.json   per-step baseline fingerprint
  workflow-immune/reports/*.png    healed/sick evidence (age = churn proxy)
  workflow-immune/strategies.json  heal strategy win/loss

Per step we score three axes (SEAgent: DOM stability, load time, visibility):
  stability  : baseline completeness (dom_path/id/cls present) + heal churn
  latency    : prior run cost (report count / registration age)
  visibility : baseline.visible + rect area sanity

Output: workflow-immune/world_state.json  {workflow: {step: risk}}
Risk 0..1 -- higher = more likely to drift on the next run.

Usage: world_state.py [<workflow>] [--json]
Exit 0 always. Read-only w.r.t. workflows.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE = Path(r"C:\Users\damir\AppData\Local\openamer-laptop\workflow-immune")
WF = STATE / "workflows.json"
REPORTS = STATE / "reports"
STRAT = STATE / "strategies.json"
OUT = STATE / "world_state.json"


def days_since(iso):
    try:
        t = datetime.fromisoformat(iso)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 86400
    except Exception:
        return None


def heal_churn(step):
    """How many times this step was healed (healed_from_<date> keys)."""
    return sum(1 for k in step if str(k).startswith("healed_from"))


GENERIC_TAGS = {"body", "div", "span", "a", "p", "input", "button", "form", "section"}


def selector_specificity(sel):
    """A selector naming only a bare tag (or tag+no id/class/#/[/.) is fragile."""
    s = (sel or "").strip()
    if not s:
        return 0.0
    has_hook = any(c in s for c in "#[.") or ">" in s or " " in s
    bare = s.lower() in GENERIC_TAGS
    if bare and not has_hook:
        return 0.2
    if not has_hook:
        return 0.6
    return 1.0


def stability(base, step):
    s = 1.0
    if not base.get("found"):
        return 0.0
    if not base.get("dom_path"):
        s -= 0.25
    if not base.get("id"):
        s -= 0.15
    if not base.get("cls"):
        s -= 0.10
    s -= min(0.45, 0.15 * heal_churn(step))
    # a bare-tag selector is structurally fragile even with a clean baseline
    spec = selector_specificity(step.get("selector"))
    s -= (1.0 - spec) * 0.30
    return max(0.0, s)



def visibility(base):
    if not base.get("visible"):
        return 0.0
    r = base.get("rect") or {}
    w, h = r.get("w") or 0, r.get("h") or 0
    if w <= 0 or h <= 0:
        return 0.3
    if w * h < 400:            # tiny target -> easy to miss/overlap
        return 0.6
    return 1.0


def latency_penalty(wf_age_days, n_recent):
    """Older registration + recent report churn => less trustworthy baseline.

    n_recent = report files touched in the last 7 days (drift evidence that is
    *current*, not lifetime accumulation -- lifetime counts saturate and stop
    discriminating).
    """
    p = 0.0
    if wf_age_days is not None and wf_age_days > 14 and n_recent == 0:
        p = 0.35      # stale, not re-checked in a while
    if n_recent > 0:
        p = max(p, min(0.5, 0.08 * n_recent))
    return p



def assess():
    if not WF.exists():
        return {}
    data = json.loads(WF.read_text(encoding="utf-8"))
    wfs = data.get("workflows", data)
    out = {}
    for name, wf in wfs.items():
        base = wf.get("baseline") or {}
        age = days_since(wf.get("registered_at"))
        now = datetime.now().timestamp()
        all_rep = list(REPORTS.glob(f"{name}_*")) if REPORTS.exists() else []
        n_recent = sum(1 for f in all_rep
                       if (now - f.stat().st_mtime) <= 7 * 86400)
        n_rep = len(all_rep)
        lat = latency_penalty(age, n_recent)
        steps = {}
        for i, step in enumerate(wf.get("steps") or []):
            b = base.get(str(i)) or {}
            st, vi = stability(b, step), visibility(b)
            # risk rises when the baseline is weak, the target is faint, or the
            # workflow has a history of churn.
            risk = 0.55 * (1.0 - st) + 0.25 * (1.0 - vi) + 0.20 * lat
            steps[str(i)] = {
                "risk": round(min(1.0, risk), 3),
                "stability": round(st, 3),
                "visibility": round(vi, 3),
                "heal_churn": heal_churn(step),
                "selector": step.get("selector", ""),
                "verdict": ("HEAL_FIRST" if risk >= 0.6 else
                            "WATCH" if risk >= 0.35 else "TRUST"),
            }
        out[name] = {
            "url": wf.get("url", ""),
            "age_days": round(age, 1) if age is not None else None,
            "reports": n_rep, "reports_recent": n_recent, "steps": steps,
        }
    return out


def main(argv):
    want = next((a for a in argv if not a.startswith("-")), None)
    res = assess()
    if not res:
        print(f"no workflows at {WF}")
        return 0
    if want:
        res = {want: res[want]} if want in res else {}
        if not res:
            print(f"unknown workflow '{want}'")
            return 0
    if "--json" in argv:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print("WORLD STATE MODEL  (pre-run step risk: stability x latency x visibility)")
        print("=" * 84)
        for name, wf in res.items():
            print(f"\n{name}  <- {wf['url']}  age={wf['age_days']}d"
                  f" reports={wf['reports']} (7d: {wf['reports_recent']})")
            for i, s in sorted(wf["steps"].items(), key=lambda kv: -kv[1]["risk"]):
                print(f"  step {i} risk={s['risk']:<5} {s['verdict']:<11}"
                      f" stab={s['stability']:<5} vis={s['visibility']:<5}"
                      f" churn={s['heal_churn']}  {s['selector'][:40]}")
        print("=" * 84)
        hot = [f"{n}:{i}" for n, w in res.items() for i, s in w["steps"].items()
               if s["verdict"] == "HEAL_FIRST"]
        print(f"pre-heal recommended: {', '.join(hot) if hot else 'none'}")
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
