"""Fixtures shared across openamer_cli kanban tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def all_assignees_spawnable(monkeypatch):
    """Pretend every assignee maps to a real OpenAmer profile.

    Most dispatcher tests use synthetic assignees ("alice", "bob") that
    don't correspond to actual profile directories on disk. Without this
    patch, the dispatcher's profile-exists guard (PR #20105) routes
    those tasks into ``skipped_nonspawnable`` instead of spawning, which
    would break tests that assert spawn behavior.
    """
    from openamer_cli import profiles
    monkeypatch.setattr(profiles, "profile_exists", lambda name: True)


@pytest.fixture(autouse=True)
def _suppress_concurrent_openamer_gate(request, monkeypatch):
    """Default ``_detect_concurrent_openamer_instances`` to ``[]`` for every test.

    The Windows update path now refuses to proceed when another
    ``openamer.exe`` is detected (issue #26670). On a developer's Windows
    machine running the test suite via ``openamer`` itself, this would
    flag the running agent as a concurrent instance and abort every
    ``cmd_update`` test. Tests that want to exercise the gate explicitly
    re-patch ``_detect_concurrent_openamer_instances`` with their own
    return value — autouse here gives a clean default without touching
    the rest of the suite.

    Tests that need to call the REAL function (e.g. unit tests for the
    helper itself) opt out with ``@pytest.mark.real_concurrent_gate``.
    """
    if request.node.get_closest_marker("real_concurrent_gate"):
        return
    try:
        from openamer_cli import main as _cli_main
    except Exception:
        return
    # raising=False: under pytest's per-test spawn isolation, a concurrent
    # xdist worker importing a module that transitively touches openamer_cli.main
    # can briefly expose a partially-initialized module object here — one where
    # _detect_concurrent_openamer_instances isn't defined yet. A bare setattr
    # would raise AttributeError and error the (unrelated) test. The attribute
    # always exists once main.py finishes importing, so a no-op when it's
    # transiently absent is the correct, race-free default.
    monkeypatch.setattr(
        _cli_main,
        "_detect_concurrent_openamer_instances",
        lambda *_a, **_k: [],
        raising=False,
    )
    # The Windows venv-process guard (_detect_venv_python_processes) also
    # refuses the update when another openamer python holds the venv (.pyd
    # lock). On a dev Windows machine running the suite from the real venv
    # while the desktop gateway is live, the real probe finds that process
    # and every cmd_update test aborts with sys.exit(2) instead of reaching
    # the assertion. Mock it to no holders by default so update tests behave
    # like the Linux/CI environment. Unit tests for the probe itself opt out
    # with @pytest.mark.real_concurrent_gate (same marker used by the shim
    # guard above).
    monkeypatch.setattr(
        _cli_main,
        "_detect_venv_python_processes",
        lambda *_a, **_k: [],
        raising=False,
    )
    # The Windows quarantine path (_quarantine_running_openamer_exe) renames
    # the REAL venv's live shims to ``*.exe.old.*`` before `pip install -e .`
    # so uv can overwrite a running openamer.exe. When a test drives the real
    # cmd_update on Windows, that quarantine targets the dev checkout's actual
    # venv and renames python.exe/openamer.exe away — corrupting the developer's
    # working venv mid-test (observed: venv python.exe vanished, replaced by
    # python.exe.old.*; plus a stray .lazy-refresh-incomplete marker). Neutralize
    # both the quarantine and its opposite cleanup as no-ops so update tests
    # never touch the real venv. The unit tests for the quarantine itself carry
    # @pytest.mark.real_concurrent_gate (module-level in
    # test_update_concurrent_quarantine.py) and keep the real function.
    monkeypatch.setattr(
        _cli_main,
        "_quarantine_running_openamer_exe",
        lambda *_a, **_k: ([], []),
        raising=False,
    )
    monkeypatch.setattr(
        _cli_main,
        "_rollback_quarantined_exes",
        lambda *_a, **_k: None,
        raising=False,
    )
