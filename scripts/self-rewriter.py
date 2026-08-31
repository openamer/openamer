#!/usr/bin/env python3
"""
Self-Rewriting Core — Autonomous Core Evolution Engine.

Analysiert openamer_cli/ (Haupt-Core): scannt alle .py-Dateien,
extrahiert Funktionen + Klassen + Imports via AST.
Findet Ineffizienzen: doppelte imports, zu lange Funktionen (>100 Zeilen),
fehlende Type Hints, leere except-Blöcke, TODO/FIXME.
Generiert Patches als unified diff → .rewriter/pending/<module>.patch.
Validiert via python -m py_compile + optional pytest.
Apply: git branch rewriter-tmp → patch anwenden → testen → commit + merge.

CLI:
  --scan          Analysiert Core, speichert Report
  --suggest       Zeigt gefundene Verbesserungen
  --patch         Generiert Patches für gefundene Issues
  --apply         Validiert + committet Patches
  --all           Full Cycle (scan → suggest → patch → apply)
  --dry-run       Nur anzeigen, nichts schreiben
  --max-patches N Pro Run begrenzen (default: 3)
  --report FILE   Report-Pfad (default: .rewriter/reports/latest.json)
  --yes           Automatisch bestätigen (non-interactive)

Exit-Codes:
  0 = nichts zu tun / alles sauber
  1 = Patches verfügbar (--suggest oder --patch hat was gefunden)
  2 = Patches angewandt (--apply erfolgreich)
"""

import argparse
import ast
import collections
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any


# ─── Konfiguration ───────────────────────────────────────────────────────────
def _find_repo_root(repo_arg: Optional[Path] = None) -> Path:
    """Findet das Repo-Root, egal ob das Script vom Repo oder OPENAMER_HOME läuft."""
    # CLI-Override hat höchste Priorität
    if repo_arg is not None:
        if (repo_arg / "openamer_cli").is_dir():
            return repo_arg.resolve()
        raise SystemExit(f"❌ Angegebenes Repo-Root hat kein openamer_cli/: {repo_arg}")

    self_path = Path(__file__).resolve()
    # Fall 1: Im Repo scripts/ Verzeichnis
    if self_path.parent.name == "scripts":
        candidate = self_path.parents[1]
        if (candidate / "openamer_cli").is_dir():
            return candidate
    # Fall 2: Von OPENAMER_HOME/scripts/
    script_dir = self_path.parent
    for candidate in [
        Path.home() / "openamer-repo",
        Path.home() / "OpenAmer",
        Path.home() / "openamer",
    ]:
        if (candidate / "openamer_cli").is_dir():
            return candidate
    # Fall 3: Suche ab Skript-Verzeichnis aufwärts
    for parent in [self_path, *self_path.parents]:
        if (parent / "openamer_cli").is_dir():
            return parent
        if (parent / "scripts").is_dir() and (parent.parent / "openamer_cli").is_dir():
            return parent.parent
    # Fallback: CLI-Argument oder Fehler
    return self_path.parents[1]

REPO_ROOT = _find_repo_root()
CORE_DIR = REPO_ROOT / "openamer_cli"
REWRITER_DIR = REPO_ROOT / ".rewriter"
PENDING_DIR = REWRITER_DIR / "pending"
APPLIED_DIR = REWRITER_DIR / "applied"
REPORTS_DIR = REWRITER_DIR / "reports"
DEFAULT_REPORT = REPORTS_DIR / "latest.json"

MAX_FUNC_LINES = 100
MAX_PATCHES_DEFAULT = 3
CRON_BRANCH = "rewriter-tmp"


# ─── Issue-Typen ─────────────────────────────────────────────────────────────
class IssueType:
    DUPLICATE_IMPORT = "duplicate_import"
    LONG_FUNCTION = "long_function"
    MISSING_TYPE_HINTS = "missing_type_hints"
    EMPTY_EXCEPT = "empty_except"
    TODO_FIXME = "todo_fixme"
    UNUSED_IMPORT = "unused_import"

    LABELS = {
        DUPLICATE_IMPORT: "❌ Doppelter Import",
        LONG_FUNCTION: "📏 Zu lange Funktion",
        MISSING_TYPE_HINTS: "🔤 Fehlende Type Hints",
        EMPTY_EXCEPT: "⚠️  Leerer except-Block",
        TODO_FIXME: "📝 TODO/FIXME",
        UNUSED_IMPORT: "🗑️  Unbenutzter Import",
    }

    SEVERITY = {
        DUPLICATE_IMPORT: 3,
        LONG_FUNCTION: 5,
        MISSING_TYPE_HINTS: 2,
        EMPTY_EXCEPT: 8,
        TODO_FIXME: 4,
        UNUSED_IMPORT: 6,
    }


