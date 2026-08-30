#!/usr/bin/env python3
"""
Swarm Communication (Phase 30) - workers talk to each other.

Workers exchange messages through a shared message board (file-based).
Each worker can:
  - SEND a message to another worker (or broadcast to all)
  - RECEIVE messages addressed to it
  - USE LLM to interpret messages and formulate responses

Message types:
  - ALERT: "I found a gap/weakness"
  - REQUEST: "I need help with X"
  - INSIGHT: "I learned something"
  - COORDINATE: "Let's work together on Y"

Storage: ~/AppData/Local/openamer-laptop/darwin/messages.json
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(_spec)
sys.modules["darwin_engine"] = darwin
_spec.loader.exec_module(darwin)

HOME = Path.home() / "AppData" / "Local" / "openamer-laptop"
MESSAGES_FILE = HOME / "darwin" / "messages.json"

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma3:4b"


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


def load_messages() -> list[dict]:
    return _load(MESSAGES_FILE, [])


def save_messages(msgs: list[dict]) -> None:
    _save(MESSAGES_FILE, msgs[-200:])  # keep last 200


def send_message(sender: str, recipient: str, msg_type: str,
                 content: str) -> dict:
    """Send a message. recipient='*' means broadcast to all."""
    msgs = load_messages()
    msg = {
        "id": len(msgs), "sender": sender, "recipient": recipient,
        "type": msg_type, "content": content[:500], "sent": _now(),
        "read": False,
    }
    msgs.append(msg)
    save_messages(msgs)
    return msg


def receive_messages(worker_name: str, mark_read: bool = True) -> list[dict]:
    """Get all unread messages addressed to this worker (or broadcast).
    Read tracking is per-recipient: broadcast messages are only marked
    read for THIS worker, not for others."""
    msgs = load_messages()
    received = []
    changed = False
    for m in msgs:
        if (m.get("recipient") in (worker_name, "*")
                and m.get("sender") != worker_name
                and worker_name not in m.get("read_by", [])):
            received.append(m)
            if mark_read:
                m.setdefault("read_by", []).append(worker_name)
                changed = True
    if changed:
        save_messages(msgs)
    return received


def llm_respond(sender: str, message: dict, identity: dict,
                context: dict) -> str:
    """Use Ollama to formulate a response to a received message."""
    name = identity.get("name", "Worker")
    personality = ", ".join(identity.get("personality", []))
    msg_type = message.get("type", "INFO")
    content = message.get("content", "")[:200]
    sender_name = message.get("sender", "unknown")
    gaps = [g["type"] for g in context.get("gaps", [])]
    pop = context.get("stats", {}).get("population", "?")

    prompt = f"""You are {name}, {personality}. You feel {identity.get('mood', 'neutral')}.

Ecosystem: {pop} skills. Gaps: {', '.join(gaps) if gaps else 'none'}.

{sender_name} sent you a {msg_type} message:
"{content}"

Respond in character as {name}. Be brief (1-2 sentences). Either:
- AGREE and offer help
- DISAGREE and explain why
- ASK a question back

Response:"""

    body = json.dumps({
        "model": "gemma3:4b", "prompt": prompt, "stream": False,
        "options": {"temperature": 0.8, "num_predict": 80},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        return resp.get("response", "").strip()[:300]
    except Exception as e:
        return f"[could not respond: {e}]"


def swarm_conversation(organisms: list[dict], ecosystem_state: dict,
                       max_exchanges: int = 3) -> list[dict]:
    """Run a conversation round: workers share discoveries and respond.

    1. Each worker with unread messages responds via LLM
    2. Workers broadcast new insights from the latest introspection
    3. All exchanges are logged in the chronicle
    """
    results = []

    # Step 1: broadcast insights from gaps
    gaps = ecosystem_state.get("gaps", [])
    if gaps:
        for gap in gaps[:2]:
            gtype = gap.get("type", "unknown")
            sender = "darwin-core"  # the core broadcasts alerts
            msg = send_message(sender, "*",
                               "ALERT",
                               f"Gap detected: {gtype}. "
                               f"Directive: {gap.get('directive', 'investigate')}")

    # Step 2: workers read and respond to their messages via LLM
    for o in organisms:
        if o.get("type") != "worker" or not o.get("identity"):
            continue
        ident = o["identity"]
        name = ident.get("name", o["id"])
        unread = receive_messages(name, mark_read=True)
        if not unread:
            continue
        for msg in unread[:2]:  # respond to max 2 messages per worker
            response = llm_respond(name, msg, ident, ecosystem_state)
            # send response back to sender (or broadcast)
            target = msg.get("sender", "*")
            send_message(name, target, "RESPONSE", response)
            results.append({
                "from": name, "to": target, "type": "RESPONSE",
                "content": response,
                "responding_to": msg.get("type", "?"),
            })

    return results


def generate_communication_tasks(results: list[dict]) -> list[str]:
    """After a conversation, generate tasks from coordination agreements."""
    task_ids = []
    for r in results:
        content = r.get("content", "").lower()
        if any(w in content for w in ("help", "mutate", "i will", "let me")):
            # the worker agreed to do something - create a real task
            from swarm_os import submit_task
            capabilities = ["evolution"]  # default
            tid = submit_task(f"COORDINATED[{r.get('from', '?')}]: "
                              f"respond to {r.get('responding_to', '?')}: "
                              f"{r.get('content', '')[:100]}",
                              capabilities)
            task_ids.append(tid)
    return task_ids


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", nargs=3, metavar=("FROM", "TO", "CONTENT"))
    ap.add_argument("--broadcast", nargs=2, metavar=("FROM", "CONTENT"))
    ap.add_argument("--read", metavar="WORKER")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--conversation", action="store_true")
    args = ap.parse_args()
    if args.send:
        m = send_message(args.send[0], args.send[1], "INFO", args.send[2])
        print(json.dumps(m, indent=1))
    elif args.broadcast:
        m = send_message(args.broadcast[0], "*", "ALERT", args.broadcast[1])
        print(json.dumps(m, indent=1))
    elif args.read:
        msgs = receive_messages(args.read)
        print(json.dumps(msgs, indent=1))
    elif args.list:
        print(json.dumps(load_messages()[-10:], indent=1))
    elif args.conversation:
        print(json.dumps(swarm_conversation([], {}), indent=1))
    else:
        ap.print_help()
