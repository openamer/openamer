"""
Tests für ``openamer_cli.cross_session_learning``.

Mindestens 5 Tests:
  1. extract_lessons — erfolgreiche Session
  2. extract_lessons — Session nicht gefunden
  3. consolidate_lessons — leere DB
  4. inject_context — leerer Context bei 0 Sessions
  5. run_consolidation_cycle — vollständiger Zyklus (simuliert)
  6. inject_context — mit Lessons
  7. list_recent_sessions — Filtert korrekt
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import TestCase, mock


# ── Test-Hilfe: simulierten State-DB erstellen ─────────────────────────────

_MOCK_TIME = 1_800_000_000.0  # 2027-01-10


def _create_mock_state_db(path: Path) -> None:
    """Erzeugt eine State-DB mit Test-Sessions und Messages."""
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT,
            model TEXT,
            started_at REAL,
            ended_at REAL,
            end_reason TEXT,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_name TEXT,
            tool_call_id TEXT,
            finish_reason TEXT,
            token_count INTEGER,
            active INTEGER DEFAULT 1
        )
    """)

    # Session 1: Erfolgreiche Coding-Session
    s1_id = "session_success_001"
    now = _MOCK_TIME
    conn.execute(
        "INSERT INTO sessions (id, source, title, model, started_at, ended_at, "
        "end_reason, message_count, tool_call_count, input_tokens, output_tokens) "
        "VALUES (?, 'cli', 'API-Integration in Python', 'deepseek/deepseek-v4-flash', "
        "?, ?, 'completed', 12, 8, 4500, 12000)",
        (s1_id, now - 3600, now),
    )
    for i in range(5):
        conn.execute(
            "INSERT INTO messages (session_id, role, content, token_count, active) "
            "VALUES (?, 'user', ?, 200, 1)",
            (s1_id, f"Wie implementiere ich die API-Route für User-{i}?"),
        )
    for i in range(5):
        conn.execute(
            "INSERT INTO messages (session_id, role, content, tool_name, "
            "finish_reason, token_count, active) VALUES (?, 'assistant', ?, "
            "'terminal', 'stop', 800, 1)",
            (s1_id, f"Hier ist der Code für Schritt {i}:"),
        )
    for i in range(2):
        conn.execute(
            "INSERT INTO messages (session_id, role, content, tool_name, "
            "token_count, active) VALUES (?, 'tool', '{}', 'terminal', 100, 1)",
            (s1_id,),
        )

    # Session 2: Fehlgeschlagene Session
    s2_id = "session_fail_002"
    conn.execute(
        "INSERT INTO sessions (id, source, title, model, started_at, ended_at, "
        "end_reason, message_count, tool_call_count, input_tokens, output_tokens) "
        "VALUES (?, 'cli', 'Debugging Pipeline', 'gpt-4o', "
        "?, ?, 'error', 3, 0, 900, 200)",
        (s2_id, now - 7200, now - 7000),
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, token_count, active) "
        "VALUES (?, 'user', 'Die Pipeline crasht mit einem MemoryError', 100, 1)",
        (s2_id,),
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, finish_reason, "
        "token_count, active) VALUES (?, 'assistant', "
        "'Ich habe den Fehler analysiert, brauche aber mehr Infos', "
        "'stop', 200, 1)",
        (s2_id,),
    )

    # Session 3: Alte Session (älter als 7 Tage)
    s3_id = "session_old_003"
    old_ts = _MOCK_TIME - 8 * 86400  # 8 days ago
    conn.execute(
        "INSERT INTO sessions (id, source, title, model, started_at, ended_at, "
        "end_reason, message_count, tool_call_count, input_tokens, output_tokens) "
        "VALUES (?, 'cli', 'Altes Projekt Setup', 'claude-3-opus', "
        "?, ?, 'completed', 20, 15, 8000, 25000)",
        (s3_id, old_ts, old_ts + 5400),
    )

    conn.commit()
    conn.close()


