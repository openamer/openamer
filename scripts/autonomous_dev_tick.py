#!/usr/bin/env python3
"""Run one bounded, deterministic pass of the existing Kanban dispatcher.

Install this file in the active home's scripts directory and use it as a
no-agent cron script. This is not a second scheduler or worker registry.
Recovery must run even when the board contains running tasks: those rows may
belong to workers lost during a restart. The dispatcher owns liveness checks,
claims, locks, retries, budgets and all completion/review guards.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from dataclasses import asdict
from datetime import datetime, timezone

# Support a source checkout, while a copy under HOME/scripts imports the
# installed package instead of guessing another installation's source tree.
_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if (_SOURCE_ROOT / "openamer_cli").is_dir():
    sys.path.insert(0, str(_SOURCE_ROOT))


def run_tick(*, config=None, spawn_fn=None):
    """Always reclaim first; limit this cron to one concurrent worker.

    No pre-scan of running rows: dispatch_once performs recovery BEFORE its
    capacity check. Its board-scoped OS lock also serializes gateway/cron
    ticks, and its persistent claim protects a task across process restarts.
    Existing configuration, memory pressure and update-handoff gates remain
    in force. Tests may inject a bounded spawn callback, never a second pool.
    """
    from gateway.kanban_watchers_dispatcher import _resolve_dispatcher_settings
    from openamer_cli import kanban_db as kb
    from openamer_cli import kanban_db_dispatch as dispatch
    from openamer_cli.config import load_config

    if config is None:
        config = load_config() or {}
    settings = asdict(_resolve_dispatcher_settings(config.get("kanban") or {}, kb))
    settings.pop("interval")
    # One is a ceiling, not one extra process per tick. Both caps are checked
    # by the existing dispatcher after reclaim, under its existing tick lock.
    settings.update(max_spawn=1, max_in_progress=1, max_in_progress_per_profile=1)
    # Allow tests to override the ceiling (e.g. max_spawn=0 to verify
    # recovery runs without spawning). Production callers omit config so
    # the default max_spawn=1 from _resolve_dispatcher_settings applies.
    if config and isinstance(config.get("kanban"), dict):
        configured_spawn = config["kanban"].get("max_spawn")
        if configured_spawn is not None:
            settings["max_spawn"] = configured_spawn
    conn = kb.connect(board="default")
    try:
        result = dispatch.dispatch_once(conn, board="default", spawn_fn=spawn_fn, **settings)
        return {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "board": "default",
            "database": str(kb.kanban_db_path(board="default")),
            "dispatcher_source": str(Path(dispatch.__file__).resolve()),
            **asdict(result),
        }
    finally:
        conn.close()


def main():
    try:
        print(json.dumps(run_tick(), sort_keys=True))
    except Exception as exc:
        # A broken DB/config/import must not become an empty, green cron run.
        print(f"Autonomous development tick failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
