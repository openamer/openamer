"""pytest plugin — keep a test run from touching the LIVE OpenAmer install.

Why this file lives in the repo
-------------------------------
``scripts/run_tests.sh`` exports ``PYTEST_PLUGINS=pytest_live_guard`` so every
per-file subprocess starts with the guard. It used to load the module from
``$HOME/.openamer/pytest_live_guard.py`` and quietly carry on when that file did
not exist — hermeticity was a property of one developer's home directory, not of
the checkout, and its absence was silent.

Measured on a machine without that file (2026-10-30): a single run of
``tests/openamer_cli/test_update_*.py`` spawned **7+ real ``gateway run``
processes**. Each one starts by stopping the gateway already running there —
that is what ``--replace`` does — and is then orphaned when the test process
exits. Afterwards ``openamer gateway status`` listed several PIDs at once and
the developer's gateway was gone (no cron ticks until it was started by hand).
The same run also printed a real ``✓ Update complete!`` banner, i.e. tests were
driving ``openamer update`` against a live install.

What the guard does
-------------------
Refuses to LAUNCH an OpenAmer *daemon* from inside a test: gateway lifecycle
(``run/start/stop/restart``), the long-running helper loops (dashboard, remote
web, snapshot, webhook engine, tool server, supervisor, learning loops) and the
desktop updater. Read-only commands (``--version``, ``gateway status``,
``tools``, …) are untouched, and so is every non-OpenAmer process.

Refusing beats killing afterwards: it happens at the call site, it cannot leave
residue behind when the test process is itself killed (a timeout, an OOM), and
it names the test that asked for a daemon instead of hiding the dependency.

Escape hatch: ``OPENAMER_PYTEST_ALLOW_DAEMONS=1`` for the rare test that must
exercise a real daemon (say, a supervisor E2E). Refusals are counted and printed
in the terminal summary, so a test that swallows the exception is still visible.
"""

from __future__ import annotations

import os
import subprocess
import sys

__all__ = [
    "LiveGuardRefusal",
    "is_openamer_daemon_launch",
    "refusals",
]

#: Sub-commands that put an OpenAmer process into a long-running, shared-state
#: role. ``status`` is deliberately absent: it is read-only.
_GATEWAY_DAEMON_SUBCOMMANDS = frozenset({"run", "start", "stop", "restart"})

#: Helper loops the CLI/desktop launch directly as ``python <script>``.
_DAEMON_SCRIPTS = frozenset(
    {
        "dashboard-server.py",
        "remote-web.py",
        "system-snapshot.py",
        "webhook-engine.py",
        "tool_server.py",
        "openamer_supervisor.py",
        "online_learning.py",
        "mini_step.py",
        "self_improve.py",
        "a2a_server.py",
    }
)

#: Tokens whose basename means "this process IS OpenAmer".
_OPENAMER_BINARIES = frozenset(
    {"openamer", "openamer.exe", "openamer.cmd", "openamer.bat", "openamer-cli"}
)

#: The desktop updater rewrites the install in place — never from a test.
_UPDATER_MARKERS = frozenset({"openamer-setup", "openamer-setup.exe"})

#: Refusals recorded this session: (test id, command).
refusals: list[tuple[str, str]] = []


class LiveGuardRefusal(RuntimeError):
    """A test tried to launch a real OpenAmer daemon."""


def _tokens(cmd) -> list[str]:
    if isinstance(cmd, (str, bytes)):
        return str(cmd).split()
    try:
        return [str(part) for part in cmd]
    except TypeError:
        return [str(cmd)]


def is_openamer_daemon_launch(cmd) -> bool:
    """True when ``cmd`` would start/stop a real OpenAmer background process.

    Pure and argv-shaped only, so it is unit-testable without a process.
    """
    tokens = _tokens(cmd)
    if not tokens:
        return False

    # The desktop updater mutates the install in place — recognised by its own
    # executable name plus the flag, wherever it sits in the argv.
    names = {os.path.basename(tok).lower() for tok in tokens}
    if names & _UPDATER_MARKERS and any(
        tok in ("--update", "-update") for tok in tokens
    ):
        return True

    target = _openamer_target(tokens)
    # Empty means the OpenAmer entry point was the last token (`openamer`,
    # `python -m openamer_cli.main`) — no sub-command, so no daemon. Indexing
    # target[0] without this check crashed inside Popen instead of returning a
    # verdict (measured in CI: tests/docker/test_config_migration.py and
    # test_container_restart.py both ERRORed with IndexError).
    if not target:
        return False

    # ``openamer … gateway run|start|stop|restart`` (the ``--replace`` launcher
    # is what silently killed the developer's running gateway).
    if target[0].lower() == "gateway":
        return any(tok.lower() in _GATEWAY_DAEMON_SUBCOMMANDS for tok in target[1:])

    # ``python <openamer tree>/scripts/dashboard-server.py`` and friends.
    return _looks_like_openamer_script(target[0])


