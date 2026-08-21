#!/usr/bin/env python3
"""
Skill Validator — 100-Punkte-Qualitätsprüfung für alle OpenAmer Skills.

Validiert alle SKILL.md Dateien im Skills-Verzeichnis gegen 5 Qualitätskategorien.
Erzeugt 0-100 Scoring pro Skill, Gesamt-Report mit Best/Worst-Ranking, und
kann Syntax-Fehler automatisch korrigieren.

CLI:
  python skill-validator.py --all                    # Alle Skills prüfen
  python skill-validator.py --skill <name>           # Einzelnen Skill prüfen
  python skill-validator.py --all --fix              # + Auto-Fix für Syntax
  python skill-validator.py --all --json             # JSON-Report
  python skill-validator.py --all --html             # HTML-Report
  python skill-validator.py --best                   # Top 10 Skills
  python skill-validator.py --worst                  # Bottom 10 Skills
  python skill-validator.py --all --json --output report.json
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ──────────────────────────────────────────────────────────────────────
# Pfade
# ──────────────────────────────────────────────────────────────────────
OPENAMER_HOME = Path(os.environ.get(
    "LOCALAPPDATA",
    str(Path.home() / "AppData/Local"),
)) / "openamer-laptop"

SKILLS_DIR = OPENAMER_HOME / "skills"
LOGS_DIR = OPENAMER_HOME / "logs"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
CRON_DIR = OPENAMER_HOME / "cron"

# ──────────────────────────────────────────────────────────────────────
# Scoring: 100 Punkte
# ──────────────────────────────────────────────────────────────────────
# Kategorie A: Frontmatter-Vollständigkeit (30 Punkte)
# Kategorie B: Description-Qualität (15 Punkte)
# Kategorie C: Body-Struktur (25 Punkte)
# Kategorie D: Cross-Refs (15 Punkte)
# Kategorie E: Commands & CLI (15 Punkte)

REQUIRED_SECTIONS = [
    "overview", "when to use", "verification",
    "troubleshooting", "pitfalls", "usage",
    "setup", "installation",
]

SKILL_NAME_REGEX = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
CLI_COMMAND_RE = re.compile(r'openamer\s+[\w-]+(?:\s+[\w-]+)*')
DESCRIPTION_LINE_RE = re.compile(r'^description:\s*[\'"](.+?)[\'"]\s*$', re.MULTILINE)


def find_all_skill_paths() -> List[Path]:
    """Finde alle SKILL.md Dateien rekursiv."""
    return sorted(SKILLS_DIR.rglob("SKILL.md"))


def parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
    """Extrahiere und parse YAML-Frontmatter aus SKILL.md.
    
    Handhabt:
    - Einfache key: value
    - Inline-Listen [a, b, c]
    - Mehrzeilige Listen (- item)
    - Geschachtelte Dicts (metadata > openamer > ...)
    """
    m = FRONTMATTER_RE.match(content)
    if not m:
        return None
    raw = m.group(1)

    # Build a line-based structure with indent tracking
    lines = []
    for line in raw.split('\n'):
        stripped = line.rstrip()
        if not stripped:
            continue
        # Calculate indent level (2 spaces = 1 level)
        indent = 0
        for ch in line:
            if ch == ' ':
                indent += 1
            else:
                break
        level = indent // 2
        content_stripped = stripped.strip()
        lines.append((level, content_stripped))

    def parse_lines(lines_list, start=0):
        """Parse YAML lines recursively from a given start index."""
        result = {}
        i = start
        base_level = lines_list[i][0] if i < len(lines_list) else 0

        while i < len(lines_list):
            level, text = lines_list[i]
            if level < base_level:
                break  # Went back up a level
            if level > base_level:
                # This is content belonging to a parent — shouldn't happen at top of loop
                i += 1
                continue

            # Try to match key: value (possibly empty)
            kv_match = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', text)
            if not kv_match:
                i += 1
                continue

            key, value = kv_match.groups()
            value = value.strip()

            # Empty value: look ahead for children on next lines
            if value == '' or value == '|':
                value = None  # Will be filled by children

            # Inline list [a, b, c]
            if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
                parsed = []
                inner = value[1:-1]
                for item in inner.split(','):
                    item = item.strip().strip('"').strip("'")
                    if item:
                        parsed.append(item)
                result[key] = parsed
                i += 1
                continue

            # Inline dict {key: val, ...}
            if isinstance(value, str) and value.startswith('{'):
                try:
                    cleaned = value.strip('{}')
                    d = {}
                    for pair in cleaned.split(','):
                        if ':' in pair:
                            k, v = pair.split(':', 1)
                            d[k.strip().strip('"').strip("'")] = v.strip().strip('"').strip("'")
                    result[key] = d
                except Exception:
                    result[key] = value.strip('"').strip("'")
                i += 1
                continue

            # Boolean
            if isinstance(value, str) and value.lower() in ('true', 'false'):
                result[key] = value.lower() == 'true'
                i += 1
                continue

            # Simple scalar string
            if isinstance(value, str) and value:
                result[key] = value.strip('"').strip("'")
                i += 1
                continue

            # Empty value — look at children (next lines with higher indent)
            if value is None or value == '':
                # Peek ahead to see if children exist
                if i + 1 < len(lines_list) and lines_list[i + 1][0] > level:
                    child_base = lines_list[i + 1][0]
                    # Find all top-level children (at child_base indent) and recurse per-child
                    # for deeper nesting
                    j = i + 1
                    child_results = {}
                    # Collect children at child_base level
                    while j < len(lines_list) and lines_list[j][0] >= child_base:
                        if lines_list[j][0] == child_base:
                            cl_text = lines_list[j][1]
                            if cl_text.startswith('- '):
                                # List at child level
                                if '_list' not in child_results:
                                    child_results['_list'] = []
                                child_results['_list'].append(re.match(r'^- (.+)', cl_text).group(1).strip().strip('"').strip("'"))
                            else:
                                ckv = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', cl_text)
                                if ckv:
                                    ck, cv = ckv.groups()
                                    cv = cv.strip()
                                    # Check if this key has sub-children (level deeper)
                                    if cv == '' or cv == '|':
                                        sub = {}
                                        k = j + 1
                                        sub_base = lines_list[k][0] if k < len(lines_list) else 0
                                        while k < len(lines_list) and lines_list[k][0] > child_base:
                                            if lines_list[k][0] == sub_base:
                                                skv = re.match(r'^(\w[\w_-]*)\s*:\s*(.*)', lines_list[k][1])
                                                if skv:
                                                    sk, sv = skv.groups()
                                                    sv = sv.strip()
                                                    if sv.startswith('[') and sv.endswith(']'):
                                                        inn = sv[1:-1]
                                                        sub[sk] = [x.strip().strip('"').strip("'") for x in inn.split(',') if x.strip()]
                                                    elif sv.startswith('- '):
                                                        s_list = [sv[2:].strip().strip('"').strip("'")]
                                                        k2 = k + 1
                                                        while k2 < len(lines_list) and lines_list[k2][0] == sub_base and lines_list[k2][1].startswith('- '):
                                                            s_list.append(re.match(r'^- (.+)', lines_list[k2][1]).group(1).strip().strip('"').strip("'"))
                                                            k2 += 1
                                                        sub[sk] = s_list
                                                    else:
                                                        sub[sk] = sv.strip('"').strip("'")
                                            k += 1
                                        child_results[ck] = sub
                                    elif cv.startswith('[') and cv.endswith(']'):
                                        inn = cv[1:-1]
                                        child_results[ck] = [x.strip().strip('"').strip("'") for x in inn.split(',') if x.strip()]
                                    elif cv.startswith('- '):
                                        s_list = [cv[2:].strip().strip('"').strip("'")]
                                        k2 = j + 1
                                        while k2 < len(lines_list) and lines_list[k2][0] == child_base and lines_list[k2][1].startswith('- '):
                                            s_list.append(re.match(r'^- (.+)', lines_list[k2][1]).group(1).strip().strip('"').strip("'"))
                                            k2 += 1
                                        child_results[ck] = s_list
                                    else:
                                        child_results[ck] = cv.strip('"').strip("'")
                        j += 1

                    if '_list' in child_results:
                        result[key] = child_results['_list']
                        del child_results['_list']
                    else:
                        result[key] = child_results
                else:
                    result[key] = ''
                i += 1
                continue

            i += 1

        return result

    return parse_lines(lines)


def get_available_skill_names() -> Set[str]:
    """Erzeuge Set aller existierenden Skill-Namen (aus Verzeichnis-Namen)."""
    names = set()
    for sp in find_all_skill_paths():
        parent = sp.parent
        # Skill-Name = letztes Verzeichnis vor SKILL.md
        names.add(parent.name)
    return names


def validate_skill_content(skill_path: Path) -> Dict[str, Any]:
    """
    Validiere einen einzelnen Skill und gib detailliertes Scoring zurück.
    
    Returns dict mit:
      - path, name, score, max_score
      - categories: dict mit Teil-Scores
      - details: Liste von Problemen
      - frontmatter: geparstes Frontmatter
    """
    result = {
        "path": str(skill_path),
        "name": skill_path.parent.name,
        "score": 0,
        "max_score": 100,
        "categories": {
            "frontmatter": {"score": 0, "max": 30, "issues": [], "warnings": []},
            "description": {"score": 0, "max": 15, "issues": [], "warnings": []},
            "body_structure": {"score": 0, "max": 25, "issues": [], "warnings": []},
            "cross_refs": {"score": 0, "max": 15, "issues": [], "warnings": []},
            "commands": {"score": 0, "max": 15, "issues": [], "warnings": []},
        },
        "details": [],
        "frontmatter": {},
        "fixable": False,
    }

    try:
        content = skill_path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        result["details"].append(f"❌ Kann Datei nicht lesen: {e}")
        return result

    result["content"] = content
    fm = parse_frontmatter(content)
    result["frontmatter"] = fm or {}

    if fm is None:
        result["details"].append("❌ Kein gültiges YAML-Frontmatter gefunden")
        result["categories"]["frontmatter"]["issues"].append("Kein Frontmatter (--- ---)")
        result["fixable"] = True
        return result

    # ── Category A: Frontmatter (30 points) ──────────────────────
    cat = result["categories"]["frontmatter"]
    fm_keys = set(fm.keys())

    # A1: name exists → 5 points
    if "name" in fm and fm["name"]:
        cat["score"] += 5
    else:
        cat["issues"].append("Fehlendes 'name' Feld")

    # A2: name valid format → 3 pts
    if "name" in fm and fm["name"]:
        if SKILL_NAME_REGEX.match(str(fm["name"])):
            cat["score"] += 3
        else:
            cat["warnings"].append(f"Name '{fm['name']}' entspricht nicht dem Muster [a-z0-9_-]")

    # A3: description exists → 5 pts
    if "description" in fm and fm["description"]:
        cat["score"] += 5
    else:
        cat["issues"].append("Fehlendes 'description' Feld")

    # A4: version exists → 4 pts
    if "version" in fm and fm["version"]:
        cat["score"] += 4
    else:
        cat["warnings"].append("Fehlendes 'version' Feld")

    # A5: tags exists (top-level or in metadata.openamer) → 4 pts
    tags = fm.get("tags", [])
    meta_tags = fm.get("metadata", {}).get("openamer", {}).get("tags", []) if isinstance(fm.get("metadata"), dict) else []
    has_tags = bool(tags) or bool(meta_tags)
    if has_tags:
        cat["score"] += 4
    else:
        cat["warnings"].append("Keine Tags gefunden (weder top-level noch in metadata.openamer)")

    # A6: platforms exists → 3 pts
    if "platforms" in fm and fm["platforms"]:
        cat["score"] += 3
    else:
        cat["warnings"].append("Fehlendes 'platforms' Feld")

    # A7: metadata.openamer exists → 3 pts
    if "metadata" in fm and isinstance(fm["metadata"], dict) and "openamer" in fm["metadata"]:
        cat["score"] += 3
    else:
        cat["warnings"].append("Fehlender 'metadata.openamer' Block")

    # A8: Author exists → 3 pts
    if "author" in fm and fm["author"]:
        cat["score"] += 3
    else:
        pass  # optional, no deduction

    # ── Category B: Description Quality (15 points) ──────────────
    cat = result["categories"]["description"]
    desc = str(fm.get("description", ""))

    # B1: Description ≤ 57 chars → 5 pts
    if len(desc) <= 57:
        cat["score"] += 5
    else:
        cat["warnings"].append(f"Description zu lang ({len(desc)} > 57 Zeichen)")

    # B2: First word is a trigger verb (Use, When, Führe, etc.) → 5 pts
    trigger_words = ["use", "when", "führe", "führen", "nutze", "verwende", "für", "create", "build",
                     "run", "deploy", "generate", "manage", "validate", "monitor", "test", "debug",
                     "install", "configure", "scan", "check", "analyse", "analyze", "convert",
                     "automatisch", "hilfe", "hilft", "scaffold", "bootstrap", "guide", "tutorial",
                     "implement", "plan", "design", "review", "control", "drive", "drive"]
    first_word = desc.split()[0].strip().strip('"').strip("'").lower() if desc else ""
    is_trigger = first_word in trigger_words or desc.lower().startswith(("use for", "use when", "use to", "führe", "nutze", "automatisch"))
    if is_trigger:
        cat["score"] += 5
    else:
        cat["warnings"].append(f"Description beginnt nicht mit einem Trigger-Wort ('{first_word}')")

    # B3: Description ist nicht leer und hat > 10 Zeichen → 5 pts
    if len(desc) > 10:
        cat["score"] += 5
    else:
        cat["issues"].append("Description ist zu kurz oder leer")

    # ── Category C: Body Structure (25 points) ───────────────────
    cat = result["categories"]["body_structure"]
    body_lower = content.lower()

    # C1: Hat Sections → 4 pts per required section (max 20 pts)
    found_sections = 0
    for section in REQUIRED_SECTIONS:
        # Look for ## Section Name
        if re.search(r'^##\s+' + re.escape(section), content, re.MULTILINE):
            found_sections += 4

    cat["score"] += min(found_sections, 20)

    # Check which are missing
    found_section_names = set()
    for sec in REQUIRED_SECTIONS:
        if re.search(r'^##\s+' + re.escape(sec), content, re.MULTILINE):
            found_section_names.add(sec)
    missing = set(REQUIRED_SECTIONS) - found_section_names
    if missing:
        cat["warnings"].append(f"Fehlende Sections: {', '.join(sorted(missing))}")

    # C2: Hat Code-Blöcke → 3 pts
    code_blocks = re.findall(r'```[\w]*\n.*?```', content, re.DOTALL)
    if code_blocks:
        cat["score"] += 3
    else:
        cat["warnings"].append("Keine Code-Blöcke gefunden")

    # C3: Hat Tabelle → 2 pts
    if re.search(r'^\|.+\|.*$', content, re.MULTILINE):
        cat["score"] += 2
    else:
        pass  # optional

    # ── Category D: Cross-Refs (15 points) ───────────────────────
    cat = result["categories"]["cross_refs"]
    all_skill_names = get_available_skill_names()

    # D1: related_skills existiert und zeigt auf existierende Skills → 8 pts
    metadata_val = fm.get("metadata", {})
    if not isinstance(metadata_val, dict):
        metadata_val = {}
    openamer = metadata_val.get("openamer", {})
    if not isinstance(openamer, dict):
        openamer = {}
    related = openamer.get("related_skills", [])
    if isinstance(fm.get("related_skills"), list) and not related:
        related = fm["related_skills"]

    if related:
        exist_count = 0
        for ref in related:
            # Strip optional description "skill-name (description)"
            ref_clean = ref.split("(")[0].strip()
            if ref_clean in all_skill_names or f"{ref_clean}/SKILL.md" in [str(p.relative_to(SKILLS_DIR)) for p in find_all_skill_paths()]:
                exist_count += 1
            else:
                cat["warnings"].append(f"related_skill '{ref_clean}' existiert nicht")
        ratio = exist_count / len(related)
        cat["score"] += int(ratio * 8)
    else:
        cat["warnings"].append("Keine related_skills definiert")
        # Still lose 5 pts if not present

    # D2: Interne Links (zum Skill-Namen passend) → 4 pts
    skill_name = fm.get("name", "")
    if skill_name and f"`{skill_name}`" in content:
        cat["score"] += 4
    elif skill_name and f"see `{skill_name}`" in content.lower():
        cat["score"] += 2
    else:
        cat["warnings"].append("Kein Selbstverweis auf Skill-Namen im Body")

    # D3: Keine broken image links → 3 pts
    img_links = re.findall(r'!\[.*?\]\((.+?)\)', content)
    if not img_links:
        cat["score"] += 3
    else:
        broken = [lnk for lnk in img_links if lnk.startswith("http") and "skills" in lnk]
        if not broken:
            cat["score"] += 3
        else:
            cat["warnings"].append(f"Potentiell broken image links: {len(broken)}")

    # ── Category E: Commands & CLI (15 points) ───────────────────
    cat = result["categories"]["commands"]

    # E1: Enthält CLI-Befehle im Body → 4 pts
    all_content = content
    commands_found = CLI_COMMAND_RE.findall(all_content)
    if commands_found:
        cat["score"] += 4
    else:
        cat["warnings"].append("Keine 'openamer' CLI-Befehle gefunden")

    # E2: Code-Blöcke mit Bash/Shell sind ausführbar → 5 pts
    bash_blocks = re.findall(r'```(?:bash|sh|shell)\s*\n(.*?)```', content, re.DOTALL)
    if bash_blocks:
        cat["score"] += 5
        result["bash_blocks"] = len(bash_blocks)
    else:
        # Check for any code blocks with commands
        any_blocks = re.findall(r'```\s*\n(.*?)```', content, re.DOTALL)
        if any_blocks:
            cat["score"] += 3
            cat["warnings"].append("Keine expliziten bash/sh Code-Blöcke (nur generische)")
        else:
            cat["warnings"].append("Keine Code-Blöcke mit Shell-Befehlen")

    # E3: Exit-Codes / Error-Handling dokumentiert → 3 pts
    exit_code_refs = re.findall(r'exit.code|exit_code|Exit-Code|exit code|\b0\b.*\bok\b|\berror\b|\bfehler\b|\berror handling|error handling', all_content, re.IGNORECASE)
    if exit_code_refs:
        cat["score"] += 3

    # E4: Setup/Installation hat konkrete package manager Befehle → 3 pts
    pkg_patterns = re.findall(r'(pip install|apt install|brew install|npm install|uv|pip3 install|choco install|winget install|npm install)', all_content)
    if pkg_patterns:
        cat["score"] += 3

    # ── Totalscore berechnen ─────────────────────────────────────
    total = sum(c["score"] for c in result["categories"].values())
    result["score"] = total

    # Alle Issues sammeln
    all_issues = []
    all_warnings = []
    for c in result["categories"].values():
        all_issues.extend(c.get("issues", []))
        all_warnings.extend(c.get("warnings", []))
    result["issues"] = all_issues
    result["warnings"] = all_warnings

    # Bewertung
    if total >= 90:
        result["grade"] = "A+"
    elif total >= 80:
        result["grade"] = "A"
    elif total >= 70:
        result["grade"] = "B"
    elif total >= 60:
        result["grade"] = "C"
    elif total >= 40:
        result["grade"] = "D"
    else:
        result["grade"] = "F"

    return result


def fix_skill_content(skill_path: Path, validation: Dict[str, Any]) -> List[str]:
    """Auto-Fix für identifizierte Frontmatter-Probleme."""
    fixes = []
    content = skill_path.read_text(encoding='utf-8', errors='replace')
    fm = validation.get("frontmatter", {})

    # Fix 1: Fehlendes Frontmatter → minimales hinzufügen
    if fm is None or not fm:
        name = skill_path.parent.name
        new_fm = f"""---
