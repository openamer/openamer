#!/usr/bin/env python3
"""Homeostasis - internal consistency regulation for OpenAmer's own knowledge.

NOT a competitor copy. Every competitor we studied optimises OUTWARD: more
tools, more integrations, more tokens served. None of them regulates its own
INTERNAL consistency. As an organism accumulates memory, skills and config over
months, it drifts: two sources assert different defaults, duplicate species
proliferate, recorded snapshots hold the wrong field. Nothing crashes. The
organism just quietly contradicts itself, and every later decision inherits the
contradiction.

Biological framing (why it is called homeostasis and not "lint"): an organism
holds internal variables near a setpoint (temperature, pH, osmolarity) with
dedicated feedback organs. Growth without regulation is cancer. This file adds
the regulatory organs to a system that so far only knew how to grow.

Three osmostats, each read-only, each reporting a setpoint deviation:

  model   - the configured model/provider SETPOINT vs every cron job that
            pins its own. Divergence is a real, documented cost leak:
            a job pin OVERRIDES config, so the fleet silently runs on models
            the operator never chose.
  skills  - 700+ skills accumulate; near-duplicate species crowd out retrieval
            and long names break the documented 64-char limit.
  claims  - durable `KEY: value` claims in MEMORY.md that collide: the same key
            asserted twice with different values.

Usage:
  homeostasis.py [audit] [--json] [--organ model|skills|claims]
  homeostasis.py check            -> exit 0 healthy, 1 degraded, 2 critical

Exit codes: 0 = within tolerance, 1 = WARN, 2 = FAIL.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

OA_HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
CONFIG = OA_HOME / "config.yaml"
JOBS = OA_HOME / "cron" / "jobs.json"
SKILLS = OA_HOME / "skills"
MEMORY = OA_HOME / "memories" / "MEMORY.md"
OUT = OA_HOME / "reports" / "homeostasis.json"

# "OK": 0 MUST be present: without it, .get(status, 2) treated a healthy organ
# as the WORST severity, so an "OK" organ silently overwrote a "WARN" one and
# the audit reported OVERALL: OK while skills was WARN. Caught by probing the
# aggregator directly instead of trusting its own verdict.
TOLERANCE = {"OK": 0, "WARN": 1, "FAIL": 2}


def load_config_model():
    """Setpoint: what the operator actually configured."""
    try:
        import yaml
        d = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return {"error": f"config unreadable: {e}"}
    m = d.get("model") or {}
    return {"default": m.get("default"), "provider": m.get("provider")}


def load_jobs():
    try:
        d = json.loads(JOBS.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": f"jobs unreadable: {e}"}
    jobs = d if isinstance(d, list) else d.get("jobs", [])
    return jobs


def _looks_like_provider(s):
    """A provider name has no '/' (models are 'vendor/model'); config uses the
    'custom:<name>' form for custom providers."""
    if not s:
        return False
    return "/" not in s


def osmostat_model():
    """Setpoint vs fleet. A job's model pin WINS over config, so any divergence
    means the fleet is not running on the operator's choice."""
    cfg = load_config_model()
    if "error" in cfg:
        return {"organ": "model", "status": "FAIL", "findings": [cfg["error"]]}
    jobs = load_jobs()
    if isinstance(jobs, dict):
        return {"organ": "model", "status": "FAIL", "findings": [jobs["error"]]}

    setpoint = f"{cfg.get('provider') or '?'}:{cfg.get('default') or '?'}"
    findings = []
    stray_model, stray_provider, misplaced = [], [], []

    for j in jobs:
        if j.get("no_agent"):
            continue          # script jobs never call a model; a pin is inert
        name = (j.get("name") or "?")[:44]
        jm, jp = j.get("model"), j.get("provider")
        snap = j.get("model_snapshot")
        if jm and jm != cfg.get("default"):
            stray_model.append((name, jm))
        if jp and jp != cfg.get("provider"):
            stray_provider.append((name, jp))
        # data integrity: model_snapshot should hold a MODEL. If it holds a
        # bare provider name, whatever wrote it put the wrong field in it.
        if snap and _looks_like_provider(snap) and jp is None:
            misplaced.append((name, snap))

    if stray_model:
        findings.append(
            f"{len(stray_model)} agent job(s) run a DIFFERENT MODEL than the "
            f"setpoint ({cfg.get('default')}) -- a job pin overrides config:")
        findings += [f"    {n} -> {m}" for n, m in stray_model[:8]]
    if stray_provider:
        findings.append(
            f"{len(stray_provider)} job(s) name a different PROVIDER than the "
            f"setpoint ({cfg.get('provider')}); a job provider pin also wins:")
        findings += [f"    {n} -> {p}" for n, p in stray_provider[:8]]
    if misplaced:
        findings.append(
            f"{len(misplaced)} job(s) store a PROVIDER name in model_snapshot "
            f"(field confusion -- snapshot should hold a model):")
        findings += [f"    {n} -> {s}" for n, s in misplaced[:8]]

    status = "FAIL" if stray_model else ("WARN" if (stray_provider or misplaced) else "OK")
    return {"organ": "model", "status": status, "setpoint": setpoint,
            "agent_jobs": sum(1 for j in jobs if not j.get("no_agent")),
            "divergent": len(stray_model) + len(stray_provider),
            "findings": findings}


