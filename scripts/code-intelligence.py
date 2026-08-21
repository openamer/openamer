#!/usr/bin/env python3
"""
OPENAMER_TOOL — Code Intelligence Graph
========================================
AST-Parsing + Dependency-Graph + Complexity-Analyse + Refactoring-Vorschläge + HTML-Report.

CLI-Modi:
  --build          Scannt alle .py-Dateien und baut den Graph neu auf
  --query TERM     Findet alle Referenzen zu einer Funktion/Klasse/Datei
  --deps FILE      Zeigt Abhängigkeiten einer Datei (importiert von → wird importiert von)
  --complexity     Top-10 komplexeste Funktionen (McCabe)
  --suggest-refactor Analysiert Graph und findet Refactoring-Kandidaten
  --report         Generiert HTML-Report mit Graph-Visualisierung

Exit-Codes:
  0 = Erfolg
  1 = Fehler (ungültige Argumente)
  2 = Graph nicht gefunden
  3 = Abhängigkeitsfehler
"""

import argparse
import ast
import json
import os
import sys
import textwrap
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Pfade ──────────────────────────────────────────────────────────────────────
_LOCALAPPDATA = os.environ.get("LOCALAPPDATA", str(Path.home()))
OPENAMER_HOME = Path(_LOCALAPPDATA) / "openamer-laptop"
REPO_DIR = OPENAMER_HOME / ".." / ".." / "openamer-repo"
if not REPO_DIR.exists():
    REPO_DIR = Path.cwd()

GRAPH_DIR = OPENAMER_HOME / ".code-intelligence"
GRAPH_FILE = GRAPH_DIR / "graph.json"

VERSION = "2.0.0"
TOOL_NAME = "code-intelligence"

# ── Scan-Dirs (relativ zu REPO_DIR) ────────────────────────────────────────────
SCAN_DIRS = ["openamer_cli", "scripts", "tests"]


# ═══════════════════════════════════════════════════════════════════════════════
# 1) AST-Analyse
# ═══════════════════════════════════════════════════════════════════════════════

class FunctionInfo:
    __slots__ = ("name", "args", "return_type", "start_line", "end_line",
                 "docstring", "complexity", "decorators", "calls")
    def __init__(self, name: str, args: List[str], return_type: Optional[str],
                 start_line: int, end_line: int, docstring: Optional[str],
                 complexity: int, decorators: List[str], calls: List[str]):
        self.name = name
        self.args = args
        self.return_type = return_type
        self.start_line = start_line
        self.end_line = end_line
        self.docstring = docstring
        self.complexity = complexity
        self.decorators = decorators
        self.calls = calls

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "args": self.args,
            "return_type": self.return_type,
            "lines": self.end_line - self.start_line + 1,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "docstring": self.docstring,
            "complexity": self.complexity,
            "decorators": self.decorators,
            "calls": self.calls,
        }


class ClassInfo:
    __slots__ = ("name", "bases", "methods", "attributes", "docstring",
                 "start_line", "end_line", "decorators")
    def __init__(self, name: str, bases: List[str],
                 methods: List[FunctionInfo], attributes: List[str],
                 docstring: Optional[str], start_line: int, end_line: int,
                 decorators: List[str]):
        self.name = name
        self.bases = bases
        self.methods = methods
        self.attributes = attributes
        self.docstring = docstring
        self.start_line = start_line
        self.end_line = end_line
        self.decorators = decorators

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "bases": self.bases,
            "methods": [m.to_dict() for m in self.methods],
            "attributes": self.attributes,
            "docstring": self.docstring,
            "lines": self.end_line - self.start_line + 1,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "decorators": self.decorators,
        }


class ImportInfo:
    __slots__ = ("module", "names", "alias", "is_from")
    def __init__(self, module: Optional[str], names: List[Tuple[str, Optional[str]]],
                 alias: Optional[str], is_from: bool):
        self.module = module
        self.names = names  # [(original_name, alias), ...]
        self.alias = alias
        self.is_from = is_from

    def to_dict(self) -> Dict:
        return {
            "module": self.module,
            "names": [{"name": n[0], "alias": n[1]} for n in self.names],
            "alias": self.alias,
            "is_from": self.is_from,
        }


def count_mccabe(node: ast.AST) -> int:
    """Zählt McCabe-Zyklomatische Komplexität via AST."""
    complexity = 1  # Basis-Pfad
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
            complexity += 1
        elif isinstance(child, ast.Try):
            complexity += len(child.handlers)
            if child.orelse:
                complexity += 1
            if child.finalbody:
                complexity += 1
        elif isinstance(child, ast.Assert):
            complexity += 1
        elif isinstance(child, (ast.And, ast.Or)):
            complexity += 1
        elif isinstance(child, ast.comprehension):
            complexity += 1  # for-Klausel in Comprehensions
        elif isinstance(child, ast.Match):
            complexity += len(child.cases)
    return complexity


def extract_calls(node: ast.AST) -> List[str]:
    """Extrahiert alle Funktionsaufrufe aus einem AST-Knoten."""
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.append(child.func.attr)
            elif isinstance(child.func, ast.Subscript):
                calls.append("<subscript>")
    return calls


def extract_return_type(node: ast.FunctionDef) -> Optional[str]:
    """Extrahiert den Rückgabetyp einer Funktion."""
    if node.returns:
        return ast.dump(node.returns)
    # Docstring-Return-Type parsen
    doc = ast.get_docstring(node)
    if doc:
        for line in doc.splitlines():
            line = line.strip()
            if line.startswith("Returns:") or line.startswith("Yields:"):
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
    return None


