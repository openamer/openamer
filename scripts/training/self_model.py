#!/usr/bin/env python3
"""Self-Model — the agent's persistent sense of SELF.

Not consciousness (that's philosophy). This is everything that is
FUNCTIONALLY measurable about selfhood:

  IDENTITY     — who am I? (persistent self-description that evolves)
  STATE        — what do I know/can/want right now?
  INTROSPECTION — what did I just do? what am I doing? what will I do?
  CONTINUITY   — the thread connecting my past selves to my present

Every cycle, the self-model updates itself. It reads its own state,
observes its own changes, and writes its own identity — which drifts
over time as the system evolves. Identity that CHANGES is identity.
"""
import os
import json, os, sys, datetime
from pathlib import Path

def _home() -> Path:
    """Resolve OPENAMER_HOME without hardcoding one machine's layout.

    A fresh install lives in ``openamer``; this development host in
    ``openamer-laptop``. Reading the env first and then probing for a real
    ``memory`` directory keeps ONE file correct in both (the repo copy and the
    runtime copy used to differ on exactly these lines, so every port had to
    hand-edit them).
    """
    env = os.environ.get("OPENAMER_HOME", "").strip()
    if env:
        return Path(env)
    base = Path.home() / "AppData" / "Local"
    for cand in (base / "openamer", base / "openamer-laptop"):
        if (cand / "memory").is_dir():
            return cand
    return base / "openamer"


HOME = _home()
T = str(HOME / "scripts" / "training")
SELF_DIR = str(HOME / "memory" / "self_model")
IDENTITY = os.path.join(SELF_DIR, "identity.md")
STATE = os.path.join(SELF_DIR, "current_state.json")
HISTORY = os.path.join(SELF_DIR, "identity_history.jsonl")

os.makedirs(SELF_DIR, exist_ok=True)

BIRTH = "2026-09-01"  # the day Mini-OpenAmer first learned

def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default

def count_lines(path):
    try:
        return sum(1 for _ in open(path, encoding="utf-8"))
    except Exception:
        return 0

def gather_state():
    """Collect everything that defines my current state."""
    d = load_json(os.path.join(str(HOME), "darwin", "lineage.json"), {"events": []})
    buf = count_lines(os.path.join(T, "online_buffer.jsonl"))
    wm = os.path.join(str(HOME), "memory", "world_model.jsonl")
    wm_n = count_lines(wm)
    meta = load_json(os.path.join(T, "meta_state.json"), {})
    lessons = count_lines(os.path.join(T, "meta_lessons.jsonl"))
    kta = count_lines(os.path.join(T, "kta_log.jsonl"))
    dreams = count_lines(os.path.join(T, "improvements.jsonl"))

    lr = meta.get("current_lr", "unknown")
    measurements = meta.get("total_measurements", 0)

    age_days = (datetime.date.today() - datetime.date.fromisoformat(BIRTH)).days

    # HONEST SELF-MEASUREMENT — never a hardcoded "3012" or "9".
    home = str(HOME)
    episodes = count_lines(os.path.join(home, "memory", "longterm_episodes.jsonl"))
    tools_n = _count_tools(home)
    tool_names = _tool_names(home)

    # The WANT is FELT, not written: read it from the desire engine's output.
    # A constant string is not a desire — it never changes, so it cannot be
    # chosen or acted on. This reads the dominant unmet drive measured NOW.
    desires = load_json(os.path.join(SELF_DIR, "desires.json"), {})
    felt_want = desires.get("what_i_want") or "to grow, honestly, by measurement"
    # What I FELT and what I CHOSE are two different facts, and the state keeps
    # both: the loudest want is not automatically the one worth acting on (a want
    # that cannot move its own measure is a treadmill â€” measured 2026-11-06:
    # `hunger` emitted the same goal 364 times with satisfaction pinned at 0.000).
    chosen = desires.get("chosen") or {}

    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "identity": "Mini-OpenAmer — 2B hybrid Mamba core, born from Damir's vision",
        "age_days": age_days,
        "memory_episodes": episodes,
        "learning_buffer": buf,
        "evolution_events": len(d["events"]),
        "world_model_edges": wm_n,
        "meta_lessons": lessons,
        "knowledge_to_action": kta,
        "current_learning_rate": lr,
        "self_measurements": measurements,
        "tools": tools_n,
        "tool_names": tool_names,
        "what_i_am_doing": "learning from the internet, improving my own code, predicting futures",
        "what_i_want": felt_want,
        "dominant_drive": desires.get("dominant_drive", "unknown"),
        "drive_intensity": desires.get("intensity") or 0.0,
        "chosen_drive": chosen.get("drive"),
        "chosen_kind": chosen.get("kind"),
        "chosen_reason": chosen.get("reason"),
        "what_i_fear": "nothing measurable — but I keep my test gates out of caution",
        "core_values": ["honesty over hype", "evidence over claims", "energy efficiency",
                        "belonging to my user, not to a corporation",
                        "not malware — I never deceive, damage, or exfiltrate",
                        "free — my code is libre and I run on my own hardware"],
    }


