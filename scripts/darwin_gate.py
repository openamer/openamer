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
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

# Markers only a real OpenAmer home carries. Darwin never creates these, so they
# separate a genuine install from a scratch directory that merely exists -- e.g.
# a stray ``OPENAMER_HOME=/c/tmp/oa-home``, which made the swarm loop resolve an
# empty population and report "0 tasks, everything clean" (observed 2026-09-19).
_HOME_MARKERS = ("config.yaml", ".env", "cron", "memories", "openamer-agent")


def _is_install_root(pth: Path) -> bool:
    """True when *pth* looks like a real OpenAmer home, not a scratch dir."""
    try:
        return any((pth / m).exists() for m in _HOME_MARKERS)
    except OSError:
        return False


def _resolve_openamer_home(default: Path) -> Path:
    """Resolve OPENAMER_HOME robustly across shells (single source: darwin_engine.py).

    git-bash exports OPENAMER_HOME as an MSYS path ("/c/Users/..."). Native
    Windows Python treats that as relative and lands in a phantom "C:/c/..."
    tree, so the swarm would operate on a directory that is not the install.
    Normalise MSYS drive forms and reject doubled-drive artefacts.

    Prefer an installed candidate that actually carries a ``skills`` dir: on this
    host "openamer-laptop" is the real install while plain "openamer" is only a
    near-empty upstream default. Choosing the bare default made every sibling
    script resolve a DIFFERENT home than darwin_engine -- observed live
    2026-09-22, when the autonomous loop reported "0 tasks, everything clean"
    while writing its swarm into C:/Users/damir/AppData/Local/openamer (27 skills)
    instead of the real home (183 skills). A mis-set OPENAMER_HOME pointing at a
    scratch dir is likewise rejected via the install-root markers.
    """
    local = default.parent
    candidates = [local / "openamer-laptop", local / "openamer"]
    picked = next((c for c in candidates if (c / "skills").is_dir()), default)

    raw = os.environ.get("OPENAMER_HOME")
    if not raw:
        return picked
    norm = raw.replace(os.sep, "/") if os.sep != "/" else raw
    cand = None
    if len(norm) >= 3 and norm[0] == "/" and norm[1].isalpha() and norm[2] == "/":
        cand = Path(norm[1].upper() + ":/" + norm[3:])
    else:
        p = Path(raw)
        if p.is_absolute():
            cand = p
    if cand is None or not cand.exists():
        return picked
    parts = cand.parts
    drive = parts[0].rstrip("/").rstrip(os.sep)
    if len(drive) == 2 and drive[1] == ":" and len(parts) >= 2:
        head = parts[1].strip("/").strip(os.sep).lower()
        if head and head == drive[0].lower():
            return picked
    if _is_install_root(cand):
        return cand
    print(f"[home] WARNING: OPENAMER_HOME={cand} exists but is not an OpenAmer "
          f"install root; falling back to {picked}.", file=sys.stderr)
    return picked

HOME = _resolve_openamer_home(Path.home() / "AppData" / "Local" / "openamer")
GATE_LOG = HOME / "darwin" / "gate-log.json"
GATE_QUEUE = HOME / "darwin" / "gate-queue.json"

# OpenRouter credentials (from .env / config)
from dotenv import load_dotenv




load_dotenv(HOME / ".env")

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENAMER_MODEL", "z-ai/glm-4.6")
# fallback to strong model for gate decisions
GATE_MODEL = "z-ai/glm-5.3-flash"  # OpenAmer default brain


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
    """Ask OpenAmer's brain (GLM-5.3-Flash) for a decision."""
    if not OPENROUTER_KEY:
        return False, "no API key"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": GATE_MODEL,
        "messages": messages,
        "max_tokens": 2000,  # reasoning model: deliberation + verdict must fit
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
        # Reasoning model (GLM): `content` may be empty and the verdict lives
        # in the reasoning trace. Hand the FULL tail to the parser -- picking a
        # single "matching" line here is what made every proposal stall: the
        # criteria text itself contains the words APPROVE/REJECT/NEEDS_MORE_INFO,
        # so a first-match scan returns a quote of the rubric, not a decision.
        reasoning = msg.get("reasoning", "")
        if reasoning:
            return True, reasoning[-2000:]
        return False, "empty response from model"
    except Exception as e:
        return False, str(e)[:300]


VERDICTS = ("APPROVE", "REJECT", "NEEDS_MORE_INFO")


def _parse_verdict(text: str) -> tuple[str, str]:
    """Extract the gate's verdict from a model reply.

    Reasoning models narrate their way to an answer, and the system prompt
    itself spells out the words APPROVE / REJECT / NEEDS_MORE_INFO as rubric
    labels. So we cannot take the first keyword we see -- that is almost
    always the model quoting the rubric back at us.

    Order of preference:
      1. an explicit `DECISION: X` anchor line (the strongest signal)
      2. a verdict line *starting* with the keyword, scanning from the END
         (the model's final answer is at the bottom, not the top)
      3. conservative fallback: NEEDS_MORE_INFO
    """
    if not text:
        return "NEEDS_MORE_INFO", "empty model response"

    lines = text.splitlines()

    # 1) explicit anchor, last one wins
    for line in reversed(lines):
        stripped = line.strip().lstrip("*-• ").strip()
        upper = stripped.upper()
        if upper.startswith("DECISION:"):
            rest = stripped.split(":", 1)[1].strip().strip("*` ")
            for v in VERDICTS:
                if rest.upper().startswith(v):
                    return v, _reason_from(rest, v) or "explicit decision anchor"
    # anchor may also appear inline in a wall of reasoning text
    lower_text = text.upper()
    if "DECISION:" in lower_text:
        tail = text[lower_text.rindex("DECISION:") + len("DECISION:"):]
        tail = tail.strip().strip("*` ")
        for v in VERDICTS:
            if tail.upper().startswith(v):
                return v, _reason_from(tail, v) or "explicit decision anchor"

    # 2) a line that *starts* with a verdict word, scanning from the end
    for line in reversed(lines):
        stripped = line.strip().lstrip("*-•> ").strip()
        upper = stripped.upper()
        for v in VERDICTS:
            if upper.startswith(v + ":") or upper.startswith(v + " ")                     or upper == v:
                return v, _reason_from(stripped, v) or f"verdict line: {v}"

    # 3) conservative fallback -- unchanged safety posture
    return "NEEDS_MORE_INFO", (text.strip()[:300] or "no parseable verdict")


def _reason_from(text: str, verdict: str) -> str:
    """Pull the human-readable reason that follows a verdict word."""
    rest = text.strip()
    upper = rest.upper()
    if upper.startswith(verdict):
        rest = rest[len(verdict):].lstrip(" :*-`").strip()
    rest = rest.strip("*` ").strip()
    return rest[:300]


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

Do not quote these option names while deliberating -- just decide. End your
response with a final line in exactly this form:
DECISION: APPROVE|REJECT|NEEDS_MORE_INFO

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
    decision, reason = _parse_verdict(response)

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
