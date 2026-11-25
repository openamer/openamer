"""The deploy workflow's trigger surface, pinned.

Why: on 2026-11-25 a comment was inserted between ``workflow_dispatch:`` and its
``inputs:`` key, which silently moved the inputs under ``workflow_run``. YAML
still parsed, the workflow still triggered — only ``gh workflow run -f
skills_index_run_id=...`` started failing with

    422 Unexpected inputs provided: ["skills_index_run_id", ...]

which is the mechanism the deploy needs to reuse a freshly built skills index
instead of crawling (and burning the installation's API quota). The failure was
invisible in review; these assertions make it loud.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-site.yml"
INDEX_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "skills-index.yml"


def _on(workflow: dict) -> dict:
    # YAML 1.1 parses the bare key `on` as the boolean True.
    return workflow.get("on") or workflow.get(True)


def test_dispatch_inputs_stay_under_workflow_dispatch() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    on = _on(workflow)
    assert set(on["workflow_dispatch"]["inputs"]) == {
        "skills_index_run_id",
        "rebuild_skills_index",
    }, "the deploy can only be pointed at an index artifact through these inputs"


def test_index_build_completion_triggers_the_deploy() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    on = _on(workflow)
    run = on["workflow_run"]
    assert run["workflows"] == ["Build Skills Index"]
    assert run["types"] == ["completed"]
    assert "inputs" not in run, "workflow_run has no inputs — inputs belong to workflow_dispatch"


def test_deploy_reuses_the_triggering_index_run() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["deploy-docs"]["steps"]
    prepare = next(s for s in steps if s.get("name", "").startswith("Prepare skills index"))
    assert "github.event.workflow_run.id" in prepare["env"]["SKILLS_INDEX_RUN_ID"]
    # `gh run download` needs Actions:read, which the App token does not carry here.
    assert prepare["env"]["GH_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"
    guard = str(workflow["jobs"]["deploy-docs"].get("if", ""))
    assert "workflow_run.conclusion == 'success'" in guard, "never deploy from a failed index build"


def test_index_workflow_no_longer_dispatches_the_deploy() -> None:
    workflow = yaml.safe_load(INDEX_WORKFLOW.read_text(encoding="utf-8"))
    assert list(workflow["jobs"]) == ["build-index"], (
        "trigger-deploy dispatched deploy-site from inside the crawl and died on "
        "HTTP 403 (installation rate limit); workflow_run replaced it"
    )


def test_the_pages_artifact_is_waited_for_before_deploying():
    """deploy-pages sees an empty artifact list for a moment after upload.

    Measured 2026-11-25 (run 45702845227): upload reported "Final size is
    139257634 bytes" and the very next step logged "Found 0 artifact(s)" and
    failed. The wait step makes that race visible instead of fatal.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["deploy-docs"]["steps"]
    names = [step.get("name", step.get("uses", "")) for step in steps]
    wait = "Wait for the Pages artifact to be visible"
    assert wait in names, names
    assert names.index(wait) < names.index("Deploy to GitHub Pages")
