"""Tests for the native Windows containment module.

These are deliberately *not* mock-only: the job-object tests create a real job,
put a real child process in it, and prove the OS applied the limits. A mock would
have passed the first, wrong version of this module — which is exactly the
failure mode this feature exists to avoid.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from agent.win_sandbox import (
    JobLimits,
    SandboxPolicy,
    assign_pid_to_job,
    build_job_object,
    canonical_path,
    check_write_path,
    contain_process,
    describe_enforcement,
    enforce_environment,
    is_supported,
    policy_from_config,
    protected_paths,
    release_process,
)

WINDOWS = sys.platform == "win32"
requires_windows = pytest.mark.skipif(not WINDOWS, reason="Windows job objects only")


# --------------------------------------------------------------------------
# Environment — delegated to the existing local-backend sanitizer
# --------------------------------------------------------------------------


def test_enforce_environment_delegates_to_the_existing_sanitizer():
    """We must not ship a second, divergent credential blocklist."""
    from tools.environments import local as local_env

    assert hasattr(local_env, "_sanitize_subprocess_env")

    env = enforce_environment({"PATH": "/bin", "OPENROUTER_API_KEY": "sk-or-secret"})
    assert "OPENROUTER_API_KEY" not in env
    assert env.get("PATH") == "/bin"


def test_enforce_environment_closes_the_unknown_provider_key_gap():
    """Names the local blocklist does not know must still be stripped.

    Live-verified leak (scripts/verify_win_sandbox.py): these four rode straight
    through the existing sanitizer because they are not in its blocklist.
    """
    host = {
        "PATH": "/bin",
        "TOKENHARBOR_API_KEY": "x",
        "OPENVID_LLM_KEY": "x",
        "OPENAMER_MESH_SECRET": "x",
        "OPENAMER_SESSION_KEY": "x",
        "MY_PASSWORD": "x",
        "GH_TOKEN": "x",
    }
    env = enforce_environment(host)
    for leaked in (
        "TOKENHARBOR_API_KEY",
        "OPENVID_LLM_KEY",
        "OPENAMER_MESH_SECRET",
        "OPENAMER_SESSION_KEY",
        "MY_PASSWORD",
        "GH_TOKEN",
    ):
        assert leaked not in env, f"{leaked} leaked into the sandbox environment"
    assert env["PATH"] == "/bin"


def test_enforce_environment_keeps_ordinary_names():
    """Suffix stripping must not eat legitimate plumbing."""
    env = enforce_environment(
        {"PATH": "/bin", "MONKEY": "1", "KEYBOARD_LAYOUT": "de", "TOKENIZER": "bpe"}
    )
    assert env["MONKEY"] == "1"
    assert env["KEYBOARD_LAYOUT"] == "de"
    assert env["TOKENIZER"] == "bpe"


def test_enforce_environment_never_returns_unsanitised_on_failure(monkeypatch):
    """A broken import must raise, not silently pass the host environment through."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.endswith("environments.local") or name.endswith("environments"):
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(Exception):
        enforce_environment({"PATH": "/bin"})


# Filesystem boundary
# --------------------------------------------------------------------------


def test_write_denied_without_a_root():
    ok, reason = check_write_path("/tmp/anything", writable_root=None)
    assert not ok
    assert "fail-closed" in reason


def test_write_inside_root_allowed(tmp_path: Path):
    root = tmp_path / "work"
    root.mkdir()
    ok, reason = check_write_path(root / "src" / "a.py", writable_root=root)
    assert ok, reason


def test_write_outside_root_denied(tmp_path: Path):
    root = tmp_path / "work"
    root.mkdir()
    ok, reason = check_write_path(tmp_path / "elsewhere.txt", writable_root=root)
    assert not ok
    assert "outside writable root" in reason


def test_sibling_prefix_is_not_treated_as_inside(tmp_path: Path):
    """`/w/work-evil` must not pass a naive startswith('/w/work') check."""
    root = tmp_path / "work"
    root.mkdir()
    sibling = tmp_path / "work-evil"
    sibling.mkdir()
    ok, _ = check_write_path(sibling / "x.txt", writable_root=root)
    assert not ok


