"""RepoMap — scan a git repo and build a structured map of the codebase.

Provides:
  - ``RepoMap`` class that orchestrates scanning, parsing, and ranking.
  - ``build_repo_map()`` — scan a repo and return: files, languages,
    key classes/functions, and dependency hints.
  - ``get_repo_context()`` — produce a human-readable text summary of
    the repo relevant to a specific file.
  - ``rank_files_by_relevance()`` — rank files by simple keyword
    matching against a query.

Zero external dependencies — uses only Python stdlib, ``git ls-files``,
and naive lexing to extract identifiers.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────────────────────────────────────
#  Language detection
# ──────────────────────────────────────────────────────────────────────────────

# Patterns are (single-line-comment, multi-line-start, multi-line-end, class-keywords, function-keywords)
_LANGUAGE_RULES: dict[str, tuple[str | None, str | None, str | None, list[str], list[str]]] = {
    ".py": ("#", None, None, ["class "], ["def ", "async def "]),
    ".js": ("//", "/*", "*/", ["class "], ["function ", "async function ", "const "]),
    ".ts": ("//", "/*", "*/", ["class ", "interface ", "enum "], ["function ", "const ", "type "]),
    ".jsx": ("//", "/*", "*/", ["class "], ["function ", "const "]),
    ".tsx": ("//", "/*", "*/", ["class ", "interface ", "enum "], ["function ", "const ", "type "]),
    ".kt": ("//", "/*", "*/", ["class ", "interface ", "object ", "enum class "], ["fun "]),
    ".kts": ("//", "/*", "*/", ["class ", "interface ", "object "], ["fun "]),
    ".java": ("//", "/*", "*/", ["class ", "interface ", "enum ", "@interface "], ["void ", "int ", "String ", "boolean ", "long ", "double ", "float "]),
    ".go": ("//", "/*", "*/", ["struct ", "interface "], ["func ", "type "]),
    ".rs": ("//", "/*", "*/", ["struct ", "enum ", "trait "], ["fn ", "mod ", "impl "]),
    ".rb": ("#", None, None, ["class ", "module "], ["def "]),
    ".swift": ("//", "/*", "*/", ["class ", "struct ", "enum ", "protocol ", "extension "], ["func "]),
    ".c": ("//", "/*", "*/", ["struct "], ["int ", "void ", "char ", "static ", "const ", "unsigned "]),
    ".h": ("//", "/*", "*/", ["struct "], ["int ", "void ", "char ", "static ", "const ", "unsigned "]),
    ".cpp": ("//", "/*", "*/", ["class ", "struct "], ["int ", "void ", "char ", "auto ", "template ", "const ", "unsigned "]),
    ".hpp": ("//", "/*", "*/", ["class ", "struct "], ["int ", "void ", "char ", "auto ", "template ", "const "]),
    ".cs": ("//", "/*", "*/", ["class ", "struct ", "interface ", "enum "], ["void ", "int ", "string ", "bool ", "public ", "private ", "protected ", "static "]),
    ".sh": ("#", None, None, [], ["function "]),
    ".bash": ("#", None, None, [], ["function "]),
    ".yaml": ("#", None, None, [], []),
    ".yml": ("#", None, None, [], []),
    ".toml": ("#", None, None, [], []),
    ".json": (None, None, None, [], []),
    ".md": (None, None, None, [], []),
    ".sql": ("--", None, None, [], ["CREATE ", "ALTER ", "SELECT ", "INSERT ", "UPDATE ", "DELETE ", "DROP "]),
    ".dockerfile": ("#", None, None, [], ["FROM ", "RUN ", "CMD ", "ENTRYPOINT "]),
    ".tf": ("#", None, None, [], ["resource ", "data ", "variable ", "output ", "module "]),
}


def _detect_language(file_path: str) -> str:
    """Return a human-readable language name for *file_path*."""
    ext = Path(file_path).suffix.lower()
    rules = _LANGUAGE_RULES.get(ext)
    if rules is not None:
        return {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".jsx": "JSX", ".tsx": "TSX", ".kt": "Kotlin", ".kts": "Kotlin Script",
            ".java": "Java", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
            ".swift": "Swift", ".c": "C", ".h": "C Header", ".cpp": "C++",
            ".hpp": "C++ Header", ".cs": "C#", ".sh": "Shell", ".bash": "Bash",
            ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".json": "JSON",
            ".md": "Markdown", ".sql": "SQL", ".dockerfile": "Dockerfile",
            ".tf": "Terraform",
        }.get(ext, ext.lstrip(".").title())
    # Fallback: try to guess from shebang
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            first = fh.readline().strip()
        if first.startswith("#!"):
            if "python" in first:
                return "Python"
            if "bash" in first or "sh" in first:
                return "Shell"
            if "node" in first:
                return "JavaScript"
            if "ruby" in first or "jruby" in first:
                return "Ruby"
        return ext.lstrip(".").title() if ext else "Unknown"
    except Exception:
        return ext.lstrip(".").title() if ext else "Unknown"


# ──────────────────────────────────────────────────────────────────────────────
#  Lexer — extract identifiers (classes, functions, imports)
# ──────────────────────────────────────────────────────────────────────────────


def _extract_identifiers(file_path: str, content: str | None = None) -> dict[str, list[str]]:
    """Extract class names, function names, and import lines from *file_path*.

    Returns ``{"classes": [...], "functions": [...], "imports": [...]}``.
    """
    if content is None:
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return {"classes": [], "functions": [], "imports": []}

    ext = Path(file_path).suffix.lower()
    rules = _LANGUAGE_RULES.get(ext)
    if rules is None:
        return {"classes": [], "functions": [], "imports": []}

    single_comment, multi_start, multi_end, class_keywords, function_keywords = rules

    lines = content.split("\n")
    filtered: list[str] = []
    in_multi = False

    for line in lines:
        st = line.strip()
        # Strip multi-line comments
        if multi_start and multi_end:
            if in_multi:
                idx = st.find(multi_end)
                if idx >= 0:
                    st = st[idx + len(multi_end) :]
                    in_multi = False
                else:
                    continue
            idx = st.find(multi_start)
            if idx >= 0:
                # Check if it spans the whole line or has code before
                before = st[:idx].strip()
                if not before:
                    # Whole line is start of block comment
                    rest = st[idx + len(multi_start) :]
                    if multi_end in rest:
                        # Inline block comment that closes on same line
                        st = before + rest[rest.index(multi_end) + len(multi_end) :]
                    else:
                        in_multi = True
                        continue
                else:
                    # Code before a block comment, strip the comment part
                    st = before
        # Strip single-line comments
        if single_comment is not None:
            idx = st.find(single_comment)
            if idx >= 0:
                st = st[:idx].strip()
        filtered.append(st)

    classes: list[str] = []
    functions: list[str] = []
    imports: list[str] = []

    for line in filtered:
        if not line:
            continue

        # Heuristic: lines ending with ; or : (typical definition markers)
        if ext == ".py":
            # Import detection (Python)
            if line.startswith("import ") or line.startswith("from "):
                imports.append(line)
                continue
        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            if line.startswith("import ") or line.startswith("const ") and "require(" in line:
                imports.append(line)
                continue
        elif ext in (".kt", ".kts"):
            if line.startswith("import "):
                imports.append(line)
                continue
        elif ext == ".java":
            if line.startswith("import "):
                imports.append(line)
                continue

        # Class / function / definition detection
        # Check class keywords first (more specific), then function keywords
        matched = False
        for kw in class_keywords:
            if kw in line:
                after_kw = line[line.index(kw) + len(kw):].strip()
                name_match = re.match(r"([A-Za-z_]\w*)", after_kw)
                if name_match:
                    name = name_match.group(1)
                    if name not in ("self", "cls", "this", "super"):
                        classes.append(name)
                matched = True
                break
        if matched:
            continue

        for kw in function_keywords:
            if kw in line:
                after_kw = line[line.index(kw) + len(kw):].strip()
                name_match = re.match(r"([A-Za-z_]\w*)", after_kw)
                if name_match:
                    name = name_match.group(1)
                    if name not in ("self", "cls", "this", "super"):
                        functions.append(name)
                break

    return {
        "classes": classes,
        "functions": functions,
        "imports": imports,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  RepoMap class
# ──────────────────────────────────────────────────────────────────────────────


class RepoMap:
    """Scans a git repository and builds a structured map of the codebase.

    Uses ``git ls-files`` to enumerate tracked files, then applies
    language-aware parsing to extract identifiers and structure.

    Parameters
    ----------
    repo_path:
        Root of the git repository to scan.
    exclude_dirs:
        Directory names to skip (e.g. ``{"node_modules", ".git", "__pycache__"}``).
    """

    def __init__(
        self,
        repo_path: str,
        exclude_dirs: set[str] | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.exclude_dirs = exclude_dirs or {
            "node_modules", ".git", "__pycache__", ".venv", "venv",
            ".tox", "dist", "build", ".idea", ".vscode", ".mypy_cache",
            ".pytest_cache", ".ruff_cache", ".eggs", "eggs",
        }

        if not self.repo_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {repo_path}")

    # ── public API ──────────────────────────────────────────────────────

    def build_map(self) -> dict[str, Any]:
        """Scan the repo and return the full repo map.

        Returns
        -------
        dict with keys:
          - ``repo_path`` — absolute path
          - ``files`` — list of file paths (relative to repo root)
          - ``languages`` — ``{language_name: file_count}``
          - ``classes_by_file`` — ``{file_path: [class_name, ...]}``
          - ``functions_by_file`` — ``{file_path: [function_name, ...]}``
          - ``imports_by_file`` — ``{file_path: [import_line, ...]}``
          - ``identifiers`` — flat list of all extracted identifiers
          - ``file_count`` — total tracked file count
          - ``total_classes``
          - ``total_functions``
        """
        files = self._get_tracked_files()
        lang_counter: Counter[str] = Counter()
        classes_by_file: dict[str, list[str]] = {}
        functions_by_file: dict[str, list[str]] = {}
        imports_by_file: dict[str, list[str]] = {}
        all_ids: list[str] = []

        for rel_path in files:
            full_path = self.repo_path / rel_path
            ext = Path(rel_path).suffix.lower()
            lang = _detect_language(str(full_path))
            lang_counter[lang] += 1

            ids = _extract_identifiers(str(full_path))
            if ids["classes"]:
                classes_by_file[rel_path] = ids["classes"]
                all_ids.extend(ids["classes"])
            if ids["functions"]:
                functions_by_file[rel_path] = ids["functions"]
                all_ids.extend(ids["functions"])
            if ids["imports"]:
                imports_by_file[rel_path] = ids["imports"]

        return {
            "repo_path": str(self.repo_path),
            "files": files,
            "languages": dict(lang_counter),
            "classes_by_file": classes_by_file,
            "functions_by_file": functions_by_file,
            "imports_by_file": imports_by_file,
            "identifiers": all_ids,
            "file_count": len(files),
            "total_classes": sum(len(v) for v in classes_by_file.values()),
            "total_functions": sum(len(v) for v in functions_by_file.values()),
        }

    def get_context(self, file_path: str = "") -> str:
        """Return a human-readable text summary of the repo structure.

        When *file_path* is given (relative to repo root), the summary
        focuses on files in the same directory and its immediate neighbours,
        as well as files that share identifiers with the target file.
        """
        repo_map = self.build_map()

        lines: list[str] = []
        lines.append(f"# Repo: {self.repo_path.name}")
        lines.append(f"  Path: {self.repo_path}")
        lines.append(f"  Files: {repo_map['file_count']}")
        lines.append(f"  Languages: {repo_map['languages']}")
        lines.append("")

        if file_path:
            target = Path(file_path)
            parent_dir = str(target.parent) if target.parent != "." else ""
            lines.append(f"## Focus: {file_path}")

            # Files in the same directory
            same_dir = sorted(
                f for f in repo_map["files"]
                if Path(f).parent == target.parent and f != file_path
            )
            if same_dir:
                lines.append(f"\n### Sibling files ({len(same_dir)}):")
                for f in same_dir:
                    lines.append(f"  - {f}")
                    if f in repo_map["classes_by_file"]:
                        cls = repo_map["classes_by_file"][f]
                        lines.append(f"      classes: {', '.join(cls)}")
                    if f in repo_map["functions_by_file"]:
                        funcs = repo_map["functions_by_file"][f]
                        lines.append(f"      functions: {', '.join(funcs)}")
            else:
                lines.append("\n  (no sibling files)")

            # Find related files (share identifiers)
            target_classes = set(repo_map["classes_by_file"].get(file_path, []))
            target_funcs = set(repo_map["functions_by_file"].get(file_path, []))
            related: list[str] = []
            for f, cls_list in repo_map["classes_by_file"].items():
                if f != file_path and (target_classes & set(cls_list) or target_funcs & set(cls_list)):
                    related.append(f)

            if related:
                lines.append(f"\n### Related files ({len(related)}):")
                for f in sorted(related):
                    lines.append(f"  - {f}")

            lines.append("")
        else:
            # Show top-level dirs
            dirs: defaultdict[str, int] = defaultdict(int)
            for f in repo_map["files"]:
                parts = Path(f).parts
                if parts:
                    dirs[parts[0]] += 1
            lines.append("## Top-level directories:")
            for d, count in sorted(dirs.items(), key=lambda x: -x[1]):
                lines.append(f"  {d}/ — {count} files")

            lines.append("")

            # Show the busiest files by identifier count
            sorted_files = sorted(
                (f for f in repo_map["files"]
                 if f in repo_map["classes_by_file"] or f in repo_map["functions_by_file"]),
                key=lambda f: (
                    len(repo_map["classes_by_file"].get(f, []))
                    + len(repo_map["functions_by_file"].get(f, []))
                ),
                reverse=True,
            )[:20]

            if sorted_files:
                lines.append("## Key files (most definitions):")
                for f in sorted_files:
                    cls = repo_map["classes_by_file"].get(f, [])
                    funcs = repo_map["functions_by_file"].get(f, [])
                    tags = []
                    if cls:
                        tags.append(f"{len(cls)} classes")
                    if funcs:
                        tags.append(f"{len(funcs)} functions")
                    lines.append(f"  {f} — {', '.join(tags)}")

        return "\n".join(lines)

    def rank_files(
        self,
        query: str,
        repo_map: dict[str, Any] | None = None,
    ) -> list[tuple[str, float]]:
        """Rank files by relevance to *query* using simple keyword matching.

        Parameters
        ----------
        query:
            Search keywords (space-separated; case-insensitive).
        repo_map:
            Pre-built map, or ``None`` to build one on the fly.

        Returns
        -------
        List of ``(file_path, score)`` tuples sorted descending by score.
        """
        if repo_map is None:
            repo_map = self.build_map()

        keywords = {
            kw.lower()
            for kw in re.findall(r"[A-Za-z_]\w*", query)
            if len(kw) > 2 and kw.lower() not in _STOPWORDS
        }
        if not keywords:
            return []

        scores: dict[str, float] = defaultdict(float)

        for file_path in repo_map["files"]:
            path_lower = file_path.lower()
            name_lower = Path(file_path).stem.lower()

            # Score 1: path / filename matches
            for kw in keywords:
                if kw in path_lower:
                    scores[file_path] += 1.0
                if kw == name_lower:
                    scores[file_path] += 2.0
                if kw in name_lower:
                    scores[file_path] += 0.5

            # Score 2: identifier matches
            for cls in repo_map["classes_by_file"].get(file_path, []):
                cls_lower = cls.lower()
                for kw in keywords:
                    if kw == cls_lower:
                        scores[file_path] += 3.0
                    elif kw in cls_lower:
                        scores[file_path] += 1.0

            for func in repo_map["functions_by_file"].get(file_path, []):
                func_lower = func.lower()
                for kw in keywords:
                    if kw == func_lower:
                        scores[file_path] += 3.0
                    elif kw in func_lower:
                        scores[file_path] += 1.0

            # Score 3: import references
            for imp in repo_map["imports_by_file"].get(file_path, []):
                imp_lower = imp.lower()
                for kw in keywords:
                    if kw in imp_lower:
                        scores[file_path] += 0.5

        return sorted(scores.items(), key=lambda x: -x[1])

    # ── internals ───────────────────────────────────────────────────────

    def _get_tracked_files(self) -> list[str]:
        """Return all tracked, non-binary file paths relative to repo root."""
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                # Fallback: walk the directory
                return self._walk_files()

            files: list[str] = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Skip excluded dirs
                parts = Path(line).parts
                if any(p in self.exclude_dirs for p in parts):
                    continue
                # Skip binary extensions
                ext = Path(line).suffix.lower()
                if ext in _BINARY_EXTENSIONS:
                    continue
                files.append(line)
            return sorted(files)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return self._walk_files()

    def _walk_files(self) -> list[str]:
        """Fallback: walk the repo tree manually."""
        files: list[str] = []
        for root, dirs, names in os.walk(str(self.repo_path)):
            # Prune excluded dirs in-place
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            rel_root = Path(root).relative_to(self.repo_path)
            for name in names:
                ext = Path(name).suffix.lower()
                if ext in _BINARY_EXTENSIONS:
                    continue
                files.append(str(rel_root / name))
        return sorted(files)


# ──────────────────────────────────────────────────────────────────────────────
#  Module-level convenience functions
# ──────────────────────────────────────────────────────────────────────────────


def build_repo_map(
    repo_path: str,
    exclude_dirs: set[str] | None = None,
) -> dict[str, Any]:
    """Build a structurd map for *repo_path*.

    Shortcut for ``RepoMap(repo_path, exclude_dirs).build_map()``.
    """
    return RepoMap(repo_path, exclude_dirs).build_map()


def get_repo_context(
    repo_path: str,
    file_path: str = "",
    exclude_dirs: set[str] | None = None,
) -> str:
    """Return a text summary of *repo_path*, focused on *file_path* when given.

    Shortcut for ``RepoMap(repo_path, exclude_dirs).get_context(file_path)``.
    """
    return RepoMap(repo_path, exclude_dirs).get_context(file_path)


def rank_files_by_relevance(
    query: str,
    repo_map: dict[str, Any],
) -> list[tuple[str, float]]:
    """Rank files in *repo_map* by relevance to *query*.

    Shortcut (class-less) — the caller already has a built map.
    """
    # We need the repo_path from the map to build a RepoMap instance
    repo_path = repo_map.get("repo_path", ".")
    return RepoMap(repo_path).rank_files(query, repo_map)


# ──────────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────────

_BINARY_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".o", ".a", ".lib",
    ".pyc", ".pyo", ".pyd",
    ".class", ".jar",
    ".db", ".sqlite", ".sqlite3",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".mp3", ".mp4", ".avi", ".mov",
    ".ttf", ".otf",
    ".whl", ".egg",
}

_STOPWORDS: set[str] = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any",
    "can", "has", "had", "was", "get", "use", "set", "put", "how",
    "why", "what", "when", "where", "who", "which", "this", "that",
    "these", "those", "from", "with", "without", "into", "over",
    "such", "each", "every", "both", "few", "more", "most", "some",
    "other", "than", "then", "also", "very", "just", "about",
    "above", "after", "again", "below", "does", "done", "give",
    "have", "here", "here", "made", "make", "much", "must",
    "need", "only", "own", "same", "should", "take", "tell",
    "well", "will", "would", "file", "code", "function",
}


# ──────────────────────────────────────────────────────────────────────────────
#  CLI entry point (``python -m openamer_cli.repomap build .``)
# ──────────────────────────────────────────────────────────────────────────────


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="OpenAmer RepoMap - codebase understanding")
    sub = parser.add_subparsers(dest="command")

    build_p = sub.add_parser("build", help="Build repo map for a directory")
    build_p.add_argument("path", nargs="?", default=".", help="Path to git repo root")

    context_p = sub.add_parser("context", help="Get repo context summary")
    context_p.add_argument("path", nargs="?", default=".", help="Path to git repo root")
    context_p.add_argument("--file", default="", help="Focus on a specific file")

    rank_p = sub.add_parser("rank", help="Rank files by relevance")
    rank_p.add_argument("path", nargs="?", default=".", help="Path to git repo root")
    rank_p.add_argument("query", help="Search query")

    args = parser.parse_args()

    if args.command == "build":
        repo_path = args.path
        try:
            result = build_repo_map(repo_path)
            import json
            print(json.dumps(result, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "context":
        try:
            ctx = get_repo_context(args.path, args.file)
            print(ctx)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "rank":
        try:
            rm = build_repo_map(args.path)
            ranked = rank_files_by_relevance(args.query, rm)
            if ranked:
                print(f"Top files for '{args.query}':")
                for f, score in ranked[:20]:
                    print(f"  {f:6.2f}  {score}")
            else:
                print("No matches found.")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()