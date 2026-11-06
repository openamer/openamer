"""Durable Execution — checkpoint/resume for agent sessions and multi-step runs.

Survives crashes: state is snapshotted to the *active profile's* home
directory, every write is an atomic replace, and a restarted process can tell
the difference between work that completed, work that failed retryably, and
work whose external effect may or may not have landed.

Storage layout (all under ``get_openamer_home() / "checkpoints"``)::

    <home>/checkpoints/<session_id>/0001.json     session snapshots
    <home>/checkpoints/runs/<run_id>/run.json      step journal (one file)

Design notes
------------
- **Profile-safe.** The store root is resolved through
  :func:`openamer_constants.get_openamer_home` on every call. It is never
  captured at import time, so ``OPENAMER_HOME`` / ``--profile`` always wins and
  two profiles can never read each other's state.
- **Atomic.** Snapshots are written to a sibling temp file, fsynced, then
  ``os.replace``-d into place. A crash mid-write leaves the previous snapshot
  byte-for-byte intact; the loader also falls back past a corrupt newest file
  instead of discarding the whole history.
- **Validated.** Payloads carry a schema version and profile identity. A
  payload from another schema (or another profile's home) is rejected instead
  of being silently coerced into a ``Checkpoint``.
- **Honest about effects.** A checkpoint alone cannot make a remote effect
  exactly-once. :meth:`DurableRun.run_step` therefore records step *intent*
  before the effect and refuses to replay a step whose external effect was
  interrupted, because it cannot know whether the effect landed. Callers
  resolve that state explicitly with :meth:`DurableRun.resolve_ambiguous`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Version of the on-disk payload contract. Bump only for breaking changes.
CHECKPOINT_SCHEMA_VERSION = 2

#: Oldest schema version this build can still read.
_MIN_SUPPORTED_SCHEMA_VERSION = 1

#: Test/embedding override for the store root. ``None`` means "resolve the
#: active profile's home on every call" (the production behaviour).
_CHECKPOINT_DIR: Optional[Path] = None

_MAX_CHECKPOINTS = 10
_CHECKPOINT_INTERVAL = 60  # seconds between automatic checkpoints
_CHECKPOINT_LOCK = threading.Lock()

_RUNS_DIRNAME = "runs"
_RUN_FILENAME = "run.json"

#: ``run_id`` doubles as a directory name — keep it path-safe.
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")

#: Defence-in-depth: caller-supplied step results are persisted, so strip
#: anything that looks like a credential even though callers must not pass one.
_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|passwd|password|authorization|cookie|"
    r"private[_-]?key|credential|session[_-]?key)",
    re.IGNORECASE,
)

_MAX_STRING_CHARS = 4096
_MAX_RESULT_BYTES = 256 * 1024
_MAX_REDACT_DEPTH = 12

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DurableExecutionError(Exception):
    """Base class for durable-execution contract violations."""


class CheckpointValidationError(DurableExecutionError):
    """A stored payload is unreadable, from another schema, or another profile."""


class AmbiguousExternalEffect(DurableExecutionError):
    """A step with a non-idempotent external effect was interrupted in flight.

    The process cannot know whether the remote side applied the effect, so
    replaying it may duplicate the effect. Resolve with
    :meth:`DurableRun.resolve_ambiguous` after checking the external system.
    """


class NonRetryableStepError(DurableExecutionError):
    """A step failed and was recorded as non-retryable."""


class ConcurrentRunError(DurableExecutionError):
    """Another executor advanced the same run journal."""


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
    schema_version: int = CHECKPOINT_SCHEMA_VERSION
    profile: str = ""
    profile_home: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        # Ignore unknown keys (``kind`` and future additive fields) so an older
        # reader never chokes on a payload it mostly understands.
        allowed = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})


class EffectClass(str, Enum):
    """How safe it is to run a step twice.

    ``NONE``
        Pure computation or a read. Repeating it is harmless.
    ``IDEMPOTENT``
        A write that converges to the same result when applied twice
        (local file replace, ``PUT`` of an absolute value). Retried after a
        crash.
    ``EXTERNAL``
        A non-idempotent effect on a system we do not control (``POST``,
        deploy, ``git push``, message send). Never replayed automatically.
    """

    NONE = "none"
    IDEMPOTENT = "idempotent"
    EXTERNAL = "external"


class StepStatus(str, Enum):
    """Persisted lifecycle of one step."""

    IN_FLIGHT = "in_flight"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Store location / identity
# ---------------------------------------------------------------------------


def _openamer_home() -> Path:
    """Return the active profile's home directory."""
    from openamer_constants import get_openamer_home

    return Path(get_openamer_home())


