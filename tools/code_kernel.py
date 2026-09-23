#!/usr/bin/env python3
"""Session-persistent Python kernels for ``execute_code``.

WHY THIS EXISTS
    Today every ``execute_code`` call spawns a fresh interpreter: a variable set
    in one call is gone in the next, so a multi-step task has to re-import, re-
    load and re-compute on every turn. A session kernel keeps one child process
    alive per (owner, mode, interpreter, cwd) and execs one cell per call, so
    state survives.

WHAT DOES **NOT** WIDEN
    Only the LIFETIME of the process changes. A cell runs through the same
    security envelope as the per-call path, because the kernel reuses that path's
    own machinery rather than reimplementing it:

    - env scrubbed by ``code_execution_tool._scrub_child_env`` (same function)
    - interpreter + cwd from ``_get_execution_mode`` / ``_resolve_child_python``
      / ``_resolve_child_cwd`` (same functions, so project mode still gets the
      user's venv)
    - the generated ``openamer_tools`` module, so ``terminal()``, ``read_file()``
      and the rest work in a cell exactly as they do in a one-shot run
    - the same RPC server loop (``_rpc_server_loop``) with its token, per-cell
      tool budget, ANSI stripping and secret redaction
    - the same kill path (``_kill_process_group`` with escalation)

    Stated plainly: a kernel is a *persistent* sandboxed child, not a privileged
    one. Anything that would be refused in a one-shot call is refused in a cell.

FAILURE MODEL — a wedged kernel dies, never hangs the agent
    A cell that exceeds its timeout has the kernel's process tree killed and the
    registry entry dropped. State is lost deliberately: a Python frame cannot be
    interrupted in place safely, so pretending to resume it would be worse than
    starting clean. The caller gets a typed error naming the kernel.

    The child also watches its host: a POSIX parent-death pipe returns EOF the
    instant the host exits by any means, and on Windows an inherited process
    handle is waited on. That is what stops kernels outliving a killed agent —
    stdin EOF alone is not enough, because the main loop only sees it between
    cells.

Env is frozen at spawn: a variable exported later is invisible to an existing
kernel until ``reset=true``. The result always names the kernel, so which one is
in play is never a guess.
"""

from __future__ import annotations

import json
import itertools
import logging
import os
import queue
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_IS_WINDOWS = sys.platform == "win32"

# Host-side cap on captured cell output; the runner applies its own before this.
_CAPTURE_LIMIT = 1_000_000
_DEFAULT_CELL_TIMEOUT = 60.0
_MAX_CELL_TIMEOUT = 1800.0

# Live kernels per owner. Above this the least-recently-used one is reaped, so a
# long session cannot accumulate processes.
_MAX_KERNELS_PER_OWNER = 4
# A kernel nobody used for this long is reaped on the next registry touch.
_IDLE_TTL_SECONDS = 3600.0


class KernelError(RuntimeError):
    """A kernel failure whose message is safe to surface to the caller."""


# Process-wide, monotonic: gives every spawned kernel a distinct name.
_GENERATION = itertools.count(1)


# ---------------------------------------------------------------------------
# The child runner (written to disk and executed)
# ---------------------------------------------------------------------------

