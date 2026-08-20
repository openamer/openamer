"""Recording and playback system for desktop automation via computer_use.

Provides:
- `ComputerUseRecording` dataclass for a sequence of actions
- `RecordingStore` for persistent JSON storage under ~/.openamer/recordings/
- `record_actions()` interactive context manager for capturing actions
- `play_recording()` to replay a recorded sequence with delays
- `play_recording_cron()` to schedule a recording as a cron job
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ComputerUseAction:
    """A single recorded computer_use action.

    Mirrors the fields of a ``computer_use`` tool call. Only the fields
    relevant to the action type are populated; others stay ``None``.
    """

    action: str  # capture, click, double_click, right_click, scroll, type, key, wait, focus_app, set_value
    coordinate: Optional[List[int]] = None      # [x, y] for pixel-targeted actions
    element: Optional[int] = None               # 1-based SOM index for element-targeted actions
    text: Optional[str] = None                  # text for action='type'
    keys: Optional[str] = None                  # key combo for action='key'
    delay: float = 1.0                          # seconds to wait AFTER this action completes
    button: Optional[str] = None                # left | right | middle
    direction: Optional[str] = None             # up | down | left | right (scroll)
    amount: Optional[int] = None                # scroll wheel ticks
    value: Optional[str] = None                 # set_value payload
    app: Optional[str] = None                    # focus_app target
    modifiers: Optional[List[str]] = None        # modifier keys
    delivery_mode: Optional[str] = None           # background | foreground


@dataclass
class ComputerUseRecording:
    """A complete recording of computer_use actions."""

    name: str
    actions: List[ComputerUseAction] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    description: str = ""


# ---------------------------------------------------------------------------
# Recording store
# ---------------------------------------------------------------------------

_RECORDINGS_DIR = Path.home() / ".openamer" / "recordings"


def _ensure_recordings_dir() -> Path:
    """Create the recordings directory if it doesn't exist."""
    _RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return _RECORDINGS_DIR


class RecordingStore:
    """Persistent storage for computer_use recordings.

    Recordings are stored as individual JSON files under
    ``~/.openamer/recordings/<name>.json``.
    """

    @staticmethod
    def _recording_path(name: str) -> Path:
        return _ensure_recordings_dir() / f"{name}.json"

    @staticmethod
    def save(recording: ComputerUseRecording) -> Path:
        """Save a recording to disk.

        Returns the path of the saved file.
        """
        recording.updated_at = datetime.now().isoformat()
        path = RecordingStore._recording_path(recording.name)
        data = asdict(recording)
        # Convert actions from dataclass to dicts manually for clean JSON
        data["actions"] = [
            {k: v for k, v in asdict(a).items() if v is not None}
            for a in recording.actions
        ]
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info("Recording saved to %s", path)
        return path

    @staticmethod
    def load(name: str) -> Optional[ComputerUseRecording]:
        """Load a recording by name.

        Returns ``None`` if the recording doesn't exist.
        """
        path = RecordingStore._recording_path(name)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            actions = [
                ComputerUseAction(**a) for a in data.get("actions", [])
            ]
            return ComputerUseRecording(
                name=data.get("name", name),
                actions=actions,
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                description=data.get("description", ""),
            )
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.error("Failed to load recording %s: %s", name, exc)
            return None

    @staticmethod
    def list_recordings() -> List[Dict[str, Any]]:
        """List all stored recordings.

        Returns a list of dicts with name, action_count, created_at, updated_at.
        """
        recordings_dir = _ensure_recordings_dir()
        result: List[Dict[str, Any]] = []
        for fpath in sorted(recordings_dir.glob("*.json")):
            name = fpath.stem
            rec = RecordingStore.load(name)
            if rec is not None:
                result.append({
                    "name": rec.name,
                    "action_count": len(rec.actions),
                    "created_at": rec.created_at,
                    "updated_at": rec.updated_at,
                    "description": rec.description,
                })
        return result

    @staticmethod
    def delete(name: str) -> bool:
        """Delete a recording by name.

        Returns ``True`` if the recording was deleted, ``False`` if not found.
        """
        path = RecordingStore._recording_path(name)
        if not path.exists():
            return False
        path.unlink()
        logger.info("Recording %s deleted", name)
        return True


# ---------------------------------------------------------------------------
# Recording context manager
# ---------------------------------------------------------------------------