STOP = {"the", "a", "an", "and", "or", "for", "with", "when", "use", "used", "using",
        "from", "into", "that", "this", "your", "you", "are", "not", "its", "it",
        "on", "in", "to", "of", "is", "as", "at", "by", "be", "it's", "via"}


def _sig(text):
    words = re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text.lower())
    return {w for w in words if w not in STOP}


def osmostat_skills():
    """Duplicate species and over-long names in the skill population."""
    if not SKILLS.exists():
        return {"organ": "skills", "status": "FAIL", "findings": ["no skills dir"]}
    items = []
    for p in SKILLS.rglob("SKILL.md"):
        # quarantined / archived tissue is not part of the living population --
        # counting it inflated the total (718 vs 696) and re-reported clusters
        # that had already been resolved.
        if any(part.startswith(("_quarantine", "_archive")) for part in p.parts):
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:1200]
        except Exception:
            continue
        m = re.search(r"^name:\s*(.+)$", head, re.M)
        d = re.search(r"^description:\s*(.+)$", head, re.M)
        name = (m.group(1).strip().strip('"\'') if m else p.parent.name)
        desc = (d.group(1).strip().strip('"\'') if d else "")
        items.append({"dir": p.parent.name, "name": name, "desc": desc,
                      "sig": _sig(name + " " + desc)})

    long_names = [i for i in items if len(i["name"]) > 64]

    # near-duplicate clustering by Jaccard on the signature
    groups, used = [], set()
    for a in range(len(items)):
        if a in used:
            continue
        cluster = [items[a]]
        for b in range(a + 1, len(items)):
            if b in used:
                continue
            sa, sb = items[a]["sig"], items[b]["sig"]
            if not sa or not sb:
                continue
            j = len(sa & sb) / len(sa | sb)
            if j >= 0.6:
                cluster.append(items[b])
                used.add(b)
        if len(cluster) > 1:
            used.add(a)
            groups.append(cluster)

    groups.sort(key=len, reverse=True)
    findings = []
    if long_names:
        findings.append(f"{len(long_names)} skill name(s) exceed the documented "
                        f"64-char limit (they cannot be loaded by name):")
        findings += [f"    {len(i['name'])} chars: {i['name'][:70]}" for i in long_names[:6]]
    if groups:
        findings.append(f"{len(groups)} near-duplicate cluster(s) found "
                        f"(Jaccard >= 0.6 on name+description); "
                        f"{sum(len(g) for g in groups)} skills total:")
        for g in groups[:5]:
            findings.append(f"    x{len(g)}: {', '.join(i['dir'][:26] for i in g[:5])}")

    status = "FAIL" if long_names else ("WARN" if groups else "OK")
    return {"organ": "skills", "status": status, "total": len(items),
            "long_names": len(long_names), "duplicate_clusters": len(groups),
            "redundant_skills": sum(len(g) - 1 for g in groups),
            "findings": findings}


