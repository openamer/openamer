"""The Pages artifact must contain the marketing root *and* the built docs.

Measured 2026-11-24: `deploy-site.yml` staged only `website/build` into
`_site/docs/`, never the repository marketing pages. Publishing that artifact
would have turned `openamer.com/` into a 404 while fixing `openamer.com/docs/` —
one broken URL traded for another, discovered only on the CDN.

These tests run the workflow's own staging script (extracted from the YAML, not
copied here) against a stub tree, so the assertion cannot drift from the step it
describes.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-site.yml"
MARKETING = "<!-- marketing root -->"
DOCS = "<!-- built docs -->"


def stage_script() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["deploy-docs"]["steps"]
    step = next(item for item in steps if item.get("name") == "Stage deployment")
    return step["run"]


@pytest.fixture()
def tree(tmp_path):
    """A stub checkout: marketing pages plus a built site."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.html").write_text(MARKETING, encoding="utf-8")
    (tmp_path / "docs" / "CNAME").write_text("openamer.com\n", encoding="utf-8")
    build = tmp_path / "website" / "build"
    build.mkdir(parents=True)
    (build / "index.html").write_text(DOCS, encoding="utf-8")
    (build / "llms.txt").write_text("llms\n", encoding="utf-8")
    return tmp_path


def run_stage(root: Path) -> subprocess.CompletedProcess:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required to execute the staging step")
    return subprocess.run(
        [bash, "-e", "-c", stage_script()],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def test_artifact_has_both_roots(tree):
    result = run_stage(tree)

    assert result.returncode == 0, result.stderr
    assert (tree / "_site" / "index.html").read_text(encoding="utf-8") == MARKETING
    assert (tree / "_site" / "docs" / "index.html").read_text(encoding="utf-8") == DOCS


def test_marketing_assets_and_cname_are_published(tree):
    result = run_stage(tree)

    assert result.returncode == 0, result.stderr
    assert (tree / "_site" / "CNAME").is_file(), "the domain mapping must ship with the site"


def test_llms_files_are_published_at_the_site_root(tree):
    result = run_stage(tree)

    assert result.returncode == 0, result.stderr
    assert (tree / "_site" / "llms.txt").is_file()


def test_missing_marketing_tree_fails_the_step(tmp_path):
    """No root page is a broken site, so the step must fail instead of shipping it."""
    build = tmp_path / "website" / "build"
    build.mkdir(parents=True)
    (build / "index.html").write_text(DOCS, encoding="utf-8")

    result = run_stage(tmp_path)

    assert result.returncode != 0
