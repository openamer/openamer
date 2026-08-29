#!/usr/bin/env python3
"""knowledge_inventory.py — map & retrieve the agent's full knowledge base.

Turns the 278 skills / 324 modules / thinking-rules from *dead files* into
*retrievable intelligence*: given a task/intent, surfaces the relevant skills,
modules, and rules so the agent reaches for the right knowledge instead of a
handful. This is the "Superintelligenz muss alles wissen und koennen" lever —
knowable, not just present.

Commands:
  --inventory            dump counts + a few per category (catalog)
  --scan                 write a persisted index (cache/inventory.json)
  --find <query>         surface relevant skills/modules/rules for a task
  --count                just the totals (for dashboards/watchdogs)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HOME = Path.home() / "AppData/Local/openamer-laptop" \
    if sys.platform == "win32" else Path.home() / ".openamer"
SKILLS_ROOT = HOME / "skills"
CACHE = HOME / "cache" / "knowledge_inventory.json"
# fallback when run from the repo checkout
REPO = Path(__file__).resolve().parent.parent


def _iter_skills() -> list[dict]:
    out = []
    if not SKILLS_ROOT.exists():
        return out
    for skill_md in SKILLS_ROOT.rglob("SKILL.md"):
        rel = skill_md.relative_to(SKILLS_ROOT)
        name = skill_md.parent.name
        # description = first paragraph after frontmatter, best-effort
        txt = skill_md.read_text(encoding="utf-8", errors="replace")
        desc = ""
        m = re.search(r"^---\n(.*?)\n---\n", txt, re.S)
        body = txt[m.end():] if m else txt
        # first non-empty line/paragraph
        for piece in re.split(r"\n\s*\n", body):
            clean = piece.strip().replace("\n", " ")
            if clean:
                desc = clean[:140]
                break
        out.append({"name": name, "path": str(skill_md),
                    "category": str(rel.parts[0]) if len(rel.parts) > 1 else "root",
                    "description": desc})
    return out


def _iter_modules() -> list[dict]:
    root = REPO / "openamer_cli"
    out = []
    if not root.exists():
        return out
    for py in root.rglob("*.py"):
        name = py.name[:-3]
        # first def line as a hint of purpose
        hint = ""
        try:
            first = next(l for l in py.read_text(encoding="utf-8", errors="replace").splitlines(keepends=False)
                         if l.strip() and not l.startswith("#"))
            hint = first.strip()[:100]
        except Exception:
            pass
        out.append({"name": name, "path": str(py), "hint": hint})
    return out


def _rules() -> list[dict]:
    p = HOME / "thinking_rules.json"
    if not p.exists():
        return []
    try:
        r = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [x for x in r if isinstance(x, dict) and x.get("status", "active") == "active"]


def _score(hay: str, query_terms: list[str]) -> int:
    h = hay.lower()
    return sum(1 for t in query_terms if t in h)


def build_index() -> dict:
    return {"skills": _iter_skills(), "modules": _iter_modules(), "rules": _rules()}


def inventory() -> str:
    idx = build_index()
    from collections import Counter
    cats = Counter(s["category"] for s in idx["skills"])
    lines = [
        f"Skills : {len(idx['skills'])}  (categories: {dict(cats)})",
        f"Modules: {len(idx['modules'])}",
        f"Rules  : {len(idx['rules'])} active",
    ]
    # top categories sample
    for cat, n in cats.most_common(5):
        sample = " ".join(s["name"] for s in idx["skills"] if s["category"] == cat)[:80]
        lines.append(f"   - {cat} ({n}): {sample}")
    return "\n".join(lines)


def find(query: str, top: int = 6) -> str:
    terms = [t for t in re.findall(r"[A-Za-z0-9_äöüß-]+", query.lower()) if len(t) > 1]
    idx = build_index()
    # skills
    scored = []
    for s in idx["skills"]:
        hay = f"{s['name']} {s['description']} {s['category']}"
        sc = _score(hay, terms)
        if sc:
            scored.append((sc, "skill", s["name"], s["description"][:90]))
    for m in idx["modules"]:
        hay = f"{m['name']} {m['hint']}"
        sc = _score(hay, terms)
        if sc:
            scored.append((sc, "module", m["name"], m["hint"][:90]))
    for r in idx["rules"]:
        hay = f"{r.get('rule','')} {r.get('trigger','')}"
        sc = _score(hay, terms)
        if sc:
            scored.append((sc, "rule", r.get("id",""), r.get("rule","")[:90]))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return f"(no knowledge matched '{query}')"
    lines = [f"Knowledge for '{query}':"]
    for sc, kind, name, desc in scored[:top]:
        lines.append(f"  [{kind}] {name}  ({sc}) {desc}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(prog="knowledge_inventory")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--inventory", action="store_true")
    g.add_argument("--count", action="store_true")
    g.add_argument("--scan", action="store_true")
    g.add_argument("--find", metavar="QUERY")
    a = ap.parse_args()
    if a.count:
        idx = build_index()
        print(f"{len(idx['skills'])} skills | {len(idx['modules'])} modules | {len(idx['rules'])} rules")
        return 0
    if a.inventory or a.scan:
        idx = build_index()
        if a.scan:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"scanned -> {CACHE}")
        else:
            print(inventory())
        return 0
    if a.find:
        print(find(a.find))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())