def parse_import(node: ast.AST) -> Optional[ImportInfo]:
    """Parst einen Import-Node."""
    if isinstance(node, ast.Import):
        names = [(alias.name, alias.asname) for alias in node.names]
        return ImportInfo(None, names, None, False)
    elif isinstance(node, ast.ImportFrom):
        names = [(alias.name, alias.asname) for alias in node.names]
        return ImportInfo(node.module, names, None, True)
    return None


def analyze_file(filepath: Path) -> Optional[Dict]:
    """Analysiert eine Python-Datei und gibt strukturierte Informationen zurück."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception:
        return None

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return None

    rel_path = filepath.relative_to(REPO_DIR).as_posix()
    lines = source.splitlines()
    file_size = len(source.encode("utf-8"))

    functions: List[FunctionInfo] = []
    classes: List[ClassInfo] = []
    imports: List[ImportInfo] = []
    all_calls: List[str] = []
    top_level_assignments: List[str] = []

    for node in ast.iter_child_nodes(tree):
        # Import erfassen
        imp = parse_import(node)
        if imp:
            imports.append(imp)
            continue

        # Top-Level Function
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            decorators = [ast.dump(d) if isinstance(d, ast.Name) else
                          getattr(d, 'attr', ast.dump(d)) for d in node.decorator_list]
            ret_type = extract_return_type(node)
            calls = extract_calls(node)
            mccabe = count_mccabe(node)
            doc = ast.get_docstring(node)
            fn = FunctionInfo(
                name=node.name,
                args=args,
                return_type=ret_type,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                docstring=doc,
                complexity=mccabe,
                decorators=decorators,
                calls=calls,
            )
            functions.append(fn)
            all_calls.extend(calls)

        # Top-Level Class
        elif isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(b.attr)
                else:
                    bases.append(ast.dump(b))
            decorators = [ast.dump(d) if isinstance(d, ast.Name) else
                          getattr(d, 'attr', ast.dump(d)) for d in node.decorator_list]
            doc = ast.get_docstring(node)
            methods: List[FunctionInfo] = []
            attributes: List[str] = []

            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_args = [a.arg for a in item.args.args]
                    m_decorators = [ast.dump(d) if isinstance(d, ast.Name) else
                                    getattr(d, 'attr', ast.dump(d)) for d in item.decorator_list]
                    m_ret_type = extract_return_type(item)
                    m_calls = extract_calls(item)
                    m_mccabe = count_mccabe(item)
                    m_doc = ast.get_docstring(item)
                    methods.append(FunctionInfo(
                        name=item.name, args=m_args, return_type=m_ret_type,
                        start_line=item.lineno,
                        end_line=item.end_lineno or item.lineno,
                        docstring=m_doc, complexity=m_mccabe,
                        decorators=m_decorators, calls=m_calls,
                    ))
                    all_calls.extend(m_calls)
                elif isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            attributes.append(target.id)

            cls = ClassInfo(
                name=node.name,
                bases=bases,
                methods=methods,
                attributes=attributes,
                docstring=doc,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                decorators=decorators,
            )
            classes.append(cls)

        # Top-Level Assignments (Konstanten etc.)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    top_level_assignments.append(target.id)

    # ── Import-Module-Namen extrahieren ──
    import_modules = set()
    for imp in imports:
        if imp.is_from and imp.module:
            import_modules.add(imp.module)
        else:
            for name, _ in imp.names:
                import_modules.add(name)

    # ── Interne Module (die im selben Repo sind) ──
    internal_deps = set()
    for mod in import_modules:
        # Prüfe ob mod als .py im Repo existiert
        mod_path = mod.replace(".", "/")
        for d in SCAN_DIRS:
            candidate = REPO_DIR / d / f"{mod_path}.py"
            if candidate.exists():
                internal_deps.add(candidate.relative_to(REPO_DIR).as_posix())
            # Prüfe als __init__.py
            init_candidate = REPO_DIR / d / mod_path / "__init__.py"
            if init_candidate.exists():
                internal_deps.add(init_candidate.relative_to(REPO_DIR).as_posix())
            # Prüfe ob der Modulname direkt ein Dateiname ist
            direct = REPO_DIR / d / mod
            if direct.exists() and direct.suffix == ".py":
                internal_deps.add(direct.relative_to(REPO_DIR).as_posix())

    # ── Externe Module (nicht im Repo) ──
    ext_modules = []
    for mod in sorted(import_modules):
        is_internal = False
        mod_path = mod.replace(".", "/")
        for d in SCAN_DIRS:
            if (REPO_DIR / d / f"{mod_path}.py").exists() or \
               (REPO_DIR / d / mod_path / "__init__.py").exists() or \
               (REPO_DIR / d / mod).exists():
                is_internal = True
                break
        if not is_internal:
            ext_modules.append(mod)

    # ── Alle Top-Level-Funktions-/Klassennamen für Referenzsuche ──
    top_level_names = [f.name for f in functions] + [c.name for c in classes]

    return {
        "file": rel_path,
        "dir": str(filepath.parent.relative_to(REPO_DIR)),
        "size": file_size,
        "lines": len(lines),
        "functions": [f.to_dict() for f in functions],
        "classes": [c.to_dict() for c in classes],
        "imports": [imp.to_dict() for imp in imports],
        "internal_deps": sorted(internal_deps),
        "ext_modules": ext_modules,
        "top_level_names": top_level_names,
        "all_calls": list(set(all_calls)),
        "top_level_assignments": top_level_assignments,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 2) Graph-Build
# ═══════════════════════════════════════════════════════════════════════════════

def find_python_files() -> List[Path]:
    """Findet alle .py-Dateien in den Scan-Verzeichnissen."""
    files = []
    for d in SCAN_DIRS:
        search_dir = REPO_DIR / d
        if not search_dir.exists():
            print(f"  ⚠ Verzeichnis nicht gefunden: {search_dir}", file=sys.stderr)
            continue
        for f in sorted(search_dir.rglob("*.py")):
            # __pycache__ ausschließen
            if "__pycache__" in f.parts:
                continue
            files.append(f)
    return files


def build_graph() -> Dict:
    """Baut den kompletten Code-Intelligence-Graph."""
    print(f"🔍 Code-Intelligence-Graph v{VERSION}")
    print(f"📂 Repo: {REPO_DIR}")
    print(f"📁 Scan-Dirs: {', '.join(SCAN_DIRS)}")
    print()

    files = find_python_files()
    print(f"📄 Python-Dateien gefunden: {len(files)}")
    print()

    nodes = []
    edges = []
    file_index: Dict[str, int] = {}  # rel_path → node-index
    all_functions: List[Tuple[str, str, int]] = []  # (file, func_name, complexity)
    circular_deps: List[Tuple[str, str]] = []

    # Alle Dateien parsen
    for i, fpath in enumerate(files):
        rel = fpath.relative_to(REPO_DIR).as_posix()
        file_index[rel] = i
        info = analyze_file(fpath)
        if info is None:
            print(f"  [{i+1:4d}/{len(files)}] ⚠ {rel} – Parse-Fehler", file=sys.stderr)
            nodes.append({
                "file": rel,
                "size": 0,
                "lines": 0,
                "functions": [],
                "classes": [],
                "imports": [],
                "internal_deps": [],
                "ext_modules": [],
                "top_level_names": [],
                "all_calls": [],
                "top_level_assignments": [],
                "error": True,
            })
            continue

        nodes.append(info)
        for fn in info["functions"]:
            all_functions.append((rel, fn["name"], fn["complexity"]))
        for cls in info["classes"]:
            for m in cls["methods"]:
                all_functions.append((f"{rel}::{cls['name']}", m["name"], m["complexity"]))

        # Edge: imports
        for dep in info["internal_deps"]:
            edges.append({
                "from": rel,
                "to": dep,
                "type": "import",
            })
            # Prüfe zirkuläre imports
            if dep in file_index:
                dep_info = analyze_file(REPO_DIR / dep.replace("/", "\\"))
                if dep_info and rel in dep_info.get("internal_deps", []):
                    circular_deps.append((rel, dep))

        print(f"  [{i+1:4d}/{len(files)}] ✓ {rel}")

    print()
    print(f"✅ {len(nodes)} Dateien analysiert")
    print(f"🔗 {len(edges)} Abhängigkeiten (internal imports)")
    if circular_deps:
        print(f"⚠  {len(circular_deps)} zirkuläre Imports gefunden")

    # Statistik
    total_lines = sum(n.get("lines", 0) for n in nodes)
    total_functions = sum(len(n.get("functions", [])) for n in nodes)
    total_classes = sum(len(n.get("classes", [])) for n in nodes)
    total_imports = sum(len(n.get("imports", [])) for n in nodes)

    graph = {
        "meta": {
            "tool": TOOL_NAME,
            "version": VERSION,
            "built_at": datetime.now().isoformat(),
            "repo": str(REPO_DIR),
            "scan_dirs": SCAN_DIRS,
            "total_files": len(nodes),
            "total_lines": total_lines,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "total_imports": total_imports,
            "total_edges": len(edges),
            "circular_imports": circular_deps,
        },
        "nodes": nodes,
        "edges": edges,
        "file_index": file_index,
    }

    return graph


# ═══════════════════════════════════════════════════════════════════════════════
# 3) Query
# ═══════════════════════════════════════════════════════════════════════════════

def query_graph(graph: Dict, term: str) -> None:
    """Findet alle Referenzen zu einem Suchbegriff."""
    term_lower = term.lower()
    results: List[Dict] = []

    for node in graph["nodes"]:
        if node.get("error"):
            continue
        matches = []

        # Dateiname
        if term_lower in node["file"].lower():
            matches.append({"type": "file", "value": node["file"]})

        # Funktionen
        for fn in node.get("functions", []):
            if term_lower in fn.get("name", "").lower():
                matches.append({
                    "type": "function",
                    "value": f"{node['file']}:{fn['name']}",
                    "lines": f"Z.{fn.get('start_line', '?')}-{fn.get('end_line', '?')}",
                    "complexity": fn.get("complexity", 0),
                })
            # Prüfe args
            for arg in fn.get("args", []):
                if term_lower == arg.lower():
                    matches.append({
                        "type": "argument",
                        "value": f"{node['file']}:{fn['name']}({arg})",
                    })

        # Klassen
        for cls in node.get("classes", []):
            if term_lower in cls.get("name", "").lower():
                matches.append({
                    "type": "class",
                    "value": f"{node['file']}:{cls['name']}",
                    "lines": f"Z.{cls.get('start_line', '?')}-{cls.get('end_line', '?')}",
                })
            for m in cls.get("methods", []):
                if term_lower in m.get("name", "").lower():
                    matches.append({
                        "type": "method",
                        "value": f"{node['file']}:{cls['name']}.{m['name']}",
                        "complexity": m.get("complexity", 0),
                    })

        # Imports
        for imp in node.get("imports", []):
            mod = imp.get("module", "")
            if mod and term_lower in mod.lower():
                matches.append({
                    "type": "import",
                    "value": f"{node['file']} → {mod}",
                })
            for n in imp.get("names", []):
                if term_lower in n.get("name", "").lower():
                    matches.append({
                        "type": "import_name",
                        "value": f"{node['file']} → {n['name']}",
                    })

        if matches:
            results.append({"file": node["file"], "matches": matches})

    if not results:
        print(f"🔍 Keine Ergebnisse für '{term}'")
        return

    print(f"🔍 Referenzen für '{term}':")
    print(f"   Gefunden in {len(results)} Dateien")
    print()
    for r in results:
        print(f"  📄 {r['file']}:")
        for m in r["matches"]:
            sym = {"function": "ƒ", "class": "⌘", "method": "◈", "import": "⬇",
                   "import_name": "⬇", "argument": "↳", "file": "📄"}.get(m["type"], "•")
            extra = ""
            if "complexity" in m and m["complexity"] > 0:
                extra = f" [CX={m['complexity']}]"
            if "lines" in m:
                extra += f" ({m['lines']})"
            print(f"    {sym} {m['type']}: {m['value']}{extra}")
        print()


# ═══════════════════════════════════════════════════════════════════════════════
# 4) Dependencies
# ═══════════════════════════════════════════════════════════════════════════════

def show_deps(graph: Dict, file_path: str) -> None:
    """Zeigt Abhängigkeiten einer Datei."""
    # Normalize path
    file_path = file_path.replace("\\", "/")
    if not file_path.startswith("openamer_cli/") and \
       not file_path.startswith("scripts/") and \
       not file_path.startswith("tests/"):
        # Versuche relative Pfaderkennung
        for d in SCAN_DIRS:
            if file_path.startswith(d) or f"/{d}" in file_path or file_path.startswith(d.replace("/", "\\")):
                break
        else:
            # Vielleicht ist es ein absoluter Pfad?
            if ":" in file_path:
                try:
                    file_path = str(Path(file_path).relative_to(REPO_DIR).as_posix())
                except ValueError:
                    pass

    node = None
    for n in graph["nodes"]:
        if n["file"] == file_path or n["file"].endswith(file_path):
            node = n
            break

    if node is None:
        print(f"❌ Datei nicht im Graph: {file_path}")
        print("   Verfügbare Dateien (Beispiele):")
        for n in graph["nodes"][:10]:
            print(f"     - {n['file']}")
        return

    print(f"📄 {node['file']}")
    print(f"   Größe: {node['size']:,} Bytes, {node['lines']} Zeilen")
    print()

    # Importiert von (diese Datei importiert andere)
    internal = node.get("internal_deps", [])
    external = node.get("ext_modules", [])

    print(f"  ⬇ Importiert {len(internal) + len(external)} Module:")
    if internal:
        print(f"     ─ Intern ─")
        for d in internal:
            print(f"       📄 {d}")
    if external:
        print(f"     ─ Extern ─")
        for d in external:
            print(f"       📦 {d}")

    # Wird importiert von (andere Dateien importieren diese)
    importers = []
    for n in graph["nodes"]:
        if file_path in n.get("internal_deps", []):
            importers.append(n["file"])

    print()
    print(f"  ⬆ Importiert von {len(importers)} Dateien:")
    for i in importers:
        print(f"     📄 {i}")

    # Funktionen die in dieser Datei definiert sind
    print()
    if node.get("functions"):
        print(f"  ƒ Funktionen ({len(node['functions'])}):")
        for fn in node["functions"]:
            print(f"     {fn['name']}({', '.join(fn['args'])}) "
                  f"[CX={fn['complexity']}, Z.{fn['start_line']}-{fn['end_line']}]")

    if node.get("classes"):
        print(f"  ⌘ Klassen ({len(node['classes'])}):")
        for cls in node["classes"]:
            print(f"     {cls['name']}({', '.join(cls['bases'])})"
                  f" [Z.{cls['start_line']}-{cls['end_line']}]")
            for m in cls.get("methods", []):
                print(f"       ◈ {m['name']}({', '.join(m['args'])})"
                      f" [CX={m['complexity']}]")


# ═══════════════════════════════════════════════════════════════════════════════
# 5) Complexity
# ═══════════════════════════════════════════════════════════════════════════════

def show_complexity(graph: Dict, top_n: int = 10) -> None:
    """Zeigt die top N komplexesten Funktionen."""
    all_funcs: List[Tuple[str, str, int, int, int]] = []  # (file, name, complexity, line, lines)
    for node in graph["nodes"]:
        if node.get("error"):
            continue
        for fn in node.get("functions", []):
            all_funcs.append((
                node["file"],
                fn["name"],
                fn.get("complexity", 0),
                fn.get("start_line", 0),
                fn.get("lines", 0),
            ))
        for cls in node.get("classes", []):
            for m in cls.get("methods", []):
                all_funcs.append((
                    f"{node['file']}::{cls['name']}",
                    m["name"],
                    m.get("complexity", 0),
                    m.get("start_line", 0),
                    m.get("lines", 0),
                ))

    # Sortieren nach Complexity absteigend
    all_funcs.sort(key=lambda x: -x[2])

    print(f"📊 Top {top_n} komplexeste Funktionen (McCabe)")
    print(f"   Gesamt: {len(all_funcs)} Funktionen/Methoden")
    print()
    print(f"   {'Rang':<5} {'Complexity':<10} {'Zeilen':<6} {'Funktion':<40} {'Datei'}")
    print(f"   {'─'*4:<5} {'─'*9:<10} {'─'*5:<6} {'─'*39:<40} {'─'*50}")
    for i, (fpath, name, cx, line, lines) in enumerate(all_funcs[:top_n], 1):
        # Display-Name kürzen
        short_name = name if len(name) <= 38 else name[:35] + "..."
        rank_mark = "⚠" if cx >= 10 else "◈" if cx >= 5 else "•"
        print(f"   {rank_mark}{i:<4} {cx:<10} {lines:<6} {short_name:<40} {fpath}")

    # Statistik
    if all_funcs:
        avg_cx = sum(f[2] for f in all_funcs) / len(all_funcs)
        high_cx = sum(1 for f in all_funcs if f[2] >= 10)
        print()
        print(f"   📈 Durchschnittliche Complexity: {avg_cx:.1f}")
        print(f"   ⚠  Funktionen mit CX ≥ 10: {high_cx}")


# ═══════════════════════════════════════════════════════════════════════════════
# 6) Refactoring-Vorschläge
# ═══════════════════════════════════════════════════════════════════════════════

def suggest_refactoring(graph: Dict) -> None:
    """Analysiert den Graph und schlägt Refactoring-Kandidaten vor."""
    print("🔄 Refactoring-Vorschläge")
    print()

    suggestions = []

    # ── 1. Zu große Dateien ──
    large_files = []
    for node in graph["nodes"]:
        if node.get("error"):
            continue
        lines = node.get("lines", 0)
        if lines > 800:
            large_files.append((node["file"], lines, "Sehr groß (>800 Zeilen)"))
        elif lines > 400:
            large_files.append((node["file"], lines, "Groß (>400 Zeilen)"))

    if large_files:
        print(f"  📏 1. Zu große Dateien ({len(large_files)} Kandidaten)")
        print(f"     {'Datei':<60} {'Zeilen':<7} {'Empfehlung'}")
        print(f"     {'─'*59:<60} {'─'*6:<7} {'─'*30}")
        for fpath, lines, reason in sorted(large_files, key=lambda x: -x[1]):
            print(f"     {fpath:<60} {lines:<7} {reason}")
        print()

    # ── 2. Zu komplexe Funktionen ──
    high_cx: List[Tuple[str, str, int]] = []
    for node in graph["nodes"]:
        if node.get("error"):
            continue
        for fn in node.get("functions", []):
            cx = fn.get("complexity", 0)
            if cx >= 10:
                high_cx.append((node["file"], fn["name"], cx))
        for cls in node.get("classes", []):
            for m in cls.get("methods", []):
                cx = m.get("complexity", 0)
                if cx >= 10:
                    high_cx.append((f"{node['file']}::{cls['name']}", m["name"], cx))

    if high_cx:
        print(f"  ⚠  2. Hochkomplexe Funktionen ({len(high_cx)} Kandidaten)")
        print(f"     {'Datei':<65} {'Funktion':<35} {'CX':<5} {'Empfehlung'}")
        print(f"     {'─'*64:<65} {'─'*34:<35} {'─'*4:<5} {'─'*30}")
        for fpath, name, cx in sorted(high_cx, key=lambda x: -x[2]):
            print(f"     {fpath:<65} {name:<35} {cx:<5} Funktion aufteilen")
        print()

    # ── 3. Zirkuläre Imports ──
    circular = graph["meta"].get("circular_imports", [])
    if circular:
        print(f"  🔄 3. Zirkuläre Imports ({len(circular)})")
        print(f"     Zirkuläre Import-Ketten:")
        visited: Set[str] = set()
        for a, b in circular:
            if a not in visited or b not in visited:
                print(f"     {a} ↔ {b}")
                visited.add(a)
                visited.add(b)
        print()

    # ── 4. Dateien ohne Klassen/Funktionen (nur imports + assignments) ──
    empty = []
    for node in graph["nodes"]:
        if node.get("error"):
            continue
        if not node.get("functions") and not node.get("classes") and node.get("lines", 0) > 50:
            empty.append((node["file"], node.get("lines", 0)))
    if empty:
        print(f"  📄 4. Skript-artige Dateien (keine Funktionen/Klassen, >50 Zeilen):")
        for fpath, lines in sorted(empty, key=lambda x: -x[1]):
            print(f"     {fpath:<60} {lines:<7} Zeilen – Evtl. in Module aufteilen")
        print()

    # ── 5. Top-Import-Wiederholungen (gleiche Imports in vielen Dateien) ──
    import_counter: Counter = Counter()
    for node in graph["nodes"]:
        if node.get("error"):
            continue
        for imp in node.get("imports", []):
            mod = imp.get("module", "")
            for n in imp.get("names", []):
                name = n.get("name", "")
                key = f"{mod}.{name}" if mod else name
                import_counter[key] += 1

    if import_counter:
        print(f"  📦 5. Meistgenutzte Imports (Top 15):")
        print(f"     {'Modul/Symbol':<45} {'Anzahl':<7}")
        print(f"     {'─'*44:<45} {'─'*6:<7}")
        for (name, count) in import_counter.most_common(15):
            print(f"     {name:<45} {count:<7}")
        print()

    # ── 6. Lange Funktionen (hohe Zeilenzahl) ──
    long_funcs: List[Tuple[str, str, int, int]] = []
    for node in graph["nodes"]:
        if node.get("error"):
            continue
        for fn in node.get("functions", []):
            flines = fn.get("lines", 0)
            if flines >= 80:
                long_funcs.append((node["file"], fn["name"], flines, fn.get("complexity", 0)))
        for cls in node.get("classes", []):
            for m in cls.get("methods", []):
                mlines = m.get("lines", 0)
                if mlines >= 80:
                    long_funcs.append((
                        f"{node['file']}::{cls['name']}", m["name"],
                        mlines, m.get("complexity", 0)
                    ))

    if long_funcs:
        print(f"  📏 6. Lange Funktionen/Methoden ({len(long_funcs)}, ≥80 Zeilen):")
        for fpath, name, flines, cx in sorted(long_funcs, key=lambda x: -x[2])[:15]:
            print(f"     {fpath:<65} {name:<30} {flines:<5} Z. [CX={cx}]")
        print()

    # Zusammenfassung
    total = sum([
        len(large_files),
        len(high_cx),
        len(circular),
        len(empty),
        len(long_funcs),
    ])
    print(f"  📊 Gesamt: {total} Refactoring-Kandidaten gefunden.")


# ═══════════════════════════════════════════════════════════════════════════════
# 7) HTML-Report
# ═══════════════════════════════════════════════════════════════════════════════

def generate_html_report(graph: Dict) -> str:
    """Generiert einen HTML-Report mit interaktiver Graph-Visualisierung."""
    meta = graph["meta"]
    nodes = graph["nodes"]
    edges = graph["edges"]

    # ── Daten für die D3.js-Visualisierung aufbereiten ──
    d3_nodes = []
    d3_links = []

    node_id_map: Dict[str, int] = {}  # file → index in d3_nodes
    for i, node in enumerate(nodes):
        if node.get("error"):
            continue
        file_name = node["file"]
        node_id_map[file_name] = len(d3_nodes)
        # Größe nach Zeilenanzahl skalieren (für D3)
        size = max(5, min(50, node.get("lines", 0) / 20))
        # Farbe nach Datei-Typ
        color = "#4CAF50" if node["file"].startswith("openamer_cli/") else \
                "#2196F3" if node["file"].startswith("scripts/") else \
                "#FF9800" if node["file"].startswith("tests/") else "#9C27B0"
        d3_nodes.append({
            "id": file_name,
            "label": Path(file_name).name,
            "group": node["dir"].split("/")[0] if "/" in node.get("dir", "") else node.get("dir", "root"),
            "size": size,
            "lines": node.get("lines", 0),
            "functions": len(node.get("functions", [])),
            "classes": len(node.get("classes", [])),
            "color": color,
        })

    for edge in edges:
        src_idx = node_id_map.get(edge["from"])
        dst_idx = node_id_map.get(edge["to"])
        if src_idx is not None and dst_idx is not None:
            d3_links.append({
                "source": src_idx,
                "target": dst_idx,
                "type": edge["type"],
            })

    # ── Top-CX-Funktionen ──
    all_funcs = []
    for node in nodes:
        if node.get("error"):
            continue
        for fn in node.get("functions", []):
            all_funcs.append((node["file"], fn["name"], fn.get("complexity", 0)))
        for cls in node.get("classes", []):
            for m in cls.get("methods", []):
                all_funcs.append((f"{node['file']}::{cls['name']}", m["name"], m.get("complexity", 0)))
    all_funcs.sort(key=lambda x: -x[2])

    # ── HTML bauen ──
    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Code-Intelligence-Graph — {Path(REPO_DIR).name}</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }}
h1, h2, h3 {{ color: #58a6ff; }}
.container {{ max-width: 1600px; margin: 0 auto; }}
.header {{ padding: 20px 0; border-bottom: 1px solid #30363d; margin-bottom: 30px; }}
.header h1 {{ font-size: 28px; }}
.header .meta {{ color: #8b949e; font-size: 14px; margin-top: 8px; }}
.stats-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 30px; }}
.stat-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
             padding: 16px 24px; min-width: 140px; }}
.stat-card .value {{ font-size: 28px; font-weight: bold; color: #58a6ff; }}
.stat-card .label {{ font-size: 12px; color: #8b949e; margin-top: 4px; }}
.stat-card.warn .value {{ color: #d29922; }}
.stat-card.danger .value {{ color: #f85149; }}
.stat-card.success .value {{ color: #3fb950; }}
#graph {{ background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
         width: 100%; height: 700px; margin-bottom: 30px; }}
.graph-tooltip {{ position: absolute; background: #1c2128; border: 1px solid #30363d;
                 border-radius: 6px; padding: 12px; font-size: 12px; pointer-events: none; }}
.graph-legend {{ display: flex; gap: 20px; padding: 10px 16px; margin-bottom: 16px;
                background: #161b22; border: 1px solid #30363d; border-radius: 6px; }}
.legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; }}
.legend-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
table {{ width: 100%; border-collapse: collapse; margin: 16px 0 30px 0; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #21262d; }}
th {{ background: #161b22; color: #8b949e; font-weight: 600; font-size: 12px;
     text-transform: uppercase; letter-spacing: 0.5px; }}
tr:hover td {{ background: #1c2128; }}
td {{ font-size: 13px; }}
.code {{ font-family: 'SF Mono', 'Cascadia Code', monospace; font-size: 12px; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; }}
.tag-cli {{ background: #1a3a1a; color: #3fb950; }}
.tag-script {{ background: #1a2a4a; color: #58a6ff; }}
.tag-test {{ background: #3a2a1a; color: #d29922; }}
.badge {{ display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 10px; }}
.badge-high {{ background: #3a1a1a; color: #f85149; }}
.badge-mid {{ background: #3a2a1a; color: #d29922; }}
.badge-low {{ background: #1a3a1a; color: #3fb950; }}
.section {{ margin-bottom: 30px; }}
.section h2 {{ margin-bottom: 12px; }}
.circular {{ color: #d29922; }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>🔬 Code-Intelligence-Graph</h1>
  <div class="meta">
    Repo: <strong>{Path(REPO_DIR).name}</strong> ·
    Version {meta.get("version", "?")} ·
    Gebaut: {meta.get("built_at", "?")} ·
    Scan: {', '.join(meta.get("scan_dirs", []))}
  </div>
</div>

<div class="stats-row">
  <div class="stat-card success">
    <div class="value">{meta.get("total_files", 0)}</div>
    <div class="label">Python-Dateien</div>
  </div>
  <div class="stat-card">
    <div class="value">{meta.get("total_lines", 0):,}</div>
    <div class="label">Code-Zeilen</div>
  </div>
  <div class="stat-card">
    <div class="value">{meta.get("total_functions", 0)}</div>
    <div class="label">Funktionen</div>
  </div>
  <div class="stat-card">
    <div class="value">{meta.get("total_classes", 0)}</div>
    <div class="label">Klassen</div>
  </div>
  <div class="stat-card">
    <div class="value">{meta.get("total_imports", 0)}</div>
    <div class="label">Imports</div>
  </div>
  <div class="stat-card">
    <div class="value">{len(d3_links)}</div>
    <div class="label">Abhängigkeiten</div>
  </div>
  <div class="stat-card warn">
    <div class="value">{len(meta.get("circular_imports", []))}</div>
    <div class="label">Zirkuläre Imports</div>
  </div>
</div>

<h2>📊 Abhängigkeits-Graph</h2>
<div class="graph-legend">
  <div class="legend-item"><span class="legend-dot" style="background:#4CAF50"></span> openamer_cli/</div>
  <div class="legend-item"><span class="legend-dot" style="background:#2196F3"></span> scripts/</div>
  <div class="legend-item"><span class="legend-dot" style="background:#FF9800"></span> tests/</div>
  <div class="legend-item"><span style="margin-left:20px">Knotengröße = Code-Zeilen</span></div>
  <div class="legend-item">Kanten = Import-Beziehungen</div>
</div>
<div id="graph"></div>

<div class="section">
  <h2>🏆 Top-{min(20, len(all_funcs))} komplexeste Funktionen</h2>
  <table>
    <tr><th>#</th><th>Funktion</th><th>Datei</th><th>Complexity</th></tr>
"""
    for i, (fpath, name, cx) in enumerate(all_funcs[:20], 1):
        badge = "badge-high" if cx >= 10 else "badge-mid" if cx >= 5 else "badge-low"
        html += f'    <tr><td>{i}</td><td class="code">{name}</td><td>{fpath}</td><td><span class="badge {badge}">{cx}</span></td></tr>\n'

    html += """  </table>
</div>

<div class="section">
  <h2>📁 Alle analysierten Dateien</h2>
  <table>
    <tr><th>Datei</th><th>Zeilen</th><th>Funktionen</th><th>Klassen</th><th>Imports</th><th>Typ</th></tr>
"""
    for node in sorted(nodes, key=lambda n: n["file"]):
        if node.get("error"):
            continue
        dir_tag = node["file"].split("/")[0]
        tag_class = "tag-cli" if dir_tag == "openamer_cli" else "tag-script" if dir_tag == "scripts" else "tag-test"
        html += f'    <tr><td class="code">{node["file"]}</td><td>{node.get("lines", 0)}</td><td>{len(node.get("functions", []))}</td><td>{len(node.get("classes", []))}</td><td>{len(node.get("imports", []))}</td><td><span class="tag {tag_class}">{dir_tag}</span></td></tr>\n'

    circular = meta.get("circular_imports", [])
    if circular:
        html += """  </table>
</div>

<div class="section">
  <h2 class="circular">⚠ Zirkuläre Imports</h2>
  <table>
    <tr><th>#</th><th>Datei A</th><th>↔</th><th>Datei B</th></tr>
"""
        for i, (a, b) in enumerate(circular, 1):
            html += f'    <tr><td>{i}</td><td class="code">{a}</td><td>↔</td><td class="code">{b}</td></tr>\n'

    html += """  </table>
</div>

<script>
const nodes = """ + json.dumps(d3_nodes) + """;
const links = """ + json.dumps(d3_links) + """;

const width = document.getElementById('graph').clientWidth;
const height = 700;

const svg = d3.select('#graph')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

const g = svg.append('g');

// Zoom
svg.call(d3.zoom()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => g.attr('transform', event.transform)));

// Simulation
const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(d => d.size * 1.5));

// Links
const link = g.append('g')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', '#30363d')
    .attr('stroke-width', 1)
    .attr('stroke-opacity', 0.6);

// Nodes
const node = g.append('g')
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r', d => Math.max(3, d.size))
    .attr('fill', d => d.color)
    .attr('stroke', '#30363d')
    .attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .call(d3.drag()
        .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        })
        .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
        })
        .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }));

// Labels
const label = g.append('g')
    .selectAll('text')
    .data(nodes)
    .join('text')
    .text(d => d.label)
    .attr('font-size', '10px')
    .attr('fill', '#8b949e')
    .attr('dx', 8)
    .attr('dy', 4)
    .style('pointer-events', 'none');

// Tooltip
const tooltip = d3.select('#graph')
    .append('div')
    .attr('class', 'graph-tooltip')
    .style('opacity', 0);

node.on('mouseover', (event, d) => {
    tooltip.transition().duration(200).style('opacity', 0.95);
    tooltip.html(`<b>${d.label}</b><br>
        ${d.id}<br>
        📏 ${d.lines} Zeilen · ƒ ${d.functions} · ⌘ ${d.classes}`)
        .style('left', (event.offsetX + 10) + 'px')
        .style('top', (event.offsetY - 10) + 'px');
})
.on('mouseout', () => {
    tooltip.transition().duration(500).style('opacity', 0);
});

// Tick
simulation.on('tick', () => {
    link.attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
    node.attr('cx', d => d.x).attr('cy', d => d.y);
    label.attr('x', d => d.x).attr('y', d => d.y);
});
</script>
</div>
</body>
</html>"""
    return html