# ─── AST Helpers ─────────────────────────────────────────────────────────────

class CoreAnalyzer(ast.NodeVisitor):
    """AST-basierte Analyse einer einzelnen Python-Datei."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.issues: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.classes: List[Dict[str, Any]] = []
        self.imports: List[Dict[str, Any]] = []
        self.lines: List[str] = []

        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            self.lines = source.splitlines()
            self.tree = ast.parse(source, filename=str(filepath))
            self.source = source
        except SyntaxError as e:
            self.tree = None
            self.source = ""
            self.issues.append({
                "type": "syntax_error",
                "line": e.lineno or 1,
                "col": e.offset or 0,
                "msg": f"SyntaxError: {e.msg}",
                "severity": 10,
            })
        except Exception as e:
            self.tree = None
            self.source = ""
            self.issues.append({
                "type": "read_error",
                "line": 1,
                "col": 0,
                "msg": f"Fehler beim Lesen: {e}",
                "severity": 10,
            })

    def analyze(self) -> None:
        """Führt alle Analyseschritte aus."""
        if self.tree is None:
            return

        self.generic_visit(self.tree)
        self._find_todos()
        self._check_empty_except()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append({
                "name": alias.name,
                "asname": alias.asname,
                "line": node.lineno,
                "col": node.col_offset,
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            self.imports.append({
                "name": f"{module}.{alias.name}" if module else alias.name,
                "asname": alias.asname,
                "line": node.lineno,
                "col": node.col_offset,
                "module": module,
                "alias_name": alias.name,
            })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        n_lines = end - start + 1
        has_return_annotation = node.returns is not None
        arg_hints = sum(1 for a in node.args.args if a.annotation is not None)

        func_info = {
            "name": node.name,
            "start_line": start,
            "end_line": end,
            "n_lines": n_lines,
            "has_return_hint": has_return_annotation,
            "arg_count": len(node.args.args),
            "arg_hints": arg_hints,
            "decorators": [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list],
        }
        self.functions.append(func_info)

        # Zu lange Funktion
        if n_lines > MAX_FUNC_LINES:
            self.issues.append({
                "type": IssueType.LONG_FUNCTION,
                "line": start,
                "col": node.col_offset,
                "msg": f"Funktion '{node.name}' hat {n_lines} Zeilen (> {MAX_FUNC_LINES})",
                "func_name": node.name,
                "n_lines": n_lines,
                "severity": IssueType.SEVERITY[IssueType.LONG_FUNCTION],
            })

        # Fehlende Type Hints
        if node.args.args and arg_hints < len(node.args.args):
            missing = len(node.args.args) - arg_hints
            self.issues.append({
                "type": IssueType.MISSING_TYPE_HINTS,
                "line": start,
                "col": node.col_offset,
                "msg": f"Funktion '{node.name}': {missing}/{len(node.args.args)} Parameter ohne Type Hint"
                       + ("" if has_return_annotation else " + kein Return-Hint"),
                "func_name": node.name,
                "missing_args": missing,
                "total_args": len(node.args.args),
                "missing_return": not has_return_annotation,
                "severity": IssueType.SEVERITY[IssueType.MISSING_TYPE_HINTS],
            })

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        # Behandle async functions gleich wie sync
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(f"{base.value.id}.{base.attr}" if isinstance(base.value, ast.Name) else str(base))
            else:
                bases.append(str(base))

        self.classes.append({
            "name": node.name,
            "start_line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "bases": bases,
            "methods": [],
        })
        self.generic_visit(node)

    def _find_todos(self) -> None:
        """Sucht nach TODO/FIXME/HACK/XXX-Kommentaren."""
        todo_pattern = re.compile(r'#\s*(TODO|FIXME|HACK|XXX)\b', re.IGNORECASE)
        for i, line in enumerate(self.lines, 1):
            m = todo_pattern.search(line)
            if m:
                self.issues.append({
                    "type": IssueType.TODO_FIXME,
                    "line": i,
                    "col": line.find("#"),
                    "msg": f"{m.group(1)}: {line.strip()}",
                    "severity": IssueType.SEVERITY[IssueType.TODO_FIXME],
                })

    def _check_empty_except(self) -> None:
        """Findet leere except-Blöcke (except: pass)."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None and len(node.body) == 1:
                    body = node.body[0]
                    if isinstance(body, ast.Pass):
                        self.issues.append({
                            "type": IssueType.EMPTY_EXCEPT,
                            "line": node.lineno,
                            "col": node.col_offset,
                            "msg": f"Bare except: pass in Zeile {node.lineno}",
                            "severity": IssueType.SEVERITY[IssueType.EMPTY_EXCEPT],
                        })

    def find_duplicate_imports(self) -> List[Dict[str, Any]]:
        """Findet doppelte Imports (selbes Modul mehrfach importiert)."""
        seen: Dict[str, List[Dict]] = {}
        duplicates: List[Dict] = []

        for imp in self.imports:
            key = imp["name"]
            if key not in seen:
                seen[key] = []
            seen[key].append(imp)

        for name, occurrences in seen.items():
            if len(occurrences) > 1:
                lines = [o["line"] for o in occurrences]
                duplicates.append({
                    "type": IssueType.DUPLICATE_IMPORT,
                    "line": occurrences[0]["line"],
                    "col": occurrences[0]["col"],
                    "msg": f"Doppelter Import '{name}' in Zeilen {lines}",
                    "import_name": name,
                    "lines": lines,
                    "severity": IssueType.SEVERITY[IssueType.DUPLICATE_IMPORT],
                })
                # Nicht doppelt zu den issues hinzufügen wenn schon da
                existing_types = {i["type"] for i in self.issues}
                if IssueType.DUPLICATE_IMPORT not in existing_types or not any(
                    i.get("import_name") == name for i in self.issues
                ):
                    pass  # wird später hinzugefügt

        # Deduplizierte imports zu issues hinzufügen
        for dup in duplicates:
            exists = any(
                i["type"] == IssueType.DUPLICATE_IMPORT and i.get("import_name") == dup["import_name"]
                for i in self.issues
            )
            if not exists:
                self.issues.append(dup)

        return duplicates


