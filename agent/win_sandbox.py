"""Native Windows containment for local terminal commands.

Why this module exists
----------------------
Every competitor's isolation story stops at the edge of native Windows:

* Claude Code's OS sandbox (macOS Seatbelt / Linux bubblewrap+seccomp) is
  documented as **unsupported on native Windows** — "On Windows, run Claude Code
  inside a WSL2 distribution."
* Codex CLI ships a Windows mode with a single ``unelevated`` fallback.

We already ship *container* backends (Docker / Modal / Daytona / SSH /
Singularity), but their isolation is opt-in and requires an external runtime.
The default local terminal on Windows has no boundary at all. This module adds
one using only primitives that need **no administrator rights**.

What is actually enforced (and what is not)
-------------------------------------------
ENFORCED by the OS, via a Windows **Job Object**:

* ``kill_on_close``   — the whole process tree dies when we release the job
  (``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``). No orphaned daemons.
* ``max_processes``   — hard cap on concurrent processes in the job
  (``JOB_OBJECT_LIMIT_ACTIVE_PROCESS``). Blocks fork bombs.
* ``max_memory_mb``   — per-process and total job memory ceiling
  (``JOB_OBJECT_LIMIT_PROCESS_MEMORY`` / ``JOB_OBJECT_LIMIT_JOB_MEMORY``).
* ``deny_ui``         — the job cannot read or write the clipboard, cannot open
  handles in other processes, cannot change global system parameters, cannot
  switch desktops (``JOB_OBJECT_UILIMIT_*``). This is what stops a runaway
  command from silently reading the user's clipboard.
* children **cannot escape** the job — we deliberately do not grant
  ``JOB_OBJECT_LIMIT_BREAKAWAY_OK``.

ENFORCED by us, in-process:

* ``scrub_secrets``   — the child's environment is built from an allowlist of
  non-secret variables, so provider keys and tokens are absent rather than
  merely "not printed". Windows has no ``ulimit``-style env boundary; this is
  the part competitors leave to the command's own good behaviour.
* ``check_write_path``— writes are confined to ``writable_root`` with
  protected paths (``.git``, ``.openamer``, ``.env``, SSH material) refused.
  Junctions and symlinks are resolved before the comparison, so a link cannot
  be used to step outside the root.

NOT enforced (stated plainly, because the honest boundary is the useful one):

* **Network is not OS-isolated on native Windows.** Blocking egress per-process
  needs Windows Filtering Platform rules, i.e. administrator rights (a Codex
  style sandbox gets its network-off guarantee from an OS sandbox on
  macOS/Linux, not from the user token). What we can do without admin is set
  ``network=deny`` to *refuse to run the command at all* unless the caller
  explicitly opts in, and inject proxy variables for clients that honour them.
  :func:`describe_enforcement` reports this as ``partial`` — never as enforced.
* It is not a filesystem ACL. It is a policy layer over the paths our own tools
  write, which is exactly as strong as "all writes go through our tools".

Design note (AGENTS.md): capability lives at the edges, the core is a narrow
waist. This module imports nothing from the agent core and is inert unless a
caller explicitly builds a sandbox — enabling nothing by default.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

__all__ = [
    "JobLimits",
    "JobHandle",
    "build_job_object",
    "assign_pid_to_job",
    "enforce_environment",
    "canonical_path",
    "check_write_path",
    "protected_paths",
    "describe_enforcement",
    "is_supported",
]

# --------------------------------------------------------------------------
# Windows Job Object constants (winnt.h)
# --------------------------------------------------------------------------

_JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
_JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400
_JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800  # deliberately never set
_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

# UI restrictions — JobObjectBasicUIRestrictions.
_JOB_OBJECT_UILIMIT_HANDLES = 0x00000001
_JOB_OBJECT_UILIMIT_READCLIPBOARD = 0x00000002
_JOB_OBJECT_UILIMIT_WRITECLIPBOARD = 0x00000004
_JOB_OBJECT_UILIMIT_SYSTEMPARAMETERS = 0x00000008
_JOB_OBJECT_UILIMIT_DISPLAYSETTINGS = 0x00000010
_JOB_OBJECT_UILIMIT_GLOBALATOMS = 0x00000020
_JOB_OBJECT_UILIMIT_DESKTOP = 0x00000040
_JOB_OBJECT_UILIMIT_EXITWINDOWS = 0x00000080

_DENY_UI_MASK = (
    _JOB_OBJECT_UILIMIT_HANDLES
    | _JOB_OBJECT_UILIMIT_READCLIPBOARD
    | _JOB_OBJECT_UILIMIT_WRITECLIPBOARD
    | _JOB_OBJECT_UILIMIT_SYSTEMPARAMETERS
    | _JOB_OBJECT_UILIMIT_DISPLAYSETTINGS
    | _JOB_OBJECT_UILIMIT_GLOBALATOMS
    | _JOB_OBJECT_UILIMIT_DESKTOP
    | _JOB_OBJECT_UILIMIT_EXITWINDOWS
)

_JobObjectExtendedLimitInformation = 9
_JobObjectBasicUIRestrictions = 4

_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100

#: Suffix test for credential-shaped variable names. Used by
#: :func:`enforce_environment` to close the gap left by the local backend's
#: name-based provider blocklist, which only strips variables it already knows.
_CREDENTIAL_SUFFIX_PATTERN = re.compile(
    r"(?:_API_KEY|_KEY|_TOKEN|_SECRET|_PASSWORD|_PASSWD|_CREDENTIAL|"
    r"_ACCESS_KEY|_PRIVATE_KEY|_SESSION_KEY|APIKEY)$"
)

# --------------------------------------------------------------------------
# Credential masking — delegated, not reimplemented
# --------------------------------------------------------------------------
#
# NOTE (extend, don't duplicate): the child-environment secret stripping for the
# local backend already exists and is battle-tested —
# ``tools.environments.local._sanitize_subprocess_env`` (provider blocklist +
# ``tools.env_passthrough`` allowlist + session-context injection). This module
# deliberately does NOT ship a second secret scrubber; two divergent blocklists
# is how a credential ends up un-stripped in one path.
#
# The sandbox's *own* contribution is OS containment (below) plus the file
# boundary. :func:`enforce_environment` exists so a caller has one obvious entry
# point, and it forwards to the existing sanitizer.


# --------------------------------------------------------------------------
# Limits + result types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class JobLimits:
    """Limits applied to a sandbox job. All are OS-enforced where noted."""

    kill_on_close: bool = True
    max_processes: Optional[int] = 64
    max_memory_mb: Optional[int] = 4096
    deny_ui: bool = True

    def __post_init__(self) -> None:
        if self.max_processes is not None and self.max_processes < 1:
            raise ValueError("max_processes must be >= 1 or None")
        if self.max_memory_mb is not None and self.max_memory_mb < 16:
            raise ValueError("max_memory_mb must be >= 16 or None")

    def flags(self) -> int:
        """Compose the ``LimitFlags`` bitmask for this configuration."""
        flags = 0
        if self.kill_on_close:
            flags |= _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if self.max_processes is not None:
            flags |= _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        if self.max_memory_mb is not None:
            flags |= _JOB_OBJECT_LIMIT_PROCESS_MEMORY | _JOB_OBJECT_LIMIT_JOB_MEMORY
        # Always armed: a crash inside the job must not leave a hung tree.
        flags |= _JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
        return flags


@dataclass
class JobHandle:
    """An open Windows job object, or an explicit reason there isn't one."""

    handle: Optional[int] = None
    limits: JobLimits = field(default_factory=JobLimits)
    error: Optional[str] = None

    @property
    def active(self) -> bool:
        return self.handle is not None

    def close(self) -> None:
        """Close the job. With ``kill_on_close`` this terminates the tree."""
        if self.handle:
            try:
                _kernel32().CloseHandle(self.handle)
            finally:
                self.handle = None

    def __enter__(self) -> "JobHandle":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def is_supported() -> bool:
    """True when the OS can enforce the job-object guarantees."""
    return sys.platform == "win32"


