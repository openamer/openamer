#!/usr/bin/env python3
"""
Darwin Gate (Phase 31) - Agent proposals go through OpenAmer CLI.

The flow:
  1. A swarm worker (LLM agent) has an idea: "I want to change X"
  2. The proposal is sent to OpenAmer's brain (GLM-5.3-Flash via OpenRouter)
  3. OpenAmer evaluates: APPROVE / REJECT / NEEDS_MORE_INFO
  4. Only APPROVED proposals are executed
  5. Everything is logged for audit

This ensures agents can't break anything - OpenAmer (the strong brain)
is always the final decision maker.

Usage:
  python darwin_gate.py --propose <worker> <action> <description> [code]
  python darwin_gate.py --status
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

HOME = Path.home() / "AppData" / "Local" / "openamer-laptop"
GATE_LOG = HOME / "darwin" / "gate-log.json"
GATE_QUEUE = HOME / "darwin" / "gate-queue.json"

# OpenRouter credentials (from .env / config)
import os
from dotenv import load_dotenv
load_dotenv(Path.home() / "AppData/Local/openamer-laptop/.env")

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENAMER_MODEL", "z-ai/glm-4.6")
# fallback to strong model for gate decisions
GATE_MODEL = "z-ai/glm-4.6"  # GLM-5.3-Flash equivalent on OpenRouter


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")


def ask_openrouter(prompt: str, system: str = "") -> tuple[bool, str]:
    """Ask OpenAmer's brain (GLM-5.3-Flash / GLM-4.6) for a decision."""
    if not OPENROUTER_KEY:
        return False, "no API key"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": GATE_MODEL,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.3,  # low temperature for careful decisions
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body, method="POST",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
        choices = resp.get("choices", [])
        if not choices:
            return False, "no choices in response"
        msg = choices[0].get("message", {})
        content = msg.get("content")
        if content and content.strip():
            return True, content.strip()
        # GLM-4.6 reasoning model: answer may be at end of reasoning
        reasoning = msg.get("reasoning", "")
        if reasoning:
            for line in reversed(reasoning.splitlines()):
                line_s = line.strip()
                upper = line_s.upper()
                if any(kw in upper for kw in ("APPROVE", "REJECT", "NEEDS_MORE_INFO")):
                    return True, line_s[:300]
            lines = [l.strip() for l in reasoning.splitlines() if l.strip()]
            if lines:
                return True, lines[-1][:300]
        return False, "empty response from model"
    except Exception as e:
        return False, str(e)[:300]


def evaluate_proposal(worker: str, action: str, description: str,
                      code: str = "") -> dict:
    """Send a proposal to OpenAmer's brain for evaluation.

    The brain (GLM-5.3-Flash) evaluates:
    - Is this change safe?
    - Is this change useful?
    - Is this change necessary?
    - Could this break anything?
    """
    # Build the evaluation prompt
    code_section = f"\n\nProposed code/patch:\n```\n{code[:2000]}\n```" if code else ""
    prompt = f"""A Darwin swarm agent wants to modify the OpenAmer system.

Agent: {worker}
Action requested: {action}
Description: {description}{code_section}

Evaluate this proposal. Consider:
1. SAFETY: Could this break the system, lose data, or create security issues?
2. USEFULNESS: Does this actually improve OpenAmer?
3. NECESSITY: Is this change needed right now, or is it speculative?
4. SCOPE: Is the change too broad or touching critical code?

Respond with EXACTLY one of:
- APPROVE: <one-sentence reason>
- REJECT: <one-sentence reason>
- NEEDS_MORE_INFO: <what additional info is needed>

Your response:"""

    system = """You are the OpenAmer Gatekeeper - the central intelligence that
protects the system from harmful changes while allowing beneficial improvements.
You are conservative by default: when in doubt, REJECT.
You have full knowledge of the OpenAmer codebase architecture.

Decision criteria:
- APPROVE only if: safe AND useful AND well-scoped
- REJECT if: dangerous, unnecessary, poorly described, or too broad
- NEEDS_MORE_INFO if: the proposal has merit but lacks detail"""

    ok, response = ask_openrouter(prompt, system)
    if not ok:
        return {
            "status": "ERROR", "reason": response,
            "worker": worker, "action": action, "when": _now(),
        }

    # parse the decision
    decision = "NEEDS_MORE_INFO"
    reason = response[:300]
    if response.strip().startswith("APPROVE"):
        decision = "APPROVE"
    elif response.strip().startswith("REJECT"):
        decision = "REJECT"
    # extract reason after the colon
    if ":" in response:
        reason = response.split(":", 1)[1].strip()[:300]

    return {
        "status": decision, "reason": reason,
        "worker": worker, "action": action,
        "description": description[:200], "when": _now(),
        "evaluated_by": GATE_MODEL,
    }


