#!/usr/bin/env python3
"""Tests for auto_skill_creation.py — dedup guards against re-creating known skills.

Run:  python test_auto_skill_creation.py

Regression guard for the bug fixed 11.09: `dedupe_check()` compared only a
description prefix, but the answer text drifts run-to-run while the question
slug stays constant — so the same skill was re-created (and overwritten) on
every run. Live evidence: the registry held 195 entries across just 33 unique
names, and a run reporting "1 new skill" produced zero net-new directories.

Every test works in a TEMP skills dir + TEMP registry; the real repo
`skills/auto-generated/` and the live `auto_skills.json` are never touched.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_skill_creation as asc


def _sandbox():
    """Point the module at temp skills dir + temp registry, return both paths."""
    d = tempfile.mkdtemp(prefix="autoskill_test_")
    skills = os.path.join(d, "skills")
    os.makedirs(skills, exist_ok=True)
    registry = os.path.join(d, "auto_skills.json")
    asc.AUTO_SKILLS = skills
    asc.REGISTRY = registry
    # The writer dual-writes (repo + live tree). In a sandbox the live target
    # MUST be disabled too, or every fixture skill is mirrored into the real
    # <home>/skills/auto-generated and the next run dedupes against its own
    # leftovers (measured 23.09.26: 5 stray dirs + 5 spurious failures).
    asc.LIVE_AUTO_SKILLS = None
    return skills, registry


def test_name_slug_is_stable_across_drifting_answers():
    """The same question must always slugify to the same skill name."""
    q = "Find the structural connection between energy efficiency and learning process"
    a1 = "KI-Performance-Optimierung: Python-Skript fuer RAM/Disk/Cron-Monitoring"
    a2 = "Performance optimization loop: monitor RAM, disk and cron timings"
    skills, _ = _sandbox()
    first = asc.create_skill_from_insight(q, a1, "test")
    second = asc.create_skill_from_insight(q, a2, "test")
    assert first is not None, "first insight should create a skill"
    assert second is None, "same question with a different answer is a duplicate"
    assert len(os.listdir(skills)) == 1, os.listdir(skills)


def test_existing_directory_blocks_recreation():
    """A pre-existing skill dir is enough to reject, even with an empty registry."""
    q = "How does energy efficiency relate to agent architecture"
    a = "A" * 120
    skills, _ = _sandbox()
    assert asc.create_skill_from_insight(q, a, "test") is not None
    # wipe the registry: the on-disk directory alone must still dedup
    with open(asc.REGISTRY, "w", encoding="utf-8") as f:
        json.dump({"created": [], "count": 0}, f)
    assert asc.create_skill_from_insight(q, a, "test") is None
    assert len(os.listdir(skills)) == 1


def test_identical_description_blocks_even_under_a_new_slug():
    """The original prefix rule still holds: same insight text → duplicate."""
    skills, _ = _sandbox()
    a = "Identical insight answer text that is comfortably longer than fifty chars"
    assert asc.create_skill_from_insight("first phrasing of the question", a, "t") is not None
    assert asc.create_skill_from_insight("second phrasing of the question", a, "t") is None
    assert len(os.listdir(skills)) == 1


def test_distinct_insights_still_create_distinct_skills():
    """The guard must not over-block: genuinely new insights still land."""
    skills, _ = _sandbox()
    a1 = "First distinct answer about quantization and 4-bit inference on CPUs ok"
    a2 = "Second distinct answer about retrieval augmented generation pipelines ok"
    assert asc.create_skill_from_insight("question alpha about quantization", a1, "t") is not None
    assert asc.create_skill_from_insight("question beta about retrieval", a2, "t") is not None
    assert len(os.listdir(skills)) == 2


def test_registry_records_each_created_skill_once():
    """Registry entries must stay unique by name — no duplicate bookkeeping."""
    skills, registry = _sandbox()
    q = "Repeated question about latency budgets in local inference stacks"
    for ans in ("answer one " * 10, "answer two " * 10, "answer three " * 10):
        asc.create_skill_from_insight(q, ans, "t")
    reg = json.load(open(registry, encoding="utf-8"))
    names = [e["name"] for e in reg["created"]]
    assert len(names) == len(set(names)) == 1, names
    assert reg["count"] == 1


# --- portal/ad-chrome gate (bug live 16.09.26) ------------------------------
# The learner scraped a Chinese software-download SEO page for an EfficiencyQAT
# question and the writer turned the ad copy into the repo skill
# auto-efficiency-learning-efficientqat-llm. Readable != relevant.

SPAM_HI = ("CAD看图王 提供 嗨格式 2019-02-19 · 百度认证:苏州舜心科技有限公司 "
           "嗨格式 嗨格式是苏州开心盒子软件有限公司旗下的独立品牌。")
SPAM_QA = ("已赞过 已踩过 你对这个回答的评价是？ 评论 收起 读书小明白 "
           "高粉答主 2020-02-14 · 醉心答题，欢迎关注 知道答主 回答量： 12")


def test_portal_ad_chrome_is_rejected():
    """Two independent portal/ad markers → never write a SKILL.md."""
    skills, _ = _sandbox()
    assert asc.create_skill_from_insight("efficiency question", SPAM_HI, "t") is None
    assert asc.create_skill_from_insight("another question", SPAM_QA, "t") is None
    assert os.listdir(skills) == [], os.listdir(skills)


def test_real_chinese_technical_note_is_not_rejected():
    """A genuine Chinese LLM/quantization note must stay learnable.

    Guards against the tempting-but-wrong "reject anything CJK" rule: the
    corpus holds real Chinese technical rows with no portal markers.
    """
    zh_ok = ("量化技术将 LLM 的权重压缩到 2 位，使 llama2-70B 在推理时"
             "显存占用大幅下降，同时保持模型精度。")
    assert asc.is_domain_relevant(zh_ok) is True


def test_plain_answers_are_not_rejected_by_gate():
    """The gate is structural, not topical — no AI keywords required."""
    for text in ("A short genuine answer about cache warming strategies here",
                 "Die Quantisierung reduziert den Speicherbedarf deutlich.",
                 "Answer " * 10):
        assert asc.is_domain_relevant(text) is True, text


def test_empty_or_none_text_is_rejected():
    assert asc.is_domain_relevant("") is False
    assert asc.is_domain_relevant(None) is False


# --- scraped nav/vote chrome on an otherwise-good insight (bug live 16.09.26) --
# The learner captured an HN item as "Remix new past ask show jobs submit login
# AI Regex Scientist: A self-improving regex solver 9 points by PranoyP 7 months
# ago | 2 comments I built a system where two LLM agents co-evolve...". The menu
# chain and score line became the skill's description + Trigger. This content is
# strippable, not rejectable -- the trailing knowledge is real.

HN_CHROME = ("Remix new past ask show jobs submit login AI Regex Scientist: "
             "A self-improving regex solver 9 points by PranoyP 7 months ago | "
             "2 comments I built a system where two LLM agents co-evolve: one "
             "invents regex problems, the other learns to solve them.")


def test_nav_chrome_prefix_and_score_are_stripped():
    """Menu chain + vote line are removed; the real insight survives."""
    out = asc.strip_nav_chrome(HN_CHROME)
    assert out.startswith("AI Regex Scientist:"), out
    assert "login" not in out.lower().split("solver")[0], out
    assert "points by" not in out, out
    assert out.endswith("the other learns to solve them."), out


def test_nav_strip_keeps_genuine_text_mentioning_points():
    """A mid-sentence 'points' must not be eaten — only the leading chrome run."""
    prose = ("The benchmark awards 5 points by default to any model that "
             "finishes within the time budget.")
    assert asc.strip_nav_chrome(prose) == prose


def test_nav_strip_is_noop_on_clean_text():
    clean = "Mamba-3 decodes faster than a Transformer and is stable."
    assert asc.strip_nav_chrome(clean) == clean
    assert asc.strip_nav_chrome("") == ""
    assert asc.strip_nav_chrome(None) is None


def test_chrome_does_not_reach_the_written_skill():
    """End-to-end: the chrome-stripped insight is what lands in SKILL.md."""
    skills, _ = _sandbox()
    entry = asc.create_skill_from_insight("Latest research insight: HN item",
                                         HN_CHROME, "internet-learner")
    assert entry is not None, "genuine insight must still produce a skill"
    md = open(os.path.join(skills, entry["name"], "SKILL.md"), encoding="utf-8").read()
    assert "submit login" not in md, md
    assert "points by" not in md, md
    assert "co-evolve" in md, md


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
