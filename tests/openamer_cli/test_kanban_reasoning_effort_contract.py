"""The dispatcher's ``Task`` model must expose every column it reads.

``openamer_cli.kanban_db_dispatch._worker_argv`` reads ``task.reasoning_effort``
unconditionally. The ``reasoning_effort`` column existed on the ``tasks`` table,
but the ``Task`` dataclass / ``Task.from_row`` never carried it — so *every*
dispatch of *every* card died before a worker started with

    'Task' object has no attribute 'reasoning_effort'

Worse, the flag it would then have emitted (``--reasoning <level>``) did not
exist on the ``openamer`` CLI at all, so even after mapping the attribute the
next spawn would have failed with argparse's "unrecognized arguments".

These tests pin the whole contract: the column is created, persisted, read back
onto ``Task``, forwarded as a flag the real CLI parser accepts, resolved into
the agent's reasoning config, and propagated from ``cmd_chat`` into ``cli.main``.
Column-to-field mapping is asserted as an invariant so the *next* dropped
attribute fails here instead of in the dispatcher.
"""

from __future__ import annotations

import dataclasses
import types
import sys
from pathlib import Path

import pytest

from openamer_cli import kanban_db as kb
from openamer_cli import kanban_db_dispatch as kbd
from openamer_constants import resolve_reasoning_config


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".openamer"
    home.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _create(**kwargs) -> str:
    with kb.connect() as conn:
        return kb.create_task(conn, **kwargs)


def _task(tid: str):
    with kb.connect() as conn:
        return kb.get_task(conn, tid)


# ---------------------------------------------------------------------------
# DB roundtrip
# ---------------------------------------------------------------------------

def test_reasoning_effort_roundtrips_from_db_to_task(kanban_home):
    tid = _create(title="deep card", reasoning_effort="high")

    with kb.connect() as conn:
        row = conn.execute(
            "SELECT reasoning_effort FROM tasks WHERE id = ?", (tid,)
        ).fetchone()

    assert row["reasoning_effort"] == "high"
    assert _task(tid).reasoning_effort == "high"


def test_reasoning_effort_defaults_to_none(kanban_home):
    tid = _create(title="default card")

    with kb.connect() as conn:
        row = conn.execute(
            "SELECT reasoning_effort FROM tasks WHERE id = ?", (tid,)
        ).fetchone()

    assert row["reasoning_effort"] is None
    assert _task(tid).reasoning_effort is None


def test_reasoning_effort_is_normalized(kanban_home):
    tid = _create(title="spaced", reasoning_effort="  HIGH  ")
    assert _task(tid).reasoning_effort == "high"


def test_reasoning_effort_rejects_unknown_level(kanban_home):
    # A typo here would otherwise only surface as a failed worker spawn.
    with pytest.raises(ValueError, match="reasoning_effort must be one of"):
        _create(title="typo", reasoning_effort="hgih")


def test_reasoning_effort_accepts_disable_level(kanban_home):
    tid = _create(title="no thinking", reasoning_effort="none")
    assert _task(tid).reasoning_effort == "none"


def test_reasoning_effort_column_exists_on_a_fresh_db(kanban_home):
    """The live ``init_db`` migration must add it — the split's copy alone
    never reached the DB the dispatcher opens."""
    with kb.connect() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(tasks)")}

    assert "reasoning_effort" in cols


def test_every_tasks_column_is_mapped_on_task(kanban_home):
    """Invariant, not a snapshot: a new column must be mapped or explicitly
    declared as raw-SQL-only, so the dispatcher can never read a missing
    attribute again."""
    # Columns read via raw SQL + ``_row_get`` and never as ``Task.<attr>``.
    raw_sql_only = {"worker_started_at"}

    with kb.connect() as conn:
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(tasks)")}

    fields = {f.name for f in dataclasses.fields(kb.Task)}
    missing = columns - fields - raw_sql_only
    assert not missing, (
        f"tasks columns not carried on Task: {sorted(missing)} — add them to "
        "the dataclass and Task.from_row (or to the raw_sql_only allowlist if "
        "they are only ever read through SQL)"
    )


# ---------------------------------------------------------------------------
# dispatcher argv
# ---------------------------------------------------------------------------

def test_worker_argv_forwards_reasoning_flag(kanban_home):
    tid = _create(title="deep card", reasoning_effort="medium")
    argv = kbd._worker_argv(_task(tid), "dev", None)

    assert "--reasoning" in argv
    assert argv[argv.index("--reasoning") + 1] == "medium"


def test_worker_argv_omits_reasoning_flag_when_unset(kanban_home):
    tid = _create(title="default card")
    argv = kbd._worker_argv(_task(tid), "dev", None)

    assert "--reasoning" not in argv


def test_worker_argv_is_accepted_by_the_real_cli_parser(kanban_home):
    """The regression that made the attribute fix insufficient on its own.

    ``-p <profile>`` is stripped by ``openamer_cli.main``'s pre-argparse profile
    scanner, so it is removed here too; every remaining token must be a flag
    ``build_top_level_parser()`` actually understands.
    """
    from openamer_cli._parser import build_top_level_parser

    tid = _create(title="deep card", reasoning_effort="high")
    argv = kbd._worker_argv(_task(tid), "dev", None)

    # argv[0] is the resolved `openamer` executable; argparse's prog is implicit.
    tokens = list(argv[1:])
    # Drop the `-p <profile>` pair the pre-argparse scanner consumes.
    assert "-p" in tokens
    profile_at = tokens.index("-p")
    assert tokens[profile_at + 1] == "dev"
    parseable = tokens[:profile_at] + tokens[profile_at + 2:]

    parser, _subparsers, _chat_parser = build_top_level_parser()
    # Must not raise SystemExit(2) "unrecognized arguments".
    args = parser.parse_args(parseable)

    assert args.reasoning_effort == "high"
    assert args.command == "chat"
    assert args.query == f"work kanban task {tid}"


