#!/usr/bin/env python3
"""openamer asi - ASI Core CLI.

Subcommands:
  status     - ASI System-Status (alle 10 Subsysteme + 5 Tools)
  think      - Tiefes Reasoning (asi_think)
  learn      - Internet-Lernzyklus (asi_learn)
  remember   - Episodisches Gedaechtnis (asi_remember)
  trigger    - ASI-Capability ausloesen (asi_trigger)
  heartbeat  - Herzschlag-Status und Tick
"""

import json
import sys
from pathlib import Path
from typing import Optional


def _import_asi():
    """Lazy import des ASI Core (i.d.R. nicht im venv der CLI)."""
    import importlib, os
    home = Path(os.environ.get(
        "OPENAMER_HOME",
        str(Path.home() / "AppData/Local/openamer-laptop"),
    ))
    agent_dir = str(home / "openamer-agent")
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)
    core_mod = importlib.import_module("tools.asi_core")
    hb_mod = importlib.import_module("tools.asi.heartbeat")
    return core_mod, hb_mod


def _cmd_status(args) -> int:
    """Zeige ASI System-Status."""
    try:
        core_mod, hb_mod = _import_asi()
        core = core_mod.get_asi_core()
        status = core.status()
        hb = hb_mod.get_heartbeat()
        hb_status = hb.status()

        print("=== ASI Core Status ===")
        print(f"Identity: {status.get('identity', '?')}")
        print(f"Episoden: {status.get('memory_episodes', '?')}")
        print(f"Weltmodell-Kanten: {status.get('world_model_edges', '?')}")
        print(f"Evolution-Events: {status.get('evolution_events', '?')}")
        print()

        print("=== ASI Herzschlag - Subsysteme ===")
        for name, info in sorted(hb_status["subsystems"].items()):
            due = "DUE" if info.get("due") else "OK"
            enabled = "ON" if info.get("enabled") else "OFF"
            print(f"  [{enabled}] {due} {name:15s} {info['cadence']:15s} {info['description']}")

        if args.json:
            print(json.dumps({"core": status, "heartbeat": hb_status}, indent=2))

        return 0
    except ImportError as e:
        print(f"ASI Core nicht verfuegbar: {e}")
        print("   (ASI-Tools sind nur im Agent-Kontext geladen)")
        return 1


def _cmd_think(args) -> int:
    """Tiefes Reasoning."""
    try:
        core_mod, _ = _import_asi()
        core = core_mod.get_asi_core()
        result = core.think(args.question)
        if result.get("success"):
            print(f"Answer: {result.get('answer', '?')}")
            print(f"Runden: {result.get('rounds', '?')}")
        else:
            print(f"Fehler: {result.get('error', '?')}")
        return 0 if result.get("success") else 1
    except ImportError as e:
        print(f"ASI Core nicht verfuegbar: {e}")
        return 1


def _cmd_learn(args) -> int:
    """Internet-Lernzyklus."""
    try:
        core_mod, _ = _import_asi()
        core = core_mod.get_asi_core()
        result = core.learn(args.topic)
        if result.get("success"):
            print("Gelernt!")
            out = result.get("stdout", result.get("result", ""))
            print(str(out)[:500])
        else:
            print(f"Fehler: {result.get('error', '?')}")
        return 0 if result.get("success") else 1
    except ImportError as e:
        print(f"ASI Core nicht verfuegbar: {e}")
        return 1


def _cmd_remember(args) -> int:
    """Episodisches Gedaechtnis."""
    try:
        core_mod, _ = _import_asi()
        core = core_mod.get_asi_core()
        result = core.recall(args.query, k=args.k)
        if result.get("success"):
            print(f"{len(result.get('results', []))} Ergebnisse:")
            for i, r in enumerate(result["results"][:10], 1):
                if isinstance(r, dict):
                    cause = r.get('cause', '?')[:80]
                    effect = r.get('effect', '?')[:80]
                    print(f"  {i}. {cause} -> {effect}")
                else:
                    print(f"  {i}. {str(r)[:100]}")
        else:
            print(f"Fehler: {result.get('error', '?')}")
        return 0 if result.get("success") else 1
    except ImportError as e:
        print(f"ASI Core nicht verfuegbar: {e}")
        return 1


