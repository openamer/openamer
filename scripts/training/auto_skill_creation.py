#!/usr/bin/env python3
"""Auto-Skill-Creation — turns internet insights into NEW SKILLS automatically.

The Darwin evolution engine mutates EXISTING skills. This script CREATES
new skills from internet insights — fresh genetic material for Darwin.

Pipeline: insight (buffer) -> skill template -> SKILL.md -> Darwin registry
Safety: new skills start in DRAFT state, must pass Darwin trials before promotion.
"""
import os
import json, os, sys, datetime, re
from pathlib import Path

def _training_dir():
    """Resolve the live training dir, tolerating a wrong/stale OPENAMER_HOME.

    Same canonical resolver as internet_learner / knowledge_to_action /
    self_improve. An MSYS-style OPENAMER_HOME (/c/Users/...) does not crash
    string-building, it just fails the isdir() probe and falls through to the
    real install dir -- so a differently-spelled correct home is tolerated and
    the ABORT guard below stays reserved for a home that truly isn't this install.
    """
    cands = []
    _env = os.environ.get("OPENAMER_HOME")
    if _env:
        cands.append(os.path.join(_env, "scripts", "training"))
    _home = Path.home()
    cands.append(str(_home / "AppData" / "Local" / "openamer-laptop" / "scripts" / "training"))
    cands.append(str(Path(__file__).resolve().parent))
    for _c in cands:
        if os.path.isdir(_c):
            return _c
    return os.path.join(str(_home), "AppData", "Local", "openamer", "scripts", "training")


T = _training_dir()
BUFFER = os.path.join(T, "online_buffer.jsonl")
KTA_LOG = os.path.join(T, "kta_log.jsonl")
SKILLS_DIR = os.path.join(str(Path.home()), "openamer-repo", "skills")
AUTO_SKILLS = os.path.join(SKILLS_DIR, "auto-generated")
REGISTRY = os.path.join(T, "auto_skills.json")

# The repo tree is the git/Darwin source of truth, but the agent and the skill
# loader read <OPENAMER_HOME>/skills -- a DIFFERENT tree. Until 23.09.26 this
# writer only touched the repo copy, so every skill it created was invisible to
# the agent: measured 15 registry entries (20.09.-23.09.) present in the repo
# and in NO tree the loader reads, while the live tree stayed at 85
# auto-generated skills. Write BOTH: repo for Darwin/git, live for the agent.
_LIVE_HOME = os.path.dirname(os.path.dirname(T))  # T = <home>/scripts/training
LIVE_AUTO_SKILLS = os.path.join(_LIVE_HOME, "skills", "auto-generated")
if not os.path.isdir(os.path.join(_LIVE_HOME, "skills")):
    # Unexpected home (throwaway test env): keep the repo write, skip mirror.
    LIVE_AUTO_SKILLS = None

if not os.path.isdir(T):
    print(f"[auto-skill] ABORT: training dir not found: {T} "
          f"(OPENAMER_HOME misconfigured - refusing to write into a throwaway env)")
    raise SystemExit(2)

SKILL_TEMPLATE = """---
name: {name}
description: {description}
auto_generated: true
created: {date}
source_insight: "{source}"
status: draft
fitness_score: 0
trials: 0
wins: 0
---

# {name_title}

## Trigger
Use when the agent encounters: {trigger_context}

## Verification
- [ ] The skill produces the expected output for its domain
- [ ] No errors in execution
- [ ] Insight quality: actionable and specific

## Notes
Auto-generated from internet insight (Knowledge-to-Action pipeline).
Darwin will trial this skill; it gets promoted only if it wins arena fights.
"""

def load_registry():
    try:
        return json.load(open(REGISTRY, encoding="utf-8"))
    except Exception:
        return {"created": [], "count": 0}

def save_registry(reg):
    with open(REGISTRY, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1)

def slugify(text):
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text.lower())
    return "-".join(text.split()[:4])[:40]