#: Interpreter basenames that can front ``-m openamer_cli.main`` or a script.
_PYTHON_BASENAMES = frozenset(
    {"python", "python.exe", "pythonw.exe", "python3", "python3.exe", "pythonw"}
)


def _openamer_target(tokens: list[str]) -> list[str] | None:
    """Tokens AFTER the OpenAmer entry point, or None when there is none.

    Anchoring on the entry point (instead of grepping the joined command line
    for "openamer") is what keeps the rule precise: ``tests/test_tini_shim.py``
    spawns ``sh docker/tini-shim.sh -g -- gateway run`` — the words
    ``gateway run`` there are an ARGUMENT to a wrapper, and the path merely
    contains the checkout directory name. Measured in CI as three false
    refusals before this anchor existed.
    """
    for index, token in enumerate(tokens):
        base = os.path.basename(token).lower()
        if base in _OPENAMER_BINARIES:
            return tokens[index + 1 :]
        if base in _PYTHON_BASENAMES:
            # ``python -m openamer_cli.main <sub-command…>``
            for pos in range(index + 1, min(index + 4, len(tokens) - 1)):
                if tokens[pos] == "-m" and tokens[pos + 1].startswith("openamer_cli"):
                    return tokens[pos + 2 :]
            # ``python <script.py> <args…>``
            for pos in range(index + 1, len(tokens)):
                if tokens[pos].lower().endswith(".py"):
                    return tokens[pos:]
    return None


def _looks_like_openamer_script(path: str) -> bool:
    """True for a daemon helper script that belongs to an OpenAmer tree.

    A bare basename is not enough (``/tmp/…/tool_server.py`` is somebody else's
    file); the script must sit in a ``scripts`` directory or under a path that
    names OpenAmer. Relative invocations (``scripts/remote-web.py``) count too.
    """
    normalised = path.replace("\\", "/").lower()
    if normalised.rsplit("/", 1)[-1] not in _DAEMON_SCRIPTS:
        return False
    return "scripts" in normalised.split("/") or "openamer" in normalised


def _allow_daemons() -> bool:
    return os.environ.get("OPENAMER_PYTEST_ALLOW_DAEMONS", "") == "1"


class _GuardedPopen(subprocess.Popen):
    """``subprocess.Popen`` that refuses OpenAmer daemon launches."""

    def __init__(self, args, *pargs, **kwargs):
        if not _allow_daemons() and is_openamer_daemon_launch(args):
            command = " ".join(_tokens(args))
            try:
                current = os.environ.get("PYTEST_CURRENT_TEST", "unknown test")
            except Exception:  # pragma: no cover - defensive
                current = "unknown test"
            refusals.append((current, command))
            raise LiveGuardRefusal(
                "pytest_live_guard refused to start an OpenAmer daemon from a "
                f"test ({command!r}). A real 'gateway run --replace' stops the "
                "developer's running gateway and outlives the test process. "
                "Mock the spawn, or set OPENAMER_PYTEST_ALLOW_DAEMONS=1 if this "
                "test is the daemon's own E2E."
            )
        super().__init__(args, *pargs, **kwargs)


def pytest_configure(config):  # noqa: D401 - pytest hook
    """Install the guarded ``Popen`` before any test module is imported."""
    if _allow_daemons():
        return
    # ``subprocess.run``/``call``/``check_output`` all construct a ``Popen``,
    # so one hook covers every call path (including code under test that
    # imported ``subprocess`` earlier — the attribute is looked up per call).
    subprocess.Popen = _GuardedPopen  # type: ignore[misc,assignment]


def pytest_terminal_summary(terminalreporter, exitstatus, config):  # noqa: D401
    """Print what the guard refused — a swallowed exception is still visible."""
    if not refusals:
        return
    terminalreporter.write_sep("=", "pytest_live_guard: refused daemon launches")
    for test_id, command in refusals:
        terminalreporter.write_line(f"  {test_id} -> {command}")
    terminalreporter.write_line(
        "  (mocked spawn needed; OPENAMER_PYTEST_ALLOW_DAEMONS=1 to opt out)"
    )


def pytest_report_header(config):  # noqa: D401
    state = "OFF (OPENAMER_PYTEST_ALLOW_DAEMONS=1)" if _allow_daemons() else "ON"
    return f"pytest_live_guard: {state} (no real OpenAmer daemons from tests)"


if __name__ == "__main__":  # pragma: no cover - manual probe
    print(sys.version)
    print(is_openamer_daemon_launch([sys.executable, "-m", "openamer_cli.main", "gateway", "run"]))
