"""Spawn a child that cannot outlive its caller.

Measured gap (missions/beyond-all P2.1, case T1): kill an agent process while it
runs a foreground tool call and the tool's own children keep running. Nothing
reaps them — they hold ports, locks and CPU until they finish on their own, and
the retry has to contend with them. That is a real leak, not a cosmetic one.

The fix is the OS-level primitive instead of a signal handler (a SIGKILLed
caller runs no handler at all):

* **Windows** — a Job Object with ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``. The
  kernel terminates every member when the last handle to the job closes, and
  the handle lives in the caller, so the caller's death tears the tree down.
* **POSIX** — ``prctl(PR_SET_PDEATHSIG, SIGKILL)`` in the child, set between
  fork and exec.

Deliberately NOT used for daemons: :func:`openamer_cli._subprocess_compat.windows_detach_flags`
exists for the opposite intent (a gateway that must survive its launcher).
Use this module only for work whose lifetime is the caller's.

Known limit: on Windows the child is assigned *after* ``CreateProcess``
returns, so a child that spawns its own children in the first microseconds can
race the assignment. Everything it spawns later inherits job membership.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

# Win32 constants (documented in winnt.h / jobapi2.h)
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JobObjectExtendedLimitInformation = 9
_PR_SET_PDEATHSIG = 1


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class KillOnCloseJob:
    """A Job Object whose members die when this handle is closed."""

    def __init__(self) -> None:
        if not IS_WINDOWS:
            raise NotImplementedError("KillOnCloseJob is a Windows-only primitive")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = self._kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = self._kernel32.SetInformationJobObject(
            wintypes.HANDLE(handle),
            _JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            self._kernel32.CloseHandle(wintypes.HANDLE(handle))
            raise ctypes.WinError(ctypes.get_last_error())
        self._handle = handle

    def assign(self, proc: subprocess.Popen) -> None:
        """Put an already-started child into the job."""
        ok = self._kernel32.AssignProcessToJobObject(
            wintypes.HANDLE(self._handle), wintypes.HANDLE(int(proc._handle))  # noqa: SLF001 — subprocess has no public accessor
        )
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(wintypes.HANDLE(self._handle))
            self._handle = 0

    def __enter__(self) -> "KillOnCloseJob":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259


def process_alive(pid: int) -> bool:
    """True while ``pid`` is a live process. Locale-independent on Windows.

    Reading ``tasklist`` output was the previous approach: it needs the system
    code page (a German Windows returns bytes that fail UTF-8 decoding) and a
    failed decode silently looks like "process gone". OpenProcess +
    GetExitCodeProcess answers the question without text at all.
    """
    if pid <= 0:
        return False
    if IS_WINDOWS:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(wintypes.HANDLE(handle), ctypes.byref(code)):
                return False
            return code.value == _STILL_ACTIVE
        finally:
            kernel32.CloseHandle(wintypes.HANDLE(handle))
    return Path(f"/proc/{pid}").exists()


def _posix_pdeathsig() -> None:
    """Child-side hook: SIGKILL when the parent dies."""
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(_PR_SET_PDEATHSIG, 9)  # 9 == SIGKILL
    except Exception:
        pass  # best effort; the caller keeps its normal lifetime semantics


def spawn_kill_on_close(argv: list[str], *, job: KillOnCloseJob | None = None, **kwargs) -> subprocess.Popen:
    """Start ``argv`` so that it cannot outlive the calling process.

    Returns the ``Popen``. Keep the returned job (when one is created here) alive
    for as long as the child should live: pass ``job=`` to own it yourself, or
    let this function create a job that closes when the ``Popen`` object is
    garbage-collected together with the process.
    """
    if IS_WINDOWS:
        proc = subprocess.Popen(argv, **kwargs)
        own_job = job is None
        the_job = job or KillOnCloseJob()
        try:
            the_job.assign(proc)
        except Exception:
            if own_job:
                the_job.close()
            proc.kill()
            raise
        if own_job:
            # keep the handle attached to the Popen so both die together
            proc._openamer_job = the_job  # noqa: SLF001 — lifetime marker
        return proc
    kwargs.setdefault("preexec_fn", _posix_pdeathsig)
    return subprocess.Popen(argv, **kwargs)
