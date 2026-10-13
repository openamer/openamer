"""Regression tests for #4707 — cron must be per-profile.

Design intent (Teknium, June 2026): a profile's cron jobs both LIVE in that
profile's OPENAMER_HOME and EXECUTE under it.

- Storage: a job created under profile ``coder`` writes to
  ``~/.openamer/profiles/coder/cron/jobs.json`` — NOT the shared default root.
- Execution: the profile-scoped gateway's in-process ticker resolves the
  active OPENAMER_HOME (profile home) at call time, so jobs run with that
  profile's ``.env`` / ``config.yaml`` / scripts / skills.

This is the opposite direction from the (reverted) #50112/#32091 "anchor at the
shared root" approach. Anchoring at the root funnels every profile's jobs into
one store and runs them under whatever OPENAMER_HOME the ticker happens to have —
leaking config/credentials/skills across profiles, the security boundary #4707
was filed for. These tests pin per-profile isolation so a stale-branch merge or
a re-anchor "fix" can't silently flip it back.
"""
import importlib
from pathlib import Path


def _set_profile_env(monkeypatch, root: Path, profile_home: Path) -> None:
    """Pretend the platform default root is ``root`` and the active
    OPENAMER_HOME is a profile under it (``<root>/profiles/<name>``)."""
    import openamer_constants

    monkeypatch.setattr(
        openamer_constants, "_get_platform_default_openamer_home", lambda: root
    )
    monkeypatch.setenv("OPENAMER_HOME", str(profile_home))


def test_cron_storage_anchors_at_profile_home(tmp_path, monkeypatch):
    """Under a profile OPENAMER_HOME (<root>/profiles/<name>), the cron store
    resolves to <profile>/cron, NOT the shared <root>/cron."""
    root = tmp_path / "openamer_home"
    profile_home = root / "profiles" / "coder"
    profile_home.mkdir(parents=True)

    _set_profile_env(monkeypatch, root, profile_home)

    import openamer_constants

    # Sanity: the override is wired the way the gateway sees it.
    assert openamer_constants.get_openamer_home().resolve() == profile_home.resolve()
    assert openamer_constants.get_default_openamer_root().resolve() == root.resolve()

    # cron/jobs.py computes OPENAMER_DIR from get_openamer_home() at import, so a
    # fresh import under this env anchors the store at <profile>/cron.
    import cron.jobs as jobs

    importlib.reload(jobs)
    try:
        assert jobs.OPENAMER_DIR.resolve() == profile_home.resolve()
        assert (
            jobs.JOBS_FILE.resolve()
            == (profile_home / "cron" / "jobs.json").resolve()
        )
        # The shared-root path must NOT be the store — that would re-break
        # per-profile isolation (#4707).
        assert (
            jobs.JOBS_FILE.resolve() != (root / "cron" / "jobs.json").resolve()
        )
    finally:
        monkeypatch.undo()
        importlib.reload(jobs)


def test_cron_lock_path_anchors_at_profile_home(tmp_path, monkeypatch):
    """The tick lock is also profile-scoped, so two profile gateways tick
    independently instead of contending on one shared lock."""
    root = tmp_path / "openamer_home"
    profile_home = root / "profiles" / "coder"
    profile_home.mkdir(parents=True)

    _set_profile_env(monkeypatch, root, profile_home)

    import cron.scheduler as scheduler

    lock_dir, lock_file = scheduler._get_lock_paths()
    assert lock_dir.resolve() == (profile_home / "cron").resolve()
    assert lock_file.resolve() == (profile_home / "cron" / ".tick.lock").resolve()
    assert lock_dir.resolve() != (root / "cron").resolve()


def test_cron_execution_home_follows_active_profile(tmp_path, monkeypatch):
    """Execution-time home resolution (.env / config.yaml / scripts) follows
    the active profile, not the shared root — so a profile gateway runs its
    jobs with that profile's runtime config."""
    root = tmp_path / "openamer_home"
    profile_home = root / "profiles" / "coder"
    profile_home.mkdir(parents=True)

    _set_profile_env(monkeypatch, root, profile_home)

    import cron.scheduler as scheduler

    # The module-level test override must be clear so the dynamic path runs.
    monkeypatch.setattr(scheduler, "_openamer_home", None, raising=False)
    assert scheduler._get_openamer_home().resolve() == profile_home.resolve()
    assert scheduler._get_openamer_home().resolve() != root.resolve()


def test_cron_storage_unaffected_when_no_profile(tmp_path, monkeypatch):
    """With no profile (OPENAMER_HOME == root), the store is the root's cron dir
    — unchanged behavior for single-profile installs."""
    root = tmp_path / "openamer_home"
    root.mkdir(parents=True)

    import openamer_constants

    monkeypatch.setattr(
        openamer_constants, "_get_platform_default_openamer_home", lambda: root
    )
    monkeypatch.setenv("OPENAMER_HOME", str(root))

    import cron.jobs as jobs

    importlib.reload(jobs)
    try:
        assert jobs.OPENAMER_DIR.resolve() == root.resolve()
        assert jobs.JOBS_FILE.resolve() == (root / "cron" / "jobs.json").resolve()
    finally:
        monkeypatch.undo()
        importlib.reload(jobs)