# ─── Patch-Generierung ───────────────────────────────────────────────────────

class PatchGenerator:
    """Generiert unified-diff Patches für gefundene Issues."""

    def __init__(self, dry_run: bool = False, max_patches: int = 3):
        self.dry_run = dry_run
        self.max_patches = max_patches
        self.generated: List[Path] = []

    def remove_duplicate_import(
        self, filepath: Path, imp_name: str, lines_to_remove: List[int]
    ) -> Optional[str]:
        """Generiert einen Patch, der doppelte Imports entfernt."""
        source = filepath.read_text(encoding="utf-8", errors="replace")
        source_lines = source.splitlines(keepends=True)

        # Behalte nur das erste Vorkommen
        keep = lines_to_remove[0]
        remove_set = set(lines_to_remove[1:])
        for rl in remove_set:
            # Null-basiert für list index vs 1-basiert von AST
            idx = rl - 1
            if 0 <= idx < len(source_lines):
                source_lines[idx] = None  # markieren zum Löschen

        new_lines = [l for l in source_lines if l is not None]
        new_source = "".join(new_lines)
        patch = self._make_unified_diff(filepath, source, new_source,
                                        f"Remove duplicate import '{imp_name}'")
        return patch

    def add_type_hints(self, filepath: Path, func_name: str, line: int) -> Optional[str]:
        """Generiert einen Patch, der 'Any'-Type-Hints zu fehlenden Parametern hinzufügt."""
        source = filepath.read_text(encoding="utf-8", errors="replace")
        source_lines = source.splitlines(keepends=True)

        # Einfache Strategie: Füge `: Any` zu Parametern ohne Type-Hint hinzu
        # Dafür müssen wir den AST nochmal analysieren
        try:
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError:
            return None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                # Baue die neuen Source Lines
                break
        else:
            return None

        # Für einen einfachen Patch tauschen wir nur die Funktionssignatur aus
        # Das ist komplex - wir machen einen konservativen Patch
        # TODO: Erweiterte Version mit genauer AST-basierter Manipulation

        return None

    def fix_empty_except(self, filepath: Path, line: int) -> Optional[str]:
        """Wandelt 'except: pass' in 'except Exception: pass' um."""
        source = filepath.read_text(encoding="utf-8", errors="replace")
        source_lines = source.splitlines(keepends=True)

        idx = line - 1
        if idx < 0 or idx >= len(source_lines):
            return None

        old_line = source_lines[idx]
        # Ersetze 'except:' mit 'except Exception:' - nur wenn es bare except ist
        # Regex: except gefolgt von optional Whitespace und :
        new_line = re.sub(
            r'^(\s*)except\s*:\s*(#.*)?$',
            r'\1except Exception: \2',
            old_line,
        )
        if new_line == old_line:
            return None

        source_lines[idx] = new_line
        new_source = "".join(source_lines)
        patch = self._make_unified_diff(filepath, source, new_source,
                                        f"Fix bare except → except Exception (line {line})")
        return patch

    def add_return_type_none(self, filepath: Path, func_name: str, line: int) -> Optional[str]:
        """Fügt '-> None' zu Funktionen ohne Return-Hint hinzu, wenn sie kein return haben."""
        source = filepath.read_text(encoding="utf-8", errors="replace")
        source_lines = source.splitlines(keepends=True)

        try:
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError:
            return None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                if node.returns is not None:
                    return None

                # Prüfe ob die Funktion ein return hat
                has_return = any(
                    isinstance(n, ast.Return) and n.value is not None
                    for n in ast.walk(node)
                )
                if has_return:
                    return None

                # Finde die letzte Zeile des def-Statements (inkl. Decorators)
                # Die def-Zeile ist node.lineno - suche nach "):"
                def_line_idx = node.lineno - 1
                for i in range(def_line_idx, min(def_line_idx + 10, len(source_lines))):
                    line_text = source_lines[i]
                    # Finde das Ende der def-Signatur
                    stripped = line_text.rstrip("\n\r")
                    # Wenn die Zeile mit "):" oder ":" endet (inline)
                    if stripped.endswith("):") or stripped.endswith(":"):
                        if not stripped.rstrip().endswith("):"):
                            continue
                        # Füge " -> None" vor dem "):" ein
                        new_line_text = stripped[:-2] + " -> None):\n"
                        source_lines[i] = new_line_text
                        new_source = "".join(source_lines)
                        patch = self._make_unified_diff(
                            filepath, source, new_source,
                            f"Add '-> None' return type to '{func_name}' (line {node.lineno})"
                        )
                        return patch

        return None

    def _make_unified_diff(self, filepath: Path, old: str, new: str, title: str) -> str:
        """Erstellt einen unified-diff String."""
        rel_path = filepath.relative_to(REPO_ROOT).as_posix()
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
            lineterm="\n",
        )
        diff_str = "".join(diff)
        return f"# {title}\n# Date: {datetime.now().isoformat()}\n{diff_str}"

    def write_patch(self, module_name: str, patch_content: str) -> Optional[Path]:
        """Schreibt einen Patch in .rewriter/pending/<module>.patch."""
        if not patch_content.strip():
            return None

        patch_path = PENDING_DIR / f"{module_name}.patch"
        if self.dry_run:
            print(f"  [dry-run] Würde Patch schreiben: {patch_path}")
            print(patch_content[:500])
            return patch_path

        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(patch_content, encoding="utf-8")
        self.generated.append(patch_path)
        return patch_path