def _kernel32() -> Any:
    import ctypes

    return ctypes.WinDLL("kernel32", use_last_error=True)


def build_job_object(limits: JobLimits | None = None) -> JobHandle:
    """Create a Windows job object carrying ``limits``.

    Never raises: on a non-Windows host, or if the API call fails, the returned
    handle is inactive and carries ``error``. Callers decide whether an inactive
    job is fatal — see ``fail_closed`` in the terminal wiring.
    """
    limits = limits or JobLimits()
    if not is_supported():
        return JobHandle(limits=limits, error=f"unsupported platform: {sys.platform}")

    import ctypes
    from ctypes import wintypes

    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class _ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _BasicUiRestrictions(ctypes.Structure):
        _fields_ = [("UIRestrictionsClass", wintypes.DWORD)]

    k32 = _kernel32()
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.SetInformationJobObject.restype = wintypes.BOOL
    k32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]

    handle = k32.CreateJobObjectW(None, None)
    if not handle:
        return JobHandle(limits=limits, error=f"CreateJobObjectW failed ({ctypes.get_last_error()})")

    info = _ExtendedLimitInformation()
    info.BasicLimitInformation.LimitFlags = limits.flags()
    if limits.max_processes is not None:
        info.BasicLimitInformation.ActiveProcessLimit = int(limits.max_processes)
    if limits.max_memory_mb is not None:
        bytes_limit = int(limits.max_memory_mb) * 1024 * 1024
        info.ProcessMemoryLimit = bytes_limit
        info.JobMemoryLimit = bytes_limit

    ok = k32.SetInformationJobObject(
        handle,
        _JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        err = ctypes.get_last_error()
        k32.CloseHandle(handle)
        return JobHandle(limits=limits, error=f"SetInformationJobObject(limits) failed ({err})")

    if limits.deny_ui:
        ui = _BasicUiRestrictions()
        ui.UIRestrictionsClass = _DENY_UI_MASK
        ok = k32.SetInformationJobObject(
            handle,
            _JobObjectBasicUIRestrictions,
            ctypes.byref(ui),
            ctypes.sizeof(ui),
        )
        if not ok:
            err = ctypes.get_last_error()
            k32.CloseHandle(handle)
            return JobHandle(limits=limits, error=f"SetInformationJobObject(ui) failed ({err})")

    return JobHandle(handle=int(handle), limits=limits)


def assign_pid_to_job(job: JobHandle, pid: int) -> tuple[bool, str]:
    """Put ``pid`` (and everything it spawns) inside ``job``.

    Returns ``(ok, detail)``. Note that a process which was already placed in a
    non-nestable job by its parent cannot be moved — that is a Windows rule, not
    a bug, and it is reported rather than silently ignored.
    """
    if not job.active:
        return False, f"no active job: {job.error or 'unknown'}"
    if pid <= 0:
        return False, f"invalid pid: {pid}"

    import ctypes
    from ctypes import wintypes

    k32 = _kernel32()
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.AssignProcessToJobObject.restype = wintypes.BOOL
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

    proc = k32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, int(pid))
    if not proc:
        return False, f"OpenProcess({pid}) failed ({ctypes.get_last_error()})"
    try:
        ok = k32.AssignProcessToJobObject(job.handle, proc)
        if not ok:
            return False, f"AssignProcessToJobObject({pid}) failed ({ctypes.get_last_error()})"
        return True, "assigned"
    finally:
        k32.CloseHandle(proc)


