#!/usr/bin/env python3
"""
Skill Knowledge Graph — OpenAmer Skill-Netzwerk

Scannt skills/ nach SKILL.md, extrahiert Frontmatter (Name, Tags, Description,
Related Skills), baut einen gewichteten Graphen und exportiert ihn als
  • skill-graph.json   (Node-Link-Format)
  • skill-graph.dot    (GraphViz DOT-Format)

CLI:
  python3 skill-knowledge-graph.py --build           # Graph bauen & exportieren
  python3 skill-knowledge-graph.py --suggest 'query' # Optimale Skill-Kette finden
  python3 skill-knowledge-graph.py --dot             # Nur DOT exportieren
  python3 skill-knowledge-graph.py --json            # Nur JSON exportieren
  python3 skill-knowledge-graph.py --stats           # Nur Statistiken anzeigen
"""

import argparse
import json
import os
import pathlib
import re
import sys
from collections import defaultdict
from heapq import heappop, heappush

try:
    import yaml
except ImportError:
    yaml = None

# ── Pfade ──────────────────────────────────────────────────────────────────
# OpenAmer Home
OPENAMER_HOME = pathlib.Path(os.environ.get(
    "OPENAMER_HOME",
    os.path.expanduser("~/.openamer")
))
# Fallback: AppData on Windows
if not OPENAMER_HOME.exists() and sys.platform == "win32":
    alt = pathlib.Path(os.environ.get("APPDATA", "")) / "openamer-laptop"
    if alt.exists():
        OPENAMER_HOME = alt
if not OPENAMER_HOME.exists() and sys.platform == "win32":
    alt2 = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "openamer-laptop"
    if alt2.exists():
        OPENAMER_HOME = alt2

SKILLS_DIR = OPENAMER_HOME / "skills"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
EXPORT_JSON = OPENAMER_HOME / "skill-graph.json"
EXPORT_DOT = OPENAMER_HOME / "skill-graph.dot"

# ── YAML Frontmatter Parser ────────────────────────────────────────────────

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL | re.MULTILINE)


