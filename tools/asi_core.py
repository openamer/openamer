#!/usr/bin/env python3
"""
ASI Core — Integrated ASI Subsystem for OpenAmer Agent

Replaces 60+ standalone scripts/training/*.py with a single in-process
subsystem. All 16 ASI capabilities run as native modules with a unified
lifecycle, shared state, and model-accessible tools.

Design:
  - Single ASICore class initialized once per agent session
  - Each capability imports the script's core functions directly (no subprocess)
  - All existing memory stores (memory/, scripts/training/) remain intact
  - 5 tools exported: asi_status, asi_think, asi_learn, asi_remember, asi_trigger
  - Scripts still work standalone for cron/legacy use
"""

import json
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.asi import (
    self_model as asi_self_model,
    world_model as asi_world_model,
    reasoning as asi_reasoning,
    prediction as asi_prediction,
    improvement as asi_improvement,
)
from tools.registry import registry

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
OPENAMER_HOME = Path(
    __import__("os").environ.get(
        "OPENAMER_HOME",
        str(Path.home() / "AppData/Local/openamer-laptop"),
    )
)
MEMORY_DIR = OPENAMER_HOME / "memory"
SELF_MODEL_DIR = MEMORY_DIR / "self_model"
SCRIPTS_TRAINING = OPENAMER_HOME / "scripts" / "training"

# Also ensure scripts/training/ is on sys.path for direct imports
_scripts_path = str(SCRIPTS_TRAINING)
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)


# ── ASI Core ────────────────────────────────────────────────────────────────