def _create_mock_lessons_db(path: Path) -> None:
    """Erzeugt eine Lessons-DB mit Testdaten."""
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            category TEXT NOT NULL,
            lesson TEXT NOT NULL,
            tool_name TEXT,
            success INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        )
    """)
    now = _MOCK_TIME
    lessons_data = [
        ("session_success_001", "result", "Session erfolgreich abgeschlossen", None, 1),
        ("session_success_001", "tools", "Top-Tools: terminal(5)", "terminal", 1),
        ("session_success_001", "efficiency", "Token: 4500/12000, Dauer: 60 Min", None, 1),
        ("session_success_001", "topics", "Themen-Schwerpunkte: api(3), route(2)", None, 1),
        ("session_success_001", "model", "Model: deepseek/deepseek-v4-flash", None, 1),
        ("session_fail_002", "result", "Session vorzeitig beendet (error)", None, 0),
        ("session_fail_002", "model", "Model: gpt-4o", None, 1),
    ]
    for i, (sid, cat, lesson, tool, success) in enumerate(lessons_data):
        conn.execute(
            "INSERT INTO lessons (session_id, category, lesson, tool_name, success, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sid, cat, lesson, tool, success, now + i),
        )
    conn.commit()
    conn.close()


def _create_mock_lessons_db_empty(path: Path) -> None:
    """Erzeugt eine leere Lessons-DB."""
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            category TEXT NOT NULL,
            lesson TEXT NOT NULL,
            tool_name TEXT,
            success INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: extract_lessons — erfolgreiche Session
# ═══════════════════════════════════════════════════════════════════════════

@mock.patch.dict(os.environ, {"OPENAMER_HOME": ""})
class TestExtractLessons(TestCase):
    """Tests für extract_lessons()."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_db = self.tmpdir / "state.db"
        self.lessons_db = self.tmpdir / "cross_session_lessons.db"
        _create_mock_state_db(self.state_db)
        _create_mock_lessons_db_empty(self.lessons_db)

        # Patch the module-level helpers
        self.patches = [
            mock.patch(
                "openamer_cli.cross_session_learning._state_db_path",
                return_value=self.state_db,
            ),
            mock.patch(
                "openamer_cli.cross_session_learning._lessons_db_path",
                return_value=self.lessons_db,
            ),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_extract_successful_session(self):
        """extract_lessons findet eine existierende Session und extrahiert Lessons."""
        from openamer_cli.cross_session_learning import extract_lessons

        result = extract_lessons("session_success_001", persist=False)

        self.assertNotIn("error", result)
        self.assertEqual(result["session_id"], "session_success_001")
        self.assertEqual(result["title"], "API-Integration in Python")
        self.assertTrue(result["success"])
        self.assertEqual(result["model"], "deepseek/deepseek-v4-flash")
        self.assertGreater(len(result["lessons"]), 2)

        # Prüfen: Lessons enthalten Kategorien
        categories = {l["category"] for l in result["lessons"]}
        self.assertIn("result", categories)
        self.assertIn("model", categories)
        self.assertIn("tools", categories)

        # Tool-Nutzung
        self.assertEqual(result["tool_call_count"], 8)
        self.assertIn("terminal", result["tool_usage"])

    def test_extract_session_not_found(self):
        """extract_lessons gibt Fehler bei unbekannter Session-ID."""
        from openamer_cli.cross_session_learning import extract_lessons

        result = extract_lessons("nonexistent_id", persist=False)
        self.assertIn("error", result)
        self.assertEqual(len(result["lessons"]), 0)

    def test_extract_failed_session(self):
        """extract_lessons erkennt fehlgeschlagene Sessions."""
        from openamer_cli.cross_session_learning import extract_lessons

        result = extract_lessons("session_fail_002", persist=False)

        self.assertFalse(result["success"])
        self.assertEqual(result["end_reason"], "error")

    def test_extract_persistence(self):
        """extract_lessons mit persist=True speichert Lessons in der DB."""
        from openamer_cli.cross_session_learning import extract_lessons

        result = extract_lessons("session_success_001", persist=True)
        self.assertNotIn("error", result)
        self.assertGreater(len(result["lessons"]), 0)

        # Prüfen, ob Lessons in der DB sind
        conn = sqlite3.connect(str(self.lessons_db))
        count = conn.execute(
            "SELECT COUNT(*) FROM lessons WHERE session_id = ?",
            ("session_success_001",),
        ).fetchone()[0]
        conn.close()
        self.assertGreater(count, 0)


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: consolidate_lessons
# ═══════════════════════════════════════════════════════════════════════════

@mock.patch.dict(os.environ, {"OPENAMER_HOME": ""})
class TestConsolidateLessons(TestCase):
    """Tests für consolidate_lessons()."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_db = self.tmpdir / "state.db"
        self.lessons_db = self.tmpdir / "cross_session_lessons.db"
        _create_mock_state_db(self.state_db)
        _create_mock_lessons_db(self.lessons_db)

        self.patches = [
            mock.patch(
                "openamer_cli.cross_session_learning._state_db_path",
                return_value=self.state_db,
            ),
            mock.patch(
                "openamer_cli.cross_session_learning._lessons_db_path",
                return_value=self.lessons_db,
            ),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_consolidate_returns_aggregated_data(self):
        """consolidate_lessons aggregiert Daten aus Lessons-DB."""
        from openamer_cli.cross_session_learning import consolidate_lessons

        data = consolidate_lessons(days=7)

        self.assertGreater(data["total_sessions"], 0)
        self.assertGreater(data["total_lessons"], 0)
        self.assertIn("consolidated_lessons", data)

        # Tool-Summary sollte vorhanden sein
        self.assertIn("top_tools", data)

        # Es sollte mindestens eine consolidated lesson geben.
        self.assertGreater(len(data["consolidated_lessons"]), 0)

    def test_consolidate_empty_db(self):
        """consolidate_lessons mit leerer Lessons-DB gibt leere Aggregate."""
        empty_db = self.tmpdir / "empty_lessons.db"
        _create_mock_lessons_db_empty(empty_db)

        with mock.patch(
            "openamer_cli.cross_session_learning._lessons_db_path",
            return_value=empty_db,
        ):
            from openamer_cli.cross_session_learning import consolidate_lessons
            data = consolidate_lessons(days=7)

        # Lessons-DB ist leer, aber Sessions existieren in State-DB
        self.assertEqual(data["total_lessons"], 0)


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: inject_context
# ═══════════════════════════════════════════════════════════════════════════

@mock.patch.dict(os.environ, {"OPENAMER_HOME": ""})
class TestInjectContext(TestCase):
    """Tests für inject_context()."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_db = self.tmpdir / "state.db"
        self.lessons_db = self.tmpdir / "cross_session_lessons.db"
        _create_mock_state_db(self.state_db)
        _create_mock_lessons_db(self.lessons_db)

        self.patches = [
            mock.patch(
                "openamer_cli.cross_session_learning._state_db_path",
                return_value=self.state_db,
            ),
            mock.patch(
                "openamer_cli.cross_session_learning._lessons_db_path",
                return_value=self.lessons_db,
            ),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_inject_context_returns_text_block(self):
        """inject_context gibt einen Text-Block mit Erkenntnissen zurück."""
        from openamer_cli.cross_session_learning import inject_context

        context = inject_context()

        self.assertIsInstance(context, str)
        self.assertGreater(len(context), 50)
        # Der Titel "Cross-Session Learning" sollte vorkommen
        self.assertIn("Cross-Session Learning", context)
        # Tools sollten erwähnt werden
        self.assertIn("terminal", context)

    def test_inject_context_empty(self):
        """inject_context mit leerer DB gibt Hinweis zurück."""
        empty_state_db = self.tmpdir / "empty_state.db"
        empty_lessons_db = self.tmpdir / "empty_lessons.db"

        # Leere State-DB (nur Tabellen, keine Daten)
        conn = sqlite3.connect(str(empty_state_db))
        conn.execute("CREATE TABLE sessions (id TEXT)")
        conn.close()
        _create_mock_lessons_db_empty(empty_lessons_db)

        with (
            mock.patch(
                "openamer_cli.cross_session_learning._state_db_path",
                return_value=empty_state_db,
            ),
            mock.patch(
                "openamer_cli.cross_session_learning._lessons_db_path",
                return_value=empty_lessons_db,
            ),
        ):
            from openamer_cli.cross_session_learning import inject_context
            context = inject_context()

        self.assertIn("Noch keine Sessions", context)


# ═══════════════════════════════════════════════════════════════════════════
# Test 4: run_consolidation_cycle
# ═══════════════════════════════════════════════════════════════════════════

@mock.patch.dict(os.environ, {"OPENAMER_HOME": ""})
class TestConsolidationCycle(TestCase):
    """Tests für run_consolidation_cycle()."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_db = self.tmpdir / "state.db"
        self.lessons_db = self.tmpdir / "cross_session_lessons.db"
        _create_mock_state_db(self.state_db)
        _create_mock_lessons_db_empty(self.lessons_db)

        self.patches = [
            mock.patch(
                "openamer_cli.cross_session_learning._state_db_path",
                return_value=self.state_db,
            ),
            mock.patch(
                "openamer_cli.cross_session_learning._lessons_db_path",
                return_value=self.lessons_db,
            ),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_full_cycle(self):
        """run_consolidation_cycle führt den kompletten Zyklus aus."""
        from openamer_cli.cross_session_learning import run_consolidation_cycle

        result = run_consolidation_cycle(
            days=7,
            extract_missing=True,
            verbose=False,
        )

        self.assertGreater(result["sessions_processed"], 0)
        self.assertGreaterEqual(result["lessons_extracted"], 0)
        self.assertIn("context", result)
        self.assertIn("duration_seconds", result)
        self.assertGreater(result["duration_seconds"], 0)

        # Context sollte nicht leer sein
        self.assertGreater(len(result["context"]), 20)


# ═══════════════════════════════════════════════════════════════════════════
# Test 5: list_recent_sessions
# ═══════════════════════════════════════════════════════════════════════════

@mock.patch.dict(os.environ, {"OPENAMER_HOME": ""})
class TestListRecentSessions(TestCase):
    """Tests für list_recent_sessions()."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_db = self.tmpdir / "state.db"
        _create_mock_state_db(self.state_db)
        _create_mock_lessons_db_empty(self.tmpdir / "cross_session_lessons.db")

        self.patches = [
            mock.patch(
                "openamer_cli.cross_session_learning._state_db_path",
                return_value=self.state_db,
            ),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_list_recent_sessions(self):
        """list_recent_sessions filtert korrekt nach Zeitfenster."""
        from openamer_cli.cross_session_learning import list_recent_sessions

        # 7 Tage Fenster sollte 2 Sessions finden (session_old_003 ist 8 Tage alt)
        sessions = list_recent_sessions(days=7)
        session_ids = {s["id"] for s in sessions}
        self.assertIn("session_success_001", session_ids)
        self.assertIn("session_fail_002", session_ids)
        self.assertNotIn("session_old_003", session_ids)

    def test_list_recent_sessions_empty_window(self):
        """list_recent_sessions mit sehr kurzem Fenster findet nichts."""
        from openamer_cli.cross_session_learning import list_recent_sessions

        sessions = list_recent_sessions(days=0)  # nur heute
        self.assertEqual(len(sessions), 0)


# ═══════════════════════════════════════════════════════════════════════════
# Test 6: Subcommand Parser
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossSessionParser(TestCase):
    """Tests für den CLI-Parser."""

    def test_parser_accepts_all_subcommands(self):
        """build_cross_session_parser registriert alle 5 Subcommands."""
        import argparse
        from openamer_cli.subcommands.cross_session import build_cross_session_parser

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        build_cross_session_parser(subparsers)

        # extract
        args = parser.parse_args(["cross-session", "extract", "abc123"])
        self.assertEqual(args.cross_session_command, "extract")
        self.assertEqual(args.session_id, "abc123")

        # consolidate
        args = parser.parse_args(["cross-session", "consolidate"])
        self.assertEqual(args.cross_session_command, "consolidate")

        # inject
        args = parser.parse_args(["cross-session", "inject"])
        self.assertEqual(args.cross_session_command, "inject")

        # auto
        args = parser.parse_args(["cross-session", "auto"])
        self.assertEqual(args.cross_session_command, "auto")

        # list
        args = parser.parse_args(["cross-session", "list"])
        self.assertEqual(args.cross_session_command, "list")

    def test_extract_no_persist_flag(self):
        """extract akzeptiert --no-persist."""
        import argparse
        from openamer_cli.subcommands.cross_session import build_cross_session_parser

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        build_cross_session_parser(subparsers)

        args = parser.parse_args(["cross-session", "extract", "xyz", "--no-persist"])
        self.assertTrue(args.no_persist)
        self.assertEqual(args.session_id, "xyz")


# ═══════════════════════════════════════════════════════════════════════════
# Test 7: Stopwords & Hilfsfunktionen
# ═══════════════════════════════════════════════════════════════════════════

class TestHelpers(TestCase):
    """Tests für Hilfsfunktionen."""

    def test_stopwords_contains_german_words(self):
        """_stopwords enthält deutsche Stoppwörter."""
        from openamer_cli.cross_session_learning import _stopwords, _STOPWORDS

        sw = _stopwords()
        self.assertIn("und", sw)
        self.assertIn("oder", sw)
        self.assertIn("nicht", sw)
        self.assertGreater(len(sw), 10)

        # _STOPWORDS sollte das gecachte Set sein
        self.assertIs(_STOPWORDS, sw)

    def test_message_count_maybe(self):
        """message_count_maybe formatiert die Anzahl korrekt."""
        from openamer_cli.cross_session_learning import message_count_maybe

        self.assertEqual(message_count_maybe({"message_count": 5}), "5")
        self.assertEqual(message_count_maybe({"message_count": 0}), "0")
        self.assertEqual(message_count_maybe({}), "0")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import unittest
    unittest.main()