PRINTABLE_OK = set("abcdefghijklmnopqrstuvwxyz"
                   "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                   "0123456789 \t\n.,;:!?()[]{}'\"-_/%+=*&<>@#$|\\~`^")

def printable_ratio(text):
    """Fraction of characters that are human-readable (ASCII printable / latin letters).

    Some buffer insights carry binary blobs (compressed/encrypted payloads) that
    .get("a") returns as mojibake. Writing those into a SKILL.md produces an
    unreadable garbage description (live 15.09: auto-latest-research-insight-adaptive).
    """
    if not text:
        return 0.0
    good = sum(1 for c in text if c in PRINTABLE_OK or ord(c) > 160 and c.isalpha())
    return good / len(text)

def clean_text(text):
    """Drop control bytes and keep only readable characters."""
    out = []
    for c in text:
        if c in PRINTABLE_OK or (c.isalpha() and ord(c) > 160) or c in "äöüÄÖÜß€§":
            out.append(c)
        elif ord(c) == 13:
            continue
        else:
            out.append(" ")
    return re.sub(r"\s+", " ", "".join(out)).strip()

def is_usable_text(text, min_len=40, min_ratio=0.9):
    return bool(text) and len(text.strip()) >= min_len and printable_ratio(text) >= min_ratio

def is_domain_relevant(text):
    """Reject insights that are scraped portal/ad chrome rather than knowledge.

    Live 16.09: the internet learner scraped a Chinese software-download SEO
    page ("CAD看图王 提供 嗨格式 ... 百度认证:苏州舜心科技有限公司 ...") for an
    EfficiencyQAT question and this script turned the ad copy into the repo
    skill auto-efficiency-learning-efficientqat-llm.

    Structural, not topical: a row must carry TWO independent portal/ad
    markers. Absence of AI vocabulary is deliberately NOT a reject reason —
    a short but genuine answer would be dropped by such a rule, and the
    learner's own junk gate already handles off-topic English rows. Nor is a
    blanket "is CJK" rule used: real Chinese LLM/quantization notes exist in
    the corpus and must stay learnable (same rationale as the learner's
    class-12 gate).
    """
    if not text:
        return False
    return not _is_portal_ad_chrome(text)

def _is_portal_ad_chrome(text):
    """True when `text` is a scraped Q&A/answer-portal or ad label chain."""
    return sum(1 for m in _PORTAL_AD_MARKERS if m in text) >= _PORTAL_AD_MIN_MARKERS

_PORTAL_AD_MARKERS = (
    # Chinese Q&A / answer-portal label chain
    "百度认证", "高粉答主", "已赞过", "已踩过", "向ta提问", "回答量",
    "你对这个回答的评价是", "展开全部", "经验内容仅供参考", "本篇经验系本人",
    # software-download ad boilerplate
    "嗨格式", "看图王", "旗下品牌", "有限公司是一家", "专注软件研发",
)
_PORTAL_AD_MIN_MARKERS = 2

# Scraped site-navigation / vote-chrome prefixes. Live 16.09: an HN item was
# captured as "Remix new past ask show jobs submit login AI Regex Scientist: A
# self-improving regex solver 9 points by PranoyP 7 months ago | 2 comments I
# built a system where two LLM agents co-evolve...". The trailing knowledge is
# genuine, but the leading menu chain and score line became the skill's
# description and Trigger. Unlike portal ad chrome this content is NOT junk, so
# it is stripped rather than rejected -- rejecting would lose a real insight.
_NAV_CHROME_PREFIXES = (
    "remix new past ask show jobs submit login ",
    "new past ask show jobs submit login ",
    "past ask show jobs submit login ",
    "ask show jobs submit login ",
)
_NAV_CHROME_SCORE = re.compile(
    r"\b\d+\s+points?\s+by\s+\S+(?:\s+\d+\s+\w+\s+ago)?(?:\s*\|\s*\d+\s+comments?)?\s*"
)

def strip_nav_chrome(text):
    """Remove leading scraped site-navigation and score chrome from an insight.

    Returns the text with the menu prefix and the "N points by X N months ago |
    M comments" run removed. The score line is only stripped when the menu prefix
    was present, so genuine prose that merely mentions "points by" (e.g. "awards
    5 points by default") is never touched. A score line with no menu chain is
    left in place -- verbose but intact beats silently eaten knowledge.
    """
    if not text:
        return text
    out = text.lstrip()
    lowered = out.lower()
    had_prefix = False
    for prefix in _NAV_CHROME_PREFIXES:
        if lowered.startswith(prefix):
            out = out[len(prefix):]
            had_prefix = True
            break
    if had_prefix:
        out = _NAV_CHROME_SCORE.sub("", out, count=1)
    return out.strip()

def dedupe_check(name, description, registry):
    """Skip if we already created this skill (same slug) or a near-identical insight.

    Name-match is the primary guard: the same insight question always slugifies to
    the same skill name, while the answer TEXT drifts run-to-run, so a
    description-only check let every run re-create (and overwrite) a known skill.
    Live 11.09: registry held 195 entries across just 33 unique names.
    """
    if os.path.isdir(os.path.join(AUTO_SKILLS, name)):
        return True
    if LIVE_AUTO_SKILLS and os.path.isdir(os.path.join(LIVE_AUTO_SKILLS, name)):
        return True
    for prev in registry["created"]:
        if prev.get("name") == name:
            return True
        if prev.get("description", "")[:50] == description[:50]:
            return True
    return False

def create_skill_from_insight(insight_question, insight_answer, source_tag):
    """Create a draft skill from one internet insight."""
    # derive skill name and description from the insight
    clean_answer = strip_nav_chrome(clean_text(insight_answer))
    if not is_usable_text(clean_answer):
        # binary/garbled insight (e.g. compressed blob in the buffer) - never write it
        print(f"[auto-skill] skipped unreadable insight: {insight_question[:60]}",
              flush=True)
        return None
    if not is_domain_relevant(clean_answer):
        # readable but off-domain (scraped SEO spam / unrelated page text)
        print(f"[auto-skill] skipped off-domain insight: {insight_question[:60]}",
              flush=True)
        return None
    desc = clean_answer[:150].strip()
    name = "auto-" + slugify(insight_question)
    if name == "auto-":
        print(f"[auto-skill] skipped empty slug: {insight_question[:60]!r}", flush=True)
        return None

    registry = load_registry()

    if dedupe_check(name, desc, registry):
        # Report WHY a run produced nothing. Without this the caller sees a bare
        # "Total: 0 new skills created" and cannot tell saturation (every insight
        # already has a skill) apart from a broken pipeline.
        print(f"[auto-skill] skipped duplicate: {name[:60]}", flush=True)
        return None  # duplicate (same slug or same insight text)

    def _write_md(root):
        """Write SKILL.md under <root>/<name>; return the path (or None)."""
        if not root:
            return None
        d = os.path.join(root, name)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "SKILL.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(skill_content)
        return p

    skill_content = SKILL_TEMPLATE.format(
        name=name,
        description=desc.replace('"', "'"),
        date=datetime.date.today().isoformat(),
        source=str(insight_question)[:100].replace('"', "'"),
        name_title=name.replace("-", " ").title(),
        trigger_context=desc[:100],
    )

    skill_path = _write_md(AUTO_SKILLS)
    live_path = _write_md(LIVE_AUTO_SKILLS)
    if live_path:
        print(f"[auto-skill] mirrored to live tree: {live_path}", flush=True)

    entry = {
        "name": name,
        "description": desc[:100],
        "source": source_tag,
        "created": datetime.datetime.now().isoformat(),
        "path": skill_path,
        "live_path": live_path,
        "status": "draft",
    }
    registry["created"].append(entry)
    registry["count"] += 1
    save_registry(registry)
    return entry

def auto_create_from_buffer():
    """Scan recent insights, create skills for novel ones."""
    # read recent KTA log (most actionable insights)
    kta_path = os.path.join(T, "kta_log.jsonl")
    kta_log = kta_path
    created = []
    if os.path.exists(kta_path):
        lines = open(kta_log, encoding="utf-8").readlines()[-10:]
        for line in lines:
            try:
                d = json.loads(line)
            except Exception:
                continue
            iq = d.get("insight_question", "")
            ia = d.get("insight_answer", "")
            gap = d.get("identified_gap", "")
            if gap:
                ia = f"{ia} GAP: {gap}"
            if iq and len(ia) > 40 and is_usable_text(clean_text(ia)):
                result = create_skill_from_insight(iq, ia, "kta-pipeline")
                if result:
                    created.append(result)
                    print(f"[auto-skill] created: {result['name']} — {result['description'][:60]}",
                          flush=True)

    # also check internet-learned insights from buffer
    buf_path = os.path.join(T, "online_buffer.jsonl")
    if os.path.exists(buf_path):
        lines = open(buf_path, encoding="utf-8").readlines()[-30:]
        for line in lines:
            try:
                d = json.loads(line)
            except Exception:
                continue
            u, a = d.get("u", ""), d.get("a", "")
            if any(k in u.lower() for k in ["trending", "best practice", "research",
                                             "competitor", "breakthrough"]) \
                    and len(a) > 80 and is_usable_text(clean_text(a)):
                result = create_skill_from_insight(u, a, "internet-learner")
                if result:
                    created.append(result)
                    print(f"[auto-skill] created: {result['name']}", flush=True)

    return created

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "loop":
        import time
        while True:
            created = auto_create_from_buffer()
            if not created:
                print("[auto-skill] no new skills this cycle", flush=True)
            time.sleep(1800)  # every 30 min
    else:
        created = auto_create_from_buffer()
        print(f"\nTotal: {len(created)} new skills created")
        if not created:
            print("[auto-skill] no new skills this cycle — every recent insight was "
                  "already covered (duplicate slug) or unreadable (see lines above)")
