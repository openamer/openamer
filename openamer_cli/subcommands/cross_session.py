"""
``openamer cross-session`` subcommand parser.

Provides:
  - ``openamer cross-session extract <session_id>``  — Lessons aus Session
  - ``openamer cross-session consolidate``            — alle Lessons zusammenfassen
  - ``openamer cross-session inject``                 — Context für neue Sessions
  - ``openamer cross-session auto``                   — full cycle
  - ``openamer cross-session list``                   — recent sessions anzeigen
"""

from __future__ import annotations

import sys


def build_cross_session_parser(subparsers) -> None:
    """Attach the ``cross-session`` subcommand (and sub-actions) to *subparsers*."""
    parser = subparsers.add_parser(
        "cross-session",
        help="Cross-Session Learning — Lessons aus Sessions extrahieren",
        description=(
            "Cross-Session Learning analysiert abgeschlossene Sessions, "
            "extrahiert Lessons Learned und gibt sie als Kontext an neue "
            "Sessions weiter. So beeinflussen Erkenntnisse aus Session A die Session B."
        ),
    )
    sub = parser.add_subparsers(dest="cross_session_command")

    # cross-session extract <session_id>
    p_extract = sub.add_parser(
        "extract",
        help="Extrahiert Lessons Learned aus einer Session",
        description=(
            "Analysiert eine Session anhand ihrer ID, identifiziert genutzte "
            "Tools, Themen-Schwerpunkte, Erfolgsmuster und speichert die "
            "Erkenntnisse für die spätere Konsolidierung."
        ),
    )
    p_extract.add_argument(
        "session_id",
        help="Session-ID aus der State-DB (z. B. 20260818_123456_abc123)",
    )
    p_extract.add_argument(
        "--no-persist", action="store_true",
        help="Nicht in der Lessons-DB speichern (nur anzeigen)",
    )

    # cross-session consolidate
    sub.add_parser(
        "consolidate",
        help="Aggregiert Lessons aus allen Sessions der letzten 7 Tage",
        description=(
            "Fasst alle extrahierten Lessons zusammen, zählt die häufigsten "
            "Tools und identifiziert wiederkehrende Muster."
        ),
    )

    # cross-session inject
    sub.add_parser(
        "inject",
        help="Erstellt Context-Block für neue Sessions",
        description=(
            "Generiert einen menschenlesbaren Text-Block mit den aggregierten "
            "Erkenntnissen, der neuen Sessions als Kontext mitgegeben werden kann."
        ),
    )

    # cross-session auto
    sub.add_parser(
        "auto",
        help="Führt den vollständigen Cross-Session-Learning-Zyklus aus",
        description=(
            "1) Fehlende Extraktionen nachholen  2) Konsolidieren  "
            "3) Context generieren. Der komplette Workflow."
        ),
    )

    # cross-session list
    sub.add_parser(
        "list",
        help="Listet Sessions der letzten 7 Tage",
        description="Zeigt alle Sessions der letzten 7 Tage mit ID, Titel und Status.",
    )

    parser.set_defaults(func=_cmd_cross_session)


def _cmd_cross_session(args) -> int:
    """Dispatch ``openamer cross-session <subcommand>``."""
    sub = getattr(args, "cross_session_command", None)

    if sub in (None, ""):
        print(
            "usage: openamer cross-session <subcommand>\n"
            "\n"
            "subcommands:\n"
            "  extract <session_id>  Lessons aus einer Session extrahieren\n"
            "  consolidate           Alle Lessons zusammenfassen\n"
            "  inject                Context-Block für neue Sessions generieren\n"
            "  auto                  Vollständigen Zyklus ausführen\n"
            "  list                  Sessions der letzten 7 Tage anzeigen\n"
            "\n"
            "Run `openamer cross-session <subcommand> -h` for details.",
            file=sys.stderr,
        )
        return 1

    if sub == "extract":
        return _cmd_extract(args.session_id, persist=not getattr(args, "no_persist", False))
    elif sub == "consolidate":
        return _cmd_consolidate()
    elif sub == "inject":
        return _cmd_inject()
    elif sub == "auto":
        return _cmd_auto()
    elif sub == "list":
        return _cmd_list()
    else:
        print(f"Unknown cross-session subcommand: {sub}", file=sys.stderr)
        return 1


# ── Sub-Handler ────────────────────────────────────────────────────────────