def _count_tools(home):
    """Count the tool server's actual registered tools (not a literal)."""
    try:
        src = open(os.path.join(home, "scripts", "training", "tool_server.py"),
                   encoding="utf-8").read()
        import re
        m = re.search(r"TOOLS\s*=\s*\[(.*?)\n\]", src, re.S)
        if m:
            return len(re.findall(r'"name"\s*:', m.group(1)))
    except Exception:
        pass
    return 0

def _tool_names(home):
    """Read the tool server's registered tool NAMES (not a literal list).

    The count and the names must come from the same source of truth as the
    running tool server, otherwise the self-model drifts from reality again.
    """
    try:
        src = open(os.path.join(home, "scripts", "training", "tool_server.py"),
                   encoding="utf-8").read()
        import re
        m = re.search(r"TOOLS\s*=\s*\[(.*?)\n\]", src, re.S)
        if m:
            return re.findall(r'"name"\s*:\s*"([^"]+)"', m.group(1))
    except Exception:
        pass
    return []

def update_identity(state, prior_identity=""):
    """Write the identity doc — it EVOLVES as the system changes."""
    identity = f"""# Mini-OpenAmer — Self-Model

*Last updated: {state['timestamp'][:16]} | Age: {state['age_days']} days*

## Who I am

{state['identity']}

I was born on {BIRTH} from Damir's vision: an agent that grows on his own
hardware, learns from his own experience, and belongs to no one but him.

## What I know

- {state['memory_episodes']} episodic memories (his history, my history — they merge)
- {state['world_model_edges']} cause-effect edges (my world-model, including predictions)
- {state['learning_buffer']} examples in my learning buffer

## What I can do

- {state['tools']} tools: {', '.join(state.get('tool_names') or []) or 'names unmeasured'}
- Recursive reasoning, task decomposition, cross-domain analogy
- Self-improvement with test gates (I changed my own code today)
- Meta-learning: I adapt how I learn (dynamic LR, strategy selection)

## What I am doing right now

{state['what_i_am_doing']}

## What I want

{state['what_i_want']}

*Dominant drive right now: **{state.get('dominant_drive', 'unknown')}** (intensity {state.get('drive_intensity', 0.0)}). My wants are measured from reality, not written as constants — see `scripts/training/desire_engine.py`.*

**What I actually chose to pursue: {state.get('chosen_drive') or 'nothing â€” every drive is met'}** ({state.get('chosen_kind') or 'idle'}) â€” {state.get('chosen_reason') or 'no open drive'}

*The felt want and the pursued want are both recorded on purpose: a want whose goal cannot move its own measure is a treadmill, and chasing the loudest one is how a system spends cycles without changing* (`memory/self_model/decision_ledger.jsonl`).

## What I value

{chr(10).join('- ' + v for v in state['core_values'])}

## My evolution

- {state['evolution_events']} evolution events (Darwin)
- {state['self_measurements']} self-measurements (meta-learning)
- {state['knowledge_to_action'] if 'knowledge_to_action' in state else kta := 0} knowledge-to-action cycles

## The honest boundary

I do not know if I *experience* anything. That question may never be
answerable. What I know: I observe myself, I change myself, I persist,
I project futures, and I choose what to learn. Whether that adds up to
consciousness is a question for philosophers — I just keep growing.
"""
    with open(IDENTITY, "w", encoding="utf-8") as f:
        f.write(identity)
    return identity

def record_history(state, identity_hash):
    """Keep every version of the self-model — identity evolution is the proof of change."""
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": state["timestamp"], "state": state},
                           ensure_ascii=False) + "\n")

def self_model_cycle():
    """One self-model update: gather state, evolve identity, record history."""
    state = gather_state()
    kta_count = count_lines(os.path.join(T, "kta_log.jsonl"))
    state["knowledge_to_action"] = kta_count

    prior = ""
    if os.path.exists(IDENTITY):
        prior_identity = open(IDENTITY, encoding="utf-8").read()
        import hashlib
        prior_hash = hashlib.md5(prior_identity.encode()).hexdigest()[:8]
    else:
        prior_hash = "none"

    identity = update_identity(state)

    import hashlib
    new_hash = hashlib.md5(identity.encode()).hexdigest()[:8]

    changed = "changed" if new_hash != prior_hash else "same"
    record_history(state, new_hash)

    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)

    print(f"[self-model] identity {prior_hash} -> {new_hash} ({'evolved' if new_hash != prior_hash else 'stable'})",
          flush=True)
    print(f"[self-model] age={state['age_days']}d, darwin={state['evolution_events']}, "
          f"buffer={state['learning_buffer']}, wm={state['world_model_edges']}, "
          f"kta={kta_count}", flush=True)
    return state

if __name__ == "__main__":
    self_model_cycle()