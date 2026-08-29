"""scripts/thinking_rules.py — persistent, self-enforcing reasoning rules.

Turn hard-won reasoning lessons into durable, loadable rules — the concrete
step beyond "a skill says do reflection". Each rule has: a trigger, the action
to take, an optional proof (a real incident), and a hit counter. Rules live in
<home>/thinking_rules.json so they survive across sessions and tasks.

Usage:
    python thinking_rules.py list                # all rules, sorted by hits
    python thinking_rules.py add "<rule>" --trigger <t> --proof "<incident>"
    python thinking_rules.py bump <rule_id>      # record that it applied
    python thinking_rules.py purge <rule_id>     # remove a stale rule
    python thinking_rules.py context             # compact context block for a task

The agent loads ``context`` (a compact line-per-rule block) at the start of
complex tasks so the rules actually steer behaviour — not just get stored.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def rules_path() -> Path:
    home = Path.home() / "AppData/Local/openamer-laptop" \
        if sys.platform == "win32" else Path.home() / ".openamer"
    return home / "thinking_rules.json"


def _load() -> list[dict]:
    p = rules_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save(rules: list[dict]) -> None:
    p = rules_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")


def add(rule: str, trigger: str = "", proof: str = "") -> int:
    rules = _load()
    # dedupe by normalised text
    norm = " ".join(rule.strip().lower().split())
    for r in rules:
        if " ".join((r.get("rule") or "").strip().lower().split()) == norm:
            print(f"exists as {r['id']} — no dup")
            return 1
    r = {
        "id": uuid.uuid4().hex[:8],
        "rule": rule.strip(),
        "trigger": trigger.strip(),
        "proof": proof.strip(),
        "hits": 0,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Dual-buffer (Memory survey 9.1): new rules enter the hot buffer as
        # pending and are promoted to active only once they earn their place.
        "status": "pending",
    }
    rules.append(r)
    _save(rules)
    print(f"added {r['id']}")
    return 0


def bump(rule_id: str) -> list[dict]:
    rules = _load()
    for r in rules:
        if r.get("id") == rule_id:
            r["hits"] = int(r.get("hits", 0)) + 1
            _save(rules)
            print(f"bumped {rule_id} -> hit {r['hits']}")
            return rules
    print(f"rule {rule_id} not found")
    return rules


def purge(rule_id: str) -> list[dict]:
    rules = [r for r in _load() if r.get("id") != rule_id]
    _save(rules)
    print(f"purged {rule_id}")
    return rules


def promote() -> int:
    """Dual-buffer promotion (Memory survey 9.1): pending -> active.

    A rule earns promotion to the long-term (active) set when it has BOTH a
    concrete proof (evidence, not a slogan) AND at least one real hit (applied).
    This is the re-verify + importance gate before a hot-buffer entry survives
    consolidation. Returns how many were promoted.
    """
    rules=_load()
    promoted=0
    for r in rules:
        if r.get("status")=="pending" and r.get("proof") and int(r.get("hits",0))>=1:
            r["status"]="active"
            promoted+=1
    _save(rules)
    print(f"promote: {promoted} pending -> active")
    return promoted



def consolidate() -> int:
    """Remove exact-duplicate rules (same normalised text); merge hits + proof."""
    rules = _load()
    seen: dict[str, dict] = {}
    out: list[dict] = []
    removed = 0
    for r in rules:
        norm = " ".join((r.get("rule") or "").strip().lower().split())
        if not norm:
            continue
        if norm in seen:
            base = seen[norm]
            base["hits"] = int(base.get("hits", 0)) + int(r.get("hits", 0))
            if r.get("proof") and not base.get("proof"):
                base["proof"] = r.get("proof")
            removed += 1
        else:
            seen[norm] = r
            out.append(r)
    _save(out)
    print(f"consolidated: removed {removed} duplicates, kept {len(out)}")
    return removed


def prune(max_rules: int = 12) -> int:
    """Trim the store to at most ``max_rules``, dropping least-hit oldest."""
    rules = _load()
    if len(rules) <= max_rules:
        print(f"prune: {len(rules)} <= {max_rules}, nothing to remove")
        return 0
    rules_sorted = sorted(rules, key=lambda r: (int(r.get("hits", 0)), r.get("created", "")))
    keep_ids = {r["id"] for r in rules_sorted[len(rules) - max_rules:]}
    out = [r for r in _load() if r.get("id") in keep_ids]
    _save(out)
    print(f"prune: removed {len(rules) - max_rules} (kept top {max_rules} by hits)")
    return len(rules) - max_rules


def recall(focus: str = "", limit: int = 6) -> list[dict]:
    """Causal/domain retrieval (survey 9.2): ACTIVE rules most relevant to focus."""
    rules=[r for r in _load() if r.get("status","active")=="active"]
    if not focus:
        rules=sorted(rules, key=lambda r: int(r.get("hits",0)), reverse=True)
        return rules[:limit]
    focus_toks=set(focus.lower().split())
    def score(r):
        hay=(r.get("trigger","")+" "+r.get("rule","")).lower()
        return (sum(1 for t in focus_toks if t in hay), int(r.get("hits",0)))
    rules.sort(key=score, reverse=True)
    return rules[:limit]


def forget(max_age_days: int = 30, min_hits: int = 1) -> int:
    """Learning-to-forget (survey 9.4): propose pruning stale, hit-less rules."""
    from datetime import datetime
    rules=_load(); now=datetime.now(timezone.utc); stale=0
    for r in rules:
        created=r.get("created","")
        if not created: continue
        try: age=(now-datetime.fromisoformat(created)).days
        except Exception: continue
        if age>max_age_days and int(r.get("hits",0))<min_hits:
            stale+=1
            print(f"  stale: {r['id']} ({age}d, {r.get('hits',0)} hits) {r.get('rule','')[:60]}")
    if stale==0: print("  forget: no stale hit-less rules")
    return stale


def context(sort_by_hits: bool = True) -> str:
    rules = _load()
    # Dual-buffer: only ACTIVE (promoted) rules steer tasks; pending rules that
    # are still in the hot buffer / probation are excluded from the load block.
    rules = [r for r in rules if r.get("status", "active") == "active"]
    if sort_by_hits:
        rules = sorted(rules, key=lambda r: r.get("hits", 0), reverse=True)
    if not rules:
        return "(no thinking rules yet — extract one after the next tricky task)"
    lines = ["THINKING RULES (apply at start of complex tasks):"]
    for r in rules:
        t = f" [if {r['trigger']}]" if r.get("trigger") else ""
        lines.append(f"  - {r['rule']}{t}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="thinking_rules")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sp = sub.add_parser("add"); sp.add_argument("rule")
    sp.add_argument("--trigger", default=""); sp.add_argument("--proof", default="")
    bp = sub.add_parser("bump"); bp.add_argument("rule_id")
    pp = sub.add_parser("purge"); pp.add_argument("rule_id")
    cl = sub.add_parser("consolidate"); cl.add_argument("--max", type=int, default=12)
    sub.add_parser("promote")
    rc = sub.add_parser("recall"); rc.add_argument("--focus", default=""); rc.add_argument("--limit", type=int, default=6)
    sub.add_parser("forget")
    sub.add_parser("context")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        for r in sorted(_load(), key=lambda r: r.get("hits", 0), reverse=True):
            print(f"[{r['id']}] (#{r.get('hits',0)}) {r['rule']}")
            if r.get("trigger"): print(f"      if {r['trigger']}")
            if r.get("proof"): print(f"      proof: {r['proof']}")
        return 0
    if a.cmd == "add":
        return add(a.rule, a.trigger or "", a.proof or "")
    if a.cmd == "bump":
        return 0 if bump(a.rule_id) else 1
    if a.cmd == "purge":
        purge(a.rule_id); return 0
    if a.cmd == "recall":
        for r in recall(a.focus, a.limit): print(f"- {r['rule']}")
        return 0
    if a.cmd == "forget":
        forget(max_age_days=30, min_hits=1); return 0
    if a.cmd == "promote":
        promote(); return 0
    if a.cmd == "consolidate":
        consolidate(); prune(max_rules=a.max); return 0
    if a.cmd == "context":
        print(context()); return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())