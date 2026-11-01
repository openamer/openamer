"""Tests for the session-dialogue corpus extractor."""

from __future__ import annotations

import json
import sqlite3

from openamer_brain import session_corpus as sc


def _make_db(path, rows):
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "session_id TEXT, role TEXT, content TEXT, active INTEGER DEFAULT 1)"
    )
    for sid, role, content in rows:
        con.execute("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)",
                    (sid, role, content))
    con.commit()
    con.close()
    return path


def test_noise_patterns_catch_compaction_mid_text():
    """A reply that embeds the summary block is machinery, not a dialogue."""
    assert sc.is_noise("[PRIOR CONTEXT — for reference only]")
    assert sc.is_noise("some leading text [PRIOR CONTEXT — for reference only] tail")
    assert sc.is_noise("[END OF PRIOR CONTEXT — COMPACTION SUMMARY]")
    assert sc.is_noise("[System note: Your previous turn was interrupted")
    assert sc.is_noise("[IMPORTANT: Background process proc_1 completed")


def test_real_dialogue_is_not_noise():
    assert not sc.is_noise("wie viele cron jobs laufen gerade?")
    assert not sc.is_noise("Mein Name ist **OpenAmer Agent**.")


def test_iter_pairs_pairs_user_with_following_assistant(tmp_path):
    db = _make_db(tmp_path / "s.db", [
        ("s1", "user", "erste frage"),
        ("s1", "assistant", "erste antwort"),
        ("s1", "user", "zweite frage"),
        ("s1", "assistant", "zweite antwort"),
    ])
    pairs = list(sc.iter_pairs(db))
    assert pairs == [
        ("s1", "erste frage", "erste antwort"),
        ("s1", "zweite frage", "zweite antwort"),
    ]


def test_iter_pairs_skips_assistant_without_question(tmp_path):
    db = _make_db(tmp_path / "s.db", [
        ("s1", "assistant", "antwort ohne frage"),
        ("s1", "user", "frage"),
        ("s1", "assistant", "antwort"),
    ])
    assert list(sc.iter_pairs(db)) == [("s1", "frage", "antwort")]


def test_build_records_filters_noise_short_and_duplicates(tmp_path):
    db = _make_db(tmp_path / "s.db", [
        ("s1", "user", "wie viele cron jobs laufen gerade?"),
        ("s1", "assistant", "Es laufen 27 aktive Jobs."),
        ("s1", "user", "[System note: interrupted]"),
        ("s1", "assistant", "egal"),
        ("s1", "user", "kurz"),
        ("s1", "assistant", "a"),
        ("s2", "user", "wie viele cron jobs laufen gerade?"),
        ("s2", "assistant", "Es laufen 27 aktive Jobs."),
    ])
    records, stats = sc.build_records(db)
    assert stats["kept"] == 1, stats
    assert stats["dropped_noise"] >= 1
    assert stats["dropped_short"] >= 1
    assert stats["dropped_duplicate"] == 1
    assert records[0]["messages"][0]["content"].startswith("wie viele cron")
    assert records[0]["engine"] == "session-dialogue"


def test_caps_are_applied(tmp_path):
    db = _make_db(tmp_path / "s.db", [
        ("s1", "user", "frage " * 2000),
        ("s1", "assistant", "antwort " * 2000),
    ])
    records, _ = sc.build_records(db)
    assert len(records[0]["messages"][0]["content"]) <= sc.MAX_USER
    assert len(records[0]["messages"][1]["content"]) <= sc.MAX_ASST


def test_write_records_is_valid_jsonl(tmp_path):
    out = tmp_path / "out.jsonl"
    recs = [{"messages": [{"role": "user", "content": "hi"},
                          {"role": "assistant", "content": "hallo"}]}]
    path = sc.write_records(recs, out)
    line = path.read_text(encoding="utf-8").strip()
    assert json.loads(line)["messages"][1]["content"] == "hallo"


def test_missing_db_returns_nothing(tmp_path):
    records, stats = sc.build_records(tmp_path / "nope.db")
    assert records == []
    assert stats["kept"] == 0