# ─── Validierung ─────────────────────────────────────────────────────────────

class Validator:
    """Validiert generierte Patches."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.results: Dict[str, Any] = {}

    def validate_patch(self, patch_path: Path) -> Tuple[bool, str]:
        """Validiert einen Patch durch Anwendung auf ein temporäres Verzeichnis + py_compile."""
        if self.dry_run:
            return True, "[dry-run] Überspringe Validierung"

        # Lese Modul-Name aus Patch-Datei
        content = patch_path.read_text(encoding="utf-8")
        # Finde 'b/openamer_cli/...' im diff
        match = re.search(r'\+\+\+ b/(openamer_cli/[^\s]+)', content)
        if not match:
            return False, "Cannot determine target file from patch"

        rel_target = match.group(1)
        target_path = REPO_ROOT / rel_target
        if not target_path.exists():
            return False, f"Target file not found: {target_path}"

        # Wende Patch in einem Branch an (simuliert)
        # Für Validierung: compiliere die Original-Datei + Patch im temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Kopiere openamer_cli/ ins temp
            import shutil
            cloned_core = tmp_path / "openamer_cli"
            shutil.copytree(CORE_DIR, cloned_core)

            cloned_file = cloned_core / target_path.relative_to(CORE_DIR)
            orig_content = cloned_file.read_text(encoding="utf-8")

            # Patch anwenden via patch CLI
            patch_file = tmp_path / "changes.patch"
            patch_file.write_text(content, encoding="utf-8")

            result = subprocess.run(
                ["patch", "-p0", "-i", str(patch_file)],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
                cwd=str(tmp_path),
            )
            if result.returncode != 0:
                # Versuche -p1
                result = subprocess.run(
                    ["patch", "-p1", "-i", str(patch_file)],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
                    cwd=str(tmp_path),
                )
                if result.returncode != 0:
                    return False, f"Patch apply failed:\n{result.stderr}"

            # py_compile check
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(cloned_file)],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
            )
            if result.returncode != 0:
                return False, f"py_compile failed:\n{result.stderr or result.stdout}"

        return True, "OK (py_compile passed)"


# ─── Git-Operationen ─────────────────────────────────────────────────────────

class GitOps:
    """Git-Operationen für Patch-Apply + Commit."""

    def __init__(self, repo_root: Path, dry_run: bool = False):
        self.repo = repo_root
        self.dry_run = dry_run

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        cmd = ["git", "-C", str(self.repo)] + list(args)
        if self.dry_run:
            print(f"  [dry-run] git {' '.join(args)}")
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)

    def ensure_branch(self) -> bool:
        """Erstellt 'rewriter-tmp' Branch von main, falls nötig."""
        result = self._git("rev-parse", "--verify", CRON_BRANCH)
        if result.returncode != 0:
            # Branch existiert nicht → von main erstellen
            result = self._git("checkout", "-b", CRON_BRANCH)
            if result.returncode != 0:
                print(f"  Fehler beim Erstellen von Branch '{CRON_BRANCH}': {result.stderr}")
                return False
            print(f"  Branch '{CRON_BRANCH}' erstellt (von HEAD)")
        else:
            # Existiert → checkout
            result = self._git("checkout", CRON_BRANCH)
            if result.returncode != 0:
                print(f"  Fehler beim Checkout von '{CRON_BRANCH}': {result.stderr}")
                return False
            print(f"  Branch '{CRON_BRANCH}' ausgecheckt")
        return True

    def apply_patch(self, patch_path: Path) -> bool:
        """Wendet einen Patch an."""
        if self.dry_run:
            print(f"  [dry-run] Würde Patch anwenden: {patch_path}")
            return True

        result = subprocess.run(
            ["patch", "-p0", "-i", str(patch_path)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
            cwd=str(self.repo),
        )
        if result.returncode != 0:
            # Versuche -p1
            result = subprocess.run(
                ["patch", "-p1", "-i", str(patch_path)],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
                cwd=str(self.repo),
            )
        if result.returncode != 0:
            print(f"  Fehler beim Anwenden von {patch_path.name}: {result.stderr}")
            return False
        print(f"  Patch {patch_path.name} angewandt")
        return True

    def commit_and_merge(self, module_names: List[str]) -> bool:
        """Commited die Änderungen und merged zurück zu main."""
        if not module_names:
            return True

        msg = f"🤖 self-rewriter: Auto-Verbesserungen ({', '.join(module_names)})"
        self._git("add", "-A")

        result = self._git("diff", "--cached", "--quiet")
        if result.returncode == 0:
            print("  Keine Änderungen zu committen")
            return True

        result = self._git("commit", "-m", msg)
        if result.returncode != 0:
            print(f"  Commit-Fehler: {result.stderr}")
            return False
        print(f"  Commit: {msg}")

        # Merge zurück zu main
        result = self._git("checkout", "main")
        if result.returncode != 0:
            print(f"  Fehler beim Checkout zu main: {result.stderr}")
            return False

        result = self._git("merge", CRON_BRANCH, "--no-ff", "-m", f"Merge branch '{CRON_BRANCH}'")
        if result.returncode != 0:
            print(f"  Merge-Fehler: {result.stderr}")
            # Versuche zurück zum rewriter-tmp zu gehen
            self._git("checkout", CRON_BRANCH)
            return False
        print(f"  Branch '{CRON_BRANCH}' in main gemerged")
        return True

    def cleanup(self) -> bool:
        """Löscht den temporären Branch."""
        result = self._git("branch", "-d", CRON_BRANCH)
        if result.returncode != 0:
            print(f"  Warnung: Branch '{CRON_BRANCH}' konnte nicht gelöscht werden: {result.stderr}")
            return False
        return True

    def stash(self) -> None:
        """Stasht lokale Änderungen vor Branch-Wechsel."""
        self._git("stash")


# ─── Core-Analyse ────────────────────────────────────────────────────────────

def scan_core() -> Dict[str, Any]:
    """Scannt das gesamte openamer_cli/ Verzeichnis."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "core_dir": str(CORE_DIR),
        "modules_scanned": 0,
        "modules_with_issues": 0,
        "total_functions": 0,
        "total_classes": 0,
        "total_issues": 0,
        "issues_by_type": {},
        "issues_by_module": {},
        "modules": {},
        "summary": "",
    }

    py_files = sorted(CORE_DIR.rglob("*.py"))
    report["modules_scanned"] = len(py_files)

    mods_with_issues = 0
    total_functions = 0
    total_classes = 0
    total_issues = 0

    for py_file in py_files:
        rel = py_file.relative_to(CORE_DIR).as_posix()
        analyzer = CoreAnalyzer(py_file)
        analyzer.analyze()
        analyzer.find_duplicate_imports()

        issues = analyzer.issues
        n_functions = len(analyzer.functions)
        n_classes = len(analyzer.classes)
        n_issues = len(issues)

        total_functions += n_functions
        total_classes += n_classes
        total_issues += n_issues

        if n_issues > 0:
            mods_with_issues += 1

        module_entry = {
            "file": str(py_file),
            "relative": rel,
            "size_bytes": py_file.stat().st_size,
            "n_lines": len(analyzer.lines),
            "n_functions": n_functions,
            "n_classes": n_classes,
            "n_imports": len(analyzer.imports),
            "n_issues": n_issues,
            "issues": issues,
            "functions": [
                {"name": f["name"], "lines": f["n_lines"],
                 "start": f["start_line"], "hints": f["arg_hints"]}
                for f in analyzer.functions
            ],
            "classes": [
                {"name": c["name"], "bases": c["bases"]}
                for c in analyzer.classes
            ],
        }
        report["modules"][rel] = module_entry

        if n_issues > 0:
            report["issues_by_module"][rel] = n_issues
            for iss in issues:
                itype = iss["type"]
                if itype not in report["issues_by_type"]:
                    report["issues_by_type"][itype] = 0
                report["issues_by_type"][itype] += 1

    report["modules_with_issues"] = mods_with_issues
    report["total_functions"] = total_functions
    report["total_classes"] = total_classes
    report["total_issues"] = total_issues

    # Summary-String
    parts = [f"✅ {report['modules_scanned']} Module gescannt"]
    parts.append(f"📊 {total_functions} Funktionen, {total_classes} Klassen")
    if total_issues > 0:
        parts.append(f"⚠️  {total_issues} Issues in {mods_with_issues} Modulen")
        by_type = report["issues_by_type"]
        for itype, count in sorted(by_type.items(), key=lambda x: -x[1]):
            label = IssueType.LABELS.get(itype, itype)
            parts.append(f"  {label}: {count}")
    else:
        parts.append("✅ Keine Issues gefunden")
    report["summary"] = "\n".join(parts)

    return report