name: {name}
description: 'Use for {name.replace("-", " ")} tasks.'
version: 1.0.0
tags:
  - generated
platforms: [linux, macos, windows]
---

"""
        new_content = new_fm + content.lstrip()
        skill_path.write_text(new_content, encoding='utf-8')
        fixes.append(f"✅ Frontmatter hinzugefügt für '{name}'")
        return fixes

    # Fix 2: Fehlende metadata.openamer
    if "metadata" not in fm or not isinstance(fm.get("metadata"), dict) or "openamer" not in fm.get("metadata", {}):
        # Find the end of frontmatter
        m = FRONTMATTER_RE.match(content)
        if m:
            raw = m.group(1)
            # Append metadata block before ---
            new_raw = raw.rstrip() + "\nmetadata:\n  openamer:\n    tags: []\n    related_skills: []\n"
            new_content = content.replace(raw, new_raw, 1)
            skill_path.write_text(new_content, encoding='utf-8')
            fixes.append(f"✅ metadata.openamer Block hinzugefügt")

    # Fix 3: Fehlende platforms
    if "platforms" not in fm:
        m = FRONTMATTER_RE.match(content)
        if m:
            raw = m.group(1)
            new_raw = raw.rstrip() + "\nplatforms: [linux, macos, windows]\n"
            new_content = content.replace(raw, new_raw, 1)
            skill_path.write_text(new_content, encoding='utf-8')
            fixes.append(f"✅ platforms Feld hinzugefügt")

    # Fix 4: Fehlende version
    if "version" not in fm:
        m = FRONTMATTER_RE.match(content)
        if m:
            raw = m.group(1)
            new_raw = raw.rstrip() + "\nversion: 1.0.0\n"
            new_content = content.replace(raw, new_raw, 1)
            skill_path.write_text(new_content, encoding='utf-8')
            fixes.append(f"✅ version Feld hinzugefügt")

    return fixes


def generate_report(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Erzeuge Gesamt-Report aus allen Validierungs-Ergebnissen."""
    if not all_results:
        return {"error": "Keine Skills gefunden", "timestamp": datetime.now().isoformat()}

    scores = [r["score"] for r in all_results]
    names = [r["name"] for r in all_results]

    # Best/Worst
    best = sorted(all_results, key=lambda x: x["score"], reverse=True)
    worst = sorted(all_results, key=lambda x: x["score"])

    # Category averages
    cat_totals = defaultdict(list)
    for r in all_results:
        for cat_name, cat_data in r["categories"].items():
            cat_totals[cat_name].append(cat_data["score"])

    cat_avgs = {}
    for cat_name, scores_list in cat_totals.items():
        max_val = all_results[0]["categories"][cat_name]["max"]
        avg = sum(scores_list) / len(scores_list) if scores_list else 0
        cat_avgs[cat_name] = {"avg": round(avg, 1), "max": max_val, "pct": round(avg / max_val * 100, 1) if max_val else 0}

    # Grade distribution
    grade_counts = Counter(r.get("grade", "?") for r in all_results)

    # Häufigste Issues
    all_issue_texts = []
    for r in all_results:
        all_issue_texts.extend(r.get("warnings", []))
        all_issue_texts.extend(r.get("issues", []))
    issue_counts = Counter(all_issue_texts).most_common(20)

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_skills": len(all_results),
        "total_score": sum(scores),
        "average_score": round(sum(scores) / len(scores), 1),
        "median_score": sorted(scores)[len(scores) // 2] if scores else 0,
        "min_score": min(scores),
        "max_score": max(scores),
        "grade_distribution": dict(grade_counts),
        "category_averages": cat_avgs,
        "top_issues": issue_counts,
        "best_skills": [
            {"name": r["name"], "score": r["score"], "grade": r.get("grade", "?"), "path": r["path"]}
            for r in best[:10]
        ],
        "worst_skills": [
            {"name": r["name"], "score": r["score"], "grade": r.get("grade", "?"), "path": r["path"]}
            for r in worst[:10]
        ],
        "skill_results": all_results,
    }

    return report