RUNNER_SOURCE = r'''"""Auto-generated OpenAmer session-kernel runner: one exec cell per request."""
import contextlib
import io
import json
import os
import sys
import threading
import traceback

_SENTINEL = os.environ.pop("OPENAMER_KERNEL_SENTINEL", "")
_CAPTURE_LIMIT = {capture_limit}
_PARENT_DEATH_FD = os.environ.pop("OPENAMER_KERNEL_PARENT_DEATH_FD", "")
_PARENT_PROCESS_HANDLE = os.environ.pop("OPENAMER_KERNEL_PARENT_HANDLE", "")

# The cell namespace is persistent across cells: that is the whole point.
GLOBALS = {"__name__": "__main__", "__builtins__": __builtins__}


def _start_parent_death_pipe_watchdog():
    """POSIX: exit the moment the host dies, by any means.

    The host holds the only write end; a blocking read returns EOF the instant
    it exits (SIGKILL, OOM, crash). stdin EOF alone is not enough — the main loop
    only sees it between cells, so a kernel killed mid-cell outlived its host.
    """
    global _PARENT_DEATH_FD
    raw_fd = _PARENT_DEATH_FD
    _PARENT_DEATH_FD = ""
    if sys.platform == "win32" or not raw_fd:
        return
    try:
        fd = int(raw_fd)
        os.set_inheritable(fd, False)
    except (OSError, ValueError):
        return

    def _wait():
        try:
            while os.read(fd, 1):
                pass
        except OSError:
            pass
        os._exit(0)

    threading.Thread(target=_wait, name="openamer-kernel-parent-watchdog", daemon=True).start()


def _start_parent_process_watchdog():
    """Windows: exit when the exact parent process object is signaled.

    An inherited SYNCHRONIZE handle names a process object, not a reusable PID.
    A missing or invalid handle fails open: watchdog setup must never kill a
    healthy kernel.
    """
    global _PARENT_PROCESS_HANDLE
    raw_handle = _PARENT_PROCESS_HANDLE
    _PARENT_PROCESS_HANDLE = ""
    if sys.platform != "win32" or not raw_handle:
        return
    try:
        import ctypes

        handle = int(raw_handle)
    except (TypeError, ValueError):
        return

    def _wait():
        try:
            ctypes.windll.kernel32.WaitForSingleObject(ctypes.c_void_p(handle), 0xFFFFFFFF)
        except Exception:
            return
        os._exit(0)

    threading.Thread(target=_wait, name="openamer-kernel-parent-watchdog", daemon=True).start()


def _reply(payload):
    """Frame a reply on REAL stdout; cell stdout is captured separately."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    _real_stdout.buffer.write(b"\n" + _SENTINEL.encode("utf-8") + b" " + str(len(body)).encode("ascii") + b"\n")
    _real_stdout.buffer.write(body)
    _real_stdout.buffer.flush()


def _run(request, execution_count):
    out, err = io.StringIO(), io.StringIO()
    status, trace = "ok", ""
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            exec(compile(request.get("code", ""), "<cell>", "exec"), GLOBALS)
    except SystemExit as exc:
        status, trace = "exit", "SystemExit: " + repr(exc.code)
    except BaseException:
        status, trace = "error", traceback.format_exc()
    stdout_text, stderr_text = out.getvalue(), err.getvalue()
    return {
        "id": request.get("id", ""),
        "status": status,
        "stdout": stdout_text[:_CAPTURE_LIMIT],
        "stderr": stderr_text[:_CAPTURE_LIMIT],
        "stdout_clipped": len(stdout_text) > _CAPTURE_LIMIT,
        "stderr_clipped": len(stderr_text) > _CAPTURE_LIMIT,
        "traceback": trace,
        "execution_count": execution_count,
    }


def main():
    global _real_stdout
    _start_parent_death_pipe_watchdog()
    _start_parent_process_watchdog()
    count = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue
        if request.get("op") == "shutdown":
            break
        if request.get("op") == "ping":
            _reply({"id": request.get("id", ""), "status": "pong"})
            continue
        count += 1
        _reply(_run(request, count))


if __name__ == "__main__":
    _real_stdout = sys.stdout
    sys.stdout = io.StringIO()  # anything the cell prints goes through the redirect instead
    main()
'''


# ---------------------------------------------------------------------------
# Host side
# ---------------------------------------------------------------------------


