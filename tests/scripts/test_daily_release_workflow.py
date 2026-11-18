"""The daily release must never push to `main` again.

`main` requires changes to arrive through a pull request. The release script
pushed the version bump straight at it, so every run died in ~1 minute with
GH006 — and the failure was invisible from the outside: the release page simply
stopped updating while the schedule kept firing.

These tests pin the contract that replaced it: the bump goes out on a release
branch, a PR is opened, and only a commit that exists on a remote is tagged.
"""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "daily-release.py"
WORKFLOW = REPO / ".github" / "workflows" / "release-daily.yml"


def test_no_direct_push_to_main() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "HEAD:main" not in source, (
        "main is protected: pushing the bump at refs/heads/main fails with GH006. "
        "Publish it on a release branch and open a PR instead."
    )


def test_bump_is_published_through_a_pull_request() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"pr", "create"' in source, "the release job must open a PR for the bump"
    assert '"pr", "merge"' in source, "and try to merge it"
    assert 'f"release/{tag}"' in source, "the bump goes out on release/<tag>"
    assert "publish_version_bump" in source, "the PR flow must have one owner"


def test_workflow_may_open_pull_requests() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull-requests: write" in workflow, (
        "gh pr create needs pull-requests: write; contents: write alone is not enough"
    )


def test_tag_only_after_the_commit_is_on_the_remote() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    tag_index = source.index('git("tag", "-a"')
    guard_index = source.index("refusing to tag")

    assert guard_index < tag_index, "the reachability check must run before the tag is created"