def test_traversal_attempt_is_resolved_before_comparison(tmp_path: Path):
    root = tmp_path / "work"
    (root / "sub").mkdir(parents=True)
    ok, reason = check_write_path(root / "sub" / ".." / ".." / "escape.txt", writable_root=root)
    assert not ok, reason


def test_protected_path_inside_root_is_refused(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    ok, reason = check_write_path(root / ".git" / "config", writable_root=root)
    assert not ok, "writable root must still protect .git"


def test_extra_protected_paths_are_honoured(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    secret = root / "secrets"
    secret.mkdir()
    ok, _ = check_write_path(secret / "k.txt", writable_root=root, extra_protected=[secret])
    assert not ok


def test_canonical_path_normalises_separators(tmp_path: Path):
    p = tmp_path / "a" / ".." / "b"
    assert canonical_path(p) == canonical_path(tmp_path / "b")


def test_protected_paths_include_ssh_and_openamer_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path / ".openamer"))
    prot = protected_paths()
    assert canonical_path(tmp_path / ".ssh") in prot
    assert canonical_path(tmp_path / ".openamer") in prot


# --------------------------------------------------------------------------
# Job objects — real OS calls, no mocks
# --------------------------------------------------------------------------


def test_limits_reject_impossible_values():
    with pytest.raises(ValueError):
        JobLimits(max_processes=0)
    with pytest.raises(ValueError):
        JobLimits(max_memory_mb=1)


def test_flags_never_grant_breakaway():
    from agent.win_sandbox import _JOB_OBJECT_LIMIT_BREAKAWAY_OK

    for limits in (JobLimits(), JobLimits(kill_on_close=False), JobLimits(deny_ui=False)):
        assert not limits.flags() & _JOB_OBJECT_LIMIT_BREAKAWAY_OK


def test_flags_compose_with_configuration():
    from agent.win_sandbox import (
        _JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
        _JOB_OBJECT_LIMIT_JOB_MEMORY,
        _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    )

    flags = JobLimits().flags()
    assert flags & _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    assert flags & _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
    assert flags & _JOB_OBJECT_LIMIT_JOB_MEMORY


@requires_windows
def test_job_object_is_created_with_limits():
    with build_job_object(JobLimits(max_processes=8, max_memory_mb=512)) as job:
        assert job.active, job.error
        assert job.handle


@requires_windows
def test_assign_to_inactive_job_reports_failure():
    from agent.win_sandbox import JobHandle

    ok, detail = assign_pid_to_job(JobHandle(error="nope"), os.getpid())
    assert not ok
    assert "no active job" in detail


