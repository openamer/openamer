#!/usr/bin/env python3
"""
LLM Worker Agents (Phase 28) - swarm workers become real LLM agents
powered by local Ollama (zero cost, zero latency to cloud).

Each worker has:
  - A personality (from darwin_identity.py)
  - An LLM conversation (Ollama) where it makes REAL decisions
  - Its own evolutionary actions (mutate, predate, migrate, challenge)
  - Memory of past decisions

The LLM decides WHICH action to take based on ecosystem state.
No hardcoded if/else - the worker thinks and acts.
"""
from __future__ import annotations
import os

import os
import importlib.util
import json
import subprocess
import sys
import urllib.request
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
    """Resolve OPENAMER_HOME robustly across shells (see darwin_engine.py).

    git-bash exports OPENAMER_HOME as an MSYS path ("/c/Users/..."). Native
    Windows Python treats that as relative and lands in a phantom "C:/c/..."
    tree. Normalise MSYS drive forms and reject doubled-drive artefacts so the
    script never silently operates on a directory that isn't the real install.
    """
    raw = os.environ.get("OPENAMER_HOME")
    if not raw:
        return default
    norm = raw.replace(os.sep, "/") if os.sep != "/" else raw
    cand = None
    if len(norm) >= 3 and norm[0] == "/" and norm[1].isalpha() and norm[2] == "/":
        cand = Path(norm[1].upper() + ":/" + norm[3:])
    else:
        p = Path(raw)
        if p.is_absolute():
            cand = p
    if cand is None:
        return default
    parts = cand.parts
    drive = parts[0].rstrip("/").rstrip(os.sep)
    if len(drive) == 2 and drive[1] == ":" and len(parts) >= 2:
        head = parts[1].strip("/").strip(os.sep).lower()
        if head and head == drive[0].lower():
            return default
    if cand is None or not cand.exists():
        return default
    # An existing directory is not enough: a scratch dir adopted as the install
    # silently evolves an empty population while the real home is untouched.
    if _is_install_root(cand):
        return cand
    print(f"[home] WARNING: OPENAMER_HOME={cand} exists but is not an OpenAmer "
          f"install root; falling back to {default}.", file=sys.stderr)
    return default


HOME = _resolve_openamer_home(Path.home() / "AppData" / "Local" / "openamer")

import importlib.util as _ilu




_spec = _ilu.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(_spec)
sys.modules["darwin_engine"] = darwin
_spec.loader.exec_module(darwin)
AGENT_LOG = HOME / "darwin" / "agent-log.json"

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma3:4b"  # fast, local, free
FALLBACK_MODEL = "qwen3.5:2b"


def _load(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")


def ollama_think(model: str, prompt: str, timeout: int = 60) -> str:
    """Call local Ollama for LLM reasoning. Returns the response text."""
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.7, "num_predict": 200},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read())
        return resp.get("response", "").strip()
    except Exception as e:
        return f"[ollama error: {e}]"


def build_system_prompt(identity: dict, ecosystem_state: dict) -> str:
    """Each worker gets its personality + ecosystem snapshot as context."""
    name = identity.get("name", "Unknown")
    traits = ", ".join(identity.get("personality", []))
    mood = identity.get("mood", "neutral")
    bio = identity.get("bio", "")
    st = ecosystem_state.get("stats", {})
    gaps = [g["type"] for g in ecosystem_state.get("gaps", [])]
    return f"""You are {name}, {traits}. You feel {mood}.
{bio}

Current ecosystem state:
- Population: {st.get('population', '?')} skills
- Gaps detected: {', '.join(gaps) if gaps else 'none'}

Available actions you can order:
1. MUTATE - create a new skill variant
2. PREDATE - consume a redundant skill
3. CHALLENGE - duel a foreign skill on the grid
4. EXPLORE - scan the ecosystem for new information
5. REST - do nothing, conserve energy

Reply with ONLY the action name (MUTATE, PREDATE, CHALLENGE, EXPLORE, or REST)
and a one-sentence reason. Format: ACTION: reason"""


