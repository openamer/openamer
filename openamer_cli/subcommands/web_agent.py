"""``openamer web-agent`` subcommand parser."""

from __future__ import annotations

from typing import Callable


def build_web_agent_parser(subparsers, *, cmd_web_agent: Callable) -> None:
    """Attach the ``web-agent`` subcommand to ``subparsers``."""
    wa_parser = subparsers.add_parser(
        "web-agent",
        help="Autonomous Web Agent — erledigt Aufgaben selbstständig im Internet",
        description=(
            "Der Autonomous Web Agent kann Ziele im Internet eigenständig "
            "verfolgen: Webseiten durchsuchen, Formulare ausfüllen, "
            "Informationen sammeln, Preise vergleichen. "
            "Alles vollautomatisch, Schritt für Schritt."
        ),
    )
    wa_sub = wa_parser.add_subparsers(dest="web_agent_command")

    run_parser = wa_sub.add_parser("run", help="Führt ein Ziel autonom aus")
    run_parser.add_argument("goal", nargs="+", help="Das Ziel (z.B. 'Finde die günstigste Flugverbindung')")

    plan_parser = wa_sub.add_parser("plan", help="Zeigt den Plan für ein Ziel (ohne Ausführung)")
    plan_parser.add_argument("goal", nargs="+", help="Das Ziel")

    wa_sub.add_parser("status", help="Zeigt Status des laufenden Web Agents")
    wa_sub.add_parser("log", help="Zeigt das Log der letzten Aktion")

    wa_parser.set_defaults(func=cmd_web_agent)