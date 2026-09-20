"""Tests for the Darwin Engine (evolutionary skill ecosystem)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "darwin_engine", REPO / "scripts" / "darwin_engine.py")
darwin = importlib.util.module_from_spec(spec)
sys.modules["darwin_engine"] = darwin
spec.loader.exec_module(darwin)


@pytest.fixture
def fake_skills(tmp_path, monkeypatch):
    skills = tmp_path / "skills"
    for name in ("alpha", "beta"):
        d = skills / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"# {name}\n\n## Trigger\nRun when X.\n", encoding="utf-8")
    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setattr(darwin, "DARWIN_DIR", tmp_path / "darwin")
    monkeypatch.setattr(darwin, "POPULATION_FILE", tmp_path / "darwin" / "population.json")
    monkeypatch.setattr(darwin, "HISTORY_FILE", tmp_path / "reports" / "darwin-history.jsonl")
    monkeypatch.setattr(darwin, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(darwin, "FITNESS_FILE", tmp_path / "reports" / "darwin-fitness.json")
    monkeypatch.setattr(darwin, "REPORT_FILE", tmp_path / "reports" / "darwin-report.md")
    monkeypatch.setattr(darwin, "PROBE_FILE", tmp_path / "reports" / "darwin-probe.json")
    monkeypatch.setattr(darwin, "TUNING_FILE", tmp_path / "darwin" / "tuning.json")
    return skills


def test_fitness_scores_all_skills(fake_skills):
    fitness = darwin.compute_fitness()
    assert set(fitness) == {"alpha", "beta"}
    for s in fitness.values():
        assert "fitness" in s and "usage" in s and "age_days" in s


def test_mutation_creates_child_variant(fake_skills):
    fitness = {"alpha": {"fitness": 10}, "beta": {"fitness": 5}}
    offspring = darwin.mutate(fitness, top_n=2, apply=True)
    assert len(offspring) == 2
    assert all(o["applied"] for o in offspring)
    child_dir = darwin.DARWIN_DIR / "offspring"
    metas = list(child_dir.glob("*.json"))
    assert len(metas) == 2
    # child SKILL.md exists for each meta
    for m in metas:
        meta = json.loads(m.read_text(encoding="utf-8"))
        assert (child_dir / meta["child"] / "SKILL.md").exists()


def test_mutation_ops_change_text(fake_skills):
    text = "# skill\n"
    for op in darwin.MUTATION_OPS:
        mutated = darwin._mutate_skill_md(text, op)
        assert mutated != text, f"op {op} produced no change"
        assert "## " in mutated


def test_crossover_combines_parents(fake_skills):
    res = darwin.crossover("alpha", "beta", apply=True)
    assert res is not None
    assert res["parents"] == ["alpha", "beta"]
    child_md = darwin.DARWIN_DIR / "offspring" / res["child"] / "SKILL.md"
    assert child_md.exists()
    assert "## Trigger" in child_md.read_text(encoding="utf-8")


def test_crossover_missing_skill_returns_none(fake_skills):
    assert darwin.crossover("alpha", "does-not-exist") is None


def test_compete_no_candidates(fake_skills):
    assert darwin.compete() == []


def test_report_renders_markdown(fake_skills):
    fitness = {"alpha": {"fitness": 9, "usage": 1, "age_days": 2,
                         "mutations_won": 0, "mutations_lost": 0,
                         "health": 1}}
    md = darwin.report(fitness, [], [])
    assert "# Darwin Engine Report" in md
    assert "alpha" in md

BS = chr(92)   # backslash, built at runtime so this file needs no literal escapes
NL = chr(10)   # newline
DQ = chr(34)   # double quote


def test_expand_env_vars_substitutes_paths_without_a_shell(monkeypatch):
    """The documented $OPENAMER_HOME form must reach Python as a real path.

    `python ...` verification blocks run without a shell, so an unexpanded
    $OPENAMER_HOME stayed a literal and Python resolved it as a relative
    path -- any skill written in the documented form failed its verification
    block and lost every duel on that alone, regardless of quality.
    """
    win_home = "C:" + BS + "Users" + BS + "x" + BS + "openamer"
    monkeypatch.setenv("OPENAMER_HOME", win_home)
    out = darwin._expand_env_vars(
        "python " + DQ + "$OPENAMER_HOME" + BS + "scripts" + BS + "s.py" + DQ)
    assert "$OPENAMER_HOME" not in out
    assert win_home in out

    # git-bash exports the MSYS form; it must become a native drive path
    monkeypatch.setenv("OPENAMER_HOME", "/c/Users/x/openamer")
    assert darwin._expand_env_vars(
        "python $OPENAMER_HOME/scripts/s.py") == "python C:/Users/x/openamer/scripts/s.py"

    # ${VAR} braces form
    assert darwin._expand_env_vars(
        "${OPENAMER_HOME}/s.py") == "C:/Users/x/openamer/s.py"


def test_expand_env_vars_leaves_plain_text_alone(monkeypatch):
    monkeypatch.delenv("NOT_SET_ANYWHERE", raising=False)
    plain = "python scripts/foo.py --json"
    assert darwin._expand_env_vars(plain) == plain
    assert darwin._expand_env_vars("$NOT_SET_ANYWHERE/x") == "$NOT_SET_ANYWHERE/x"


def test_run_skill_check_expands_env_var_block(tmp_path, monkeypatch):
    """End-to-end: a block whose script path comes from $OPENAMER_HOME runs."""
    home = tmp_path / "home"
    (home / "scripts").mkdir(parents=True)
    (home / "scripts" / "probe.py").write_text("print('probe-ok')", encoding="utf-8")

    skills = tmp_path / "skills"
    d = skills / "envvar-skill"
    d.mkdir(parents=True)
    body = "# envvar-skill" + NL + NL + "## Verification" + NL + NL + "```bash" + NL
    body += ("python " + DQ + "$OPENAMER_HOME" + BS + "scripts" + BS
             + "probe.py" + DQ + NL + "```" + NL)
    (d / "SKILL.md").write_text(body, encoding="utf-8")

    monkeypatch.setattr(darwin, "SKILLS_DIR", skills)
    monkeypatch.setenv("OPENAMER_HOME", str(home))

    res = darwin.run_skill_check("envvar-skill")
    assert res["ok"] is True, res
    assert res["exit_code"] == 0, res
    assert "No such file" not in (res.get("stderr_tail") or "")