def _checkpoint_root() -> Path:
    """Return the checkpoint store root for the *currently active* profile."""
    if _CHECKPOINT_DIR is not None:
        return Path(_CHECKPOINT_DIR)
    return _openamer_home() / "checkpoints"


def _profile_name() -> str:
    """Return a human-readable profile name derived from the home path."""
    home = _openamer_home()
    if home.parent.name == "profiles" and home.name:
        return home.name
    return "default"


def _profile_identity() -> Dict[str, str]:
    """Return the identity fields stamped into every payload."""
    home = _openamer_home()
    try:
        resolved = str(home.resolve())
    except OSError:  # pragma: no cover - unreadable parent
        resolved = str(home)
    return {"profile": _profile_name(), "profile_home": resolved}


def _session_checkpoint_dir(session_id: str) -> Path:
    """Return the checkpoint directory for a given session."""
    _validate_component(session_id, "session_id")
    d = _checkpoint_root() / session_id
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


def _validate_component(value: str, field_name: str) -> None:
    """Reject path separators / traversal in a user-supplied identifier."""
    if not isinstance(value, str) or not value:
        raise CheckpointValidationError(f"{field_name} must be a non-empty string")
    if "/" in value or "\\" in value or value in (".", "..") or ".." in value:
        raise CheckpointValidationError(f"invalid {field_name}: {value!r}")


# ---------------------------------------------------------------------------
# Atomic persistence
# ---------------------------------------------------------------------------


def _fsync_dir(directory: Path) -> None:
    """Best-effort directory fsync so a rename survives power loss."""
    if os.name == "nt":  # Windows has no directory handles to fsync
        return
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:  # pragma: no cover - platform without dir fds
        return
    try:
        os.fsync(fd)
    except OSError:  # pragma: no cover
        pass
    finally:
        os.close(fd)


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write ``payload`` to ``path`` atomically.

    A crash before ``os.replace`` leaves the previous contents of ``path``
    untouched — the partial bytes only ever exist in the temp sibling.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, default=str, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Payload validation
# ---------------------------------------------------------------------------


def _validate_payload(
    data: Any,
    *,
    expected_kind: str,
    expected_id: Optional[str] = None,
    id_field: str = "session_id",
) -> Dict[str, Any]:
    """Validate a loaded payload against the schema and profile identity."""
    if not isinstance(data, dict):
        raise CheckpointValidationError("payload is not a JSON object")

    kind = data.get("kind", "checkpoint")
    if kind != expected_kind:
        raise CheckpointValidationError(
            f"payload kind mismatch: expected {expected_kind!r}, got {kind!r}"
        )

    raw_version = data.get("schema_version", 1)
    if not isinstance(raw_version, int) or isinstance(raw_version, bool):
        raise CheckpointValidationError(f"invalid schema_version: {raw_version!r}")
    if raw_version < _MIN_SUPPORTED_SCHEMA_VERSION:
        raise CheckpointValidationError(f"schema_version {raw_version} is too old")
    if raw_version > CHECKPOINT_SCHEMA_VERSION:
        raise CheckpointValidationError(
            f"schema_version {raw_version} is newer than this build "
            f"({CHECKPOINT_SCHEMA_VERSION}); upgrade OpenAmer to read it"
        )

    if expected_id is not None:
        stored = data.get(id_field)
        if stored != expected_id:
            raise CheckpointValidationError(
                f"{id_field} mismatch: expected {expected_id!r}, stored {stored!r}"
            )

    identity = _profile_identity()
    stored_home = data.get("profile_home")
    if stored_home and stored_home != identity["profile_home"]:
        raise CheckpointValidationError(
            "payload belongs to another profile "
            f"({stored_home!r} != {identity['profile_home']!r})"
        )
    return data