def osmostat_claims():
    """Colliding durable claims in MEMORY.md: same key, incompatible value."""
    if not MEMORY.exists():
        return {"organ": "claims", "status": "FAIL", "findings": ["no MEMORY.md"]}
    text = MEMORY.read_text(encoding="utf-8", errors="ignore")
    entries = [e.strip() for e in re.split(r"^\s*§\s*$", text, flags=re.M) if e.strip()]

    by_key = defaultdict(list)
    for e in entries:
        m = re.match(r"^([A-Za-z][A-Za-z0-9 _/\-]{2,28})\s*[:=]", e)
        if m:
            by_key[m.group(1).strip().upper()].append(e.replace(chr(10), " ")[:110])

    collisions, redundant = [], []
    for k, v in by_key.items():
        if len(v) == 1:
            continue
        uniq = {re.sub(r"\s+", " ", x.split(":", 1)[-1]).strip() for x in v}
        if len(uniq) > 1:
            collisions.append((k, v))
        else:
            redundant.append(k)

    findings = []
    if collisions:
        findings.append(f"{len(collisions)} key(s) asserted more than once with "
                        f"DIFFERENT content -- one silently wins:")
        for k, v in collisions[:5]:
            findings.append(f"    {k}:")
            findings += [f"      - {x[:96]}" for x in v[:3]]
    if redundant:
        findings.append(f"{len(redundant)} key(s) asserted more than once with "
                        f"identical content (pure redundancy, safe to merge): "
                        f"{', '.join(redundant[:8])}")

    status = "WARN" if (collisions or redundant) else "OK"
    return {"organ": "claims", "status": status, "entries": len(entries),
            "keys": len(by_key), "collisions": len(collisions),
            "redundant_keys": len(redundant), "findings": findings}


ORGANS = {"model": osmostat_model, "skills": osmostat_skills, "claims": osmostat_claims}
ICON = {"OK": "OK  ", "WARN": "WARN", "FAIL": "FAIL"}


def run(only=None):
    res = {}
    for name, fn in ORGANS.items():
        if only and name != only:
            continue
        try:
            res[name] = fn()
        except Exception as e:                      # an organ must not kill the body
            res[name] = {"organ": name, "status": "FAIL",
                         "findings": [f"organ raised {type(e).__name__}: {e}"]}
    # severity = the WORST organ, computed from the tolerance table
    worst_rank = max((TOLERANCE.get(r["status"], 2) for r in res.values()), default=0)
    overall = {0: "OK", 1: "WARN", 2: "FAIL"}[worst_rank]
    return {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "overall": overall, "organs": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="audit", choices=["audit", "check"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--organ", choices=list(ORGANS))
    a = ap.parse_args()

    res = run(a.organ)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif a.cmd == "check":
        # one line for a cron: the whole point is a verdict, not a lecture
        print(f"[HOMEOSTASIS] {res['overall']} | " + " | ".join(
            f"{k}={v['status']}" for k, v in res["organs"].items()))
    else:
        print("HOMEOSTASIS - internal consistency of this organism")
        print("=" * 72)
        for name, r in res["organs"].items():
            print(f"\n[{ICON[r['status']]}] {name}")
            head = {k: v for k, v in r.items()
                    if k not in ("findings", "status", "organ")
                    and not isinstance(v, (list, dict))}
            print(f"  {head}")
            for f in r["findings"]:
                print(f"  {f}")
        print("\n" + "=" * 72)
        print(f"OVERALL: {res['overall']}   (written to {OUT.name})")
        print("An organism that only grows becomes a tumour; this is the "
              "regulatory half.")

    return TOLERANCE.get(res["overall"], 0)


if __name__ == "__main__":
    sys.exit(main())
