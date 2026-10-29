"""Tests for the per-profile Projects store (openamer_cli/projects_db)."""

from __future__ import annotations

import os

import pytest

from openamer_cli import projects_db as pdb


@pytest.fixture
def conn(tmp_path):
    c = pdb.connect(db_path=tmp_path / "projects.db")
    try:
        yield c
    finally:
        c.close()



def _host(path: str) -> str:
    """The host's spelling of an absolute fixture path.

    The tests below deliberately use POSIX literals ("/a", "/www/alpha",
    "/tmp/openamer") as *inputs* -- they are readable and the product's job is
    to normalise them. What they must not do is expect them back unchanged:
    the product normalises with the host's rules, so on Windows "/a" comes back
    as "C:\\a". Comparing against the product's own normaliser keeps the
    inputs readable and the assertion honest.
    """
    return pdb._normalize_path(path)


def _fixture_path(tmp_path, *parts) -> str:
    """A host-native absolute path to use as a fixture.

    These tests used POSIX literals ("/a", "/www/app"). The product normalises
    with the host's rules, so on Windows "/a" becomes "C:\\a" and every
    comparison failed on the drive prefix -- the test was pinning the POSIX
    spelling of an absolute path, not the behaviour it meant to check.
    Measured 2026-10-25: four failures, all this.
    """
    return str(tmp_path.joinpath(*parts))

def test_record_and_list_discovered_repos(conn):
    n = pdb.record_discovered_repos(conn, [("/www/alpha", "alpha"), ("/www/beta", None)])
    assert n == 2

    rows = {r["root"]: r["label"] for r in pdb.list_discovered_repos(conn)}
    assert rows[_host("/www/alpha")] == "alpha"
    # Label defaults to the basename when not given.
    assert rows[_host("/www/beta")] == "beta"


def test_record_discovered_repos_upserts(conn):
    pdb.record_discovered_repos(conn, [("/www/alpha", "old")])
    pdb.record_discovered_repos(conn, [("/www/alpha", "new")])

    rows = pdb.list_discovered_repos(conn)
    assert len(rows) == 1
    assert rows[0]["label"] == "new"


def test_record_discovered_repos_replace_drops_stale_rows(conn):
    pdb.record_discovered_repos(conn, [("/www/alpha", "alpha"), ("/www/beta", "beta")])
    pdb.record_discovered_repos(conn, [("/www/alpha", "fresh")], replace=True)

    rows = {r["root"]: r["label"] for r in pdb.list_discovered_repos(conn)}
    assert rows == {_host("/www/alpha"): "fresh"}


def test_discovery_policy_change_clears_only_discovered_rows(conn):
    project_id = pdb.create_project(conn, name="Explicit", folders=["/www/explicit"])
    pdb.record_discovered_repos(
        conn, [("/www/scanned", "scanned")], policy_key="policy-a"
    )

    assert pdb.reconcile_discovered_repos_policy(conn, "policy-b") is True
    assert pdb.list_discovered_repos(conn) == []
    assert pdb.get_project(conn, project_id) is not None
    assert pdb.get_discovery_policy_key(conn) == "policy-b"


def test_default_policy_adopts_unversioned_cache_without_clearing(conn):
    pdb.record_discovered_repos(conn, [("/www/scanned", "scanned")])

    assert (
        pdb.reconcile_discovered_repos_policy(
            conn, "default-policy", preserve_unversioned=True
        )
        is False
    )
    assert [row["root"] for row in pdb.list_discovered_repos(conn)] == [
        _host("/www/scanned")
    ]
    assert pdb.get_discovery_policy_key(conn) == "default-policy"


def test_clear_discovered_repos_records_policy_atomically(conn):
    pdb.record_discovered_repos(conn, [("/www/scanned", "scanned")])

    pdb.clear_discovered_repos(conn, policy_key="disabled")

    assert pdb.list_discovered_repos(conn) == []
    assert pdb.get_discovery_policy_key(conn) == "disabled"


def test_create_get_list(conn):
    pid = pdb.create_project(conn, name="OpenAmer Agent", folders=["/tmp/openamer"])
    proj = pdb.get_project(conn, pid)

    assert proj is not None
    assert proj.slug == "openamer-agent"
    assert proj.name == "OpenAmer Agent"
    # First folder becomes primary.
    assert proj.primary_path == _host("/tmp/openamer")
    assert [f.path for f in proj.folders] == [_host("/tmp/openamer")]
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


def test_add_remove_folder_and_primary_repoint(conn, tmp_path):
    a, b, c = (_fixture_path(tmp_path, n) for n in ("a", "b", "c"))
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
    pid = pdb.create_project(conn, name="P", folders=["/a"])
    assert pdb.set_primary(conn, pid, "/nope") is False
    assert pdb.set_primary(conn, pid, "/a") is True


def test_paths_normalized(conn, tmp_path):
    messy = _fixture_path(tmp_path, "a", "b", "..", "c") + os.sep
    pid = pdb.create_project(conn, name="P", folders=[messy])
    proj = pdb.get_project(conn, pid)
    # Trailing slash stripped, .. collapsed.
    assert proj.primary_path == _fixture_path(tmp_path, "a", "c")


def test_project_for_path_longest_prefix(conn, tmp_path):
    www = _fixture_path(tmp_path, "www")
    app = _fixture_path(tmp_path, "www", "app")
    outer = pdb.create_project(conn, name="Outer", folders=[www])
    inner = pdb.create_project(conn, name="Inner", folders=[app])

    assert pdb.project_for_path(conn, _fixture_path(tmp_path, "www", "app", "src", "x.py")).id == inner
    assert pdb.project_for_path(conn, _fixture_path(tmp_path, "www", "other")).id == outer
    assert pdb.project_for_path(conn, _fixture_path(tmp_path, "elsewhere")) is None
    # Segment-wise prefix only: /www/app must not match /www/application.
    assert pdb.project_for_path(conn, _fixture_path(tmp_path, "www", "application")).id == outer


def test_project_for_path_skips_archived(conn):
    pid = pdb.create_project(conn, name="P", folders=["/www/app"])
    pdb.archive_project(conn, pid)

    assert pdb.project_for_path(conn, "/www/app/src") is None
    # Archived hidden from the default list but visible with include_archived.
    assert pdb.list_projects(conn) == []
    assert len(pdb.list_projects(conn, include_archived=True)) == 1

    pdb.restore_project(conn, pid)
    assert pdb.project_for_path(conn, "/www/app/src").id == pid


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
        root_a = _fixture_path(tmp_path, "root-a")
        scanned = _fixture_path(tmp_path, "root-a", "scanned")
        pdb.create_project(a, name="Only In A", folders=[root_a])
        pdb.record_discovered_repos(a, [(scanned, "scanned")])

        assert [p.slug for p in pdb.list_projects(a)] == ["only-in-a"]
        assert pdb.list_projects(b) == []
        assert [row["root"] for row in pdb.list_discovered_repos(a)] == [scanned]
        assert pdb.list_discovered_repos(b) == []
    finally:
        a.close()
        b.close()


def test_db_path_under_openamer_home():
    # Resolves under OPENAMER_HOME (set by the autouse isolation fixture).
    assert pdb.projects_db_path().name == "projects.db"
    assert os.path.basename(str(pdb.projects_db_path().parent))  # non-empty parent