def _validate_checkpoint_payload(
    data: Any, session_id: Optional[str] = None
) -> Dict[str, Any]:
    _validate_payload(
        data,
        expected_kind="checkpoint",
        expected_id=session_id,
        id_field="session_id",
    )
    for key, types in (
        ("number", int),
        ("timestamp", str),
        ("messages", list),
        ("tool_states", dict),
        ("memory_state", dict),
    ):
        value = data.get(key)
        if not isinstance(value, types) or isinstance(value, bool):
            raise CheckpointValidationError(f"invalid or missing field {key!r}")
    return data


def _read_json(path: Path) -> Any:
    # A just-killed process (or an antivirus/indexer) can hold a Windows file
    # handle for a few milliseconds after ``os.replace``; retry briefly before
    # treating that as a corrupt payload.
    last_error: Optional[BaseException] = None
    for attempt in range(5):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.02 * (attempt + 1))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CheckpointValidationError(f"{path.name}: unreadable payload ({exc})") from exc
    raise CheckpointValidationError(f"{path.name}: file is locked ({last_error})")


# ---------------------------------------------------------------------------
# Session checkpoints — public API
# ---------------------------------------------------------------------------


def save_checkpoint(
    session_id: str,
    messages: List[Dict[str, Any]],
    tool_states: Optional[Dict[str, Any]] = None,
    memory_state: Optional[Dict[str, Any]] = None,
    context_summary: str = "",
) -> int:
    """Save a checkpoint of the current session state.

    Returns the checkpoint number. The write is atomic: an interrupted save
    cannot damage the previous checkpoint.
    """
    with _CHECKPOINT_LOCK:
        session_dir = _session_checkpoint_dir(session_id)
        latest = _latest_checkpoint_number(session_dir)
        number = (latest or 0) + 1

        identity = _profile_identity()
        checkpoint = Checkpoint(
            number=number,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            messages=messages,
            tool_states=tool_states or {},
            memory_state=memory_state or {},
            context_summary=context_summary,
            schema_version=CHECKPOINT_SCHEMA_VERSION,
            profile=identity["profile"],
            profile_home=identity["profile_home"],
        )

        payload = checkpoint.to_dict()
        payload["kind"] = "checkpoint"
        path = _checkpoint_path(session_dir, number)
        atomic_write_json(path, payload)

        # Prune old checkpoints
        _prune_old(session_dir)

        logger.info("Checkpoint %d saved for session %s", number, session_id)
        return number


def load_latest_checkpoint(
    session_id: str, *, strict: bool = False
) -> Optional[Checkpoint]:
    """Load the newest *valid* checkpoint for a session.

    A truncated or foreign newest file is skipped so the last good checkpoint
    is still usable; pass ``strict=True`` to raise instead.
    Returns ``None`` if no checkpoints exist.
    """
    session_dir = _checkpoint_root() / session_id
    if not session_dir.exists():
        return None

    numbers = sorted(
        (
            int(f.stem)
            for f in session_dir.iterdir()
            if f.suffix == ".json" and f.stem.isdigit()
        ),
        reverse=True,
    )
    for number in numbers:
        path = _checkpoint_path(session_dir, number)
        try:
            data = _read_json(path)
            _validate_checkpoint_payload(data, session_id)
            return Checkpoint.from_dict(data)
        except (CheckpointValidationError, TypeError, KeyError, FileNotFoundError) as exc:
            logger.warning("Skipping unusable checkpoint %s: %s", path.name, exc)
            if strict:
                raise CheckpointValidationError(
                    f"checkpoint {path} is unusable: {exc}"
                ) from exc
            continue
    return None


def list_checkpoints(session_id: str) -> List[Dict[str, Any]]:
    """List all checkpoints for a session with metadata."""
    session_dir = _checkpoint_root() / session_id
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
    _validate_component(session_id, "session_id")
    session_dir = _checkpoint_root() / session_id
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
    session_dir = _session_checkpoint_dir(session_id)
    last_cp = _latest_checkpoint_number(session_dir)
    if last_cp is not None:
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
    return _latest_checkpoint_number(_checkpoint_root() / session_id) is not None