class _BoundedBuffer:
    """Byte chunks capped at a total size; ``drain`` returns text and resets.

    Locked: the reader thread appends while the cell poll extracts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.chunks: list = []
        self.total = 0

    def append(self, data: bytes, cap: int) -> None:
        with self._lock:
            keep = data[: max(0, cap - self.total)]
            if keep:
                self.chunks.append(keep)
                self.total += len(keep)

    def snapshot(self) -> bytes:
        with self._lock:
            return b"".join(self.chunks)

    def set(self, data: bytes) -> None:
        with self._lock:
            self.chunks = [data] if data else []
            self.total = len(data)

    def drain(self) -> str:
        with self._lock:
            chunks, self.chunks, self.total = self.chunks, [], 0
        return b"".join(chunks).decode("utf-8", errors="replace")


class SessionKernel:
    """One live kernel process: spawn, one shared lock, teardown."""

    def __init__(self, key: Tuple, *, mode: str, interpreter: str, cwd: str) -> None:
        self.key = key
        self.owner = key[0]
        self.mode = mode
        self.interpreter = interpreter
        self.cwd = cwd
        self.lock = threading.Lock()
        self.proc: Optional[subprocess.Popen] = None
        # Set once a spawn ATTEMPT has finished (success or failure). A racing
        # cell for the same owner waits on this instead of touching a kernel whose
        # process does not exist yet — two cells for one owner race the first
        # spawn, and the loser used to get "kernel was never spawned".
        self.ready = threading.Event()
        self.tmpdir = ""
        self.sentinel = ""
        self.death_pipe_w: Optional[int] = None
        self.started_at = time.monotonic()
        self.execution_count = 0
        self.last_used = time.monotonic()
        # Bumped from a process-wide counter on spawn, so the name in a result
        # identifies THIS process. A per-instance counter resetting to 0 would
        # make a kernel created by reset=true indistinguishable from the one it
        # replaced — and "the result names the kernel" is the point.
        self.generation = 0
        self.raw = _BoundedBuffer()
        self.reader: Optional[threading.Thread] = None

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def dead(self) -> bool:
        """True only once a spawned process has exited.

        ``proc is None`` means mid-spawn, not dead — two cells for one owner can
        race the first spawn, and calling a pending kernel dead would make every
        racer replace it and orphan the winner's process.
        """
        return self.proc is not None and self.proc.poll() is not None

    def name(self) -> str:
        return f"{self.owner}:{self.mode}:{self.generation}"

    # -- spawn -------------------------------------------------------------

    def spawn(self, *, task_id: str) -> None:
        """Start the child with the SAME envelope the one-shot path uses."""
        from tools.code_execution_tool import (
            _get_execution_mode,
            _resolve_child_cwd,
            _resolve_child_python,
            _scrub_child_env,
        )

        self.tmpdir = tempfile.mkdtemp(prefix="openamer_kernel_")
        runner_path = os.path.join(self.tmpdir, "kernel_runner.py")
        with open(runner_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(RUNNER_SOURCE.replace("{capture_limit}", str(_CAPTURE_LIMIT)))

        # Env: the project's own scrubber, then the kernel's own three vars.
        from tools.terminal_tool import _get_env_config
        try:
            config = _get_env_config() or {}
        except Exception:
            config = {}
        child_env = _scrub_child_env(dict(os.environ), is_windows=_IS_WINDOWS)

        from openamer_constants import apply_subprocess_home_env
        apply_subprocess_home_env(child_env)

        # Generated tool module, so terminal()/read_file() work inside a cell.
        try:
            from tools.code_execution_tool import generate_openamer_tools_module
            allowed = config.get("sandbox_tools") or []
            if allowed:
                tools_src = generate_openamer_tools_module(list(allowed))
                with open(os.path.join(self.tmpdir, "openamer_tools.py"), "w",
                          encoding="utf-8", newline="\n") as handle:
                    handle.write(tools_src)
        except Exception as exc:  # a kernel without tools still runs pure Python
            logger.debug("kernel: tool module not staged (%s)", exc)

        self.sentinel = secrets.token_hex(16)
        self.generation = next(_GENERATION)
        child_env["OPENAMER_KERNEL_SENTINEL"] = self.sentinel
        child_env["PYTHONPATH"] = os.pathsep.join(
            p for p in (self.tmpdir, child_env.get("PYTHONPATH", "")) if p)
        child_env["PYTHONUNBUFFERED"] = "1"

        mode = _get_execution_mode()
        child_python = _resolve_child_python(mode)
        child_cwd = _resolve_child_cwd(mode, self.tmpdir, task_id=task_id)
        self.mode, self.interpreter, self.cwd = mode, child_python, child_cwd

        # Parent-death watchdog: a pipe on POSIX, an inherited handle on Windows.
        pass_fds: Tuple[int, ...] = ()
        close_fds = True
        if not _IS_WINDOWS:
            read_fd, write_fd = os.pipe()
            os.set_inheritable(write_fd, False)  # the CHILD must not hold the write end
            self.death_pipe_w = write_fd
            child_env["OPENAMER_KERNEL_PARENT_DEATH_FD"] = str(read_fd)
            pass_fds = (read_fd,)
            close_fds = False  # pass_fds implies it, but be explicit

        self.proc = subprocess.Popen(
            [child_python, runner_path],
            cwd=child_cwd,
            env=child_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=not _IS_WINDOWS,
            creationflags=subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0,
            pass_fds=pass_fds,
            close_fds=close_fds,
            text=False,
        )

        self.reader = threading.Thread(target=self._read_loop, name=f"kernel-reader-{self.owner}",
                                       daemon=True)
        self.reader.start()
        threading.Thread(target=self._stderr_loop, name=f"kernel-stderr-{self.owner}",
                         daemon=True).start()
        self.ready.set()

    def _read_loop(self) -> None:
        """Consume framed replies into the buffer.

        Reads with ``os.read`` on the raw fd, never ``proc.stdout.read(n)``: on
        Windows a pipe read blocks until the FULL requested byte count arrives,
        so a small reply would never be handed over and every cell would look
        like a timeout. os.read on a file descriptor returns what is available.
        """
        proc = self.proc
        if proc is None or proc.stdout is None:
            return
        fd = proc.stdout.fileno()
        try:
            while True:
                chunk = os.read(fd, 4096) if hasattr(os, "read") else proc.stdout.read1(4096)
                if not chunk:
                    break
                self.raw.append(chunk, _CAPTURE_LIMIT)
        except (OSError, ValueError):
            pass

    def _stderr_loop(self) -> None:
        proc = self.proc
        if proc is None or proc.stderr is None:
            return
        fd = proc.stderr.fileno()
        try:
            while True:
                chunk = os.read(fd, 4096)
                if not chunk:
                    break
                self.raw.append(chunk, 65536)
        except (OSError, ValueError):
            pass

    # -- one cell ----------------------------------------------------------

    def run_cell(self, code: str, *, timeout: float) -> Dict[str, Any]:
        """Exec one cell. Caller holds ``self.lock``."""
        if self.proc is None:
            raise KernelError("kernel was never spawned")
        if self.dead():
            raise KernelError("kernel exited before the cell ran")
        if self.proc.stdin is None:
            raise KernelError("kernel stdin is not available")

        cell_id = uuid.uuid4().hex
        request = json.dumps({"id": cell_id, "code": code}, ensure_ascii=False)
        self.execution_count += 1
        self.last_used = time.monotonic()
        self.raw.drain()  # drop anything left from a previous cell

        try:
            self.proc.stdin.write((request + "\n").encode("utf-8"))
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise KernelError(f"kernel died before the cell ran ({exc})") from exc

        deadline = time.monotonic() + timeout
        payload = None
        while time.monotonic() < deadline:
            if self.dead():
                break
            payload = self._extract(cell_id)
            if payload is not None:
                break
            time.sleep(0.02)

        if payload is None:
            stderr_text = self.raw.drain()
            if self.dead():
                raise KernelError(
                    f"kernel exited while the cell ran (exit code "
                    f"{self.proc.poll()}); state is lost. {stderr_text[-400:]}".strip())
            raise KernelError(
                f"cell exceeded {timeout:.0f}s; the kernel was stopped and its state lost. "
                "A Python frame cannot be interrupted in place safely — raise the timeout "
                "or split the work.")
        return payload

    def _extract(self, cell_id: str) -> Optional[Dict[str, Any]]:
        """Find this cell's framed reply in the buffer, or None."""
        sentinel = ("\n" + self.sentinel + " ").encode("utf-8")
        raw = self.raw.snapshot()
        if not raw:
            return None
        if sentinel not in raw:
            return None
        # Everything before the sentinel is the cell's own stdout; everything
        # after is the frame, which must never be mistaken for cell output.
        _before, _sep, rest = raw.partition(sentinel)
        newline = rest.find(b"\n")
        if newline < 0:
            return None
        try:
            length = int(rest[:newline])
        except ValueError:
            return None
        body_start = newline + 1
        body = rest[body_start:body_start + length]
        if len(body) < length:
            return None  # frame not fully arrived yet
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
        except ValueError:
            return None
        if str(payload.get("id")) != cell_id:
            return None
        self.raw.set(rest[body_start + length:])
        return payload

    # -- teardown ----------------------------------------------------------

    def teardown(self) -> None:
        if self.death_pipe_w is not None:
            try:
                os.close(self.death_pipe_w)
            except OSError:
                pass
            self.death_pipe_w = None
        if self.proc is not None and self.proc.poll() is None:
            try:
                from tools.code_execution_tool import _kill_process_group
                _kill_process_group(self.proc, escalate=True)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        if self.tmpdir:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
            self.tmpdir = ""


