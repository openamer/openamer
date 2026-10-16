"""Tests for the per-profile Projects store (openamer_cli/projects_db)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from openamer_cli import projects_db as pdb


# Fixture paths must be *absolute on the host*, not merely POSIX-shaped.
# ``Path("/www/alpha")`` is drive-relative on Windows (``\www\alpha``), so the
# store's ``os.path.abspath`` normalization — correct, and identical on POSIX —
# prepends the current drive and ``"/www/alpha"`` no longer round-trips.
# Anchoring every fixture under the temp dir keeps these assertions about the
# store's behaviour (round-trip, upsert, primary repointing, prefix matching)
# meaningful on Windows and POSIX alike.
_FIXTURE_ROOT = Path(tempfile.gettempdir()) / "openamer-projects-test"


def _p(*parts: str) -> str:
    """A native absolute fixture path under the temp root."""
    return str(_FIXTURE_ROOT.joinpath(*parts))


@pytest.fixture
def conn(tmp_path):
    c = pdb.connect(db_path=tmp_path / "projects.db")
    try:
        yield c
    finally:
        c.close()


def test_record_and_list_discovered_repos(conn):
    alpha, beta = _p("www", "alpha"), _p("www", "beta")
    n = pdb.record_discovered_repos(conn, [(alpha, "alpha"), (beta, None)])
    assert n == 2

    rows = {r["root"]: r["label"] for r in pdb.list_discovered_repos(conn)}
    assert rows[alpha] == "alpha"
    # Label defaults to the basename when not given.
    assert rows[beta] == "beta"


def test_record_discovered_repos_upserts(conn):
    alpha = _p("www", "alpha")
    pdb.record_discovered_repos(conn, [(alpha, "old")])
    pdb.record_discovered_repos(conn, [(alpha, "new")])

    rows = pdb.list_discovered_repos(conn)
    assert len(rows) == 1
    assert rows[0]["label"] == "new"


def test_record_discovered_repos_replace_drops_stale_rows(conn):
    alpha = _p("www", "alpha")
    pdb.record_discovered_repos(
        conn, [(alpha, "alpha"), (_p("www", "beta"), "beta")]
    )
    pdb.record_discovered_repos(conn, [(alpha, "fresh")], replace=True)

    rows = {r["root"]: r["label"] for r in pdb.list_discovered_repos(conn)}
    assert rows == {alpha: "fresh"}


def test_discovery_policy_change_clears_only_discovered_rows(conn):
    project_id = pdb.create_project(
        conn, name="Explicit", folders=[_p("www", "explicit")]
    )
    pdb.record_discovered_repos(
        conn, [(_p("www", "scanned"), "scanned")], policy_key="policy-a"
    )

    assert pdb.reconcile_discovered_repos_policy(conn, "policy-b") is True
    assert pdb.list_discovered_repos(conn) == []
    assert pdb.get_project(conn, project_id) is not None
    assert pdb.get_discovery_policy_key(conn) == "policy-b"


def test_default_policy_adopts_unversioned_cache_without_clearing(conn):
    scanned = _p("www", "scanned")
    pdb.record_discovered_repos(conn, [(scanned, "scanned")])

    assert (
        pdb.reconcile_discovered_repos_policy(
            conn, "default-policy", preserve_unversioned=True
        )
        is False
    )
    assert [row["root"] for row in pdb.list_discovered_repos(conn)] == [scanned]
    assert pdb.get_discovery_policy_key(conn) == "default-policy"


def test_clear_discovered_repos_records_policy_atomically(conn):
    pdb.record_discovered_repos(conn, [(_p("www", "scanned"), "scanned")])

    pdb.clear_discovered_repos(conn, policy_key="disabled")

    assert pdb.list_discovered_repos(conn) == []
    assert pdb.get_discovery_policy_key(conn) == "disabled"


def test_create_get_list(conn):
    folder = _p("tmp", "openamer")
    pid = pdb.create_project(conn, name="OpenAmer Agent", folders=[folder])
    proj = pdb.get_project(conn, pid)

    assert proj is not None
    assert proj.slug == "openamer-agent"
    assert proj.name == "OpenAmer Agent"
    # First folder becomes primary.
    assert proj.primary_path == folder
    assert [f.path for f in proj.folders] == [folder]
    assert proj.folders[0].is_primary is True

    # Lookup by slug too.
    assert pdb.get_project(conn, "openamer-agent").id == pid
    assert len(pdb.list_projects(conn)) == 1


def test_slug_collision_disambiguates(conn):
    pdb.create_project(conn, name="OpenAmer Agent")
    pdb.create_project(conn, name="OpenAmer Agent")
    slugs = sorted(p.slug for p in pdb.list_projects(conn))

    assert slugs == ["openamer-agent", "openamer-agent-2"]


def test_empty_name_rejected(conn):
    with pytest.raises(ValueError):
        pdb.create_project(conn, name="   ")


def test_add_remove_folder_and_primary_repoint(conn):
    a, b, c = _p("a"), _p("b"), _p("c")
    pid = pdb.create_project(conn, name="P", folders=[a])
    pdb.add_folder(conn, pid, b)
    pdb.add_folder(conn, pid, c, is_primary=True)

    proj = pdb.get_project(conn, pid)
    assert proj.primary_path == c
    assert {f.path for f in proj.folders} == {a, b, c}

    # Removing the primary repoints to the oldest remaining folder.
    pdb.remove_folder(conn, pid, c)
    proj = pdb.get_project(conn, pid)
    assert proj.primary_path == a

    # Removing the last folder clears the primary.
    pdb.remove_folder(conn, pid, a)
    pdb.remove_folder(conn, pid, b)
    proj = pdb.get_project(conn, pid)
    assert proj.primary_path is None
    assert proj.folders == []


def test_set_primary_requires_existing_folder(conn):
    pid = pdb.create_project(conn, name="P", folders=[_p("a")])
    assert pdb.set_primary(conn, pid, _p("nope")) is False
    assert pdb.set_primary(conn, pid, _p("a")) is True


def test_paths_normalized(conn):
    pid = pdb.create_project(conn, name="P", folders=[_p("a", "b", "..", "c") + os.sep])
    proj = pdb.get_project(conn, pid)
    # Trailing slash stripped, .. collapsed.
    assert proj.primary_path == _p("a", "c")


def test_project_for_path_longest_prefix(conn):
    outer = pdb.create_project(conn, name="Outer", folders=[_p("www")])
    inner = pdb.create_project(conn, name="Inner", folders=[_p("www", "app")])

    assert pdb.project_for_path(conn, _p("www", "app", "src", "x.py")).id == inner
    assert pdb.project_for_path(conn, _p("www", "other")).id == outer
    assert pdb.project_for_path(conn, _p("elsewhere")) is None
    # Segment-wise prefix only: /www/app must not match /www/application.
    assert pdb.project_for_path(conn, _p("www", "application")).id == outer


def test_project_for_path_skips_archived(conn):
    pid = pdb.create_project(conn, name="P", folders=[_p("www", "app")])
    pdb.archive_project(conn, pid)

    assert pdb.project_for_path(conn, _p("www", "app", "src")) is None
    # Archived hidden from the default list but visible with include_archived.
    assert pdb.list_projects(conn) == []
    assert len(pdb.list_projects(conn, include_archived=True)) == 1

    pdb.restore_project(conn, pid)
    assert pdb.project_for_path(conn, _p("www", "app", "src")).id == pid


def test_active_pointer(conn):
    pid = pdb.create_project(conn, name="P")
    assert pdb.get_active_id(conn) is None

    pdb.set_active(conn, pid)
    assert pdb.get_active_id(conn) == pid

    pdb.set_active(conn, None)
    assert pdb.get_active_id(conn) is None


def test_branch_name_for_is_deterministic():
    proj = pdb.Project(id="p_1", slug="web-app", name="Web App", created_at=0)

    assert pdb.branch_name_for(proj, "t_abc") == "web-app/t_abc"
    assert pdb.branch_name_for(proj, "t_abc", title="Add login!") == "web-app/t_abc-add-login"
    # Stable across calls.
    assert pdb.branch_name_for(proj, "t_abc") == pdb.branch_name_for(proj, "t_abc")


def test_per_profile_isolation(tmp_path):
    # Two distinct DB paths stand in for two profiles' OPENAMER_HOME.
    a = pdb.connect(db_path=tmp_path / "a" / "projects.db")
    b = pdb.connect(db_path=tmp_path / "b" / "projects.db")
    try:
        pdb.create_project(a, name="Only In A", folders=[_p("a")])
        pdb.record_discovered_repos(a, [(_p("a", "scanned"), "scanned")])

        assert [p.slug for p in pdb.list_projects(a)] == ["only-in-a"]
        assert pdb.list_projects(b) == []
        assert [row["root"] for row in pdb.list_discovered_repos(a)] == [
            _p("a", "scanned")
        ]
        assert pdb.list_discovered_repos(b) == []
    finally:
        a.close()
        b.close()


def test_db_path_under_openamer_home():
    # Resolves under OPENAMER_HOME (set by the autouse isolation fixture).
    assert pdb.projects_db_path().name == "projects.db"
    assert os.path.basename(str(pdb.projects_db_path().parent))  # non-empty parent
