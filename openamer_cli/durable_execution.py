"""Durable Execution — checkpoint/resume for agent sessions.

Survives crashes: the agent periodically snapshots its state, and
``openamer --resume`` picks up from the last checkpoint.

Design:
- Checkpoints are stored under ``~/.openamer/checkpoints/<session_id>/``
- Each checkpoint is a numbered JSON file (``0001.json``, ``0002.json``, …)
- At most N checkpoints are kept (configurable, default 10)
- On resume, the agent loads the latest checkpoint and replays from there
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CHECKPOINT_DIR = Path.home() / ".openamer" / "checkpoints"
_MAX_CHECKPOINTS = 10
_CHECKPOINT_INTERVAL = 60  # seconds between automatic checkpoints
_CHECKPOINT_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Checkpoint:
    """A single checkpoint snapshot of an agent session."""

    number: int
    session_id: str
    timestamp: str
    messages: List[Dict[str, Any]]
    tool_states: Dict[str, Any]
    memory_state: Dict[str, Any]
    context_summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(**data)


# ---------------------------------------------------------------------------
# Checkpoint storage
# ---------------------------------------------------------------------------


def _session_checkpoint_dir(session_id: str) -> Path:
    """Return the checkpoint directory for a given session."""
    d = _CHECKPOINT_DIR / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _checkpoint_path(session_dir: Path, number: int) -> Path:
    return session_dir / f"{number:04d}.json"


def _latest_checkpoint_number(session_dir: Path) -> Optional[int]:
    """Return the highest checkpoint number in the directory, or None."""
    if not session_dir.exists():
        return None
    numbers = []
    for f in session_dir.iterdir():
        if f.suffix == ".json" and f.stem.isdigit():
            numbers.append(int(f.stem))
    return max(numbers) if numbers else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_checkpoint(
    session_id: str,
    messages: List[Dict[str, Any]],
    tool_states: Optional[Dict[str, Any]] = None,
    memory_state: Optional[Dict[str, Any]] = None,
    context_summary: str = "",
) -> int:
    """Save a checkpoint of the current session state.

    Returns the checkpoint number.
    """
    with _CHECKPOINT_LOCK:
        session_dir = _session_checkpoint_dir(session_id)
        latest = _latest_checkpoint_number(session_dir)
        number = (latest or 0) + 1

        checkpoint = Checkpoint(
            number=number,
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            messages=messages,
            tool_states=tool_states or {},
            memory_state=memory_state or {},
            context_summary=context_summary,
        )

        path = _checkpoint_path(session_dir, number)
        path.write_text(
            json.dumps(checkpoint.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

        # Prune old checkpoints
        _prune_old(session_dir)

        logger.info("Checkpoint %d saved for session %s", number, session_id)
        return number


def load_latest_checkpoint(session_id: str) -> Optional[Checkpoint]:
    """Load the latest checkpoint for a session.

    Returns ``None`` if no checkpoints exist.
    """
    session_dir = _session_checkpoint_dir(session_id)
    latest = _latest_checkpoint_number(session_dir)
    if latest is None:
        return None

    path = _checkpoint_path(session_dir, latest)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Checkpoint.from_dict(data)
    except (json.JSONDecodeError, KeyError, FileNotFoundError) as exc:
        logger.error("Failed to load checkpoint %d: %s", latest, exc)
        return None


def list_checkpoints(session_id: str) -> List[Dict[str, Any]]:
    """List all checkpoints for a session with metadata."""
    session_dir = _session_checkpoint_dir(session_id)
    results = []
    if not session_dir.exists():
        return results
    for f in sorted(session_dir.iterdir()):
        if f.suffix == ".json" and f.stem.isdigit():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append({
                    "number": data.get("number", int(f.stem)),
                    "timestamp": data.get("timestamp", ""),
                    "message_count": len(data.get("messages", [])),
                    "size": f.stat().st_size,
                })
            except Exception:
                pass
    return results


def clear_checkpoints(session_id: str) -> bool:
    """Delete all checkpoints for a session.

    Returns True if any were deleted.
    """
    session_dir = _CHECKPOINT_DIR / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir)
        logger.info("Cleared checkpoints for session %s", session_id)
        return True
    return False


def auto_checkpoint(
    session_id: str,
    messages: List[Dict[str, Any]],
    tool_states: Optional[Dict[str, Any]] = None,
    memory_state: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Auto-checkpoint if enough time has passed since the last one.

    Call this periodically (e.g. after every turn). Returns the checkpoint
    number if one was saved, or None if it was too soon.
    """
    last_cp = _latest_checkpoint_number(_session_checkpoint_dir(session_id))
    if last_cp is not None:
        session_dir = _session_checkpoint_dir(session_id)
        path = _checkpoint_path(session_dir, last_cp)
        if path.exists():
            age = time.time() - path.stat().st_mtime
            if age < _CHECKPOINT_INTERVAL:
                return None  # too soon

    return save_checkpoint(
        session_id=session_id,
        messages=messages,
        tool_states=tool_states,
        memory_state=memory_state,
    )