def decide_action(identity: dict, ecosystem_state: dict,
                  model: str = DEFAULT_MODEL) -> dict:
    """The worker THINKS about what to do using its LLM personality."""
    system = build_system_prompt(identity, ecosystem_state)
    prompt = f"{system}\n\nWhat do you do now, {identity.get('first_name', 'worker')}?"
    response = ollama_think(model, prompt)
    # parse the action from the response
    action = "REST"  # default
    for act in ("MUTATE", "PREDATE", "CHALLENGE", "EXPLORE", "REST"):
        if act in response.upper():
            action = act
            break
    # extract reason (text after the colon)
    reason = ""
    for line in response.split("\n"):
        if act in line.upper() and ":" in line:
            reason = line.split(":", 1)[1].strip()[:200]
            break
    if not reason:
        reason = response[:150]
    return {"agent": identity.get("name", "?"), "action": action,
            "reason": reason, "raw_response": response[:300]}


def execute_action(agent_name: str, action: str) -> dict:
    """Actually execute the chosen action on the real system."""
    cmds = {
        "MUTATE": [sys.executable, str(REPO / "scripts" / "darwin_engine.py"),
                   "--autopilot"],
        "PREDATE": [sys.executable, str(REPO / "scripts" / "darwin_engine.py"),
                    "--predate"],
        "CHALLENGE": [sys.executable,
                      str(REPO / "scripts" / "darwin_grid_github.py"),
                      "--duel", "damir-desktop"],
        "EXPLORE": [sys.executable,
                    str(REPO / "scripts" / "darwin_metacognition.py"),
                    "--introspect"],
        "REST": None,
    }
    cmd = cmds.get(action)
    if cmd is None:
        return {"action": action, "executed": False, "result": "rested"}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=110, cwd=str(REPO))
        success = r.returncode in (0, 2)
        return {"action": action, "executed": True, "success": success,
                "output": (r.stdout or r.stderr)[-200:]}
    except subprocess.TimeoutExpired:
        return {"action": action, "executed": True, "success": False,
                "output": "timeout"}
    except Exception as e:
        return {"action": action, "executed": False, "output": str(e)[:200]}


def run_agent_turn(identity: dict, ecosystem_state: dict) -> dict:
    """One complete agent turn: think → decide → execute → log."""
    decision = decide_action(identity, ecosystem_state)
    execution = execute_action(decision["agent"], decision["action"])
    result = {**decision, **execution, "when": _now_iso()}
    # log for the chronicle
    log = _load(AGENT_LOG, [])
    log.append(result)
    _save(AGENT_LOG, log[-50:])
    return result


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def run_swarm_turn(organisms: list[dict], ecosystem_state: dict,
                   max_agents: int = 3) -> list[dict]:
    """Run one LLM turn for up to max_agents workers (not all - cost time)."""
    workers = [o for o in organisms if o.get("type") == "worker"]
    workers.sort(key=lambda w: w.get("energy", 0), reverse=True)
    results = []
    for w in workers[:max_agents]:
        ident = w.get("identity")
        if not ident:
            continue
        r = run_agent_turn(ident, ecosystem_state)
        results.append(r)
    return results


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--think", metavar="SKILL_NAME",
                    help="one agent turn for a specific worker")
    ap.add_argument("--swarm", action="store_true",
                    help="run a turn for the top workers")
    args = ap.parse_args()
    if args.think:
        # get identity for this skill
        spec = importlib.util.spec_from_file_location(
            "darwin_identity", REPO / "scripts" / "darwin_identity.py")
        di = importlib.util.module_from_spec(spec)
        sys.modules["darwin_identity"] = di
        spec.loader.exec_module(di)
        ident = di.identity_for(args.think, "worker", fitness=30, energy=50)
        # get ecosystem state
        fitness = _load(darwin.FITNESS_FILE, {}).get("skills", {})
        st = {"stats": {"population": len(fitness)}, "gaps": []}
        result = run_agent_turn(ident, st)
        print(json.dumps(result, indent=1))
    elif args.swarm:
        # get world state from dashboard API
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:8910/api/world", timeout=10) as r:
                world = json.loads(r.read())
            results = run_swarm_turn(world["organisms"],
                                     {"stats": world["stats"], "gaps": []})
            print(json.dumps(results, indent=1))
        except Exception as e:
            print(f"error: {e}")
    else:
        ap.print_help()
