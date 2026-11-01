"""Tests for the brain corpus curation pipeline (no torch needed)."""

from __future__ import annotations

import json

from openamer_brain.corpus import (
    CurationStats,
    curate_message_stream,
    default_sources,
)


def _write(tmp_path, name: str, records: list[dict]) -> "object":
    p = tmp_path / name
    p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return p


def test_dedupe_keeps_one_copy_of_repeated_text(tmp_path):
    """The brain log re-writes history per trajectory; curation must collapse it."""
    rec = {"messages": [{"role": "user", "content": "wie viele cron jobs laufen?"}]}
    src = _write(tmp_path, "brain.jsonl", [rec, rec, rec])

    text, stats = curate_message_stream([src], drop_roles=())
    assert text.count("wie viele cron jobs laufen?") == 1
    assert stats.dropped_duplicate == 2
    assert stats.messages_kept == 1


def test_dedupe_can_be_disabled(tmp_path):
    rec = {"messages": [{"role": "assistant", "content": "gleiche Antwort hier"}]}
    src = _write(tmp_path, "brain.jsonl", [rec, rec])

    text, stats = curate_message_stream([src], drop_roles=(), dedupe=False)
    assert text.count("gleiche Antwort hier") == 2
    assert stats.dropped_duplicate == 0


def test_long_messages_are_capped_head_and_tail(tmp_path):
    head, tail = "HEAD-MARKER " * 40, "TAIL-MARKER " * 40
    body = "x" * 5000
    rec = {"messages": [{"role": "assistant", "content": head + body + tail}]}
    src = _write(tmp_path, "brain.jsonl", [rec])

    text, stats = curate_message_stream([src], drop_roles=(), max_msg_chars=800)
    assert stats.truncated == 1
    assert "HEAD-MARKER" in text, "head must survive the cut"
    assert "TAIL-MARKER" in text, "tail must survive the cut"
    assert "chars cut" in text
    assert len(text) < 1200


def test_drop_roles_removes_tool_output(tmp_path):
    rec = {
        "messages": [
            {"role": "user", "content": "zeig mir die cron jobs"},
            {"role": "tool", "content": "total 48 drwxr-xr-x 1 damir 197609"},
            {"role": "assistant", "content": "Es laufen 27 aktive Jobs."},
        ]
    }
    src = _write(tmp_path, "brain.jsonl", [rec])

    text, stats = curate_message_stream([src], drop_roles=("tool",))
    assert "drwxr-xr-x" not in text
    assert "27 aktive Jobs" in text
    assert stats.dropped_role == 1
    assert stats.by_role == {"user": 1, "assistant": 1}


def test_keep_roles_is_a_whitelist(tmp_path):
    rec = {
        "messages": [
            {"role": "system", "content": "du bist OpenAmer"},
            {"role": "user", "content": "hallo, wie geht es dir heute?"},
            {"role": "assistant", "content": "Guten Tag, mir geht es gut."},
        ]
    }
    src = _write(tmp_path, "brain.jsonl", [rec])

    text, _ = curate_message_stream([src], drop_roles=(), keep_roles=("user", "assistant"))
    assert "du bist OpenAmer" not in text
    assert "wie geht es dir" in text and "Guten Tag" in text


def test_short_valid_answers_survive(tmp_path):
    """`Ja.` is a legitimate reply and must not be filtered as noise."""
    rec = {
        "messages": [
            {"role": "user", "content": "soll ich das jetzt ausfuehren?"},
            {"role": "assistant", "content": "Ja."},
        ]
    }
    src = _write(tmp_path, "brain.jsonl", [rec])

    text, stats = curate_message_stream([src], drop_roles=())
    assert "<|assistant|> Ja." in text
    assert stats.dropped_empty == 0


def test_u_a_records_are_read(tmp_path):
    """online_buffer.jsonl is {"u": ..., "a": ...} shaped."""
    src = _write(
        tmp_path,
        "buf.jsonl",
        [
            {"u": "What makes a self-improving system safe?", "a": "Control: sandboxing, limits."},
            {"u": "short", "a": "also short"},
        ],
    )

    text, stats = curate_message_stream([src], drop_roles=())
    assert "sandboxing" in text
    assert stats.records_read == 2


def test_tiny_messages_are_dropped(tmp_path):
    rec = {"messages": [{"role": "assistant", "content": "ok"}]}
    src = _write(tmp_path, "brain.jsonl", [rec])

    text, stats = curate_message_stream([src], drop_roles=(), min_msg_chars=12)
    assert text.strip() == ""
    assert stats.dropped_empty == 1


def test_role_markers_are_emitted(tmp_path):
    rec = {
        "messages": [
            {"role": "user", "content": "eine ausreichend lange Frage hier"},
            {"role": "assistant", "content": "eine ausreichend lange Antwort hier"},
        ]
    }
    src = _write(tmp_path, "brain.jsonl", [rec])

    text, _ = curate_message_stream([src], drop_roles=())
    assert "<|user|> " in text
    assert "<|assistant|> " in text


def test_stats_ratios_are_consistent(tmp_path):
    rec = {"messages": [{"role": "assistant", "content": "y" * 400}]}
    src = _write(tmp_path, "brain.jsonl", [rec])

    _, stats = curate_message_stream([src], drop_roles=(), max_msg_chars=100)
    d = stats.as_dict()
    assert 0.0 < d["kept_ratio"] <= 1.0
    assert d["chars_kept"] <= d["chars_seen"]
    assert d["messages_kept"] == 1


def test_missing_source_is_ignored(tmp_path):
    text, stats = curate_message_stream([tmp_path / "nope.jsonl"])
    assert text == ""
    assert stats == CurationStats()


def test_default_sources_includes_dropin_dir(tmp_path):
    home = tmp_path / "home"
    (home / "a2a").mkdir(parents=True)
    extra = tmp_path / "dropin"
    extra.mkdir()
    (extra / "notes.md").write_text("hello", encoding="utf-8")

    srcs = default_sources(home, extra)
    names = [p.name for p in srcs]
    assert "openamer-brain.jsonl" in names
    assert "notes.md" in names


def test_bad_json_lines_are_kept_verbatim(tmp_path):
    p = tmp_path / "brain.jsonl"
    p.write_text('{"messages": []}\nnot json at all\n', encoding="utf-8")

    text, _ = curate_message_stream([p], drop_roles=())
    assert "not json at all" in text