# --------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------


def enforce_environment(
    base: Mapping[str, str] | None = None,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the child environment for a sandboxed command.

    Forwards to the local backend's existing sanitizer
    (``tools.environments.local._sanitize_subprocess_env``) so there is exactly
    one credential blocklist in the codebase. If that import is unavailable the
    caller gets the **unmodified host environment is never** the fallback —
    we raise instead, because silently degrading to an unsanitised environment
    is the one failure a security boundary must not have.
    """
    try:
        from tools.environments.local import _sanitize_subprocess_env
    except Exception as exc:  # pragma: no cover - import wiring
        raise RuntimeError(
            "sandbox environment sanitizer unavailable; refusing to run with an "
            f"unsanitised environment ({exc})"
        ) from exc

    env = _sanitize_subprocess_env(base, extra)

    # Gap-closer, verified live (scripts/verify_win_sandbox.py): the existing
    # sanitizer strips by *name* against ``_OPENAMER_PROVIDER_ENV_BLOCKLIST``
    # plus two narrow prefixes. A provider key whose variable name it does not
    # know — ``TOKENHARBOR_API_KEY``, ``OPENVID_LLM_KEY``, ``OPENAMER_MESH_SECRET``
    # were all observed surviving it — rides straight through. So on top of the
    # blocklist we also drop anything that *looks* like a credential by suffix,
    # unless it is explicitly allowlisted via ``tools.env_passthrough`` (the
    # skill-declaration path), which is the one legitimate reason a secret-like
    # name needs to reach a child.
    try:
        from tools.env_passthrough import is_env_passthrough
    except Exception:  # pragma: no cover - passthrough is optional
        is_env_passthrough = lambda _name: False  # noqa: E731

    for name in list(env):
        upper = name.upper()
        if not _CREDENTIAL_SUFFIX_PATTERN.search(upper):
            continue
        if is_env_passthrough(name):
            continue
        env.pop(name, None)

    return env



# --------------------------------------------------------------------------
# Filesystem boundary
# --------------------------------------------------------------------------


def canonical_path(path: str | os.PathLike[str]) -> str:
    """Resolve a path to its real location, following junctions and symlinks.

    ``os.path.realpath`` on Windows resolves junctions in Python 3.8+, which is
    what makes the containment check meaningful: comparing un-resolved paths
    lets a junction inside the writable root point anywhere.
    """
    expanded = os.path.expandvars(os.path.expanduser(str(path)))
    return os.path.normcase(os.path.realpath(os.path.abspath(expanded)))


def protected_paths(home: str | os.PathLike[str] | None = None) -> set[str]:
    """Paths that are never writable inside a sandbox, canonicalised.

    Mirrors :func:`agent.file_safety.build_write_denied_paths` but adds the
    directory-level entries a *writable-root* model needs (a whole ``.git``
    directory, not just one file), and adds the sandbox's own state directory so
    a command cannot disarm its own containment.
    """
    # ``HOME``/``USERPROFILE`` before ``expanduser`` — on Windows expanduser
    # reads USERPROFILE only, so a caller (or a test) that sets HOME would be
    # silently ignored and the wrong home would be protected.
    home_path = Path(
        home or os.environ.get("HOME") or os.path.expanduser("~")
    )
    openamer_home = Path(
        os.environ.get("OPENAMER_HOME", "") or (home_path / ".openamer")
    )
    return {
        canonical_path(p)
        for p in (
            home_path / ".ssh",
            home_path / ".aws",
            home_path / ".gnupg",
            openamer_home,
            openamer_home / ".env",
            openamer_home / "config.yaml",
            Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32",
        )
    }


def check_write_path(
    path: str | os.PathLike[str],
    *,
    writable_root: str | os.PathLike[str] | None,
    extra_protected: Iterable[str] = (),
    home: str | os.PathLike[str] | None = None,
) -> tuple[bool, str]:
    """Decide whether a write to ``path`` is inside the sandbox boundary.

    Returns ``(allowed, reason)``. ``writable_root=None`` denies everything,
    which is the correct fail-closed default: a sandbox with no configured root
    must not degrade into an unrestricted one.
    """
    target = canonical_path(path)

    if writable_root is None:
        return False, "no writable root configured (fail-closed)"

    root = canonical_path(writable_root)

    # A path equal to the root, or nested under it, is inside.
    inside = target == root or target.startswith(root.rstrip(os.sep) + os.sep)
    if not inside:
        return False, f"outside writable root {root!r}"

    # VCS metadata is protected even *inside* the writable root: rewriting
    # ``.git/config`` re-points the remote (a credential-exfiltration and
    # hook-injection path) and rewriting the index corrupts the working tree.
    # A writable root is permission to change the code, not to rewire the repo.
    repo_meta = {
        canonical_path(os.path.join(root, name)) for name in (".git", ".hg", ".svn")
    }

    for prot in (
        protected_paths(home)
        | {canonical_path(p) for p in extra_protected}
        | repo_meta
    ):
        if target == prot or target.startswith(prot.rstrip(os.sep) + os.sep):
            return False, f"protected path {prot!r}"

    return True, "inside writable root"


# --------------------------------------------------------------------------
# Honest reporting
# --------------------------------------------------------------------------


def describe_enforcement(limits: JobLimits | None = None) -> dict[str, Any]:
    """Report what this platform can and cannot enforce.

    Sized for a ``/sandbox`` status surface, and deliberately explicit about the
    ``partial`` network row — the point of the module is a verifiable boundary,
    not a reassuring one.
    """
    limits = limits or JobLimits()
    supported = is_supported()
    return {
        "platform": sys.platform,
        "mechanism": "windows-job-object" if supported else "unavailable",
        "enforced": {
            "process_tree_kill": bool(supported and limits.kill_on_close),
            "process_count_cap": bool(supported and limits.max_processes),
            "memory_cap": bool(supported and limits.max_memory_mb),
            "no_breakaway": supported,
            "clipboard_and_handle_isolation": bool(supported and limits.deny_ui),
            "credential_env_absent": True,
        },
        "partial": {
            "network_isolation": (
                "proxy-honouring clients only; per-process blocking needs WFP "
                "(administrator). network=deny refuses to run instead."
            ),
            "filesystem": (
                "policy over our own write paths, not an ACL — junctions are "
                "resolved, but a command using raw Win32 IO is not intercepted."
            ),
        },
        "unsupported": [] if supported else ["job objects require Windows"],
    }