def parse_skill_md(path: pathlib.Path) -> dict | None:
    """Parse a SKILL.md file and return a clean skill dict."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    match = FRONTMATTER_RE.search(text)
    if not match:
        return None

    raw = match.group(1)

    if yaml:
        try:
            fm = yaml.safe_load(raw)
        except Exception:
            return None
    else:
        fm = _fallback_yaml_load(raw)

    if not isinstance(fm, dict):
        return None

    name = (fm.get("name") or path.parent.name).strip()
    description = (fm.get("description") or "").strip()

    # Extract tags — try multiple locations
    tags = _extract_tags(fm)

    # Extract related_skills
    related = _extract_related(fm)

    # Category = parent directory name (e.g. "github", "creative")
    category = path.parent.parent.name if path.parent.parent.name != "skills" else ""

    return {
        "name": name,
        "category": category,
        "description": description,
        "tags": tags,
        "related_skills": related,
    }


def _extract_tags(fm: dict) -> list[str]:
    """Extract tags from various frontmatter locations."""
    tags = set()

    # 1) metadata.openamer.tags (most common for OpenAmer skills)
    meta = fm.get("metadata", {})
    if isinstance(meta, dict):
        oa = meta.get("openamer", {})
        if isinstance(oa, dict):
            raw_tags = oa.get("tags", [])
            if isinstance(raw_tags, list):
                for t in raw_tags:
                    if isinstance(t, str):
                        tags.add(t.strip().lower().replace(" ", "-"))

    # 2) top-level tags
    raw_tags = fm.get("tags", [])
    if isinstance(raw_tags, list):
        for t in raw_tags:
            if isinstance(t, str):
                tags.add(t.strip().lower().replace(" ", "-"))

    # 3) triggers — use as soft tags
    triggers = fm.get("triggers", [])
    if isinstance(triggers, list):
        for t in triggers:
            if isinstance(t, str) and len(t) < 40:
                tags.add(t.strip().lower().replace(" ", "-"))

    return sorted(tags)


def _extract_related(fm: dict) -> list[str]:
    """Extract related_skills from frontmatter."""
    related = set()

    # 1) metadata.openamer.related_skills
    meta = fm.get("metadata", {})
    if isinstance(meta, dict):
        oa = meta.get("openamer", {})
        if isinstance(oa, dict):
            raw = oa.get("related_skills", [])
            if isinstance(raw, list):
                for r in raw:
                    if isinstance(r, str):
                        related.add(r.strip())

    # 2) top-level
    raw = fm.get("related_skills", [])
    if isinstance(raw, list):
        for r in raw:
            if isinstance(r, str):
                related.add(r.strip())

    return sorted(related)


def _fallback_yaml_load(text: str) -> dict:
    """Minimal YAML frontmatter parser (no PyYAML). Handles list/string/dict."""
    result = {}
    in_block = False
    block_key = None
    block_lines = []

    for line in text.split("\n"):
        stripped = line.strip()

        # Skip comments
        if stripped.startswith("#"):
            continue
        if not stripped:
            continue

        # Detect block scalar
        if in_block:
            if stripped.startswith("- "):
                block_lines.append(stripped[2:].strip())
            else:
                # Check if this is a sub-key
                if ":" in stripped and not stripped.startswith("-"):
                    in_block = False
                    # Fall through to normal parsing
                else:
                    continue

        if in_block:
            continue

        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            # Block sequence
            if value == "" and not stripped.endswith(":"):
                pass
            elif value == "" or value == "[]":
                result[key] = []
                in_block = True
                block_lines = []
                block_key = key
            elif value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                result[key] = items
            else:
                value = value.strip("'\"").strip()
                result[key] = value

    if block_key and block_lines:
        result[block_key] = block_lines

    return result


# ── Graph Builder ──────────────────────────────────────────────────────────


def build_graph(skills: list[dict]) -> dict:
    """Build a weighted undirected graph from parsed skills using inverted indexes.

    Returns {"nodes": [...], "edges": [...]}
    """
    n = len(skills)
    name_to_idx = {s["name"]: i for i, s in enumerate(skills)}
    name_to_tags = {s["name"]: set(s["tags"]) for s in skills}
    name_to_cat = {s["name"]: s["category"] for s in skills}
    name_to_desc = {s["name"]: set(re.findall(r"[a-z\xe4\xf6\xfc\xdf-]+",
                     s["description"].lower())) for s in skills}

    # Nodes
    nodes = [
        {
            "id": i,
            "name": s["name"],
            "category": s["category"],
            "description": s["description"],
            "tags": s["tags"],
            "related_skills": s["related_skills"],
        }
        for i, s in enumerate(skills)
    ]

    # Edge accumulator
    edge_weights: dict[tuple[str, str], tuple[float, list[str]]] = {}

    def add_edge(src: str, dst: str, weight: float, reason: str):
        if src == dst:
            return
        key = (src, dst) if src < dst else (dst, src)
        w, reasons = edge_weights.get(key, (0.0, []))
        edge_weights[key] = (min(1.0, w + weight * 0.5), reasons + [reason])

    # ── 1) Explicit related_skills (weight: 1.0) ──
    for s in skills:
        src = s["name"]
        for rel in s.get("related_skills", []):
            if rel in name_to_idx:
                add_edge(src, rel, 1.0, "explicit_related")

    # ── 2) Shared tags via inverted index ──
    tag_to_skills: dict[str, list[str]] = defaultdict(list)
    for s in skills:
        for t in s["tags"]:
            tag_to_skills[t].append(s["name"])

    for tag, skill_list in tag_to_skills.items():
        m = len(skill_list)
        if m < 2:
            continue
        # Connect all pairs under this tag
        for i in range(m):
            for j in range(i + 1, m):
                add_edge(skill_list[i], skill_list[j], 0.4, f"tag:{tag}")

    # ── 3) Description keyword overlap via inverted index ──
    STOPWORDS = {"the", "a", "an", "and", "or", "for", "of", "to", "in",
                 "is", "it", "on", "with", "as", "by", "at", "from", "use",
                 "used", "using", "this", "that", "be", "are", "was", "were"}

    word_to_skills: dict[str, list[str]] = defaultdict(list)
    for s in skills:
        words = name_to_desc[s["name"]] - STOPWORDS
        for w in words:
            if len(w) > 2:  # skip very short words
                word_to_skills[w].append(s["name"])

    for word, skill_list in word_to_skills.items():
        m = len(skill_list)
        if m < 2 or m > 100:  # too common words would create noise
            continue
        if m > 20:
            # Sample down for very common words
            skill_list = skill_list[:20]
            m = 20
        for i in range(m):
            for j in range(i + 1, m):
                add_edge(skill_list[i], skill_list[j], 0.1, f"keyword:{word}")

    # ── 4) Same category bonus ──
    cat_to_skills: dict[str, list[str]] = defaultdict(list)
    for s in skills:
        if s["category"]:
            cat_to_skills[s["category"]].append(s["name"])

    for cat, skill_list in cat_to_skills.items():
        m = len(skill_list)
        if m < 2:
            continue
        for i in range(m):
            for j in range(i + 1, m):
                add_edge(skill_list[i], skill_list[j], 0.15, f"category:{cat}")

    # Convert edge dict to list
    edge_list = [
        {
            "source": src,
            "target": dst,
            "weight": w,
            "reasons": rs,
        }
        for (src, dst), (w, rs) in edge_weights.items()
    ]

    return {"nodes": nodes, "edges": edge_list}


# ── Suggestion Engine (Dijkstra) ──────────────────────────────────────────


def suggest_skills(graph: dict, query: str, top_n: int = 5) -> list[dict]:
    """Find the best skill chain for a query using weighted graph search.

    Uses a combination of:
    1. Text relevance (description + tag matching against query)
    2. Graph traversal (Dijkstra to find closest connected skills)
    """
    nodes = graph["nodes"]
    edges = graph["edges"]

    # Build adjacency list
    adj: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for e in edges:
        adj[e["source"]].append((e["target"], 1.0 - e["weight"]))
        adj[e["target"]].append((e["source"], 1.0 - e["weight"]))

    # Score each node against query
    query_lower = query.lower()
    query_words = set(re.findall(r"[a-z0-9-]+", query_lower))

    scored = []
    for n in nodes:
        score = 0.0
        desc_lower = n["description"].lower()
        name_lower = n["name"].lower()

        # Direct name match
        if query_lower in name_lower or name_lower in query_lower:
            score += 1.0
        elif any(qw in name_lower for qw in query_words):
            score += 0.5

        # Tag matches
        tag_matches = sum(1 for t in n["tags"] if any(qw in t for qw in query_words))
        score += tag_matches * 0.3

        # Description word matches
        desc_words = set(re.findall(r"[a-z0-9-]+", desc_lower))
        word_overlap = len(query_words & desc_words)
        score += word_overlap * 0.15

        # Category hint
        cat_lower = n["category"].lower()
        if any(qw in cat_lower for qw in query_words):
            score += 0.25

        if score > 0:
            scored.append((score, n["name"]))

    # Sort by relevance
    scored.sort(reverse=True, key=lambda x: x[0])

    if not scored:
        return []

    # Take top N seeds
    seeds = [s[1] for s in scored[:top_n]]

    # For each seed, find closest neighbors via Dijkstra
    results = []
    seen = set()

    for seed in seeds:
        if seed in seen:
            continue
        seen.add(seed)

        # Dijkstra from seed
        dist = {seed: 0}
        pq = [(0, seed)]
        while pq:
            d, u = heappop(pq)
            if d > dist.get(u, float("inf")):
                continue
            for v, w in adj.get(u, []):
                nd = d + w
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    heappush(pq, (nd, v))

        # Get the seed's neighbors sorted by distance
        neighbors = sorted(
            [(dist.get(v, float("inf")), v)
             for v in dist if v != seed and dist.get(v, float("inf")) < 3.0],
            key=lambda x: (x[0], x[1])
        )[:top_n]

        node_map = {n["name"]: n for n in nodes}
        seed_node = node_map.get(seed)

        chain = [seed]
        chain_scores = [float(sc) for sc, _ in scored if sc[1] == seed] if False else [max(s for s, n in scored if n == seed)]

        for d, v in neighbors:
            if v not in seen or len(neighbors) < 3:
                seen.add(v)
                chain.append(v)

        results.append({
            "seed": seed,
            "chain": chain,
            "description": seed_node["description"] if seed_node else "",
            "tags": seed_node["tags"] if seed_node else [],
            "category": seed_node["category"] if seed_node else "",
        })

    return results


# ── DOT Export ─────────────────────────────────────────────────────────────


def export_dot(graph: dict) -> str:
    """Export graph as GraphViz DOT format with color coding by category."""
    lines = [
        "digraph SkillGraph {",
        "  rankdir=LR;",
        "  splines=polyline;",
        "  bgcolor=\"#1a1a2e\";",
        "  fontcolor=\"#e0e0e0\";",
        "  fontname=\"Segoe UI, Arial, sans-serif\";",
        "  node [style=filled, fontname=\"Segoe UI, Arial, sans-serif\", fontsize=10]",
        "  edge [color=\"#4a4a6a\", penwidth=0.8]",
        "",
        "  // Categories as subgraphs",
    ]

    # Group nodes by category
    cat_nodes: dict[str, list] = defaultdict(list)
    for n in graph["nodes"]:
        cat = n["category"] or "uncategorized"
        cat_nodes[cat].append(n)

    # Color palette by category
    colors = [
        "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
        "#1abc9c", "#e67e22", "#34495e", "#16a085", "#c0392b",
        "#2980b9", "#27ae60", "#d35400", "#8e44ad", "#f1c40f",
        "#2c3e50", "#7f8c8d", "#e91e63", "#00bcd4", "#ff5722",
        "#795548", "#607d8b", "#009688", "#3f51b5", "#ff9800",
    ]
    cat_colors = {}
    for i, cat in enumerate(sorted(cat_nodes.keys())):
        cat_colors[cat] = colors[i % len(colors)]

    # Print nodes
    for n in graph["nodes"]:
        color = cat_colors.get(n["category"] or "uncategorized", "#7f8c8d")
        escaped_name = n["name"].replace('"', '\\"')
        label = f"{escaped_name}\\n({n['category']})" if n["category"] else escaped_name
        lines.append(f'  "{escaped_name}" [fillcolor="{color}", fontcolor="white", '
                     f'tooltip="{n["description"][:100]}"];')

    # Print edges
    lines.append("")
    for e in graph["edges"]:
        src = e["source"].replace('"', '\\"')
        dst = e["target"].replace('"', '\\"')
        weight = e["weight"]
        opacity = int(80 + weight * 120)
        lines.append(f'  "{src}" -> "{dst}" '
                     f'[penwidth={max(0.5, weight * 2):.1f}, '
                     f'color="#aaaaaa{opacity:02x}", '
                     f'label="{weight:.2f}"];')

    lines.append("}")
    return "\n".join(lines)


# ── Stats ──────────────────────────────────────────────────────────────────


def print_stats(graph: dict):
    nodes = graph["nodes"]
    edges = graph["edges"]

    cats = defaultdict(list)
    for n in nodes:
        cats[n["category"] or "uncategorized"].append(n["name"])

    print(f"📊  Skill Knowledge Graph — Statistik")
    print(f"{'='*50}")
    print(f"  Nodes (Skills):     {len(nodes)}")
    print(f"  Edges (Beziehungen): {len(edges)}")
    print(f"  Kategorien:         {len(cats)}")
    print()
    print(f"  Top-Kategorien:")
    for cat in sorted(cats, key=lambda c: len(cats[c]), reverse=True)[:10]:
        print(f"    {cat:30s}  {len(cats[cat]):3d} Skills")
    print()
    print(f"  Dichte: {len(edges) / max(1, len(nodes) * (len(nodes) - 1) / 2) * 100:.2f}%")

    # Top connected
    degree = defaultdict(int)
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1

    print()
    print(f"  Am besten vernetzt:")
    for skill, deg in sorted(degree.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"    {skill:35s}  {deg:3d} Verbindungen")


# ── Main ───────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="OpenAmer Skill Knowledge Graph"
    )
    parser.add_argument("--build", action="store_true",
                        help="Scan skills, build graph, export JSON + DOT")
    parser.add_argument("--suggest", type=str, metavar="QUERY",
                        help="Find optimal skill chain for a query")
    parser.add_argument("--dot", action="store_true",
                        help="Export only DOT format")
    parser.add_argument("--json", action="store_true",
                        help="Export only JSON format")
    parser.add_argument("--stats", action="store_true",
                        help="Show graph statistics only")
    parser.add_argument("--skills-dir", type=str,
                        help=f"Override skills directory (default: {SKILLS_DIR})")
    parser.add_argument("--output", type=str,
                        help=f"Output directory (default: {OPENAMER_HOME})")
    args = parser.parse_args()

    skills_dir = pathlib.Path(args.skills_dir) if args.skills_dir else SKILLS_DIR
    output_dir = pathlib.Path(args.output) if args.output else OPENAMER_HOME

    if not args.build and not args.suggest and not args.dot and not args.json and not args.stats:
        # Default mode for cron: build graph
        args.build = True

    # ── Parse skills ──────────────────────────────────────────────────────
    skills = []
    errors = 0

    if not skills_dir.exists():
        print(f"❌ Skills-Verzeichnis nicht gefunden: {skills_dir}", file=sys.stderr)
        sys.exit(1)

    skill_files = sorted(skills_dir.rglob("SKILL.md"))

    print(f"🔍 Scanne {len(skill_files)} SKILL.md Dateien in {skills_dir} ...")

    for sf in skill_files:
        parsed = parse_skill_md(sf)
        if parsed:
            skills.append(parsed)
        else:
            errors += 1

    print(f"✅ {len(skills)} Skills geparst, {errors} Fehler")

    # ── Build graph ───────────────────────────────────────────────────────
    if args.build or args.dot or args.json or args.stats:
        graph = build_graph(skills)

        export_json_path = output_dir / "skill-graph.json"
        export_dot_path = output_dir / "skill-graph.dot"

        if args.build or args.json:
            with open(export_json_path, "w", encoding="utf-8") as f:
                json.dump(graph, f, indent=2, ensure_ascii=False)
            print(f"✅ JSON exportiert: {export_json_path}  ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")

        if args.build or args.dot:
            dot = export_dot(graph)
            with open(export_dot_path, "w", encoding="utf-8") as f:
                f.write(dot)
            print(f"✅ DOT exportiert: {export_dot_path}")

        if args.stats:
            print()
            print_stats(graph)

    # ── Suggest ───────────────────────────────────────────────────────────
    if args.suggest:
        # Load or build graph
        graph_path = output_dir / "skill-graph.json"
        if graph_path.exists():
            with open(graph_path, "r", encoding="utf-8") as f:
                graph = json.load(f)
        else:
            graph = build_graph(skills)

        results = suggest_skills(graph, args.suggest)

        print(f"\n🔎  Vorschläge für: \"{args.suggest}\"")
        print(f"{'='*60}")
        if not results:
            print("  Keine passenden Skills gefunden.")
        else:
            for i, r in enumerate(results, 1):
                print(f"\n  {i}. 🎯  {r['seed']}")
                print(f"     {r['description'][:120]}")
                if r["tags"]:
                    print(f"     Tags: {', '.join(r['tags'][:8])}")
                if r["category"]:
                    print(f"     Kategorie: {r['category']}")
                if len(r["chain"]) > 1:
                    print(f"     Kette: {' → '.join(r['chain'])}")
            print()

        # Also show raw scores for insight
        print("  ── Roh-Scores ──")
        scored = []
        query_lower = args.suggest.lower()
        query_words = set(re.findall(r"[a-z0-9-]+", query_lower))

        for n in graph["nodes"]:
            score = 0.0
            desc_lower = n["description"].lower()
            name_lower = n["name"].lower()

            if query_lower in name_lower or name_lower in query_lower:
                score += 1.0
            elif any(qw in name_lower for qw in query_words):
                score += 0.5

            tag_matches = sum(1 for t in n["tags"] if any(qw in t for qw in query_words))
            score += tag_matches * 0.3
            desc_words = set(re.findall(r"[a-z0-9-]+", desc_lower))
            word_overlap = len(query_words & desc_words)
            score += word_overlap * 0.15

            if score > 0.1:
                scored.append((score, n["name"], n["description"][:80]))

        scored.sort(reverse=True, key=lambda x: x[0])
        for score, name, desc in scored[:15]:
            print(f"    {score:5.2f}  {name:35s}  {desc}")


if __name__ == "__main__":
    main()