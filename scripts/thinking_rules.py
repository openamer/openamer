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


def context(sort_by_hits: bool = True) -> str:
    rules = _load()
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
    if a.cmd == "context":
        print(context()); return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())