def _cmd_trigger(args) -> int:
    """ASI-Capability ausloesen."""
    try:
        core_mod, _ = _import_asi()
        core = core_mod.get_asi_core()

        if args.system:
            from tools.asi.heartbeat import get_heartbeat
            hb = get_heartbeat()
            result = hb.tick(system=args.system, force=args.force)
        else:
            method_map = {
                "self_improve": lambda: core.improve(),
                "predict": lambda: core.predict(args.situation or ""),
                "validate": lambda: core.validate_predictions(),
                "meta_learn": lambda: core.meta_learn(),
                "knowledge_to_action": lambda: core.knowledge_to_action(),
                "self_model": lambda: core.self_model(),
                "consolidate_memory": lambda: core.consolidate_memory(),
                "diary": lambda: core.diary(),
                "session_outcome": lambda: core.session_outcome(),
                "heartbeat": lambda: core.heartbeat(),
            }
            fn = method_map.get(args.capability)
            if fn is None:
                print(f"Unbekannte Capability: {args.capability}")
                return 1
            result = fn()

        print(json.dumps(result, indent=2, default=str))
        return 0
    except ImportError as e:
        print(f"ASI Core nicht verfuegbar: {e}")
        return 1


def _cmd_heartbeat(args) -> int:
    """Herzschlag-Status und Tick."""
    try:
        _, hb_mod = _import_asi()
        hb = hb_mod.get_heartbeat()

        if args.tick:
            result = hb.tick(system=args.system, force=args.force)
            ok = sum(1 for r in result["results"].values()
                     if r.get("any_success") or r.get("skipped"))
            fail = sum(1 for r in result["results"].values()
                       if not r.get("any_success") and not r.get("skipped"))
            print(f"Heartbeat Tick: {result['systems_ticked']} systems, {ok} ok, {fail} failed")
            if args.json:
                print(json.dumps(result, indent=2, default=str))
        else:
            s = hb.status()
            for name, info in sorted(s["subsystems"].items()):
                due = "DUE" if info.get("due") else "OK"
                print(f"  {due} {name:15s} {info['cadence']:15s} {info['description']}")
            if args.json:
                print(json.dumps(s, indent=2))
        return 0
    except ImportError as e:
        print(f"ASI Core nicht verfuegbar: {e}")
        return 1


def build_asi_parser(subparsers) -> None:
    """Wire `openamer asi` subcommands."""
    p = subparsers.add_parser(
        "asi",
        help="ASI Core - integrierte Superintelligenz",
        description="ASI Core Kommando: Status, Reasoning, Lernen, Erinnern, Trigger, Herzschlag.",
    )
    sub = p.add_subparsers(dest="asi_command", metavar="COMMAND")
    p.set_defaults(func=lambda args: p.print_help() if not args.asi_command else None)

    # status
    sp = sub.add_parser("status", help="Zeige ASI System-Status")
    sp.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    sp.set_defaults(func=_cmd_status)

    # think
    sp = sub.add_parser("think", help="Tiefes Reasoning")
    sp.add_argument("question", help="Die Frage")
    sp.set_defaults(func=_cmd_think)

    # learn
    sp = sub.add_parser("learn", help="Internet-Lernzyklus")
    sp.add_argument("--topic", help="Optional: Thema fokussieren")
    sp.set_defaults(func=_cmd_learn)

    # remember
    sp = sub.add_parser("remember", help="Episodisches Gedaechtnis")
    sp.add_argument("query", help="Suchbegriff")
    sp.add_argument("-k", type=int, default=5, help="Anzahl Ergebnisse")
    sp.set_defaults(func=_cmd_remember)

    # trigger
    sp = sub.add_parser("trigger", help="Capability ausloesen")
    sp.add_argument("capability",
                    choices=["self_improve", "predict", "validate", "meta_learn",
                             "knowledge_to_action", "self_model",
                             "consolidate_memory", "diary", "session_outcome",
                             "heartbeat"])
    sp.add_argument("--system", help="Heartbeat: Subsystem-Name")
    sp.add_argument("--force", action="store_true", help="Heartbeat: erzwingen")
    sp.add_argument("--situation", help="Predict: Situation")
    sp.set_defaults(func=_cmd_trigger)

    # heartbeat
    sp = sub.add_parser("heartbeat", help="Herzschlag-Status und Tick")
    sp.add_argument("--tick", action="store_true", help="Einen Tick ausfuehren")
    sp.add_argument("--system", help="Nur ein Subsystem")
    sp.add_argument("--force", action="store_true", help="Erzwingen auch wenn nicht faellig")
    sp.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    sp.set_defaults(func=_cmd_heartbeat)