@requires_windows
def test_process_tree_is_killed_when_the_job_closes():
    """The core promise: closing the job takes the whole tree with it."""
    child = subprocess.Popen(
        ["cmd", "/c", "ping -n 60 127.0.0.1 > NUL"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        job = build_job_object(JobLimits(kill_on_close=True))
        assert job.active, job.error
        ok, detail = assign_pid_to_job(job, child.pid)
        assert ok, detail
        assert child.poll() is None, "child should still be running"
        job.close()
        # Give the OS a moment to tear the tree down.
        for _ in range(50):
            if child.poll() is not None:
                break
            time.sleep(0.1)
        assert child.poll() is not None, "job close must terminate the child"
    finally:
        if child.poll() is None:  # pragma: no cover - only on failure path
            child.kill()


@requires_windows
def test_assigned_process_respects_the_process_cap():
    """A 1-process cap must stop a second child from joining the job."""
    job = build_job_object(JobLimits(max_processes=1, kill_on_close=True))
    assert job.active, job.error
    first = subprocess.Popen(
        ["cmd", "/c", "ping -n 60 127.0.0.1 > NUL"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    second = None
    try:
        ok, detail = assign_pid_to_job(job, first.pid)
        assert ok, detail
        second = subprocess.Popen(
            ["cmd", "/c", "ping -n 60 127.0.0.1 > NUL"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ok2, _detail2 = assign_pid_to_job(job, second.pid)
        # The OS must refuse the second assignment (ERROR_NOT_ENOUGH_QUOTA) or
        # immediately terminate it — either way it never becomes an unbounded
        # second process under the job.
        assert (not ok2) or second.poll() is not None
    finally:
        job.close()
        for proc in (first, second):
            if proc is not None and proc.poll() is None:  # pragma: no cover
                proc.kill()


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def test_describe_enforcement_reports_network_as_partial_never_enforced():
    report = describe_enforcement()
    assert "network_isolation" in report["partial"]
    assert "network_isolation" not in report["enforced"]
    # filesystem is a policy layer, not an ACL — must not be advertised as enforced
    assert "filesystem" not in report["enforced"]


@requires_windows
def test_describe_enforcement_marks_windows_mechanism():
    report = describe_enforcement()
    assert report["mechanism"] == "windows-job-object"
    assert report["enforced"]["process_tree_kill"] is True


def test_unsupported_platform_reports_cleanly(monkeypatch):
    monkeypatch.setattr("agent.win_sandbox.sys.platform", "linux")
    job = build_job_object()
    assert not job.active
    assert "unsupported platform" in (job.error or "")
    assert describe_enforcement()["mechanism"] == "unavailable"
    assert is_supported() is False


# --------------------------------------------------------------------------
# Wiring: policy resolution + containment of a real process
# --------------------------------------------------------------------------


def test_policy_defaults_to_disabled():
    policy = policy_from_config(get=lambda _key, default: default)
    assert policy.enabled is False
    assert policy.fail_closed is True
    assert policy.limits.kill_on_close is True


def test_policy_reads_config_values():
    values = {
        "terminal.sandbox.windows.enabled": True,
        "terminal.sandbox.windows.writable_root": "C:/work",
        "terminal.sandbox.windows.max_processes": 7,
        "terminal.sandbox.windows.max_memory_mb": 256,
        "terminal.sandbox.windows.deny_ui": False,
        "terminal.sandbox.windows.fail_closed": False,
        "terminal.sandbox.windows.strip_secrets": False,
    }
    policy = policy_from_config(get=lambda key, default: values.get(key, default))
    assert policy.enabled is True
    assert policy.writable_root == "C:/work"
    assert policy.limits.max_processes == 7
    assert policy.limits.max_memory_mb == 256
    assert policy.limits.deny_ui is False
    assert policy.fail_closed is False
    assert policy.strip_secrets is False


def test_policy_treats_blank_writable_root_as_unset():
    policy = policy_from_config(
        get=lambda key, default: "" if key.endswith("writable_root") else default
    )
    assert policy.writable_root is None


def test_contain_process_is_a_noop_when_disabled():
    class _Fake:
        pid = 4242

    ok, detail = contain_process(_Fake(), SandboxPolicy(enabled=False))
    assert ok and detail == "sandbox disabled"
    assert not hasattr(_Fake(), "_openamer_sandbox_job")


@requires_windows
def test_contain_process_assigns_and_release_kills_the_tree():
    policy = SandboxPolicy(
        enabled=True, limits=JobLimits(kill_on_close=True, max_processes=8, max_memory_mb=512)
    )
    child = subprocess.Popen(
        ["cmd", "/c", "ping -n 60 127.0.0.1 > NUL"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ok, detail = contain_process(child, policy)
        assert ok, detail
        assert getattr(child, "_openamer_sandbox_job", None) is not None
        assert child.poll() is None
        release_process(child)
        for _ in range(50):
            if child.poll() is not None:
                break
            time.sleep(0.1)
        assert child.poll() is not None, "release_process must kill the tree"
        assert getattr(child, "_openamer_sandbox_job", None) is None
    finally:
        if child.poll() is None:  # pragma: no cover
            child.kill()


@requires_windows
def test_release_process_is_safe_without_a_job():
    class _Fake:
        pid = 1

    release_process(_Fake())  # must not raise


def test_contain_process_fails_closed_on_unsupported_platform(monkeypatch):
    monkeypatch.setattr("agent.win_sandbox.sys.platform", "linux")

    class _Fake:
        pid = 1234

    ok, detail = contain_process(_Fake(), SandboxPolicy(enabled=True, fail_closed=True))
    assert not ok
    assert "unsupported" in detail

    # …and does not block when the operator explicitly opted out of fail-closed.
    ok, detail = contain_process(_Fake(), SandboxPolicy(enabled=True, fail_closed=False))
    assert ok
    assert "not fail-closed" in detail


def test_local_backend_defaults_to_no_containment():
    """The default path must be byte-identical to before the wiring."""
    from tools.environments.local import _terminal_sandbox_policy

    assert _terminal_sandbox_policy().enabled is False