def has_checkpoints(session_id: str) -> bool:
    """Return True if the session has any saved checkpoints."""
    return _latest_checkpoint_number(_session_checkpoint_dir(session_id)) is not None


def get_checkpoint_stats() -> Dict[str, Any]:
    """Return aggregate statistics about all stored checkpoints."""
    if not _CHECKPOINT_DIR.exists():
        return {"total_sessions": 0, "total_checkpoints": 0, "total_size_bytes": 0}

    total_sessions = 0
    total_checkpoints = 0
    total_size = 0

    for entry in _CHECKPOINT_DIR.iterdir():
        if entry.is_dir():
            total_sessions += 1
            for f in entry.iterdir():
                if f.suffix == ".json":
                    total_checkpoints += 1
                    total_size += f.stat().st_size

    return {
        "total_sessions": total_sessions,
        "total_checkpoints": total_checkpoints,
        "total_size_bytes": total_size,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _prune_old(session_dir: Path) -> None:
    """Remove oldest checkpoints when over the limit."""
    checkpoints = sorted(
        [f for f in session_dir.iterdir() if f.suffix == ".json" and f.stem.isdigit()],
        key=lambda f: int(f.stem),
    )
    while len(checkpoints) > _MAX_CHECKPOINTS:
        oldest = checkpoints.pop(0)
        oldest.unlink()
        logger.info("Pruned old checkpoint %s", oldest.name)


def resolve_checkpoint_for_resume(session_id: str) -> Optional[tuple]:
    """Resolve the checkpoint to resume from.

    Returns ``(checkpoint_number, messages)`` or ``None`` if nothing to resume.
    """
    cp = load_latest_checkpoint(session_id)
    if cp is None:
        return None
    return (cp.number, cp.messages)


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------


def cmd_checkpoint(args) -> None:
    """Handle ``openamer checkpoint <subcommand>``."""
    action = getattr(args, "checkpoint_action", None)

    if action == "list":
        session_id = getattr(args, "session_id", "")
        if session_id:
            cps = list_checkpoints(session_id)
            if cps:
                print(f"Checkpoints for session {session_id}:")
                for cp in cps:
                    print(f"  #{cp['number']}: {cp['timestamp']} — {cp['message_count']} messages, {cp['size']} bytes")
            else:
                print(f"No checkpoints for session {session_id}.")
        else:
            stats = get_checkpoint_stats()
            print(f"Checkpoint storage: {stats['total_sessions']} sessions, "
                  f"{stats['total_checkpoints']} checkpoints, "
                  f"{stats['total_size_bytes'] / 1024:.1f} KB")

    elif action == "clear":
        session_id = getattr(args, "session_id", "")
        if clear_checkpoints(session_id):
            print(f"Cleared checkpoints for session {session_id}.")
        else:
            print(f"No checkpoints found for session {session_id}.")

    elif action == "stats":
        stats = get_checkpoint_stats()
        print("Checkpoint Statistics:")
        print(f"  Sessions with checkpoints: {stats['total_sessions']}")
        print(f"  Total checkpoints: {stats['total_checkpoints']}")
        print(f"  Total storage: {stats['total_size_bytes'] / 1024:.1f} KB")

    else:
        print("Usage: openamer checkpoint <list|clear|stats> [session_id]")


def build_checkpoint_parser(subparsers) -> None:
    """Add the ``openamer checkpoint`` subcommand."""
    parser = subparsers.add_parser(
        "checkpoint",
        help="Manage session checkpoints for durable execution",
        description=(
            "Create, list, and manage session checkpoints so agent work "
            "survives crashes and can be resumed."
        ),
    )
    sub = parser.add_subparsers(dest="checkpoint_action")

    # list
    list_parser = sub.add_parser("list", help="List checkpoints")
    list_parser.add_argument(
        "session_id",
        nargs="?",
        default="",
        help="Session ID to list (omit for aggregate stats)",
    )

    # clear
    clear_parser = sub.add_parser("clear", help="Clear checkpoints for a session")
    clear_parser.add_argument("session_id", help="Session ID to clear")

    # stats
    sub.add_parser("stats", help="Show checkpoint storage statistics")

    parser.set_defaults(func=cmd_checkpoint)