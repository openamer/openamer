"""The daily release must never push to `main` again.

`main` requires changes to arrive through a pull request. The release script
pushed the version bump straight at it, so every run died in ~1 minute with
GH006 — and the failure was invisible from the outside: the release page simply
stopped updating while the schedule kept firing.

These tests pin the contract that replaced it: the bump goes out on a release
branch, a PR is opened, and only a commit that exists on a remote is tagged.
"""
from __future__ import annotations

import importlib.util
import pathlib
import types

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


def test_both_artifact_jobs_retry_and_name_the_release() -> None:
    """A failed upload must not be the end of the release.

    Measured 2026-11-18 (run 44333660100): both artifact jobs built fine, then
    `gh release upload` answered "release not found" for a published release the
    REST API resolved (id 450165465) and an owner token could upload to minutes
    later. Two upload sites, one bare command, no retry, no diagnostics — the
    release shipped empty and the log named no cause.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    uploads = [line.strip() for line in workflow.splitlines() if "gh release upload" in line]

    assert len(uploads) == 2, f"expected two upload sites, found {len(uploads)}: {uploads}"
    for line in uploads:
        assert "--repo $repo" in line, f"the upload must name the repo, not infer it: {line}"
        assert "--clobber" in line, f"a re-run must replace the asset: {line}"

    retries = "for ($i = 1; $i -le 3; $i++)"
    assert workflow.count(retries) == 2, "both upload sites must retry a bounded number of times"
    assert workflow.count("gh release view $tag --repo $repo") == 2, (
        "on failure the step must print the release gh sees, or the next occurrence hides its cause"
    )

# --------------------------------------------------------------------------
# The decision logic, exercised without the network: push ok + merge refused
# must still count as "published", because the release ships from the branch.
# --------------------------------------------------------------------------
import importlib.util  # noqa: E402
import subprocess  # noqa: E402
import types  # noqa: E402


def _release_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("daily_release", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = ""
        self.stderr = stderr


def _fake_git(returncode: int = 0):
    def git(*_args: str) -> _Result:
        return _Result(returncode)
    return git


def test_unmerged_pr_still_counts_as_published(monkeypatch, capsys) -> None:
    module = _release_module()
    monkeypatch.setattr(module, "git", _fake_git(0))

    seen: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        seen.append(cmd)
        return _Result(1, "refusing to allow a GitHub App to merge") if "merge" in cmd else _Result(0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    pushed, merged = module.publish_version_bump("release/vTEST", "vTEST", "2026.11.18")

    assert pushed is True, "the branch push is what makes the release possible"
    assert merged is False
    assert any("pr" in cmd and "create" in cmd for cmd in seen), "a PR must be opened"
    assert "needs a human merge" in capsys.readouterr().out


def test_merged_pr_reports_merged(monkeypatch) -> None:
    module = _release_module()
    monkeypatch.setattr(module, "git", _fake_git(0))
    monkeypatch.setattr(module.subprocess, "run", lambda cmd, **_kw: _Result(0))

    pushed, merged = module.publish_version_bump("release/vTEST", "vTEST", "2026.11.18")

    assert (pushed, merged) == (True, True)


def test_failed_branch_push_stops_the_release(monkeypatch) -> None:
    module = _release_module()
    module.git = _fake_git(1)

    pushed, merged = module.publish_version_bump("release/vTEST", "vTEST", "2026.11.18")

    assert (pushed, merged) == (False, False)