def record_actions(
    name: str,
    description: str = "",
) -> ComputerUseRecording:
    """Interactive recording session.

    Prompts the user for one action per line. Returns after an empty line.
    The user types commands like::

        click 5              → click element #5
        click 100,200        → click at pixel coordinate (100, 200)
        double-click 3       → double-click element #3
        right-click 7        → right-click element #7
        type Hello World     → type "Hello World"
        key ctrl+s           → press key combo ctrl+s
        scroll down 3        → scroll down 3 ticks
        scroll up            → scroll up (default 3 ticks)
        wait 2.5             → wait 2.5 seconds
        capture              → take a screenshot (annotation step)
        focus_app Safari     → focus the Safari app
        set_value element 5  → set value on element #5 (prompted after)
        delay 2              → set default delay for subsequent actions
        # comment            → ignored line
        <empty line>         → stop recording

    Returns the populated ``ComputerUseRecording``.
    """
    recording = ComputerUseRecording(name=name, description=description)
    current_delay = 1.0

    print(f"\n  Recording '{name}' — enter actions one per line.")
    print("  Empty line to stop. 'help' for command reference.\n")

    while True:
        try:
            line = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            # Empty line → stop recording
            break

        if line.lower() in ("help", "?"):
            _print_help()
            continue

        if line.startswith("#"):
            continue

        action = _parse_action_line(line, current_delay)
        if action is not None:
            recording.actions.append(action)
            print(f"    ✓ {action.action}"
                  + (f" element={action.element}" if action.element is not None else "")
                  + (f" at {action.coordinate}" if action.coordinate else "")
                  + (f" text={action.text!r}" if action.text else "")
                  + (f" keys={action.keys!r}" if action.keys else "")
                  + (f" delay={action.delay}s" if action.delay != current_delay else "")
                  )
            # Update current delay if this was an explicit delay command
            tokens = line.lower().split()
            if tokens and tokens[0] == "delay":
                try:
                    current_delay = float(tokens[1])
                except (IndexError, ValueError):
                    pass

    print(f"\n  Recording '{name}' complete — {len(recording.actions)} action(s).")
    return recording


def _print_help() -> None:
    """Print the interactive recording command reference."""
    print("""
  Commands:
    click <element|'x,y'>     Click element by SOM index or pixel coordinate
    double-click <el|'x,y'>   Double-click
    right-click <el|'x,y'>    Right-click
    type <text>               Type text
    key <combo>               Key combo (e.g. ctrl+s, enter, tab)
    scroll <dir> [amount]     Scroll up/down/left/right (default amount=3)
    wait <seconds>            Pause (max 30)
    capture                   Screenshot capture
    focus_app <name>          Focus an application
    set_value <value> [el]    Set value on element
    delay <seconds>           Set default delay (persists for subsequent actions)
    #                        Comment (ignored)
    <empty>                   Stop recording
""")