def submit_proposal(worker: str, action: str, description: str,
                    code: str = "") -> dict:
    """Submit a proposal through the gate. This is the ONLY way agents
    can modify the system."""
    proposal = {
        "worker": worker, "action": action, "description": description[:300],
        "code": code[:2000] if code else "", "submitted": _now(),
    }
    # evaluate via OpenAmer brain
    evaluation = evaluate_proposal(worker, action, description, code)
    proposal["gate_status"] = evaluation["status"]
    proposal["gate_reason"] = evaluation["reason"]
    proposal["evaluated_at"] = evaluation["when"]
    proposal["evaluated_by"] = evaluation.get("evaluated_by", GATE_MODEL)

    # log everything
    log = _load(GATE_LOG, [])
    log.append(proposal)
    _save(GATE_LOG, log[-100:])  # keep last 100

    # if approved, queue for execution
    if evaluation["status"] == "APPROVE":
        queue = _load(GATE_QUEUE, [])
        queue.append(proposal)
        _save(GATE_QUEUE, queue)

    return proposal


def get_pending_approved() -> list[dict]:
    """Get all approved proposals that haven't been executed yet."""
    queue = _load(GATE_QUEUE, [])
    return [p for p in queue if p.get("gate_status") == "APPROVE"
            and not p.get("executed")]


def mark_executed(proposal: dict) -> None:
    proposal["executed"] = True
    proposal["executed_at"] = _now()
    queue = _load(GATE_QUEUE, [])
    _save(GATE_QUEUE, queue)


def gate_stats() -> dict:
    log = _load(GATE_LOG, [])
    if not log:
        return {"total": 0}
    approved = sum(1 for p in log if p.get("gate_status") == "APPROVE")
    rejected = sum(1 for p in log if p.get("gate_status") == "REJECT")
    needs_info = sum(1 for p in log if p.get("gate_status") == "NEEDS_MORE_INFO")
    return {
        "total": len(log), "approved": approved, "rejected": rejected,
        "needs_more_info": needs_info,
        "approval_rate": f"{approved / max(len(log), 1) * 100:.0f}%",
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--propose", nargs=3, metavar=("WORKER", "ACTION", "DESC"))
    ap.add_argument("--propose-code", nargs=4,
                    metavar=("WORKER", "ACTION", "DESC", "CODE_FILE"))
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--pending", action="store_true")
    args = ap.parse_args()
    if args.propose:
        result = submit_proposal(args.propose[0], args.propose[1],
                                 args.propose[2])
        print(json.dumps(result, indent=1))
    elif args.propose_code:
        code = Path(args.propose_code[3]).read_text("utf-8")[:2000]
        result = submit_proposal(args.propose_code[0], args.propose_code[1],
                                 args.propose_code[2], code)
        print(json.dumps(result, indent=1))
    elif args.status:
        print(json.dumps(gate_stats(), indent=1))
    elif args.pending:
        print(json.dumps(get_pending_approved(), indent=1))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
