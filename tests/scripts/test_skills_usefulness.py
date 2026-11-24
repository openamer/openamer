"""Tests for scripts/skills_usefulness.py.

The first version of the checker reported 25 of 44 skills as BROKEN because a
`scripts/x.py` citation was resolved against the skill's own directory instead of
the repo. These tests exist to keep that class of false positive out: a checker
that over-reports is worse than none, because it turns a real 15-skill finding
into noise nobody reads.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "scripts" / "skills_usefulness.py"


@pytest.fixture()
def checker(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("skills_usefulness", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    skills = tmp_path / "skills"
    repo = tmp_path / "repo"
    skills.mkdir()
    repo.mkdir()
    monkeypatch.setattr(module, "SKILLS", skills)
    monkeypatch.setattr(module, "HOME", tmp_path)
    monkeypatch.setattr(module, "REPO", repo)
    monkeypatch.setattr(module, "OUT", tmp_path / "reports")
    monkeypatch.setattr(module, "JOBS", tmp_path / "jobs.json")
    return module


def make_skill(root: Path, name: str, body: str, files: dict[str, str] | None = None) -> Path:
    directory = root / "category" / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: a test skill\n---\n\n{body}\n", encoding="utf-8"
    )
    for relative, content in (files or {}).items():
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return directory


def test_clean_skill_is_verified(checker):
    make_skill(checker.SKILLS, "clean-skill", "Uses `references/notes.md` at runtime.")
    (checker.SKILLS / "category" / "clean-skill" / "references").mkdir()
    (checker.SKILLS / "category" / "clean-skill" / "references" / "notes.md").write_text("ok", encoding="utf-8")

    row = checker.check_skill("clean-skill", checker.SKILLS / "category" / "clean-skill" / "SKILL.md")

    assert row["verdict"] == "VERIFIED"
    assert row["problems"] == []


def test_missing_reference_file_is_broken(checker):
    make_skill(checker.SKILLS, "dead-link-skill", "See `references/gone.md`.")

    row = checker.check_skill("dead-link-skill", checker.SKILLS / "category" / "dead-link-skill" / "SKILL.md")

    assert row["verdict"] == "BROKEN"
    assert any("references/gone.md" in problem for problem in row["problems"])


def test_repo_script_citation_resolves_against_the_repo(checker):
    """The measured false positive: `scripts/x.py` is a repo path, not a sibling file."""
    make_skill(checker.SKILLS, "cites-repo-skill", "Run `scripts/run_tests.sh` instead of pytest.")
    (checker.REPO / "scripts").mkdir()
    (checker.REPO / "scripts" / "run_tests.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    row = checker.check_skill("cites-repo-skill", checker.SKILLS / "category" / "cites-repo-skill" / "SKILL.md")

    assert row["verdict"] == "VERIFIED", row["problems"]


def test_repo_script_shipped_inside_the_skill_also_resolves(checker):
    make_skill(
        checker.SKILLS,
        "ships-script-skill",
        "Run `scripts/helper.py`.",
        files={"scripts/helper.py": "print('hi')\n"},
    )

    row = checker.check_skill("ships-script-skill", checker.SKILLS / "category" / "ships-script-skill" / "SKILL.md")

    assert row["verdict"] == "VERIFIED", row["problems"]


def test_missing_repo_script_is_broken(checker):
    make_skill(checker.SKILLS, "ghost-script-skill", "Run `scripts/does_not_exist.py`.")

    row = checker.check_skill("ghost-script-skill", checker.SKILLS / "category" / "ghost-script-skill" / "SKILL.md")

    assert row["verdict"] == "BROKEN"
    assert any("does_not_exist.py" in problem for problem in row["problems"])


def test_uncompilable_shipped_script_is_broken(checker):
    make_skill(
        checker.SKILLS,
        "broken-python-skill",
        "Ships a script.",
        files={"probe.py": "def broken(:\n"},
    )

    row = checker.check_skill("broken-python-skill", checker.SKILLS / "category" / "broken-python-skill" / "SKILL.md")

    assert row["verdict"] == "BROKEN"
    assert any(problem.startswith("compile:") for problem in row["problems"])


def test_frontmatter_name_must_match_directory(checker):
    directory = make_skill(checker.SKILLS, "dir-name-skill", "no claims here")
    (directory / "SKILL.md").write_text(
        "---\nname: other-name\ndescription: mismatch\n---\n", encoding="utf-8"
    )

    row = checker.check_skill("dir-name-skill", directory / "SKILL.md")

    assert row["verdict"] == "BROKEN"
    assert any("frontmatter" in problem for problem in row["problems"])


def test_population_includes_cron_attached_skills(checker, tmp_path):
    make_skill(checker.SKILLS, "cron-skill", "body")
    checker.JOBS.write_text(
        json.dumps({"jobs": [{"jobs_id": "x", "skills": ["cron-skill"]}]}), encoding="utf-8"
    )

    assert "cron-skill" in checker.cron_population()


def test_report_is_written_and_exit_code_follows_verdicts(checker, monkeypatch, tmp_path):
    make_skill(checker.SKILLS, "dead-link-skill", "See `references/gone.md`.")
    # The population is centrality + cron-attached, so pin the skill into it the
    # way the fleet does, instead of relying on a reference count it cannot have.
    checker.JOBS.write_text(
        json.dumps({"jobs": [{"job_id": "j1", "skills": ["dead-link-skill"]}]}), encoding="utf-8"
    )
    monkeypatch.setattr("sys.argv", ["skills_usefulness.py"])

    code = checker.main()

    assert code == 1
    payload = json.loads((tmp_path / "reports" / "latest.json").read_text(encoding="utf-8"))
    assert payload["verdicts"]["BROKEN"] == 1
    assert payload["population"] == 1


def test_empty_population_is_not_a_pass(checker, monkeypatch):
    """Nothing measured must exit 2, never 0: an empty run is not a green run."""
    make_skill(checker.SKILLS, "lonely-skill", "no claims and nobody cites me")
    monkeypatch.setattr("sys.argv", ["skills_usefulness.py"])

    assert checker.main() == 2
