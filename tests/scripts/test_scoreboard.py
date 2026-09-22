"""Contract test for the capability scoreboard (scripts/scoreboard.py).

WHY THIS EXISTS
    The scoreboard's whole point is honesty: every number must name its source,
    and the report must state what it does NOT prove. Those two properties are
    the reason the script exists - without them it degenerates into the thing it
    replaced (`memory/benchmarks.json`: a self-scored number with no comparison
    and no caveat). So they are pinned here as a contract, not left to review.

HERMETIC
    No network, no GitHub API, no real HOME. `gh()` is replaced and `HOME`
    points at a tmp dir, so the test never touches the live machine.
"""
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("scoreboard", REPO / "scripts" / "scoreboard.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load scoreboard.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["scoreboard"] = mod
    spec.loader.exec_module(mod)
    return mod


SB = _load()


def _fixture(home: Path, monkeypatch_gh=True):
    """A minimal, deterministic world: one competitor + our two real files."""
    (home / "skills").mkdir(parents=True, exist_ok=True)
    (home / "skills" / "a").mkdir()
    (home / "skills" / "a" / "SKILL.md").write_text("x", encoding="utf-8")
    (home / "cron").mkdir(parents=True, exist_ok=True)
    (home / "cron" / "jobs.json").write_text(
        json.dumps([{"enabled": True}, {"enabled": False}]), encoding="utf-8")
    (home / "memory").mkdir(parents=True, exist_ok=True)
    (home / "memory" / "longterm_episodes.jsonl").write_text(
        '{"a":1}\n{"b":2}\n', encoding="utf-8")
    (home / "memory" / "benchmarks.json").write_text(
        json.dumps({"best": {"overall": 0.7},
                    "runs": [{"overall_accuracy": 0.0, "knowledge": {"questions": {"q": {"error": "401"}}}}]}),
        encoding="utf-8")
    (home / "scripts" / "training").mkdir(parents=True, exist_ok=True)

    def fake_gh(path, tok):
        if path == "openamer/openamer":
            return {"stargazers_count": 6, "forks_count": 3, "open_issues_count": 25,
                    "created_at": "2026-08-16T00:25:37Z"}
        return {"stargazers_count": 100, "forks_count": 10, "open_issues_count": 1,
                "created_at": "2020-01-01T00:00:00Z"}

    if monkeypatch_gh:
        SB.gh = fake_gh
    SB.HOME = home


def test_star_counts_come_from_the_api_not_from_memory(tmp_path):
    """Our row must be the live figure, and competitors must be sorted by stars."""
    _fixture(tmp_path)
    d = SB.build()
    assert d["ours"]["stars"] == 6, d["ours"]
    assert "GitHub API openamer/openamer" in d["ours"]["source"]
    stars = [c["stars"] for c in d["competitors"]]
    assert stars == sorted(stars, reverse=True), stars


def test_every_capability_value_names_its_source(tmp_path):
    """The core anti-fabrication rule: a number without a source is not allowed."""
    _fixture(tmp_path)
    cap = SB.build()["capability"]
    assert cap, "capability section is empty"
    for key, val in cap.items():
        assert isinstance(val, dict), f"{key} must carry value+source, got {val!r}"
        assert val.get("source"), f"{key} has no source"
        assert val.get("value") is not None, f"{key} has no value"


def test_report_states_what_it_does_not_prove(tmp_path):
    """A scoreboard with no honest-limits section is the failure it replaced."""
    _fixture(tmp_path)
    md = SB.render(SB.build())
    assert "What this does NOT prove" in md
    assert "UNMEASURED" in md or "not" in md.lower()


def test_report_does_not_claim_superiority(tmp_path):
    """Guard against the flattering-sentence failure mode."""
    _fixture(tmp_path)
    md = SB.render(SB.build()).lower()
    for claim in ("better than all", "we win", "market leader", "best agent"):
        assert claim not in md, f"scoreboard claims {claim!r}"


def test_learner_yield_is_computed_from_the_log_not_assumed(tmp_path):
    """Two cycles, one rejected -> 50.0%. Measured, not a constant."""
    _fixture(tmp_path)
    now = __import__("datetime").datetime.now().isoformat()
    (tmp_path / "scripts" / "training" / "internet_learn_log.jsonl").write_text(
        json.dumps({"ts": now, "result": "learned: something"}) + "\n" +
        json.dumps({"ts": now, "result": "rejected, not trained (gated)"}) + "\n",
        encoding="utf-8")
    y = SB.learner_rate(1)
    assert y == {"cycles": 2, "rejected": 1, "yield_pct": 50.0}, y


def test_self_benchmark_reports_the_error_count(tmp_path):
    """The 401 failure must surface as a number, not be rounded into a score."""
    _fixture(tmp_path)
    b = SB.self_benchmark()
    assert b["last_errors"] == 1, b
    assert b["last_overall"] == 0.0, b


def test_json_mode_is_serialisable(tmp_path):
    """--json is consumed by other tools; it must round-trip."""
    _fixture(tmp_path)
    d = SB.build()
    assert json.loads(json.dumps(d, ensure_ascii=False)) == d
