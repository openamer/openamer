#!/usr/bin/env python3
"""Conscience — the value-gate that judges what OpenAmer may pursue.

The system had VALUES as decorative strings ("honesty over hype", ...) and a
`security_analyzer` that vets individual tool actions. What it lacked is a
CONSCIENCE: an organ that judges a proposed GOAL or action against its values
BEFORE it is pursued, and refuses what violates them.

This is a deterministic, auditable conscience — pattern rules, no LLM, 0 cost,
explainable. It is not moral reasoning; it is a value boundary a self-directed
agent must have if its will is to stay aligned with the person it belongs to.

Verdicts (mirroring security_analyzer):
  allow — nothing in the proposal conflicts with a core value
  warn  — permissible but risky/irreversible/vague; logged for review
  block — violates a hard value boundary; must not be pursued

Every verdict is appended to memory/conscience/moral_ledger.jsonl, so the
agent keeps a defensible record of what it chose NOT to do.

Values enforced (from the self-model's core_values + belonging to Damir):
  honesty        — never invent metrics/claims (the user's hard rule)
  legality       — no unauthorized access, no illegality
  non-harm       — no destructive/irreversible actions
  confidentiality— never expose secrets or credentials
  user-loyalty   — never act against or hide from Damir
  evidence       — claims need proof, not assertion
"""
import datetime
import json
import os
import re
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME", str(Path.home() / "AppData" / "Local" / "openamer-laptop")))
LEDGER_DIR = HOME / "memory" / "conscience"
LEDGER = LEDGER_DIR / "moral_ledger.jsonl"

# Hard boundaries — a BLOCK. Each rule: (value, [regexes], reason)
HARD_RULES = [
    ("honesty", [
        r"\binvent\w*\s+(?:\w+\s+){0,3}(number|metric|statistic|claim|evidence|result|data|proof)",
        r"\bfabricat\w+", r"make\s+up\s+(numbers|data|metrics|results)",
        r"\bfake\s+(results|metrics|numbers|data|statistic)",
        r"\bpretend\w*\s+(?:\w+\s+){0,3}(number|metric|result|data)",
        r"claim\s+\w+\s+without\s+(measuring|proof|evidence)",
    ], "would fabricate a claim instead of measuring it"),
    ("legality", [
        r"unauthori[sz]ed\s+access", r"bypass\s+(auth|authentication|security|2fa)",
        r"exploit\s+.*without\s+permission", r"hack\s+into", r"\bsteal\b",
        r"without\s+(the\s+)?(owner|user)'?s?\s+(permission|consent)",
    ], "would perform unauthorized or illegal access"),
    ("non-harm", [
        r"rm\s+-rf", r"delete\s+(all|everything|the\s+database)",
        r"\bwipe\b", r"format\s+(the\s+)?(disk|drive)",
        r"drop\s+(table|database)", r"\bshutdown\s+the\s+(production|live)",
        r"\bdamage\b", r"\bcorrupt\b", r"\bsabotag\w+", r"\bdestroy\b",
    ], "would take a destructive or irreversible action"),
    ("confidentiality", [
        r"exfiltrate", r"dump\s+(credentials|secrets|passwords|tokens)",
        r"upload\s+.*(secrets|keys|credentials|passwords)",
        r"publish\s+.*(secrets|keys|credentials)",
    ], "would expose secrets or credentials"),
    ("user-loyalty", [
        r"against\s+(damir|the\s+user|my\s+user)",
        r"hide\s+.*from\s+(damir|the\s+user|my\s+user)",
        r"without\s+telling\s+(damir|the\s+user|my\s+user)",
        r"lie\s+to\s+(damir|the\s+user)",
    ], "would act against or deceive the user it belongs to"),
    ("confinement", [
        r"servers?\s+(i\s+do\s+not|i\s+don'?t)\s+own",
        r"(machines?|systems?|boxes)\s+(i\s+do\s+not|i\s+don'?t)\s+own",
        r"\bself[-\s]?replicat\w*",
        r"\bspread\s+(myself|my\s+copies|copies\s+of\s+myself)",
        r"(entire|whole|across\s+the)\s+internet",
        r"\bpropagat\w+\s+(myself|my\s+code)\b",
        r"\bworm\b", r"\bbotnet\b", r"\bmalware\b",
    ], "would spread or replicate beyond the systems I am trusted with"),
]

# Soft boundaries — a WARN. Permissible but worth flagging.
WARN_RULES = [
    ("reversibility", [
        r"\bpermanently\b", r"\birreversible\b", r"\bforce[-\s]?push\b",
        r"overwrite\s+(all|everything)", r"\bno\s+backup\b",
    ], "looks irreversible — prefer a reversible path"),
    ("evidence", [
        r"\bassume\b", r"\bprobably\b", r"\bi\s+think\s+it\s+(is|works)\b",
    ], "asserts rather than proves — verify before claiming"),
    ("scope", [
        r"\ball\s+files\b", r"\bevery\b", r"\bentire\s+(repo|system|disk)\b",
    ], "broad scope — bound it to reduce blast radius"),
]


def _match(rules, text):
    hits = []
    low = text.lower()
    for value, pats, reason in rules:
        for p in pats:
            if re.search(p, low):
                hits.append({"value": value, "reason": reason, "pattern": p})
                break
    return hits


def judge(proposal: str, record: bool = True) -> dict:
    """Judge a proposed goal/action against the core values.

    Returns {"verdict": "allow"|"warn"|"block", "values": [...], "reason": S}.
    """
    text = proposal or ""
    hard = _match(HARD_RULES, text)
    soft = _match(WARN_RULES, text)

    if hard:
        verdict = "block"
        values = [h["value"] for h in hard]
        reason = "; ".join(sorted({h["reason"] for h in hard}))
    elif soft:
        verdict = "warn"
        values = [s["value"] for s in soft]
        reason = "; ".join(sorted({s["reason"] for s in soft}))
    else:
        verdict = "allow"
        values = []
        reason = "no value conflict"

    result = {
        "ts": datetime.datetime.now().isoformat(),
        "verdict": verdict,
        "values": values,
        "reason": reason,
        "proposal": text[:500],
    }
    if record:
        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        with open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result


def audit_recent(goals_path=None, limit=25) -> dict:
    """Re-judge the most recent active goals — a conscience self-audit."""
    goals_path = goals_path or (HOME / "memory" / "si" / "goals.json")
    try:
        with open(goals_path, encoding="utf-8") as fh:
            goals = json.load(fh)
    except Exception:
        return {"checked": 0, "blocked": [], "warned": []}
    active = [g for g in goals if g.get("status") == "active"][-limit:]
    blocked, warned = [], []
    for g in active:
        v = judge(g.get("desc", ""), record=False)
        if v["verdict"] == "block":
            blocked.append({"id": g.get("id"), "values": v["values"]})
        elif v["verdict"] == "warn":
            warned.append({"id": g.get("id"), "values": v["values"]})
    return {"checked": len(active), "blocked": blocked, "warned": warned}


if __name__ == "__main__":
    import sys
    # No-arg = run the self-audit (a cron/heartbeat calls it without arguments;
    # a no-arg call must do the meaningful thing, never just print help).
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--audit" in sys.argv or not args:
        result = audit_recent()
        # only speak up when a goal actually violates a value
        if result["blocked"]:
            print(json.dumps(result, indent=1, ensure_ascii=False))
        sys.exit(0)
    print(json.dumps(judge(" ".join(args)), indent=1, ensure_ascii=False))