def print_report(report: Dict[str, Any], verbose: bool = False):
    """Gib Report als farbigen Terminal-Text aus."""
    from datetime import datetime

    ts = report.get("timestamp", "?")
    total = report["total_skills"]
    avg = report["average_score"]
    median = report["median_score"]

    print("=" * 70)
    print(f"  SKILL VALIDATOR REPORT")
    print(f"  {datetime.fromisoformat(ts).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print(f"\n  Skills geprüft:  {total}")
    print(f"  Durchschnitt:    {avg:.1f}/100")
    print(f"  Median:          {median}/100")
    print(f"  Min/Max:         {report['min_score']}/{report['max_score']}")
    print(f"  Gesamtscore:     {report['total_score']}")

    print(f"\n  ── Notenverteilung ──")
    for grade in ["A+", "A", "B", "C", "D", "F"]:
        count = report["grade_distribution"].get(grade, 0)
        bar = "█" * (count // 10) if count > 0 else ""
        pct = (count / total * 100) if total > 0 else 0
        print(f"    {grade:>3}: {count:>4} ({pct:5.1f}%) {bar}")

    print(f"\n  ── Kategorien (Durchschnitt) ──")
    for cat, data in report["category_averages"].items():
        name = {
            "frontmatter": "Frontmatter",
            "description": "Description",
            "body_structure": "Body-Struktur",
            "cross_refs": "Cross-Refs",
            "commands": "Commands/CLI",
        }.get(cat, cat)
        bar_len = int(data["pct"] / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"    {name:<20} {data['avg']:>5.1f}/{data['max']:<3} {bar} {data['pct']:.0f}%")

    print(f"\n  ── TOP 10 Skills ──")
    for i, s in enumerate(report["best_skills"], 1):
        print(f"    {i:>2}. {s['name']:<40} {s['score']:>3}/100  {s['grade']}")

    print(f"\n  ── WORST 10 Skills ──")
    for i, s in enumerate(report["worst_skills"], 1):
        print(f"    {i:>2}. {s['name']:<40} {s['score']:>3}/100  {s['grade']}")
        if verbose and s["score"] < 50:
            # Find full result for details
            for r in report.get("skill_results", []):
                if r["name"] == s["name"]:
                    for w in r.get("warnings", [])[:3]:
                        print(f"        ⚠ {w}")
                    for iss in r.get("issues", [])[:3]:
                        print(f"        ❌ {iss}")
                    break

    if report.get("top_issues"):
        print(f"\n  ── Top 20 Probleme ──")
        for issue, count in report["top_issues"][:10]:
            print(f"    {issue:<55} {count:>4}x")

    print("\n" + "=" * 70)


def generate_html_report(report: Dict[str, Any], output_path: Path):
    """Erzeuge HTML-Report aus dem Report-Dict."""
    from datetime import datetime

    ts = datetime.fromisoformat(report["timestamp"])

    # Grade colors
    grade_colors = {"A+": "#00c853", "A": "#64dd17", "B": "#ffc107", "C": "#ff9800", "D": "#f44336", "F": "#d50000"}

    best = report["best_skills"]
    worst = report["worst_skills"]
    cat_data = report["category_averages"]
    total = report["total_skills"]
    avg = report["average_score"]
    median = report["median_score"]

    rows_html = ""
    for r in sorted(report["skill_results"], key=lambda x: x["score"], reverse=True):
        gc = grade_colors.get(r.get("grade", "F"), "#888")
        warnings = r.get("warnings", [])
        issues = r.get("issues", [])
        warn_html = ""
        for w in warnings[:3]:
            warn_html += f'<div class="warn">⚠ {w}</div>'
        for iss in issues[:3]:
            warn_html += f'<div class="err">❌ {iss}</div>'

        cat_scores = r.get("categories", {})
        cat_bar = ""
        for ck, cv in cat_scores.items():
            pct = (cv["score"] / cv["max"] * 100) if cv["max"] > 0 else 0
            color = "#00c853" if pct >= 80 else "#ffc107" if pct >= 50 else "#f44336"
            cat_bar += f'<div style="display:flex;align-items:center;gap:4px;font-size:11px"><span style="width:80px">{ck[:12]}</span><div style="width:60px;height:8px;background:#eee;border-radius:4px"><div style="width:{pct}%;height:8px;background:{color};border-radius:4px"></div></div><span style="width:30px">{cv["score"]}/{cv["max"]}</span></div>'

        rows_html += f"""<tr>
            <td style="font-weight:bold">{r['name']}</td>
            <td style="text-align:center"><span class="grade" style="background:{gc}">{r.get('grade','?')}</span></td>
            <td style="text-align:center;font-weight:bold">{r['score']}</td>
            <td>{cat_bar}</td>
            <td>{warn_html}</td>
        </tr>"""

    best_html = ""
    for i, s in enumerate(best, 1):
        gc = grade_colors.get(s["grade"], "#888")
        best_html += f'<div class="rank-card" style="border-left:4px solid {gc}"><span class="rank-num">#{i}</span><strong>{s["name"]}</strong> <span class="score">{s["score"]}/100 <span class="grade" style="background:{gc}">{s["grade"]}</span></span></div>'

    worst_html = ""
    for i, s in enumerate(worst, 1):
        gc = grade_colors.get(s["grade"], "#888")
        worst_html += f'<div class="rank-card" style="border-left:4px solid {gc}"><span class="rank-num">#{i}</span><strong>{s["name"]}</strong> <span class="score">{s["score"]}/100 <span class="grade" style="background:{gc}">{s["grade"]}</span></span></div>'

    cat_html = ""
    for ck, cv in cat_data.items():
        name = {"frontmatter": "Frontmatter", "description": "Description", "body_structure": "Body-Struktur", "cross_refs": "Cross-Refs", "commands": "Commands"}.get(ck, ck)
        pct = cv["pct"]
        color = "#00c853" if pct >= 80 else "#ffc107" if pct >= 50 else "#f44336"
        cat_html += f"""<div class="cat-bar"><span class="cat-label">{name}</span><div class="cat-track"><div class="cat-fill" style="width:{pct}%;background:{color}"></div></div><span class="cat-stat">{cv["avg"]:.1f}/{cv["max"]}</span></div>"""

    grade_html = ""
    for grade in ["A+", "A", "B", "C", "D", "F"]:
        count = report["grade_distribution"].get(grade, 0)
        pct = (count / total * 100) if total > 0 else 0
        grade_html += f"""<div class="grade-row"><span class="grade-badge" style="background:{grade_colors.get(grade, '#888')}">{grade}</span><div class="grade-track"><div class="grade-fill" style="width:{pct}%;background:{grade_colors.get(grade, '#888')}"></div></div><span>{count} ({pct:.0f}%)</span></div>"""

    issues_html = ""
    for issue, count in report.get("top_issues", [])[:15]:
        issues_html += f'<div class="issue-item"><span class="issue-text">{issue}</span><span class="issue-count">{count}x</span></div>'

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Skill Validator Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 30px; }}
h1 {{ font-size: 28px; color: #58a6ff; margin-bottom: 5px; }}
h2 {{ font-size: 20px; color: #f0f6fc; margin: 25px 0 15px; }}
.subtitle {{ color: #8b949e; font-size: 14px; margin-bottom: 25px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 30px; }}
.stat-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; }}
.stat-value {{ font-size: 32px; font-weight: bold; color: #58a6ff; }}
.stat-label {{ font-size: 12px; color: #8b949e; margin-top: 5px; text-transform: uppercase; }}
.section {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 25px; }}
.cat-bar {{ display: flex; align-items: center; gap: 12px; margin: 8px 0; }}
.cat-label {{ width: 120px; font-size: 13px; color: #c9d1d9; }}
.cat-track {{ flex: 1; height: 12px; background: #21262d; border-radius: 6px; overflow: hidden; }}
.cat-fill {{ height: 12px; border-radius: 6px; transition: width 0.3s; }}
.cat-stat {{ width: 60px; text-align: right; font-size: 13px; color: #8b949e; }}
.grade-row {{ display: flex; align-items: center; gap: 10px; margin: 6px 0; }}
.grade-badge {{ display: inline-block; width: 36px; text-align: center; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 13px; color: #000; }}
.grade-track {{ flex: 1; height: 10px; background: #21262d; border-radius: 5px; overflow: hidden; }}
.grade-fill {{ height: 10px; border-radius: 5px; }}
.rank-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
.rank-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 10px 14px; display: flex; align-items: center; gap: 10px; margin: 5px 0; }}
.rank-num {{ color: #8b949e; font-size: 12px; min-width: 25px; }}
.score {{ margin-left: auto; font-size: 14px; }}
.grade {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-weight: bold; font-size: 11px; color: #000; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ background: #21262d; color: #8b949e; padding: 10px 12px; text-align: left; border-bottom: 1px solid #30363d; position: sticky; top: 0; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #21262d; vertical-align: top; }}
tr:hover td {{ background: #1c2128; }}
.warn {{ color: #d29922; font-size: 11px; }}
.err {{ color: #f44336; font-size: 11px; }}
.issue-item {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 13px; }}
.issue-count {{ color: #8b949e; }}
@media (max-width: 768px) {{ .rank-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>🔍 Skill Validator Report</h1>
<div class="subtitle">{ts.strftime('%Y-%m-%d %H:%M:%S')} — {total} Skills analysiert</div>

<div class="stats-grid">
<div class="stat-card"><div class="stat-value">{avg}/{median}</div><div class="stat-label">⌀ / Median</div></div>
<div class="stat-card"><div class="stat-value">{report["min_score"]}</div><div class="stat-label">Min</div></div>
<div class="stat-card"><div class="stat-value">{report["max_score"]}</div><div class="stat-label">Max</div></div>
<div class="stat-card"><div class="stat-value">{report["grade_distribution"].get("A+",0) + report["grade_distribution"].get("A",0)}</div><div class="stat-label">Top (A+/A)</div></div>
<div class="stat-card"><div class="stat-value">{report["grade_distribution"].get("F",0)}</div><div class="stat-label">Failed (F)</div></div>
</div>

<h2>📊 Notenverteilung</h2>
<div class="section">{grade_html}</div>

<h2>📈 Kategorien</h2>
<div class="section">{cat_html}</div>

<h2>🏆 Beste Skills</h2>
<div class="rank-grid"><div class="section">{best_html}</div><div class="section">{worst_html}</div></div>

<h2>⚠️ Top Probleme</h2>
<div class="section">{issues_html}</div>

<h2>📋 Alle Skills</h2>
<div class="section" style="overflow-x:auto;max-height:600px;overflow-y:auto">
<table>
<thead><tr><th>Name</th><th style="width:40px">Note</th><th style="width:50px">Score</th><th style="width:250px">Kategorien</th><th style="width:250px">Probleme</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>
</div>
</body>
</html>"""

    output_path.write_text(html, encoding='utf-8')
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Skill Validator — 100-Punkte-Qualitätsprüfung für alle Skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--all", action="store_true", help="Alle Skills prüfen")
    parser.add_argument("--skill", type=str, help="Einzelnen Skill prüfen (Name)")
    parser.add_argument("--fix", action="store_true", help="Auto-Korrektur von Syntax-Fehlern")
    parser.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    parser.add_argument("--html", action="store_true", help="Ausgabe als HTML-Report")
    parser.add_argument("--output", type=str, help="Zieldatei für Report (--json oder --html)")
    parser.add_argument("--best", action="store_true", help="Top 10 beste Skills")
    parser.add_argument("--worst", action="store_true", help="Top 10 schlechteste Skills")
    parser.add_argument("--verbose", action="store_true", help="Ausführliche Ausgabe")

    args = parser.parse_args()

    # Wenn kein Argument: --all default
    if not any([args.all, args.skill, args.best, args.worst]):
        args.all = True

    # Sicherstellen, dass Skills-Verzeichnis existiert
    if not SKILLS_DIR.exists():
        print(f"❌ Skills-Verzeichnis nicht gefunden: {SKILLS_DIR}")
        sys.exit(1)

    # Validierung durchführen
    all_results = []

    if args.skill:
        # Einzelnen Skill finden
        found = list(SKILLS_DIR.rglob(f"**/{args.skill}/SKILL.md"))
        if not found:
            # Direkte Pfadsuche
            found = list(SKILLS_DIR.rglob(f"**/SKILL.md"))
            found = [p for p in found if p.parent.name == args.skill]

        if not found:
            print(f"❌ Skill '{args.skill}' nicht gefunden")
            sys.exit(1)

        for fp in found:
            result = validate_skill_content(fp)
            all_results.append(result)
            if args.fix and result.get("fixable"):
                fix_skill_content(fp, result)
    else:
        skill_paths = find_all_skill_paths()
        print(f"🔍 Validiere {len(skill_paths)} Skills...", file=sys.stderr)
        total = len(skill_paths)
        for i, sp in enumerate(skill_paths, 1):
            if i % 50 == 0:
                print(f"   Fortschritt: {i}/{total}", file=sys.stderr)
            result = validate_skill_content(sp)
            all_results.append(result)

            if args.fix and result.get("fixable"):
                fixes = fix_skill_content(sp, result)
                if fixes:
                    for f in fixes:
                        print(f"   🔧 {f}", file=sys.stderr)

    if not all_results:
        print("❌ Keine Skills gefunden oder validiert")
        sys.exit(1)

    # Report generieren
    report = generate_report(all_results)

    # Logs-Ordner anlegen
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Ausgabe
    if args.json:
        output_path = None
        if args.output:
            output_path = Path(args.output)

        if args.best:
            data = {"best_skills": report["best_skills"]}
        elif args.worst:
            data = {"worst_skills": report["worst_skills"]}
        else:
            data = report

        if output_path:
            output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f"📄 JSON-Report gespeichert: {output_path}")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))

    elif args.html:
        output_path = Path(args.output) if args.output else LOGS_DIR / f"skill-validator-report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        generate_html_report(report, output_path)
        print(f"📄 HTML-Report gespeichert: {output_path}")

    elif args.best:
        print(f"\n🏆 TOP 10 SKILLS\n")
        for i, s in enumerate(report["best_skills"], 1):
            print(f"  {i:>2}. {s['name']:<45} {s['score']:>3}/100  {s['grade']}")

    elif args.worst:
        print(f"\n📉 WORST 10 SKILLS\n")
        for i, s in enumerate(report["worst_skills"], 1):
            print(f"  {i:>2}. {s['name']:<45} {s['score']:>3}/100  {s['grade']}")
            if args.verbose:
                for r in all_results:
                    if r["name"] == s["name"]:
                        for w in r.get("warnings", [])[:3]:
                            print(f"        ⚠ {w}")
                        for iss in r.get("issues", [])[:3]:
                            print(f"        ❌ {iss}")
                        break

    else:
        print_report(report, verbose=args.verbose)

    # JSON-Dump auch ins Log-Verzeichnis
    log_path = LOGS_DIR / "skill-validator-latest.json"
    log_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    if not args.json:
        print(f"\n📄 JSON-Log: {log_path}")

    # Exit-Code: Anzahl der Skills mit Note F
    failed = report["grade_distribution"].get("F", 0)
    sys.exit(min(failed, 127))


if __name__ == "__main__":
    main()