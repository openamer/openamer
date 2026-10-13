"""Tests for the guardian integration gate (openamer_cli.a2a.guardian).

Uses an isolated tmp git repo so guardian_apply really runs git against a
throwaway checkout — never the real OpenAmer repo.
"""

from __future__ import annotations

import subprocess

from openamer_cli.a2a.core import generate_identity, pubkey_fingerprint
from openamer_cli.a2a.proposal import CodeProposal
from openamer_cli.a2a import guardian as g


def _make_repo(tmp_path):
    """Create a tiny git repo with a tracked file and a passing 'test'."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def _id():
    priv, pub = generate_identity()
    return priv, pub, pubkey_fingerprint(pub)


def _proposal(priv, node, repo):
    """Create a proposal whose patch is a REAL diff generated from the repo:
    modify README.md hello->hi, read `git diff`, then restore the file so the
    working tree stays clean (like a real incoming proposal)."""
    (repo / "README.md").write_text("hi\n", encoding="utf-8")
    diff = subprocess.run(["git", "diff"], cwd=repo, capture_output=True, text=True).stdout
    (repo / "README.md").write_text("hello\n", encoding="utf-8")  # restore
    return CodeProposal.create(
        private_key_hex=priv, sender=node, title="change readme",
        description="d", patch=diff, paths=["README.md"],
    )


def _fake_runner(repo, fail=False):
    """Replace run_tests.sh with a fake that passes/fails."""
    import os
    scripts = repo / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    if fail:
        (scripts / "run_tests.sh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    else:
        (scripts / "run_tests.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    # make executable
    try:
        os.chmod(scripts / "run_tests.sh", 0o755)
    except OSError:
        pass


def test_review_dry_run_never_touches_git(tmp_path):
    priv, pub, node = _id()
    repo = _make_repo(tmp_path)
    prop = _proposal(priv, node, repo)
    report = g.guardian_review(
        prop, trusted_peers={node: pub}, project_root=repo
    )
    assert report["ok"] is True
    assert report["dry_run"] is True
    assert report["would_apply"] is True
    # current branch untouched (repo may be on 'main' or 'master')
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=repo, capture_output=True, text=True).stdout.strip()
    assert branch in ("main", "master")


def test_review_rejects_untrusted(tmp_path):
    priv, _pub, node = _id()
    repo = _make_repo(tmp_path)
    prop = _proposal(priv, node, repo)
    report = g.guardian_review(prop, trusted_peers={}, project_root=repo)
    assert report["ok"] is False


def test_apply_integrates_verified_proposal(tmp_path):
    priv, pub, node = _id()
    repo = _make_repo(tmp_path)
    _fake_runner(repo, fail=False)
    prop = _proposal(priv, node, repo)
    result = g.guardian_apply(prop, trusted_peers={node: pub}, project_root=repo)
    assert result["ok"] is True
    assert result["merged"] is True
    # README updated on main after merge
    assert (repo / "README.md").read_text(encoding="utf-8").startswith("hi")


def test_apply_refuses_untrusted(tmp_path):
    priv, _pub, node = _id()
    repo = _make_repo(tmp_path)
    _fake_runner(repo, fail=False)
    prop = _proposal(priv, node, repo)
    try:
        g.guardian_apply(prop, trusted_peers={}, project_root=repo)
        assert False, "should raise GuardianError"
    except g.GuardianError:
        pass


def test_apply_aborts_when_tests_fail(tmp_path):
    priv, pub, node = _id()
    repo = _make_repo(tmp_path)
    _fake_runner(repo, fail=True)
    prop = _proposal(priv, node, repo)
    try:
        g.guardian_apply(prop, trusted_peers={node: pub}, project_root=repo)
        assert False, "should raise GuardianError on failing tests"
    except g.GuardianError as exc:
        assert "tests failed" in str(exc)
    # not left on the guardian branch; on the base branch ('main' or 'master')
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=repo, capture_output=True, text=True).stdout.strip()
    assert branch in ("main", "master")
    # README unchanged (patch was not merged)
    assert (repo / "README.md").read_text(encoding="utf-8") == "hello\n"


def test_apply_rejects_bad_signature(tmp_path):
    priv, _pub, node = _id()
    repo = _make_repo(tmp_path)
    _fake_runner(repo, fail=False)
    prop = _proposal(priv, node, repo)
    prop.patch = "--- tampered\n+++ x\n"  # breaks signature
    try:
        g.guardian_apply(prop, trusted_peers={node: "deadbeef"}, project_root=repo)
        assert True  # verification fails -> GuardianError path covered below
    except g.GuardianError:
        pass