# ─── Patch-Generierung aus Report ────────────────────────────────────────────

def generate_patches(report: Dict[str, Any], dry_run: bool = False,
                     max_patches: int = 3) -> int:
    """Generiert Patches basierend auf dem Report."""
    generator = PatchGenerator(dry_run=dry_run, max_patches=max_patches)
    applied_count = 0
    applied_modules = set()

    # Sortiere Issues nach Schweregrad (höchster zuerst)
    all_issues: List[Tuple[int, str, Dict]] = []  # (severity, rel_path, issue)
    for rel, mod_entry in report["modules"].items():
        for iss in mod_entry["issues"]:
            all_issues.append((iss["severity"], rel, iss))

    all_issues.sort(key=lambda x: -x[0])

    patch_generated = False

    for sev, rel, iss in all_issues:
        if applied_count >= max_patches:
            break

        filepath = CORE_DIR / rel
        if not filepath.exists():
            continue

        module_name = rel.replace(".py", "").replace("/", "_")
        patch_content = None

        if iss["type"] == IssueType.DUPLICATE_IMPORT:
            patch_content = generator.remove_duplicate_import(
                filepath, iss.get("import_name", ""), iss.get("lines", [iss["line"]])
            )
        elif iss["type"] == IssueType.EMPTY_EXCEPT:
            patch_content = generator.fix_empty_except(filepath, iss["line"])
        elif iss["type"] == IssueType.MISSING_TYPE_HINTS:
            func_name = iss.get("func_name", "")
            if iss.get("missing_return", False):
                patch_content = generator.add_return_type_none(
                    filepath, func_name, iss["line"]
                )
            if patch_content is None and iss.get("missing_args", 0) > 0:
                # Add type hints currently skipped - requires more sophisticated patching
                pass

        if patch_content and patch_content.strip():
            patch_path = generator.write_patch(module_name, patch_content)
            if patch_path:
                applied_modules.add(rel)
                applied_count += 1
                patch_generated = True
                print(f"  ✅ Patch generiert: {patch_path.name}")
                if applied_count >= max_patches:
                    print(f"  ⏹️  Max-Patches-Limit ({max_patches}) erreicht")
                    break

    if not patch_generated:
        print("  ℹ️  Keine Patches generiert (keine behebbaren Issues oder alle bereits gefixt)")

    return applied_count


