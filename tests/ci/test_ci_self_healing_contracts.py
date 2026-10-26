"""CI must not lose the measurements it needs to route around its own failures.

Two lanes went red on an otherwise green ``main`` for reasons that were purely
bookkeeping:

``tests.yml``
    LPT slicing is only as good as the ``test_durations.json`` it is fed. Both
    the per-slice artifact upload and the ``save-durations`` job were gated on
    the run being green, so the one run whose durations mattered — the one that
    mis-bucketed a 300 s file into a slice full of small ones and then died —
    was the one run that published nothing. The cache froze at the last
    distribution that happened to be measured green and the mis-bucketing was
    replayed on every following run. A cache that only learns from success
    cannot correct the failure it produced.

``publish-e2e-evidence.yml``
    ``GH_IMAGE_SESSION_TOKEN`` is optional infrastructure (a user session
    token, which a PAT or the default ``GITHUB_TOKEN`` cannot substitute for).
    When it was absent the workflow failed with
    ``publish_e2e_evidence.py: error: GH_SESSION_TOKEN is required`` — a red
    workflow for a missing cosmetic secret that never affected the E2E run.

These assertions pin the *contract*, not a snapshot: whatever the step is
called and however the YAML is laid out, the durations input must be refreshed
from failing runs, and the attachment publisher must degrade instead of fail.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"


def _load(name: str) -> dict[str, Any]:
    data = yaml.safe_load((_WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{name} did not parse to a mapping"
    return data


def _jobs(workflow: dict[str, Any]) -> dict[str, Any]:
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict) and jobs, "workflow has no jobs"
    return jobs


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = job.get("steps")
    assert isinstance(steps, list) and steps
    return steps


def _find_step(job: dict[str, Any], needle: str) -> dict[str, Any]:
    for step in _steps(job):
        if needle.lower() in str(step.get("name", "")).lower():
            return step
    raise AssertionError(f"no step matching {needle!r} in job {job.get('name')!r}")


def test_per_slice_durations_survive_a_failed_slice() -> None:
    jobs = _jobs(_load("tests.yml"))
    test_job = jobs["test"]
    step = _find_step(test_job, "durations")
    condition = str(step.get("if", ""))
    assert "always()" in condition.replace(" ", ""), (
        "the per-slice duration upload must run even when the slice failed: a slice "
        "that timed out is precisely the one whose measurements the balancer needs "
        "next run. Without it the LPT input never learns from the failure it caused. "
        f"Found if: {condition!r}"
    )


def test_duration_cache_is_refreshed_from_failing_runs() -> None:
    jobs = _jobs(_load("tests.yml"))
    save = jobs["save-durations"]
    condition = str(save.get("if", "")).replace(" ", "")
    assert "always()" in condition, (
        "save-durations must run with always(): gating it on a green test job freezes "
        "the duration cache at the last passing distribution and replays the "
        f"mis-bucketing that caused the failure. Found if: {condition!r}"
    )
    # It must still be a main-only job: PR runs read the cache, they don't write it.
    assert "refs/heads/main" in condition, (
        "save-durations must stay restricted to main; PR runs would race on the cache key"
    )


def test_durations_are_uploaded_before_the_cache_is_merged() -> None:
    """The merge job downloads what the slices uploaded — both must be wired."""
    jobs = _jobs(_load("tests.yml"))
    upload = _find_step(jobs["test"], "durations")
    assert upload.get("uses", "").startswith("actions/upload-artifact"), upload.get("uses")
    download = _find_step(jobs["save-durations"], "Download")
    assert download.get("uses", "").startswith("actions/download-artifact"), download.get("uses")


def test_e2e_evidence_publisher_degrades_without_a_session_token() -> None:
    jobs = _jobs(_load("publish-e2e-evidence.yml"))
    job = jobs["publish"]
    step = _find_step(job, "evidence")
    run = str(step.get("run", ""))
    assert "GH_SESSION_TOKEN" in run, "publisher must inspect the session token itself"
    guard = re.search(r"if\s+\[\s*-z\s+\"?\$\{GH_SESSION_TOKEN:?-?", run)
    assert guard, (
        "the publisher must exit successfully when GH_SESSION_TOKEN is unset: the secret "
        "is optional infrastructure and its absence must not turn the workflow red"
    )
    # The guard has to come *before* the script is invoked, or the script's own
    # argparse failure wins again.
    guard_at = run.find("GH_SESSION_TOKEN:-")
    script_at = run.find("publish_e2e_evidence.py")
    assert -1 < guard_at < script_at, (
        "the missing-token check must run before publish_e2e_evidence.py is called"
    )


def test_publish_workflow_still_checks_out_the_default_branch_only() -> None:
    """The publisher treats the artifact as untrusted: it must never check out PR code."""
    jobs = _jobs(_load("publish-e2e-evidence.yml"))
    checkout = next(s for s in _steps(jobs["publish"]) if str(s.get("uses", "")).startswith("actions/checkout"))
    ref = str(checkout.get("with", {}).get("ref", ""))
    assert "default_branch" in ref, f"publisher must check out the default branch, found ref={ref!r}"
    assert "head_sha" not in ref, "publisher must never check out the untrusted PR head"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