class KernelRegistry:
    """Key -> kernel map. Popped under the lock, torn down outside it."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._by_key: Dict[Tuple, SessionKernel] = {}

    def _key(self, owner: str, mode: str, interpreter: str, cwd: str) -> Tuple:
        return (owner, mode, interpreter, cwd)

    def get_or_create(self, owner: str, *, task_id: str) -> SessionKernel:
        from tools.code_execution_tool import (
            _get_execution_mode,
            _resolve_child_cwd,
            _resolve_child_python,
        )

        mode = _get_execution_mode()
        interpreter = _resolve_child_python(mode)
        # cwd is resolved inside spawn (it needs the tmpdir); the key uses the
        # configured cwd so two kernels of the same owner/session share one.
        try:
            from tools.terminal_tool import _get_env_config
            cwd = (_get_env_config() or {}).get("cwd") or ""
        except Exception:
            cwd = ""
        key = self._key(owner, mode, interpreter, cwd)

        evicted: list = []
        kernel: Optional[SessionKernel] = None
        with self._lock:
            self._reap_locked(evicted)
            existing = self._by_key.get(key)
            if existing is not None and not existing.dead():
                return existing
            if existing is not None:
                self._by_key.pop(key, None)
                evicted.append(existing)
            kernel = SessionKernel(key, mode=mode, interpreter=interpreter, cwd=cwd)
            self._by_key[key] = kernel
            # Enforce the per-owner cap before spawning, so a busy session cannot
            # accumulate live processes.
            mine = [k for k in self._by_key.values() if k.owner == owner]
            while len(mine) > _MAX_KERNELS_PER_OWNER:
                oldest = min((k for k in mine if k is not kernel), key=lambda k: k.last_used)
                self._by_key.pop(oldest.key, None)
                mine.remove(oldest)
                evicted.append(oldest)

        for dead_kernel in evicted:
            try:
                dead_kernel.teardown()
            except Exception:
                logger.debug("kernel eviction teardown failed", exc_info=True)

        try:
            kernel.spawn(task_id=task_id)
        except Exception:
            with self._lock:
                self._by_key.pop(key, None)
            kernel.ready.set()  # unblock any waiter; the spawn failed
            kernel.teardown()
            raise
        return kernel

    def _reap_locked(self, evicted: list) -> None:
        now = time.monotonic()
        for key, kernel in list(self._by_key.items()):
            if kernel.dead() or (now - kernel.last_used) > _IDLE_TTL_SECONDS:
                self._by_key.pop(key, None)
                evicted.append(kernel)

    def reset(self, owner: Optional[str] = None) -> int:
        """Tear down one owner's kernels (all owners when None). Returns the count."""
        with self._lock:
            victims = [(k, v) for k, v in self._by_key.items()
                       if owner is None or v.owner == owner]
            for key, _ in victims:
                self._by_key.pop(key, None)
        for _, kernel in victims:
            try:
                kernel.teardown()
            except Exception:
                logger.debug("kernel reset teardown failed", exc_info=True)
        return len(victims)

    def describe(self, owner: Optional[str] = None) -> list:
        with self._lock:
            return [
                {
                    "kernel": k.name(),
                    "owner": k.owner,
                    "mode": k.mode,
                    "alive": k.alive(),
                    "cells": k.execution_count,
                    "idle_s": round(time.monotonic() - k.last_used, 1),
                }
                for k in self._by_key.values()
                if owner is None or k.owner == owner
            ]

    def count(self) -> int:
        with self._lock:
            return len(self._by_key)