def test_reasoning_flag_parses_before_and_after_the_subcommand():
    from openamer_cli._parser import build_top_level_parser

    parser, _subparsers, _chat_parser = build_top_level_parser()

    before = parser.parse_args(["--reasoning", "high", "chat", "-q", "x"])
    after = parser.parse_args(["chat", "-q", "x", "--reasoning", "low"])

    assert before.reasoning_effort == "high"
    assert after.reasoning_effort == "low"


def test_reasoning_flag_absent_leaves_attribute_unset_for_config_fallback():
    from openamer_cli._parser import build_top_level_parser

    parser, _subparsers, _chat_parser = build_top_level_parser()
    args = parser.parse_args(["chat", "-q", "x"])

    assert getattr(args, "reasoning_effort", None) is None


# ---------------------------------------------------------------------------
# resolution + propagation into the agent
# ---------------------------------------------------------------------------

def test_resolve_reasoning_config_honours_override():
    assert resolve_reasoning_config({}, "", override="high") == {
        "enabled": True, "effort": "high",
    }


def test_resolve_reasoning_config_override_can_disable_thinking():
    assert resolve_reasoning_config({}, "", override="none") == {"enabled": False}


def test_resolve_reasoning_config_override_beats_per_model_and_global():
    cfg = {
        "agent": {
            "reasoning_effort": "low",
            "reasoning_overrides": {"some-model": "minimal"},
        }
    }
    assert resolve_reasoning_config(cfg, "some-model", override="ultra") == {
        "enabled": True, "effort": "ultra",
    }


def test_resolve_reasoning_config_without_override_is_unchanged():
    cfg = {"agent": {"reasoning_effort": "low"}}
    assert resolve_reasoning_config(cfg, "") == {"enabled": True, "effort": "low"}
    assert resolve_reasoning_config({}, "", override=None) is None


def test_cmd_chat_forwards_reasoning_effort_to_cli_main(monkeypatch):
    """``openamer --reasoning LEVEL`` must reach ``cli.main`` (and from there
    ``OpenAmerCLI``/``resolve_reasoning_config``) — not be dropped on the floor.
    """
    import openamer_cli.main as main_mod
    from openamer_cli._parser import build_top_level_parser

    parser, _subparsers, chat_parser = build_top_level_parser()
    chat_parser.set_defaults(func=main_mod.cmd_chat)
    args = parser.parse_args(["--reasoning", "high", "chat", "-q", "x"])

    captured: dict = {}
    fake_cli = types.ModuleType("cli")
    fake_cli.main = lambda **kwargs: captured.update(kwargs)
    fake_banner = types.ModuleType("openamer_cli.banner")
    fake_banner.prefetch_update_check = lambda: None
    fake_skills_sync = types.ModuleType("tools.skills_sync")
    fake_skills_sync.sync_skills = lambda quiet=True: None

    monkeypatch.setitem(sys.modules, "cli", fake_cli)
    monkeypatch.setitem(sys.modules, "openamer_cli.banner", fake_banner)
    monkeypatch.setitem(sys.modules, "tools.skills_sync", fake_skills_sync)
    monkeypatch.setattr(main_mod, "_has_any_provider_configured", lambda: True)
    monkeypatch.setattr(main_mod, "_pin_kanban_board_env", lambda: None)

    main_mod.cmd_chat(args)

    assert captured["reasoning_effort"] == "high"


def test_cmd_chat_omits_reasoning_effort_when_flag_absent(monkeypatch):
    import openamer_cli.main as main_mod
    from openamer_cli._parser import build_top_level_parser

    parser, _subparsers, chat_parser = build_top_level_parser()
    chat_parser.set_defaults(func=main_mod.cmd_chat)
    args = parser.parse_args(["chat", "-q", "x"])

    captured: dict = {}
    fake_cli = types.ModuleType("cli")
    fake_cli.main = lambda **kwargs: captured.update(kwargs)
    fake_banner = types.ModuleType("openamer_cli.banner")
    fake_banner.prefetch_update_check = lambda: None
    fake_skills_sync = types.ModuleType("tools.skills_sync")
    fake_skills_sync.sync_skills = lambda quiet=True: None

    monkeypatch.setitem(sys.modules, "cli", fake_cli)
    monkeypatch.setitem(sys.modules, "openamer_cli.banner", fake_banner)
    monkeypatch.setitem(sys.modules, "tools.skills_sync", fake_skills_sync)
    monkeypatch.setattr(main_mod, "_has_any_provider_configured", lambda: True)
    monkeypatch.setattr(main_mod, "_pin_kanban_board_env", lambda: None)

    main_mod.cmd_chat(args)

    assert captured.get("reasoning_effort") is None


# ---------------------------------------------------------------------------
# CLI flag on `kanban create`
# ---------------------------------------------------------------------------

def test_kanban_create_accepts_reasoning_flag(kanban_home, tmp_path, capsys):
    import argparse

    from openamer_cli import kanban as kanban_cli

    wrap = argparse.ArgumentParser(add_help=False)
    parser = kanban_cli.build_parser(wrap.add_subparsers(dest="_top"))
    args = parser.parse_args([
        "create", "cli flagged card",
        "--workspace", f"dir:{tmp_path / 'ws'}",
        "--reasoning", "high",
    ])

    assert kanban_cli.kanban_command(args) == 0

    with kb.connect() as conn:
        row = conn.execute(
            "SELECT id FROM tasks ORDER BY created_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
    assert _task(row["id"]).reasoning_effort == "high"