def get_checkpoint_stats() -> Dict[str, Any]:
    """Return aggregate statistics about all stored checkpoints."""
    root = _checkpoint_root()
    if not root.exists():
        return {
            "total_sessions": 0,
            "total_checkpoints": 0,
            "total_size_bytes": 0,
            "root": str(root),
        }

    total_sessions = 0
    total_checkpoints = 0
    total_size = 0

    for entry in root.iterdir():
        if not entry.is_dir() or entry.name == _RUNS_DIRNAME:
            continue
        counted = False
        for f in entry.iterdir():
            if f.suffix == ".json" and f.stem.isdigit():
                counted = True
                total_checkpoints += 1
                total_size += f.stat().st_size
        if counted:
            total_sessions += 1

    return {
        "total_sessions": total_sessions,
        "total_checkpoints": total_checkpoints,
        "total_size_bytes": total_size,
        "root": str(root),
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
# Step journal — durable step results and commit boundaries
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_for_persist(value: Any, depth: int = 0) -> Any:
    """Return a JSON-safe, secret-free, size-bounded copy of ``value``."""
    if depth > _MAX_REDACT_DEPTH:
        return {"_truncated": "max depth"}
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else repr(value)
    if isinstance(value, str):
        if len(value) > _MAX_STRING_CHARS:
            return value[:_MAX_STRING_CHARS] + f"... [{len(value) - _MAX_STRING_CHARS} chars omitted]"
        return value
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if _SECRET_KEY_RE.search(key_str):
                out[key_str] = "[redacted]"
            else:
                out[key_str] = _sanitize_for_persist(item, depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_for_persist(item, depth + 1) for item in value]
    text = repr(value)
    if len(text) > _MAX_STRING_CHARS:
        text = text[:_MAX_STRING_CHARS] + "... [truncated]"
    return {"_unserializable": type(value).__name__, "repr": text}


def _bounded_result(value: Any) -> Any:
    """Sanitize and size-bound a step result before persisting it."""
    safe = _sanitize_for_persist(value)
    try:
        encoded = json.dumps(safe, allow_nan=False)
    except (TypeError, ValueError):
        return {"_unserializable": type(value).__name__, "repr": repr(value)[:512]}
    if len(encoded) > _MAX_RESULT_BYTES:
        return {
            "_truncated": f"result exceeded {_MAX_RESULT_BYTES} bytes "
                          f"({len(encoded.encode('utf-8'))} bytes)",
            "preview": encoded[:2048],
        }
    return safe


@dataclass
class StepRecord:
    """Persisted state of one step in a :class:`DurableRun`."""

    name: str
    status: str
    effect: str = EffectClass.NONE.value
    attempts: int = 0
    retryable: bool = True
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    @property
    def is_completed(self) -> bool:
        return self.status == StepStatus.COMPLETED.value

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StepRecord":
        return cls(
            name=data["name"],
            status=data["status"],
            effect=data.get("effect", EffectClass.NONE.value),
            attempts=int(data.get("attempts", 0)),
            retryable=bool(data.get("retryable", True)),
            result=data.get("result"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
        )


@dataclass
class DurableRun:
    """A crash-safe, resumable sequence of steps persisted in the profile home.

    The contract is deliberately narrow:

    - A step that reached ``completed`` is **never executed again**; its
      persisted result is returned instead.
    - A step that was ``in_flight`` when the process died is retried only when
      its effect is safe to repeat (``EffectClass.NONE`` / ``IDEMPOTENT``).
      With ``EffectClass.EXTERNAL`` the run raises
      :class:`AmbiguousExternalEffect` because the outcome is unknown — that
      is the whole point: a journal cannot promise exactly-once for a remote
      system.
    - A step that raised is recorded as ``failed`` with a ``retryable`` flag and
      the exception is re-raised to the caller.

    Only one executor may advance a run at a time. Writes are
    compare-and-swap on a ``revision`` counter, so a second process touching
    the same run fails loudly with :class:`ConcurrentRunError` instead of
    interleaving checkpoints.
    """

    run_id: str
    root: Optional[Path] = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    revision: int = 0
    steps: Dict[str, StepRecord] = field(default_factory=dict)
    reused_steps: List[str] = field(default_factory=list)
    executed_steps: List[str] = field(default_factory=list)
    _loaded: bool = False

    def __post_init__(self) -> None:
        _validate_run_id(self.run_id)
        if self.root is not None:
            self.root = Path(self.root)

    # -- paths ---------------------------------------------------------

    @property
    def run_dir(self) -> Path:
        base = self.root if self.root is not None else _checkpoint_root() / _RUNS_DIRNAME
        return Path(base) / self.run_id

    @property
    def journal_path(self) -> Path:
        return self.run_dir / _RUN_FILENAME

    # -- persistence ---------------------------------------------------

    def load(self) -> "DurableRun":
        """Read the journal from disk (no-op when it does not exist yet)."""
        path = self.journal_path
        if not path.exists():
            self._loaded = True
            return self
        data = _read_json(path)
        _validate_payload(
            data, expected_kind="durable_run", expected_id=self.run_id, id_field="run_id"
        )
        if not isinstance(data.get("steps"), dict):
            raise CheckpointValidationError("durable run journal has no steps mapping")
        self.created_at = data.get("created_at", self.created_at)
        self.updated_at = data.get("updated_at", self.updated_at)
        self.revision = int(data.get("revision", 0))
        self.steps = {
            name: StepRecord.from_dict(record)
            for name, record in data["steps"].items()
        }
        self._loaded = True
        return self

    def to_dict(self) -> Dict[str, Any]:
        identity = _profile_identity()
        return {
            "kind": "durable_run",
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "run_id": self.run_id,
            "profile": identity["profile"],
            "profile_home": identity["profile_home"],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revision": self.revision,
            "steps": {name: rec.to_dict() for name, rec in self.steps.items()},
        }

    def _persist(self) -> None:
        """Atomically write the journal, enforcing single-executor semantics."""
        on_disk = 0
        if self.journal_path.exists():
            try:
                on_disk = int(_read_json(self.journal_path).get("revision", 0))
            except (CheckpointValidationError, AttributeError, TypeError, ValueError):
                on_disk = self.revision
        if on_disk != self.revision:
            raise ConcurrentRunError(
                f"run {self.run_id!r} was advanced by another executor "
                f"(on disk revision {on_disk}, ours {self.revision})"
            )
        self.revision = on_disk + 1
        self.updated_at = _now()
        atomic_write_json(self.journal_path, self.to_dict())

    # -- execution -----------------------------------------------------

    def run_step(
        self,
        name: str,
        fn: Callable[[], Any],
        *,
        effect: Any = EffectClass.NONE,
        retryable: bool = True,
        allow_retry_failed: bool = False,
    ) -> Any:
        """Run ``fn`` at most once per successful completion of ``name``."""
        if not self._loaded:
            self.load()
        _validate_component(name, "step name")
        # An unknown effect label is treated as external: a typo must not turn
        # a non-repeatable effect into an automatically retried one.
        effect_class = _coerce_effect(effect)

        record = self.steps.get(name)
        if record is not None and record.is_completed:
            if name not in self.reused_steps:
                self.reused_steps.append(name)
            logger.info("Run %s: step %s already completed, reusing result", self.run_id, name)
            return record.result

        if record is not None and record.status == StepStatus.IN_FLIGHT.value:
            stored_effect = _coerce_effect(record.effect)
            if (
                stored_effect is EffectClass.EXTERNAL
                or effect_class is EffectClass.EXTERNAL
            ):
                raise AmbiguousExternalEffect(
                    f"step {name!r} of run {self.run_id!r} was interrupted while an "
                    "external effect was in flight; its outcome is unknown. "
                    "Verify the external system, then call "
                    f"resolve_ambiguous({name!r}, ...) before resuming."
                )
            logger.warning(
                "Run %s: step %s was in flight with a repeatable effect; retrying",
                self.run_id,
                name,
            )

        if (
            record is not None
            and record.status == StepStatus.FAILED.value
            and not record.retryable
            and not allow_retry_failed
        ):
            raise NonRetryableStepError(
                f"step {name!r} of run {self.run_id!r} failed and is marked "
                f"non-retryable ({record.error}); pass allow_retry_failed=True "
                "to override"
            )

        attempts = (record.attempts if record is not None else 0) + 1
        record = StepRecord(
            name=name,
            status=StepStatus.IN_FLIGHT.value,
            effect=effect_class.value,
            attempts=attempts,
            retryable=retryable,
            started_at=_now(),
        )
        self.steps[name] = record
        # Commit boundary: the intent is durable *before* the effect runs, so a
        # crash here is detected as in-flight rather than silently forgotten.
        self._persist()

        try:
            value = fn()
        except Exception as exc:
            # A normal failure is a known outcome: record it and surface it.
            record.status = StepStatus.FAILED.value
            record.retryable = retryable
            record.error = f"{type(exc).__name__}: {exc}"[:2048]
            record.finished_at = _now()
            self._persist()
            raise
        except BaseException:
            # KeyboardInterrupt / SystemExit / process teardown: the step's
            # outcome is unknown, so leave the durable intent record in
            # ``in_flight``. A resume then treats an external effect as
            # ambiguous instead of quietly assuming it failed.
            logger.warning(
                "Run %s: step %s interrupted mid-flight; leaving it in_flight",
                self.run_id,
                name,
            )
            raise

        record.status = StepStatus.COMPLETED.value
        record.result = _bounded_result(value)
        record.error = None
        record.finished_at = _now()
        self._persist()
        if name not in self.executed_steps:
            self.executed_steps.append(name)
        return value

    # -- inspection / recovery ----------------------------------------

    def status(self) -> Dict[str, Any]:
        """Return a JSON-safe snapshot of the run for display."""
        if not self._loaded:
            self.load()
        return {
            "run_id": self.run_id,
            "path": str(self.journal_path),
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "profile": _profile_identity()["profile"],
            "steps": [
                {
                    "name": rec.name,
                    "status": rec.status,
                    "effect": rec.effect,
                    "attempts": rec.attempts,
                    "retryable": rec.retryable,
                    "error": rec.error,
                    "started_at": rec.started_at,
                    "finished_at": rec.finished_at,
                }
                for rec in self.steps.values()
            ],
            "completed": [n for n, r in self.steps.items() if r.is_completed],
            "ambiguous": [
                n
                for n, r in self.steps.items()
                if r.status == StepStatus.IN_FLIGHT.value
                and _coerce_effect(r.effect) is EffectClass.EXTERNAL
            ],
            "failed": [
                n for n, r in self.steps.items() if r.status == StepStatus.FAILED.value
            ],
        }

    def resolve_ambiguous(
        self,
        name: str,
        *,
        resolution: str,
        result: Any = None,
    ) -> StepRecord:
        """Close an interrupted external-effect step explicitly.

        ``resolution="completed"`` records that the effect *did* land (the
        operator verified it externally) and stores ``result``.
        ``resolution="retry"`` records that the effect did not land, making the
        step retryable again.
        """
        if not self._loaded:
            self.load()
        record = self.steps.get(name)
        if record is None:
            raise KeyError(f"unknown step {name!r} in run {self.run_id!r}")
        if record.status != StepStatus.IN_FLIGHT.value:
            raise DurableExecutionError(
                f"step {name!r} is {record.status!r}, not in_flight; nothing to resolve"
            )
        if resolution == "completed":
            record.status = StepStatus.COMPLETED.value
            record.result = _bounded_result(result)
            record.error = None
        elif resolution == "retry":
            record.status = StepStatus.FAILED.value
            record.retryable = True
            record.error = "interrupted external effect resolved as not applied"
        else:
            raise ValueError("resolution must be 'completed' or 'retry'")
        record.finished_at = _now()
        self._persist()
        return record


def _coerce_effect(value: Any) -> EffectClass:
    try:
        return value if isinstance(value, EffectClass) else EffectClass(value)
    except ValueError:
        # Unknown effect labels are treated as unsafe to replay.
        return EffectClass.EXTERNAL


def _validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or not _RUN_ID_RE.match(run_id or ""):
        raise CheckpointValidationError(
            f"invalid run_id {run_id!r}: use 1-96 characters of [A-Za-z0-9._-]"
        )


def open_run(run_id: str, *, root: Optional[Path] = None) -> DurableRun:
    """Open (or create) a durable run journal for the active profile."""
    run = DurableRun(run_id=run_id, root=root)
    return run.load()


def list_runs(*, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """List durable run journals in the active profile."""
    base = Path(root) if root is not None else _checkpoint_root() / _RUNS_DIRNAME
    if not base.exists():
        return []
    results: List[Dict[str, Any]] = []
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        try:
            run = DurableRun(run_id=entry.name, root=base).load()
        except (DurableExecutionError, OSError):
            results.append({"run_id": entry.name, "error": "unreadable journal"})
            continue
        snapshot = run.status()
        results.append({
            "run_id": snapshot["run_id"],
            "updated_at": snapshot["updated_at"],
            "steps": len(snapshot["steps"]),
            "completed": len(snapshot["completed"]),
            "ambiguous": snapshot["ambiguous"],
            "failed": snapshot["failed"],
        })
    return results


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
            print(f"Checkpoint storage: {stats['root']}")
            print(f"  {stats['total_sessions']} sessions, "
                  f"{stats['total_checkpoints']} checkpoints, "
                  f"{stats['total_size_bytes'] / 1024:.1f} KB")

    elif action == "runs":
        runs = list_runs()
        if not runs:
            print("No durable runs recorded for this profile.")
            return
        for run in runs:
            if "error" in run:
                print(f"  {run['run_id']}: {run['error']}")
                continue
            flags = []
            if run["ambiguous"]:
                flags.append(f"ambiguous={','.join(run['ambiguous'])}")
            if run["failed"]:
                flags.append(f"failed={','.join(run['failed'])}")
            suffix = f"  [{' '.join(flags)}]" if flags else ""
            print(f"  {run['run_id']}: {run['completed']}/{run['steps']} steps "
                  f"completed, updated {run['updated_at']}{suffix}")

    elif action == "show":
        run_id = getattr(args, "run_id", "")
        try:
            run = open_run(run_id)
        except (DurableExecutionError, OSError) as exc:
            print(f"Cannot open run {run_id!r}: {exc}")
            return
        if not run.journal_path.exists():
            print(f"No durable run {run_id!r} for this profile.")
            return
        snapshot = run.status()
        print(f"Run {snapshot['run_id']} ({snapshot['path']})")
        for step in snapshot["steps"]:
            print(f"  {step['status']:<10} {step['name']}  attempts={step['attempts']} "
                  f"effect={step['effect']}")
            if step["error"]:
                print(f"             error: {step['error']}")
        if snapshot["ambiguous"]:
            print("Ambiguous external effects (verify externally, then resolve): "
                  + ", ".join(snapshot["ambiguous"]))

    elif action == "clear":
        session_id = getattr(args, "session_id", "")
        if clear_checkpoints(session_id):
            print(f"Cleared checkpoints for session {session_id}.")
        else:
            print(f"No checkpoints found for session {session_id}.")

    elif action == "stats":
        stats = get_checkpoint_stats()
        print("Checkpoint Statistics:")
        print(f"  Store: {stats['root']}")
        print(f"  Sessions with checkpoints: {stats['total_sessions']}")
        print(f"  Total checkpoints: {stats['total_checkpoints']}")
        print(f"  Total storage: {stats['total_size_bytes'] / 1024:.1f} KB")

    else:
        print("Usage: openamer checkpoint <list|runs|show|clear|stats> [id]")


def build_checkpoint_parser(subparsers) -> None:
    """Add the ``openamer checkpoint`` subcommand."""
    parser = subparsers.add_parser(
        "checkpoint",
        help="Inspect durable session checkpoints and run journals",
        description=(
            "Inspect the per-profile durable-execution store: agent session "
            "snapshots and the step journals written by durable runs. This is "
            "distinct from `openamer checkpoints`, which manages the filesystem "
            "rollback (shadow git) store."
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

    # runs
    sub.add_parser("runs", help="List durable run journals for this profile")

    # show
    show_parser = sub.add_parser("show", help="Show one durable run journal")
    show_parser.add_argument("run_id", help="Run ID to show")

    # clear
    clear_parser = sub.add_parser("clear", help="Clear checkpoints for a session")
    clear_parser.add_argument("session_id", help="Session ID to clear")

    # stats
    sub.add_parser("stats", help="Show checkpoint storage statistics")

    parser.set_defaults(func=cmd_checkpoint)