# ═══════════════════════════════════════════════════════════════════════════════
# 8) CLI-Dispatch
# ═══════════════════════════════════════════════════════════════════════════════

def ensure_graph() -> Dict:
    """Stellt sicher, dass der Graph existiert (baut bei Bedarf)."""
    if GRAPH_FILE.exists():
        try:
            with open(GRAPH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            print("⚠ Graph-Datei beschädigt, baue neu…", file=sys.stderr)
    print("🔨 Baue Graph (kein gecachter Graph gefunden)…")
    print()
    graph = build_graph()
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    with open(GRAPH_FILE, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    print()
    print(f"💾 Graph gespeichert: {GRAPH_FILE}")
    return graph


def main():
    parser = argparse.ArgumentParser(
        description=f"Code-Intelligence-Graph v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Beispiele:
              %(prog)s --build
              %(prog)s --query 'cmd_cron'
              %(prog)s --query 'class:KanbanBoard'
              %(prog)s --deps 'openamer_cli/main.py'
              %(prog)s --complexity
              %(prog)s --complexity --top 20
              %(prog)s --suggest-refactor
              %(prog)s --report
              %(prog)s --build --report    # bauen + Report generieren
        """),
    )
    parser.add_argument("--build", action="store_true", help="Graph neu bauen")
    parser.add_argument("--query", type=str, metavar="TERM", help="Referenz-Suche")
    parser.add_argument("--deps", type=str, metavar="FILE", help="Abhängigkeiten einer Datei")
    parser.add_argument("--complexity", action="store_true", help="Top komplexe Funktionen")
    parser.add_argument("--top", type=int, default=10, metavar="N",
                        help="Top N für --complexity (default: 10)")
    parser.add_argument("--suggest-refactor", action="store_true",
                        help="Refactoring-Kandidaten finden")
    parser.add_argument("--report", action="store_true", help="HTML-Report generieren")
    parser.add_argument("--no-cache", action="store_true",
                        help="Immer neu bauen (ignoriert Cache)")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON-Output")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    args = parser.parse_args()

    # Kein Argument → Help
    if not any([args.build, args.query, args.deps, args.complexity,
                args.suggest_refactor, args.report]):
        parser.print_help()
        return

    # --build (immer zuerst, da Report darauf aufbauen kann)
    if args.build or args.no_cache:
        if not args.no_cache:
            print("🔨 Baue Graph neu…")
        else:
            print("🔨 Baue Graph (--no-cache)…")
        print()
        graph = build_graph()
        GRAPH_DIR.mkdir(parents=True, exist_ok=True)
        with open(GRAPH_FILE, "w", encoding="utf-8") as f:
            json.dump(graph, f, indent=2, ensure_ascii=False)
        print()
        print(f"💾 Graph gespeichert: {GRAPH_FILE}")

        if args.json:
            print(json.dumps({
                "tool": TOOL_NAME,
                "version": VERSION,
                "status": "ok",
                "output": {
                    "action": "build",
                    "graph_file": str(GRAPH_FILE),
                    "meta": graph["meta"],
                },
                "exit_code": 0,
            }, indent=2))
        return

    # Für andere Modi Graph laden (oder bauen falls nicht vorhanden)
    if not GRAPH_FILE.exists():
        graph = ensure_graph()
    else:
        try:
            with open(GRAPH_FILE, "r", encoding="utf-8") as f:
                graph = json.load(f)
        except (json.JSONDecodeError, OSError):
            graph = ensure_graph()

    if args.query:
        if args.json:
            # JSON Query
            results = query_graph_json(graph, args.query)
            print(json.dumps({
                "tool": TOOL_NAME,
                "version": VERSION,
                "status": "ok",
                "output": {"action": "query", "term": args.query, "results": results},
                "exit_code": 0,
            }, indent=2))
        else:
            query_graph(graph, args.query)

    if args.deps:
        show_deps(graph, args.deps)

    if args.complexity:
        show_complexity(graph, args.top)

    if args.suggest_refactor:
        suggest_refactoring(graph)

    if args.report:
        print("📊 Generiere HTML-Report…")
        html = generate_html_report(graph)
        report_file = GRAPH_DIR / "report.html"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"   Report gespeichert: {report_file}")
        # Auch in den repo-eigenen Ordner kopieren
        repo_report = REPO_DIR / ".code-intelligence" / "report.html"
        repo_report.parent.mkdir(parents=True, exist_ok=True)
        with open(repo_report, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"   Report (Repo-Kopie): {repo_report}")


def query_graph_json(graph: Dict, term: str) -> List[Dict]:
    """JSON-Variante der Query."""
    term_lower = term.lower()
    results = []
    for node in graph["nodes"]:
        matches = []
        if term_lower in node["file"].lower():
            matches.append({"type": "file", "value": node["file"]})
        for fn in node.get("functions", []):
            if term_lower in fn.get("name", "").lower():
                matches.append({
                    "type": "function",
                    "value": f"{node['file']}:{fn['name']}",
                    "complexity": fn.get("complexity", 0),
                    "start_line": fn.get("start_line"),
                })
        for cls in node.get("classes", []):
            if term_lower in cls.get("name", "").lower():
                matches.append({
                    "type": "class",
                    "value": f"{node['file']}:{cls['name']}",
                })
        if matches:
            results.append({"file": node["file"], "matches": matches})
    return results


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠ Abbruch durch Benutzer", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Fehler: {e}", file=sys.stderr)
        sys.exit(1)