"""
ASI Heartbeat — zentrales Subsystem, das alle 10 Subsystem-Pulse steuert.

Ersetzt 104 separate Cron-Jobs durch einen einzigen Herzschlag mit
10 Subsystem-Modulen. Jedes Subsystem hat seine eigene Kadenz und
wird in-process ausgeführt (Direktimport) mit subprocess-Fallback.

State: memory/asi_heartbeat.json (über Cron-Prozesse hinweg persistent)
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
OPENAMER_HOME = Path(
    os.environ.get(
        "OPENAMER_HOME",
        str(Path.home() / "AppData/Local/openamer-laptop"),
    )
)
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
SCRIPTS_TRAINING = OPENAMER_HOME / "scripts" / "training"
MEMORY_DIR = OPENAMER_HOME / "memory"
CRON_DIR = OPENAMER_HOME / "cron"

# Script path for cron scripts (in scripts/)  
_scripts_path = str(SCRIPTS_DIR)
if _scripts_path not in sys.path:
    sys.path.insert(0, _scripts_path)

_training_path = str(SCRIPTS_TRAINING)
if _training_path not in sys.path:
    sys.path.insert(0, _training_path)


# ── Subsystem Definition ────────────────────────────────────────────────────

class Subsystem:
    """A single ASI subsystem with its own cadence and execution."""

    def __init__(
        self,
        name: str,
        category: str,
        cadence_minutes: int,
        scripts: List[str],
        description: str = "",
        load_fn: Optional[str] = None,
        cron_ids: Optional[List[str]] = None,
    ):
        self.name = name
        self.category = category
        self.cadence_minutes = cadence_minutes
        self.scripts = scripts
        self.description = description
        self.load_fn = load_fn  # "module.function" for direct import
        self.cron_ids = cron_ids or []
        self.last_run: Optional[float] = None
        self.enabled = True
        self._state: Dict[str, Any] = {}

    def is_due(self, now: float, last_run: Optional[float]) -> bool:
        """Return True if this subsystem is due for a tick."""
        if last_run is None:
            return True  # never run
        return (now - last_run) >= (self.cadence_minutes * 60)

    def tick(self, force: bool = False) -> Dict[str, Any]:
        """Execute one tick of this subsystem in-process (direct import)."""
        results = []

        for script in self.scripts:
            try:
                result = self._run_script(script)
                results.append({
                    "script": script,
                    "success": result.get("success", False),
                    "output": result.get("stdout", "")[-200:] if isinstance(result.get("stdout"), str) else "",
                })
            except Exception as e:
                results.append({
                    "script": script,
                    "success": False,
                    "error": str(e),
                })

        return {
            "subsystem": self.name,
            "category": self.category,
            "results": results,
            "any_success": any(r.get("success") for r in results),
        }

    def _run_script(self, script_name: str) -> Dict[str, Any]:
        """Run a script — try native module first, then direct import, fallback to subprocess.

        Native modules (tools/asi/*.py) are preferred for A2A, Darwin, Swarm, etc.
        """
        # Native module routing (in-process, no subprocess)
        native_map = {
            "darwin-cron.py":              "tools.asi.darwin.autopilot",
            "darwin-autopatch-cron.py":    "tools.asi.darwin.autopatch",
            "darwin_publish.py":           "tools.asi.darwin.publish",
            "darwin_grid_github.py":       "tools.asi.darwin.grid_sync",
            "darwin-probe-cron.py":        "tools.asi.darwin.skill_probe",
            "training/swarm_intelligence.py": "tools.asi.swarm.cycle",
            "swarm_intelligence.py":       "tools.asi.swarm.route",
            "autonomous_loop.py":          "tools.asi.swarm.autonomous",
            "a2a_worker.py":               "tools.asi.a2a.run",
            "brain_collect.py":            "tools.asi.a2a.brain_collect",
        }

        native_path = native_map.get(script_name)
        if native_path:
            try:
                parts = native_path.split(".")
                mod_name = ".".join(parts[:-1])
                func_name = parts[-1]
                import importlib
                mod = importlib.import_module(mod_name)
                fn = getattr(mod, func_name, None)
                if fn:
                    result = fn()
                    return {"success": True, "stdout": str(result)[:500]}
            except Exception as e:
                logger.warning(f"Native module {native_path} failed: {e}, falling back")

        # Direct import fallback
        mod_name = script_name.replace(".py", "").replace("/", ".").replace("\\", ".")
        try:
            import importlib
            mod = importlib.import_module(mod_name)
            for fn_name in ("main", "run", "run_once", "tick"):
                fn = getattr(mod, fn_name, None)
                if fn is not None:
                    result = fn()
                    return {"success": True, "stdout": str(result)[:500] if result else "ok"}
        except Exception:
            pass

        # Subprocess fallback
        return self._run_subprocess(script_name)

    def _run_subprocess(self, script_name: str) -> Dict[str, Any]:
        """Run a script via subprocess."""
        candidates = [
            SCRIPTS_DIR / script_name,
            SCRIPTS_TRAINING / script_name,
            CRON_DIR / script_name,
            OPENAMER_HOME / script_name,
            Path(script_name),
        ]
        script_path = None
        for c in candidates:
            if c.exists():
                script_path = c
                break

        if script_path is None:
            return {"success": False, "error": f"Script not found: {script_name}"}

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True, text=True, timeout=120,
                env={**os.environ, "OPENAMER_HOME": str(OPENAMER_HOME)},
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[-500:] if result.stdout else "",
                "stderr": result.stderr[-200:] if result.stderr else "",
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout (120s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Heartbeat ────────────────────────────────────────────────────────────────

class Heartbeat:
    """Zentraler ASI-Herzschlag — tickt alle N Minuten, prüft alle Subsysteme."""

    STATE_FILE = MEMORY_DIR / "asi_heartbeat.json"

    def __init__(self):
        self.subsystems: Dict[str, Subsystem] = {}
        self._init_subsystems()
        self._load_state()

    def _init_subsystems(self):
        """Register all subsystems with their scripts and cadences."""
        # ── 1. Darwin (6 Jobs) ────────────────────────────────────────
        self.subsystems["darwin"] = Subsystem(
            name="darwin", category="darwin", cadence_minutes=15,
            description="Darwin Engine — evolutionäre Skill-Evolution",
            scripts=[
                "darwin-cron.py",        # AutoPilot (15m)
                "darwin-grid.py",          # Darwin Grid Sync (6h)
                "darwin-autopatch-cron.py",  # AutoPatch (daily)
                "darwin_publish.py",         # Publish (daily)
                "darwin-probe-cron.py",      # Skill-Probe (daily)
            ],
            cron_ids=["0c6eba12054d", "244c90058f07", "e6d653d611d7",
                      "d7d490258374", "c839342998f5"],
        )

        # ── 2. Swarm (5 Jobs) ─────────────────────────────────────────
        self.subsystems["swarm"] = Subsystem(
            name="swarm", category="swarm", cadence_minutes=30,
            description="Swarm Intelligence — Multi-Agent-Koordination",
            scripts=[
                "training/swarm_intelligence.py",  # Swarm Cycle (hourly)
                "autonomous_loop.py",               # Swarm OS Loop (30m)
            ],
            cron_ids=["21cd8fbb7a1a", "c1ab0f604f8d"],
        )

        # ── 3. A2A (1 Job) ────────────────────────────────────────────
        self.subsystems["a2a"] = Subsystem(
            name="a2a", category="a2a", cadence_minutes=240,
            description="Agent-to-Agent — Brain-Export & Peer-Kommunikation",
            scripts=[
                "brain_collect.py",
            ],
            cron_ids=["6b81f6f726da"],
        )

        # ── 4. Learning (9 Jobs) ──────────────────────────────────────
        self.subsystems["learning"] = Subsystem(
            name="learning", category="learning", cadence_minutes=5,
            description="Lern-Subsystem — Internet, Aktiv, Selbst-Modell",
            scripts=[
                "training/internet_learner.py",       # 5m
                "training/active_learn.py",            # 7m
                "training/knowledge_to_action.py",     # 30m
                "training/auto_skill_creation.py",     # 30m
                "training/self_model.py",              # hourly
                "training/predict_validate.py",        # 2h
                "training/session_outcome.py",         # 60m
                "learning-loop.py",                    # 60m
                "morning_brief.py",                    # 8h
            ],
            cron_ids=["91a6a02a6148", "31c5faaff6c2", "59537494492c",
                      "461d46fd24ab", "4bf2a814db7c", "f2f49bc80dbe",
                      "sessout984075", "learning_loop_60m", "morning-brief"],
        )

        # ── 5. Senses (5 Jobs) ────────────────────────────────────────
        self.subsystems["senses"] = Subsystem(
            name="senses", category="senses", cadence_minutes=30,
            description="Sinne & biologischer Rhythmus",
            scripts=[
                "circadian.py",           # 30m
                "senses.py",              # 30m
                "autonom_watchtower.py",  # 30m
                "trend_scout.py",         # 60m
                "self_evolve.py",         # 6h
            ],
            cron_ids=["d53013d60e14", "a53f24c07e03", "6d602cd72e74",
                      "93b0d21eb0fb", "1475a7e0d62c"],
        )

        # ── 6. System (15 Jobs) ────────────────────────────────────────
        self.subsystems["system"] = Subsystem(
            name="system", category="system", cadence_minutes=5,
            description="System-Health — Self-Healing, Ressourcen, Cache",
            scripts=[
                "self-healer.py",                 # 30m
                "cron-self-healer.py",            # sync
                "cron-resource-monitor.py",        # 5m
                "smart-cache.py --clean",          # 360m
                "service-watchdog.py",             # 5m
                "self-hosted-cron.py",             # 5m
                "cron-traffic-cop.py",             # 15m
                "notification-engine.py",          # 1m
                "identity-watchdog.py",            # daily
                "global-sync.py",                  # 60m
                "circadian.py",
            ],
            cron_ids=["self_healer_30m", "resource-monitor-alert",
                      "smart_cache_clean", "service-watchdog-4-ports",
                      "self-hosted-health-check", "traffic_cop_15m",
                      "notification_engine_daemon", "identity-refresh-watchdog",
                      "global-sync", "0b532e629b3b", "7c3d5648b06c"],
        )

        # ── 7. Security (5 Jobs) ───────────────────────────────────────
        self.subsystems["security"] = Subsystem(
            name="security", category="security", cadence_minutes=240,
            description="Sicherheit — CVE-Scan, Bugbot, Pen-Test",
            scripts=[
                "bugbot.py",                       # 240m
                "cron-security-cve-scan.py",         # 240m
                "cron-pen-tester.py",                # 240m
                "cron-auto-code-review.py",           # 60m
                "cron-skill-safety-scan.py",          # daily
            ],
            cron_ids=["62eeb6a84682", "ae6175c36492",
                      "pen_tester_4h", "1e060c35b79d", "skill-safety-scan"],
        )

        # ── 8. Outreach (7 Jobs) ───────────────────────────────────────
        self.subsystems["outreach"] = Subsystem(
            name="outreach", category="outreach", cadence_minutes=180,
            description="Social & GitHub Outreach — Wachstum",
            scripts=[
                "cron-social-outreach.py",          # 180m
                "cron-github-outreach.py",           # 120m
                "cron-growth-report.py",             # daily
                "cron-funding-tracker.py",           # daily
                "cron-autonom-growth.py",            # 60m
            ],
            cron_ids=["af955d3d0f27", "3c57f9727b5d", "ac8e13cefe91",
                      "c25c2d18740a", "9d9eaf3e918b"],
        )

        # ── 9. Infra (14 Jobs) ─────────────────────────────────────────
        self.subsystems["infra"] = Subsystem(
            name="infra", category="infra", cadence_minutes=30,
            description="Infrastruktur — Browser, SSH, Plugins, Sync",
            scripts=[
                "cron-auto-env-checker.py",         # 60m
                "ab-test-engine.py",                 # 30m
                "cron-model-sync.py",                # 240m
                "cron-tokenharbor-watchdog.py",      # 360m
                "gpu-worker-watchdog.py",            # 10m
                "cron-plugin-loader.py",             # 30m
                "cron-browser-watchdog.py",          # 5m
                "cron-stealth-server.py",            # 15m
                "cron-wiki-generator.py",            # daily
                "cron-deepseek-import.py",           # daily
                "hub-cache-warmer.py",               # 360m
                "cron_mesh_daemon.py",               # 5m
                "cron-context-compressor.py",        # daily
                "cron-file-organizer.py",            # daily
            ],
            cron_ids=["fb6973a70e35", "ab_test_collect", "1ab80658d306",
                      "9a6bcf2436d5", "414a4fa6f0a7", "a08bce193d56",
                      "b8dbf1f98adc", "4ac85a7de695", "ed618c851dd0",
                      "e2c0bad7dbe0", "cfa3d413462c", "0ccce21c5738",
                      "8d94e3136326", "fileorganizer_clean_24h"],
        )

        # ── 10. Meta (37 Jobs) ─────────────────────────────────────────
        self.subsystems["meta"] = Subsystem(
            name="meta", category="meta", cadence_minutes=60,
            description="Metakognition — Reflexion, Rewriting, Research",
            scripts=[
                "self-reflection",       # 120m
                "training/self_improve.py",          # 30m
                "goal-engine.py",                     # 30m
                "domain_mastery.py",                  # 360m
                "self-directed-research",              # 720m
                "cross-domain-synthesis",              # daily
                "tool-invention",                      # daily
                "cron-model-benchmarker.py",           # weekly
                "asi-audit",                           # weekly
                "dream-cron.py",                       # nightly
                "provenance_cleanup.py",               # daily
            ],
            cron_ids=["d201e7cfdb55", "aeadd353df7e", "goal_engine_tick",
                      "039e0ae4878e", "347915bd1bff", "6ba7c8471507",
                      "43f6d0b62df8", "361c2c58b296", "asi-capability-audit",
                      "9abf330dd545", "64f3e8231a29"],
        )

    def _load_state(self):
        """Load last-run timestamps from state file."""
        if self.STATE_FILE.exists():
            try:
                state = json.loads(self.STATE_FILE.read_text(encoding="utf-8"))
                for name, sub in self.subsystems.items():
                    ts = state.get("subsystems", {}).get(name, {}).get("last_run")
                    if ts is not None:
                        sub.last_run = ts
            except (json.JSONDecodeError, Exception):
                pass

    def _save_state(self):
        """Persist last-run timestamps."""
        state = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "subsystems": {
                name: {"last_run": sub.last_run, "enabled": sub.enabled}
                for name, sub in self.subsystems.items()
            },
        }
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.STATE_FILE.write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )

    # ── Public API ─────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return full heartbeat status."""
        now = time.time()
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state_file": str(self.STATE_FILE),
            "subsystems": {
                name: {
                    "category": sub.category,
                    "cadence": f"every {sub.cadence_minutes}m",
                    "enabled": sub.enabled,
                    "last_run": sub.last_run,
                    "due": sub.is_due(now, sub.last_run),
                    "scripts": sub.scripts,
                    "description": sub.description,
                }
                for name, sub in sorted(self.subsystems.items())
            },
        }

    def tick(self, system: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """Execute one heartbeat tick. Checks all due subsystems (or one)."""
        now = time.time()
        results = {}

        targets = [system] if system else list(self.subsystems.keys())

        for name in targets:
            sub = self.subsystems.get(name)
            if sub is None:
                results[name] = {"error": f"Unknown subsystem: {name}", "skipped": True}
                continue
            if not sub.enabled:
                results[name] = {"skipped": True, "reason": "disabled"}
                continue

            if not sub.is_due(now, sub.last_run) and not force:
                results[name] = {"skipped": True, "reason": "not_due"}
                continue

            # Execute tick
            tick_result = sub.tick(force=force)
            sub.last_run = now
            results[name] = tick_result

        # Save state
        self._save_state()

        return {
            "tick_time": datetime.now(timezone.utc).isoformat(),
            "systems_ticked": len(results),
            "results": results,
        }


# ── Global singleton ────────────────────────────────────────────────────────

_heartbeat: Optional[Heartbeat] = None


def get_heartbeat() -> Heartbeat:
    global _heartbeat
    if _heartbeat is None:
        _heartbeat = Heartbeat()
    return _heartbeat


# ── CLI entry point (for cron no_agent script) ──────────────────────────────

def main():
    """CLI entry: asi_heartbeat --tick [--system name] [--force] [--status]"""
    import argparse
    parser = argparse.ArgumentParser(description="ASI Heartbeat")
    parser.add_argument("--tick", action="store_true", help="Run heartbeat tick")
    parser.add_argument("--system", type=str, default=None, help="Specific subsystem")
    parser.add_argument("--force", action="store_true", help="Force tick even if not due")
    parser.add_argument("--status", action="store_true", help="Show heartbeat status")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    hb = get_heartbeat()

    if args.status:
        result = hb.status()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for name, info in result["subsystems"].items():
                due_str = "⏰" if info["due"] else "✓"
                print(f'{due_str} {name:15s} {info["cadence"]:15s} {info["description"]}')
            print(f'\nState: {result["state_file"]}')
        return

    if args.tick:
        result = hb.tick(system=args.system, force=args.force)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            ok = sum(1 for r in result["results"].values()
                     if r.get("any_success") or r.get("skipped"))
            fail = sum(1 for r in result["results"].values()
                       if not r.get("any_success") and not r.get("skipped"))
            skipped = sum(1 for r in result["results"].values()
                          if r.get("skipped"))
            print(f'ASI Heartbeat: {result["systems_ticked"]} systems')
            print(f'  ✅ {ok} ok/skipped | ❌ {fail} failed')
            for name, r in result["results"].items():
                status = "✅" if r.get("any_success") else ("⏭️" if r.get("skipped") else "❌")
                print(f'  {status} {name}')
        return

    parser.print_help()


if __name__ == "__main__":
    main()