#!/usr/bin/env python3
"""Auto-Skill-Creation — turns internet insights into NEW SKILLS automatically.

The Darwin evolution engine mutates EXISTING skills. This script CREATES
new skills from internet insights — fresh genetic material for Darwin.

Pipeline: insight (buffer) -> skill template -> SKILL.md -> Darwin registry
Safety: new skills start in DRAFT state, must pass Darwin trials before promotion.
"""
import json, os, sys, datetime, re

T = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
BUFFER = os.path.join(T, "online_buffer.jsonl")
KTA_LOG = os.path.join(T, "kta_log.jsonl")
SKILLS_DIR = r"C:/Users/damir/openamer-repo/skills"
AUTO_SKILLS = os.path.join(SKILLS_DIR, "auto-generated")
REGISTRY = os.path.join(T, "auto_skills.json")

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

def dedupe_check(description, registry):
    """Skip if we already created a similar skill."""
    for prev in registry["created"]:
        if prev["description"][:50] == description[:50]:
            return True
    return False

def create_skill_from_insight(insight_question, insight_answer, source_tag):
    """Create a draft skill from one internet insight."""
    # derive skill name and description from the insight
    desc = insight_answer[:150].strip()
    name = "auto-" + slugify(insight_question)

    registry = load_registry()

    if dedupe_check(desc, registry):
        return None  # duplicate

    os.makedirs(AUTO_SKILLS, exist_ok=True)
    skill_dir = os.path.join(AUTO_SKILLS, name)
    os.makedirs(skill_dir, exist_ok=True)

    skill_content = SKILL_TEMPLATE.format(
        name=name,
        description=desc,
        date=datetime.date.today().isoformat(),
        source=insight_question[:100],
        name_title=name.replace("-", " ").title(),
        trigger_context=desc[:100],
    )

    skill_path = os.path.join(skill_dir, "SKILL.md")
    with open(skill_path, "w", encoding="utf-8") as f:
        f.write(skill_content)

    entry = {
        "name": name,
        "description": desc[:100],
        "source": source_tag,
        "created": datetime.datetime.now().isoformat(),
        "path": skill_path,
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
            d = json.loads(line)
            iq = d.get("insight_question", "")
            ia = d.get("insight_answer", "")
            gap = d.get("identified_gap", "")
            if gap:
                ia = f"{ia} GAP: {gap}"
            if iq and len(ia) > 40:
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
            d = json.loads(line)
            u, a = d.get("u", ""), d.get("a", "")
            if any(k in u.lower() for k in ["trending", "best practice", "research",
                                             "competitor", "breakthrough"]) and len(a) > 80:
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