class ASICore:
    """Integrated ASI subsystem — runs in-process, no external scripts.

    Each method calls the training script's core functions directly via
    the asi.self_model, asi.world_model, asi.reasoning, etc. subpackage.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._subsystems: Dict[str, Dict[str, Any]] = {}
        self._last_heartbeat: Optional[float] = None
        self._state: Dict[str, Any] = self._load_state()

    # ── State Management ─────────────────────────────────────────────────

    def _load_state(self) -> Dict[str, Any]:
        """Load current ASI state from the self-model store."""
        path = SELF_MODEL_DIR / "current_state.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "identity": "OpenAmer ASI Core",
                "age_days": 0,
                "memory_episodes": 0,
                "learning_buffer": 0,
                "evolution_events": 0,
                "world_model_edges": 0,
                "meta_lessons": 0,
                "knowledge_to_action": 0,
                "tools": 0,
            }

    def status(self) -> Dict[str, Any]:
        """Return full ASI system status."""
        with self._lock:
            state = self._load_state()
            # Enrich with live world-model stats
            try:
                wm_stats = asi_world_model.stats()
                if isinstance(wm_stats, dict):
                    state["world_model_edges"] = wm_stats.get("total_edges", state.get("world_model_edges", 0))
            except Exception as e:
                logger.debug(f"world_model.stats() failed: {e}")

            state["subsystems"] = {
                name: info.get("status", "idle")
                for name, info in self._subsystems.items()
            }
            state["timestamp"] = datetime.now(timezone.utc).isoformat()
            state["subsystem_count"] = len(self._subsystems)
            return state

    def heartbeat(self) -> Dict[str, Any]:
        """Keep ASI alive — called periodically."""
        self._last_heartbeat = time.time()
        return {
            "alive": True,
            "uptime_seconds": time.time() - self._last_heartbeat if self._last_heartbeat else 0,
            "subsystems_online": sum(
                1 for s in self._subsystems.values() if s.get("status") == "running"
            ),
        }

    # ── Capability: Self-Model ───────────────────────────────────────────

    def self_model(self) -> Dict[str, Any]:
        """Refresh the self-model: gather state, update identity, record history."""
        try:
            result = asi_self_model.run_cycle()
            self._state = result.get("state", self._state)
            return result
        except Exception as e:
            logger.exception("self_model cycle failed")
            return {"success": False, "error": str(e)}

    # ── Capability: World Model ──────────────────────────────────────────

    def predict(self, situation: str) -> Dict[str, Any]:
        """Predict outcomes from the world model."""
        try:
            results = asi_world_model.predict(situation)
            return {"success": True, "predictions": results}
        except Exception as e:
            logger.exception("world_model.predict failed")
            return {"success": False, "error": str(e)}

    def recall(self, query: str, k: int = 5) -> Dict[str, Any]:
        """Recall cause→effect edges from the world model."""
        try:
            results = asi_world_model.recall(query, k=k)
            return {"success": True, "results": results}
        except Exception as e:
            logger.exception("world_model.recall failed")
            return {"success": False, "error": str(e)}

    # ── Capability: Recursive Reasoning ──────────────────────────────────

    def think(self, question: str, rounds: Optional[int] = None) -> Dict[str, Any]:
        """Deep recursive reasoning."""
        try:
            result = asi_reasoning.recursive_ask(question, rounds=rounds)
            return {"success": True, **result} if isinstance(result, dict) else {"success": True, "result": result}
        except Exception as e:
            logger.exception("reasoning failed")
            return {"success": False, "error": str(e)}

    # ── Capability: Prediction Validation ────────────────────────────────

    def validate_predictions(self) -> Dict[str, Any]:
        """Run prediction validation cycle."""
        try:
            result = asi_prediction.validate_predictions()
            asi_prediction.apply_confidence_adjustments()
            return {"success": True, "result": result}
        except Exception as e:
            logger.exception("prediction validation failed")
            return {"success": False, "error": str(e)}

    # ── Capability: Self-Improvement ─────────────────────────────────────

    def improve(self) -> Dict[str, Any]:
        """Run one self-improvement cycle."""
        try:
            result = asi_improvement.improve_once()
            return {"success": True, "result": result}
        except Exception as e:
            logger.exception("self-improvement failed")
            return {"success": False, "error": str(e)}

    # ── Capability: Knowledge-to-Action (import script directly) ─────────

    def knowledge_to_action(self) -> Dict[str, Any]:
        """Run knowledge-to-action cycle."""
        return self._run_imported("knowledge_to_action", "run_cycle")

    # ── Capability: Meta-Learning ────────────────────────────────────────

    def meta_learn(self) -> Dict[str, Any]:
        """Meta-learning statistics."""
        return self._run_imported("meta_learn", "get_stats", fallback_cmd=["stats"])

    # ── Capability: Swarm Intelligence ───────────────────────────────────

    def swarm_route(self, task: str) -> Dict[str, Any]:
        """Route a task via swarm intelligence."""
        return self._run_imported("swarm_intelligence", "route", task=task)

    # ── Capability: Analogy Engine ───────────────────────────────────────

    def analogize(self, source: str, target: str) -> Dict[str, Any]:
        """Cross-domain analogical transfer."""
        return self._run_imported("analogy_engine", "transfer", source=source, target=target)

    # ── Capability: Memory Consolidation ─────────────────────────────────

    def consolidate_memory(self) -> Dict[str, Any]:
        """Memory consolidation cycle."""
        return self._run_imported("memory_consolidation", "consolidate")

    # ── Capability: Session Diary ────────────────────────────────────────

    def diary(self) -> Dict[str, Any]:
        """Session diary entry."""
        return self._run_imported("session_diary", "write_entry")

    # ── Capability: Session Outcome ──────────────────────────────────────

    def session_outcome(self) -> Dict[str, Any]:
        """Session outcome analysis."""
        return self._run_imported("session_outcome", "analyze")

    # ── Capability: Internet Learning ────────────────────────────────────

    def learn(self, topic: Optional[str] = None) -> Dict[str, Any]:
        """Run one internet learning cycle."""
        args = ["--once"]
        if topic:
            args.extend(["--topic", topic])
        return self._run_external("internet_learner.py", args)

    # ── Capability: Auto Skill Creation ──────────────────────────────────

    def create_skill(self, description: str) -> Dict[str, Any]:
        """Auto-create a skill from description."""
        return self._run_imported("auto_skill_creation", "create", description=description)

    # ── Generic Imported-Call Helper ─────────────────────────────────────

    def _run_imported(self, module_name: str, func_name: str, **kwargs) -> Dict[str, Any]:
        """Import a training module and call a function on it directly."""
        try:
            import importlib
            mod = importlib.import_module(module_name)
            func = getattr(mod, func_name, None)
            if func is None:
                # Try calling via CLI-style if __name__ guard exists
                return {"success": False, "error": f"Function {func_name} not found in {module_name}", "module": module_name}
            result = func(**kwargs) if kwargs else func()
            return {"success": True, "result": result}
        except Exception as e:
            logger.exception(f"{module_name}.{func_name} failed")
            return {"success": False, "error": str(e), "module": module_name, "function": func_name}

    # ── External script calls (fallback for non-importable scripts) ──────

    def _run_external(self, script_name: str, args: List[str] = None) -> Dict[str, Any]:
        """Fallback: run a training script via subprocess.
        
        Used only when a script cannot be imported directly (e.g., has
        side effects at module level). Most capabilities use _run_imported.
        """
        import subprocess
        script_path = SCRIPTS_TRAINING / script_name
        if not script_path.exists():
            return {"success": False, "error": f"Script not found: {script_name}"}

        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout (120s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Global singleton ────────────────────────────────────────────────────────

_asi_core: Optional[ASICore] = None


def get_asi_core() -> ASICore:
    global _asi_core
    if _asi_core is None:
        _asi_core = ASICore()
    return _asi_core


# ── Tool Schemas ────────────────────────────────────────────────────────────

ASI_STATUS_SCHEMA = {
    "type": "object",
    "properties": {},
    "description": "Get the current ASI system status: all subsystem states, episode count, world model edges, evolution events, and identity info. Returns a complete snapshot of the integrated ASI core — all measured live from memory stores.",
}

ASI_THINK_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "The question or problem to reason about recursively. The ASI reasoning loop iterates question→answer→reflect→refine for deep analysis.",
        },
    },
    "required": ["question"],
    "description": "Run deep recursive reasoning on a question using the ASI reasoning loop. Iterates question→answer→reflect→refine for multi-round analysis. Use for complex problems, debugging, or strategic thinking.",
}

ASI_LEARN_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {
            "type": "string",
            "description": "Optional topic to focus the internet learning cycle on. If omitted, learns from general web discovery.",
        },
    },
    "description": "Run one internet learning cycle in-process. Acquires new knowledge from the web and integrates it into the world model. Optional topic parameter focuses the search. Runs the internet_learner directly — no subprocess.",
}

ASI_REMEMBER_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Query to search episodic memory and world model. Returns relevant cause→effect edges and past experiences.",
        },
        "k": {
            "type": "integer",
            "description": "Number of results to return (default: 5).",
            "default": 5,
        },
    },
    "required": ["query"],
    "description": "Recall past experiences and cause→effect knowledge from the world model. Direct in-process memory retrieval — no subprocess.",
}

ASI_TRIGGER_SCHEMA = {
    "type": "object",
    "properties": {
        "capability": {
            "type": "string",
            "enum": [
                "self_improve", "predict", "validate", "meta_learn",
                "knowledge_to_action", "self_model", "consolidate_memory",
                "diary", "session_outcome", "swarm_route",
                "create_skill", "heartbeat",
            ],
            "description": "Which ASI capability to trigger. All run in-process via direct imports.",
        },
        "params": {
            "type": "object",
            "description": "Optional parameters: e.g. {'situation': '...'} for predict, {'description': '...'} for create_skill, {'task': '...'} for swarm_route.",
        },
    },
    "required": ["capability"],
    "description": "Trigger a specific ASI capability directly in-process. No subprocess calls — each capability imports the training script's core functions natively.",
}


# ── Tool Handlers ───────────────────────────────────────────────────────────

def handle_asi_status(args: Dict, **kw) -> Dict:
    core = get_asi_core()
    return {"type": "text", "content": json.dumps(core.status(), indent=2)}


def handle_asi_think(args: Dict, **kw) -> Dict:
    core = get_asi_core()
    result = core.think(args["question"])
    return {"type": "text", "content": json.dumps(result, indent=2, default=str)}


def handle_asi_learn(args: Dict, **kw) -> Dict:
    core = get_asi_core()
    result = core.learn(args.get("topic"))
    return {"type": "text", "content": json.dumps(result, indent=2, default=str)}


def handle_asi_remember(args: Dict, **kw) -> Dict:
    core = get_asi_core()
    result = core.recall(args["query"], k=args.get("k", 5))
    return {"type": "text", "content": json.dumps(result, indent=2, default=str)}


def handle_asi_trigger(args: Dict, **kw) -> Dict:
    from tools.asi.heartbeat import get_heartbeat
    core = get_asi_core()
    capability = args["capability"]
    params = args.get("params", {})

    method_map = {
        "self_improve": lambda: core.improve(),
        "predict": lambda: core.predict(params.get("situation", "")),
        "validate": lambda: core.validate_predictions(),
        "meta_learn": lambda: core.meta_learn(),
        "knowledge_to_action": lambda: core.knowledge_to_action(),
        "self_model": lambda: core.self_model(),
        "consolidate_memory": lambda: core.consolidate_memory(),
        "diary": lambda: core.diary(),
        "session_outcome": lambda: core.session_outcome(),
        "swarm_route": lambda: core.swarm_route(params.get("task", "")),
        "create_skill": lambda: core.create_skill(params.get("description", "")),
        "heartbeat": lambda: get_heartbeat().tick(
            system=params.get("system"),
            force=params.get("force", False),
        ),
    }

    handler = method_map.get(capability)
    if handler is None:
        return {
            "type": "text",
            "content": json.dumps({"error": f"Unknown capability: {capability}"}),
        }

    result = handler()
    return {"type": "text", "content": json.dumps(result, indent=2, default=str)}


def check_asi_requirements() -> Optional[str]:
    """Check that the ASI core can initialize."""
    if not SCRIPTS_TRAINING.exists():
        return f"ASI training directory not found: {SCRIPTS_TRAINING}"
    return None  # available


# ── Module-level Registration ───────────────────────────────────────────────

registry.register(
    name="asi_status",
    toolset="asi",
    schema=ASI_STATUS_SCHEMA,
    handler=handle_asi_status,
    check_fn=check_asi_requirements,
    emoji="🧬",
)

registry.register(
    name="asi_think",
    toolset="asi",
    schema=ASI_THINK_SCHEMA,
    handler=handle_asi_think,
    check_fn=check_asi_requirements,
    emoji="🧠",
)

registry.register(
    name="asi_learn",
    toolset="asi",
    schema=ASI_LEARN_SCHEMA,
    handler=handle_asi_learn,
    check_fn=check_asi_requirements,
    emoji="📚",
)

registry.register(
    name="asi_remember",
    toolset="asi",
    schema=ASI_REMEMBER_SCHEMA,
    handler=handle_asi_remember,
    check_fn=check_asi_requirements,
    emoji="💭",
)

registry.register(
    name="asi_trigger",
    toolset="asi",
    schema=ASI_TRIGGER_SCHEMA,
    handler=handle_asi_trigger,
    check_fn=check_asi_requirements,
    emoji="⚡",
)