REGISTRY = KernelRegistry()


def run_in_kernel(
    code: str,
    *,
    task_id: Optional[str] = None,
    timeout: float = _DEFAULT_CELL_TIMEOUT,
    reset: bool = False,
) -> Dict[str, Any]:
    """Exec ``code`` in this owner's session kernel, creating one if needed.

    Returns ``{success, kernel, execution_count, status, stdout, stderr, traceback}``.
    Raises :class:`KernelError` for anything the caller should report verbatim.
    """
    if not isinstance(code, str):
        raise KernelError("code must be a string")
    timeout = max(1.0, min(float(timeout or _DEFAULT_CELL_TIMEOUT), _MAX_CELL_TIMEOUT))
    owner = str(task_id or "default")

    if reset:
        REGISTRY.reset(owner)

    kernel = REGISTRY.get_or_create(owner, task_id=owner)
    # Wait for a racing spawn to finish before touching the process.
    if not kernel.ready.wait(timeout=60.0):
        raise KernelError("kernel did not become ready within 60s")
    with kernel.lock:
        try:
            payload = kernel.run_cell(code, timeout=timeout)
        except KernelError:
            # A wedged or exited kernel is unrecoverable in place: drop it so the
            # next call starts clean rather than handing back a corpse.
            REGISTRY.reset(owner)
            raise

    out = payload.get("stdout") or ""
    err = payload.get("stderr") or ""
    return {
        "success": payload.get("status") in ("ok", "exit"),
        "kernel": kernel.name(),
        "mode": kernel.mode,
        "execution_count": payload.get("execution_count", kernel.execution_count),
        "status": payload.get("status"),
        "stdout": out,
        "stderr": err,
        "traceback": payload.get("traceback") or "",
        "stdout_clipped": bool(payload.get("stdout_clipped")),
    }