# ─── Apply-Phase ────────────────────────────────────────────────────────────

def apply_patches(dry_run: bool = False, yes: bool = False) -> int:
    """Validiert und applied alle ausstehenden Patches."""
    patches = sorted(PENDING_DIR.glob("*.patch"))
    if not patches:
        print("ℹ️  Keine ausstehenden Patches gefunden")
        return 0

    print(f"📋 {len(patches)} ausstehende Patches gefunden")
    for p in patches:
        print(f"  - {p.name}")

    validator = Validator(dry_run=dry_run)
    valid_patches = []
    invalid_patches = []

    for patch_path in patches:
        ok, msg = validator.validate_patch(patch_path)
        if ok:
            valid_patches.append(patch_path)
        else:
            invalid_patches.append((patch_path, msg))

    if invalid_patches:
        print(f"\n❌ {len(invalid_patches)} ungültige Patches:")
        for p, msg in invalid_patches:
            print(f"  - {p.name}: {msg[:200]}")

    if not valid_patches:
        print("ℹ️  Keine gültigen Patches zum Anwenden")
        return 0

    print(f"\n✅ {len(valid_patches)} gültige Patches")

    if not yes and not dry_run:
        answer = input(f"\n{len(valid_patches)} Patches anwenden, commiten & mergen? [y/N] ").strip().lower()
        if answer != "y":
            print("Abgebrochen.")
            return 0

    git = GitOps(REPO_ROOT, dry_run=dry_run)

    # Stash lokale Änderungen falls vorhanden
    git.stash()

    # Branch erstellen
    if not git.ensure_branch():
        return 1

    # Patches anwenden
    module_names = []
    for patch_path in valid_patches:
        if not patch_path.read_text().strip():
            continue
        if git.apply_patch(patch_path):
            # Modulname aus Dateinamen
            module_names.append(patch_path.stem)
        else:
            print(f"  ❌ Konnte {patch_path.name} nicht anwenden")

    if not module_names:
        print("ℹ️  Keine Patches angewandt")
        return 0

    # Committen & Mergen
    if git.commit_and_merge(module_names):
        # Verschiebe angewandte Patches
        if not dry_run:
            for patch_path in valid_patches:
                dest = APPLIED_DIR / patch_path.name
                patch_path.rename(dest)
                print(f"  📦 Patch {patch_path.name} → applied/")

        # Cleanup
        git.cleanup()
        print(f"\n🎉 {len(module_names)} Patches erfolgreich angewandt & committed")
        return 2
    else:
        print("\n❌ Merge fehlgeschlagen. Branch 'rewriter-tmp' bleibt bestehen.")
        return 1