def _cmd_extract(session_id: str, *, persist: bool = True) -> int:
    """Extrahiere Lessons aus einer Session und zeige sie an."""
    try:
        from openamer_cli.cross_session_learning import extract_lessons
        result = extract_lessons(session_id, persist=persist)
    except ImportError as exc:
        print(f"❌ Modul-Fehler: {exc}", file=sys.stderr)
        return 1

    if "error" in result:
        print(f"❌ {result['error']}", file=sys.stderr)
        return 1

    print("╔══════════════════════════════════════════════╗")
    print("║       CROSS-SESSION — LESSONS EXTRACTED      ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"  Session:   {result.get('title', '?')}")
    print(f"  ID:        {result['session_id']}")
    print(f"  Model:     {result.get('model', '?')}")
    print(f"  Status:    {'✅ Erfolg' if result.get('success') else '❌ Fehler'}")
    print(f"  Messages:  {result.get('message_count', '?')}")
    print(f"  Tools:     {result.get('tool_call_count', 0)} Aufrufe")
    print(f"  Dauer:     {result.get('duration_min', 0)} Minuten")
    print(f"  Tokens:    {result.get('input_tokens', 0)} in / {result.get('output_tokens', 0)} out")
    print()
    print("  ── Lessons ──")
    for i, les in enumerate(result.get("lessons", []), start=1):
        icon = "✅" if les.get("success") else "❌"
        print(f"  {i}. {icon} [{les.get('category', 'general')}] {les['lesson']}")
    print()
    if persist:
        print(f"  💾 {len(result.get('lessons', []))} Lessons gespeichert.")
    return 0


def _cmd_consolidate() -> int:
    """Zeige konsolidierte Lessons an."""
    try:
        from openamer_cli.cross_session_learning import consolidate_lessons
        data = consolidate_lessons()
    except ImportError as exc:
        print(f"❌ Modul-Fehler: {exc}", file=sys.stderr)
        return 1

    print("╔══════════════════════════════════════════════╗")
    print("║     CROSS-SESSION — CONSOLIDATED LESSONS     ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"  Sessions:  {data['total_sessions']}")
    print(f"  Lessons:   {data['total_lessons']} (✅ {data['success_count']} / ❌ {data['fail_count']})")
    print()

    if data["top_tools"]:
        print("  🔧 Top-Tools:")
        for tool, cnt in list(data["top_tools"].items())[:5]:
            print(f"     {tool}: {cnt}x")

    if data["topics"]:
        print("  📋 Haupt-Themen:")
        for topic, cnt in list(data["topics"].items())[:5]:
            print(f"     {topic}: {cnt}x")

    print()
    print("  ── Konsolidierte Erkenntnisse ──")
    for i, c in enumerate(data.get("consolidated_lessons", []), start=1):
        conf = c.get("confidence", 0)
        conf_bar = "▌" * min(conf, 10) + "░" * max(0, 10 - min(conf, 10))
        print(f"  {i}. [{c['category']}] {conf_bar}")
        print(f"     {c['lesson']}")
    print()
    return 0


def _cmd_inject() -> int:
    """Generiere und zeige den Context-Block."""
    try:
        from openamer_cli.cross_session_learning import inject_context
        context = inject_context()
    except ImportError as exc:
        print(f"❌ Modul-Fehler: {exc}", file=sys.stderr)
        return 1

    print(context)
    return 0


def _cmd_auto() -> int:
    """Führe den vollständigen Zyklus aus."""
    try:
        from openamer_cli.cross_session_learning import run_consolidation_cycle
        result = run_consolidation_cycle(verbose=True)
    except ImportError as exc:
        print(f"❌ Modul-Fehler: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"✅ Zyklus abgeschlossen in {result['duration_seconds']}s")
    print(f"   Sessions verarbeitet: {result['sessions_processed']}")
    print(f"   Lessons extrahiert:   {result['lessons_extracted']}")
    print(f"   Lessons in DB:        {result['total_lessons_db']}")
    return 0


def _cmd_list() -> int:
    """Zeige Sessions der letzten 7 Tage an."""
    try:
        from openamer_cli.cross_session_learning import list_recent_sessions
        sessions = list_recent_sessions(days=7)
    except ImportError as exc:
        print(f"❌ Modul-Fehler: {exc}", file=sys.stderr)
        return 1

    if not sessions:
        print("ℹ️  Keine Sessions in den letzten 7 Tagen gefunden.")
        return 0

    print("╔══════════════════════════════════════════════╗")
    print("║          RECENT SESSIONS (7 Tage)            ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"{'ID':32s} {'Titel':30s} {'Model':20s} {'Status':12s}")
    print("─" * 96)
    for s in sessions:
        sid = s.get("id", "?")[:30]
        title = (s.get("title") or "(kein Titel)")[:28]
        model = (s.get("model") or "?")[:18]
        reason = s.get("end_reason") or "unknown"
        status = "✅" if reason not in ("error", "cancelled", "interrupted") else "❌"
        print(f"{sid:32s} {title:30s} {model:20s} {status:5s}  {reason}")
    print()
    return 0