def _parse_action_line(line: str, default_delay: float) -> Optional[ComputerUseAction]:
    """Parse a single user-typed action line into a ``ComputerUseAction``.

    Returns ``None`` if the line can't be parsed (error already printed).
    """
    tokens = shlex.split(line)
    if not tokens:
        return None

    cmd = tokens[0].lower()
    args = tokens[1:]

    try:
        if cmd in ("click", "double_click", "right_click", "double-click", "right-click"):
            # Normalize dashed variants
            actual_cmd = cmd.replace("-", "_")
            if cmd == "double-click":
                actual_cmd = "double_click"
            elif cmd == "right-click":
                actual_cmd = "right_click"

            action = ComputerUseAction(action=actual_cmd, delay=default_delay)
            if args:
                raw = args[0]
                if "," in raw:
                    parts = raw.split(",")
                    action.coordinate = [int(parts[0].strip()), int(parts[1].strip())]
                else:
                    try:
                        action.element = int(raw)
                    except ValueError:
                        print(f"    ✗ Cannot parse target: {raw!r} (expected element index or x,y)")
                        return None
            return action

        if cmd == "type":
            text = " ".join(args) if args else ""
            if not text:
                print("    ✗ type requires text argument")
                return None
            return ComputerUseAction(action="type", text=text, delay=default_delay)

        if cmd == "key":
            keys = args[0] if args else ""
            if not keys:
                print("    ✗ key requires a key combo (e.g. 'enter', 'ctrl+s')")
                return None
            return ComputerUseAction(action="key", keys=keys, delay=default_delay)

        if cmd == "scroll":
            direction = args[0].lower() if args else "down"
            if direction not in ("up", "down", "left", "right"):
                print(f"    ✗ Invalid scroll direction: {direction!r} (use up/down/left/right)")
                return None
            amount = int(args[1]) if len(args) > 1 and args[1].isdigit() else 3
            return ComputerUseAction(
                action="scroll", direction=direction, amount=amount, delay=default_delay,
            )

        if cmd == "wait":
            seconds = float(args[0]) if args else 1.0
            seconds = max(0.0, min(seconds, 30.0))
            return ComputerUseAction(action="wait", delay=0.0, text=str(seconds))

        if cmd == "capture":
            return ComputerUseAction(action="capture", delay=default_delay)

        if cmd in ("focus_app", "focus"):
            app_name = args[0] if args else ""
            if not app_name:
                print("    ✗ focus_app requires an app name")
                return None
            return ComputerUseAction(action="focus_app", app=app_name, delay=default_delay)

        if cmd == "set_value":
            if not args:
                print("    ✗ set_value requires a value and optionally an element index")
                return None
            value = args[0]
            element = int(args[1]) if len(args) > 1 else None
            return ComputerUseAction(action="set_value", value=value, element=element, delay=default_delay)

        if cmd == "delay":
            try:
                new_delay = float(args[0])
                print(f"    Default delay set to {new_delay}s")
                # This action doesn't create a recorded step — just sets the default
                return None
            except (IndexError, ValueError):
                print(f"    ✗ delay requires a number (seconds)")
                return None

        print(f"    ✗ Unknown command: {cmd!r} (type 'help' for available commands)")
        return None

    except (IndexError, ValueError) as exc:
        print(f"    ✗ Parse error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------

def play_recording(name: str, *, verbose: bool = True) -> bool:
    """Replay a recorded sequence of computer_use actions.

    Args:
        name: The recording name to replay.
        verbose: If True, print progress for each action.

    Returns:
        ``True`` on success, ``False`` if the recording wasn't found or
        the backend couldn't be started.
    """
    recording = RecordingStore.load(name)
    if recording is None:
        print(f"Recording '{name}' not found.")
        print("Available recordings:")
        for r in RecordingStore.list_recordings():
            print(f"  - {r['name']} ({r['action_count']} actions)")
        return False

    # Start the computer_use backend
    from tools.computer_use.tool import _get_backend, reset_backend_for_tests

    try:
        backend = _get_backend()
    except Exception as exc:
        print(f"Failed to start computer_use backend: {exc}")
        return False

    if verbose:
        print(f"\n  Playing recording '{name}' ({len(recording.actions)} actions)...\n")

    try:
        for i, step in enumerate(recording.actions, start=1):
            if verbose:
                _print_step_progress(i, step)

            _execute_action(backend, step)

            # Apply delay after action
            if step.delay > 0:
                if verbose and step.action != "wait":
                    print(f"    (waiting {step.delay}s...)")
                time.sleep(step.delay)

        if verbose:
            print(f"\n  ✓ Playback of '{name}' complete.")
        return True

    except Exception as exc:
        print(f"\n  ✗ Playback failed at action {i}: {exc}")
        return False
    finally:
        reset_backend_for_tests()


def _execute_action(backend: Any, step: ComputerUseAction) -> None:
    """Execute a single recorded action against the backend."""
    action = step.action

    if action == "capture":
        backend.capture(mode="som", app=step.app)
        return

    if action in ("click", "double_click", "right_click", "middle_click"):
        click_count = 2 if action == "double_click" else 1
        button = {"right_click": "right", "middle_click": "middle"}.get(action, step.button or "left")
        backend.click(
            element=step.element,
            x=step.coordinate[0] if step.coordinate else None,
            y=step.coordinate[1] if step.coordinate else None,
            button=button,
            click_count=click_count,
            modifiers=step.modifiers,
            delivery_mode=step.delivery_mode,
        )
        return

    if action == "type":
        backend.type_text(
            step.text or "",
            delivery_mode=step.delivery_mode,
        )
        return

    if action == "key":
        backend.key(
            step.keys or "",
            delivery_mode=step.delivery_mode,
        )
        return

    if action == "scroll":
        backend.scroll(
            direction=step.direction or "down",
            amount=step.amount or 3,
            element=step.element,
            modifiers=step.modifiers,
            delivery_mode=step.delivery_mode,
        )
        return

    if action == "wait":
        seconds = float(step.text or 1.0)
        backend.wait(seconds)
        return

    if action == "focus_app":
        backend.focus_app(step.app or "")
        return

    if action == "set_value":
        backend.set_value(step.value or "", element=step.element)
        return


def _print_step_progress(i: int, step: ComputerUseAction) -> None:
    """Print human-readable progress for a playback step."""
    parts = [f"  [{i}] {step.action}"]
    if step.element is not None:
        parts.append(f"element={step.element}")
    if step.coordinate:
        parts.append(f"at={step.coordinate}")
    if step.text:
        parts.append(f"text={step.text!r}")
    if step.keys:
        parts.append(f"keys={step.keys!r}")
    if step.app:
        parts.append(f"app={step.app!r}")
    if step.direction:
        parts.append(f"dir={step.direction}")
    if step.amount:
        parts.append(f"amount={step.amount}")
    print("  " + " ".join(parts))


# ---------------------------------------------------------------------------
# Cron scheduling
# ---------------------------------------------------------------------------

def play_recording_cron(
    recording_name: str,
    schedule: str,
    *,
    job_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Schedule a recording as a cron job.

    Creates a cron job that runs ``openamer computer-use play <recording_name>``
    on the given schedule.

    Args:
        recording_name: Name of the recording to play.
        schedule: Cron schedule expression (e.g. ``"every 1h"``, ``"0 9 * * *"``).
        job_name: Optional friendly job name (defaults to ``play-<recording_name>``).

    Returns:
        The result dict from ``cron.jobs.create_job``.

    Raises:
        FileNotFoundError: If the recording doesn't exist.
        ImportError: If the cron module can't be imported.
    """
    # Verify the recording exists before scheduling
    recording = RecordingStore.load(recording_name)
    if recording is None:
        raise FileNotFoundError(
            f"Recording '{recording_name}' not found. "
            "Create it first with: openamer computer-use record"
        )

    from cron.jobs import create_job

    final_name = job_name or f"play-{recording_name}"
    script = f"openamer computer-use play {shlex.quote(recording_name)}"

    result = create_job(
        prompt="",
        schedule=schedule,
        name=final_name,
        script=script,
        no_agent=True,
        repeat=None,
        deliver="local",
    )
    return result


# ---------------------------------------------------------------------------
# CLI Entry points
# ---------------------------------------------------------------------------

def cmd_record(args: Any) -> None:
    """Handle ``openamer computer-use record <name>``."""
    name = args.recording_name

    existing = RecordingStore.load(name)
    if existing is not None:
        print(f"Recording '{name}' already exists ({len(existing.actions)} actions).")
        ans = input("  Overwrite? [y/N]: ").strip().lower()
        if ans not in ("y", "yes"):
            print("  Cancelled.")
            return

    description = getattr(args, "description", "")
    recording = record_actions(name, description=description)

    if recording.actions:
        RecordingStore.save(recording)
        print(f"  Saved to ~/.openamer/recordings/{name}.json")
    else:
        print("  No actions recorded — nothing saved.")


def cmd_play(args: Any) -> None:
    """Handle ``openamer computer-use play <name>``."""
    name = args.recording_name
    success = play_recording(name)
    sys.exit(0 if success else 1)


def cmd_list_recordings(args: Any) -> None:
    """Handle ``openamer computer-use list``."""
    recordings = RecordingStore.list_recordings()
    if not recordings:
        print("  No recordings found.")
        print("  Create one with: openamer computer-use record <name>")
        return

    print(f"\n  Recordings ({len(recordings)}):")
    print(f"  {'Name':<24} {'Actions':<9} {'Created'}")
    print(f"  {'─'*24} {'─'*9} {'─'*24}")
    for r in recordings:
        created = r["created_at"][:19] if r["created_at"] else "?"
        print(f"  {r['name']:<24} {r['action_count']:<9} {created}")
    print()


def cmd_delete_recording(args: Any) -> None:
    """Handle ``openamer computer-use delete <name>``."""
    name = args.recording_name
    if not RecordingStore.delete(name):
        print(f"Recording '{name}' not found.")
        sys.exit(1)
    print(f"Recording '{name}' deleted.")


def cmd_schedule_recording(args: Any) -> None:
    """Handle ``openamer computer-use schedule <name> <schedule>``."""
    recording_name = args.recording_name
    schedule = args.schedule

    try:
        result = play_recording_cron(
            recording_name=recording_name,
            schedule=schedule,
            job_name=getattr(args, "job_name", None),
        )
    except FileNotFoundError as exc:
        print(f"  {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"  Failed to schedule: {exc}")
        sys.exit(1)

    print(f"  ✓ Scheduled playback of '{recording_name}' as cron job:")
    print(f"    Job ID: {result.get('job_id', '?')}")
    print(f"    Name:   {result.get('name', '?')}")
    print(f"    Schedule: {result.get('schedule', schedule)}")
    print(f"    Next run: {result.get('next_run_at', '?')}")