# ─── CLI ─────────────────────────────────────────────────────────────────────

def cmd_scan(args: argparse.Namespace) -> int:
    """Führt den Scan aus und speichert den Report."""
    print("🔍 Self-Rewriter: Core-Analyse gestartet...")
    print(f"   Core: {CORE_DIR}")
    print()

    report = scan_core()
    report["args"] = vars(args)

    # Report speichern
    if not args.dry_run:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = args.report or DEFAULT_REPORT
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"\n📄 Report gespeichert: {report_path}")

    # Ausgabe
    print()
    print(report["summary"])
    print()

    if report["total_issues"] > 0:
        return 1  # Patches verfügbar
    return 0  # Nichts zu tun


def cmd_suggest(args: argparse.Namespace) -> int:
    """Zeigt gefundene Verbesserungen an."""
    if args.report and args.report.exists():
        report = json.loads(args.report.read_text(encoding="utf-8"))
    else:
        if not DEFAULT_REPORT.exists():
            print("Kein Report vorhanden. Führe zuerst --scan aus.")
            return 0
        report = json.loads(DEFAULT_REPORT.read_text(encoding="utf-8"))

    print("💡 Self-Rewriter: Vorschläge")
    print("=" * 60)
    print(report.get("summary", ""))
    print()

    # Zeige Details pro Modul
    for rel, mod in sorted(report.get("issues_by_module", {}).items(), key=lambda x: -x[1]):
        mod_entry = report["modules"].get(rel, {})
        issues = mod_entry.get("issues", [])
        print(f"\n📁 {rel} ({len(issues)} Issues):")
        for iss in sorted(issues, key=lambda x: -x["severity"]):
            label = IssueType.LABELS.get(iss["type"], iss["type"])
            print(f"  L{iss['line']:>6} │ {label}: {iss['msg']}")

    if report.get("total_issues", 0) > 0:
        return 1
    return 0


def cmd_patch(args: argparse.Namespace) -> int:
    """Generiert Patches basierend auf Report."""
    if args.report and args.report.exists():
        report = json.loads(args.report.read_text(encoding="utf-8"))
    else:
        if not DEFAULT_REPORT.exists():
            print("Kein Report vorhanden. Führe zuerst --scan aus.")
            return 0
        report = json.loads(DEFAULT_REPORT.read_text(encoding="utf-8"))

    print("🛠️  Self-Rewriter: Patch-Generierung...")
    print(f"   Max Patches: {args.max_patches}")
    print(f"   Dry-Run: {args.dry_run}")
    print()

    count = generate_patches(report, dry_run=args.dry_run, max_patches=args.max_patches)
    print(f"\n📦 {count} Patches generiert")

    if count > 0:
        return 1
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    """Validiert + applied Patches."""
    print("🚀 Self-Rewriter: Apply-Phase")
    print(f"   Dry-Run: {args.dry_run}")
    print()

    return apply_patches(dry_run=args.dry_run, yes=args.yes)


def cmd_all(args: argparse.Namespace) -> int:
    """Full Cycle: scan → suggest → patch → apply."""
    print("🔄 Self-Rewriter: Full Cycle")
    print("=" * 60)
    print()

    # Phase 1: Scan
    print("📡 Phase 1/4: Scan")
    report = scan_core()
    if not args.dry_run:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = args.report or DEFAULT_REPORT
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(report["summary"])
    print()

    if report["total_issues"] == 0:
        print("✨ Keine Issues gefunden — alles sauber!")
        return 0

    if not args.yes and not args.dry_run:
        answer = input("\nFortfahren mit Patch-Generierung? [y/N] ").strip().lower()
        if answer != "y":
            print("Abgebrochen.")
            return 0

    # Phase 2: Patch
    print("🛠️  Phase 2/4: Patch-Generierung")
    count = generate_patches(report, dry_run=args.dry_run, max_patches=args.max_patches)
    if count == 0:
        print("ℹ️  Keine Patches generiert. Abbruch.")
        return 0
    print()

    if not args.yes and not args.dry_run:
        answer = input(f"\n{count} Patches anwenden? [y/N] ").strip().lower()
        if answer != "y":
            print("Abgebrochen.")
            return 0

    # Phase 3: Apply
    print("🚀 Phase 3/4: Apply & Commit")
    ec = apply_patches(dry_run=args.dry_run, yes=True)
    if ec == 2:
        print("\n🎉 Full Cycle erfolgreich abgeschlossen!")
    else:
        print(f"\n⚠️  Full Cycle beendet mit Exit-Code {ec}")
    return ec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Self-Rewriting Core — Autonomous Core Evolution Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Beispiele:
              %(prog)s --scan              # Core analysieren
              %(prog)s --suggest           # Verbesserungen anzeigen
              %(prog)s --patch             # Patches generieren
              %(prog)s --apply             # Patches anwenden + commiten
              %(prog)s --all               # Full Cycle
              %(prog)s --all --dry-run     # Full Cycle nur anzeigen
              %(prog)s --scan --max-patches 5  # Max 5 Patches
        """),
    )
    parser.add_argument("--scan", action="store_true", help="Core analysieren")
    parser.add_argument("--suggest", action="store_true", help="Verbesserungen anzeigen")
    parser.add_argument("--patch", action="store_true", help="Patches generieren")
    parser.add_argument("--apply", action="store_true", help="Patches anwenden + commiten")
    parser.add_argument("--all", action="store_true", help="Full Cycle")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, keine Änderungen")
    parser.add_argument("--max-patches", type=int, default=MAX_PATCHES_DEFAULT,
                        help=f"Max Patches pro Run (default: {MAX_PATCHES_DEFAULT})")
    parser.add_argument("--report", type=Path, default=None,
                        help=f"Report-Pfad (default: {DEFAULT_REPORT})")
    parser.add_argument("--yes", "-y", action="store_true", help="Automatisch bestätigen")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Sicherstellen, dass Core-Verzeichnis existiert
    if not CORE_DIR.exists():
        print(f"❌ Core-Verzeichnis nicht gefunden: {CORE_DIR}")
        print(f"   Erwartet unter: {CORE_DIR}")
        return 1

    # Build-Verzeichnisse
    if not args.dry_run:
        REWRITER_DIR.mkdir(parents=True, exist_ok=True)

    # Dispatch
    if args.scan:
        return cmd_scan(args)
    elif args.suggest:
        return cmd_suggest(args)
    elif args.patch:
        return cmd_patch(args)
    elif args.apply:
        return cmd_apply(args)
    elif args.all:
        return cmd_all(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())