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

import ast
import math
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterator


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


def _strip_comments(
    content: str,
    rules: tuple[str | None, str | None, str | None, list[str], list[str]],
) -> list[str]:
    """Return *content* split into lines with comments removed.

    One output line per input line is preserved (blanked lines are kept as an
    empty string) so callers can report real source line numbers.
    """
    single_comment, multi_start, multi_end = rules[0], rules[1], rules[2]

    filtered: list[str] = []
    in_multi = False

    for line in content.split("\n"):
        st = line.strip()
        # Strip multi-line comments
        if multi_start and multi_end:
            if in_multi:
                idx = st.find(multi_end)
                if idx >= 0:
                    st = st[idx + len(multi_end) :]
                    in_multi = False
                else:
                    filtered.append("")
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
                        filtered.append("")
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

    return filtered


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

    class_keywords, function_keywords = rules[3], rules[4]
    filtered = _strip_comments(content, rules)

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
#  Symbol table — definitions, references, and graph ranking
#
#  The ranking patterns follow Aider's repo map (Aider-AI/aider, pinned at
#  commit 253f0368b873ba30d8ee26e463718f0c03614ddf, Apache-2.0): per-file
#  definition/reference tags, a file graph whose edge weight reflects how
#  specific the shared identifier is, and a personalized PageRank pass over
#  that graph. This is an independent implementation — it imports neither
#  aider, networkx, grep-ast nor tree-sitter — see NOTICE for attribution.
#
#  Python is parsed with the stdlib ``ast`` module, so the default build is
#  genuinely syntax-aware with no extra dependency. Every other language falls
#  back to the existing comment-stripping lexer. A caller may inject its own
#  ``symbol_parser`` (e.g. a tree-sitter adapter) through ``RepoMap``; a parser
#  that raises or returns a malformed table is ignored in favour of the
#  built-in extraction.
# ──────────────────────────────────────────────────────────────────────────────

_IDENT_SPLIT = re.compile(r"[^A-Za-z0-9]+")
_CAMEL_SPLIT = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_IDENT_TOKEN = re.compile(r"[A-Za-z_]\w*")
_MAX_REF_TOKENS_PER_FILE = 6000


def _split_identifier(name: str) -> list[str]:
    """Split ``compute_backoff`` / ``CacheStore`` into lowercase words."""
    tokens: list[str] = []
    for chunk in _IDENT_SPLIT.split(name):
        if not chunk:
            continue
        tokens.extend(part.lower() for part in _CAMEL_SPLIT.findall(chunk))
    return tokens


def _extract_python_symbols(content: str) -> dict[str, Any] | None:
    """Return defs/refs/imports for Python source, or ``None`` if unparsable."""
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None

    defs: list[dict[str, Any]] = []
    refs: list[str] = []
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            defs.append({"name": node.name, "kind": "class", "line": node.lineno})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.append({"name": node.name, "kind": "function", "line": node.lineno})
        elif isinstance(node, ast.Name):
            refs.append(node.id)
        elif isinstance(node, ast.Attribute):
            # ``self.policy.compute_backoff`` references the attribute, not the
            # bare name — this is the signal a keyword scan cannot see.
            refs.append(node.attr)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")
                refs.append(alias.name.split(".")[0])
                if alias.asname:
                    refs.append(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(
                f"from {module} import " + ", ".join(alias.name for alias in node.names)
            )
            for alias in node.names:
                refs.append(alias.name)
                if alias.asname:
                    refs.append(alias.asname)

    defs.sort(key=lambda item: (item["line"], item["name"]))
    return {"defs": defs, "refs": refs, "imports": imports, "parser": "ast"}


def _extract_generic_symbols(
    file_path: str,
    content: str,
    rules: tuple[str | None, str | None, str | None, list[str], list[str]],
) -> dict[str, Any]:
    """Lexer fallback: definitions by keyword prefix, references by token scan."""
    class_keywords, function_keywords = rules[3], rules[4]
    ext = Path(file_path).suffix.lower()

    defs: list[dict[str, Any]] = []
    refs: list[str] = []
    imports: list[str] = []

    for line_number, line in enumerate(_strip_comments(content, rules), start=1):
        if not line:
            continue

        if ext == ".py" and (line.startswith("import ") or line.startswith("from ")):
            imports.append(line)
        elif ext in (".js", ".ts", ".jsx", ".tsx") and (
            line.startswith("import ") or "require(" in line
        ):
            imports.append(line)
        elif ext in (".kt", ".kts", ".java") and line.startswith("import "):
            imports.append(line)

        recorded = False
        for keyword in class_keywords:
            if keyword in line:
                after = line[line.index(keyword) + len(keyword) :].strip()
                match = re.match(r"([A-Za-z_]\w*)", after)
                if match and match.group(1) not in ("self", "cls", "this", "super"):
                    defs.append(
                        {"name": match.group(1), "kind": "class", "line": line_number}
                    )
                recorded = True
                break
        if recorded:
            continue

        for keyword in function_keywords:
            if keyword in line:
                after = line[line.index(keyword) + len(keyword) :].strip()
                match = re.match(r"([A-Za-z_]\w*)", after)
                if match and match.group(1) not in ("self", "cls", "this", "super"):
                    defs.append(
                        {"name": match.group(1), "kind": "function", "line": line_number}
                    )
                break

        refs.extend(token for token in _IDENT_TOKEN.findall(line) if len(token) > 2)

    defs.sort(key=lambda item: (item["line"], item["name"]))
    return {
        "defs": defs,
        "refs": refs[:_MAX_REF_TOKENS_PER_FILE],
        "imports": imports,
        "parser": "lexer",
    }


def _extract_symbol_table(
    file_path: str,
    content: str,
    parser: Callable[[str, str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Build the def/ref table for one file, degrading gracefully.

    Order of preference: caller-supplied *parser*, then ``ast`` for Python,
    then the language lexer. Any failure silently moves to the next option —
    an unparsable file must never break the repo map.
    """
    if parser is not None:
        try:
            table = parser(file_path, content)
        except Exception:
            table = None
        if isinstance(table, dict) and isinstance(table.get("defs"), list) and isinstance(
            table.get("refs"), list
        ):
            return {
                "defs": table["defs"],
                "refs": [str(ref) for ref in table["refs"]],
                "imports": [str(imp) for imp in table.get("imports", [])],
                "parser": str(table.get("parser") or "custom"),
            }

    ext = Path(file_path).suffix.lower()
    rules = _LANGUAGE_RULES.get(ext)
    if rules is None:
        return {"defs": [], "refs": [], "imports": [], "parser": "none"}
    if not rules[3] and not rules[4]:
        # Prose/config files have no definition keywords. Token-scanning them
        # invents references for every word they mention (a README "deploy"
        # would look like a call site), so they stay out of the symbol index.
        return {"defs": [], "refs": [], "imports": [], "parser": "none"}

    if ext == ".py":
        table = _extract_python_symbols(content)
        if table is not None:
            return table

    return _extract_generic_symbols(file_path, content, rules)


def _ident_weight(ident: str, mentioned: set[str], definer_count: int) -> float:
    """Score how informative a shared identifier is (Aider's heuristics)."""
    weight = 1.0
    is_snake = "_" in ident and any(char.isalpha() for char in ident)
    is_camel = any(char.isupper() for char in ident) and any(
        char.islower() for char in ident
    )
    if ident in mentioned:
        weight *= 10.0
    if (is_snake or is_camel) and len(ident) >= 8:
        weight *= 10.0
    if ident.startswith("_"):
        weight *= 0.1
    if definer_count > 5:
        weight *= 0.1
    return weight


def _personalized_pagerank(
    nodes: list[str],
    edges: dict[str, list[tuple[str, float, str]]],
    personalization: dict[str, float],
    damping: float = 0.85,
    iterations: int = 50,
    tolerance: float = 1e-10,
) -> dict[str, float]:
    """Power-iteration PageRank with a personalization (teleport) vector."""
    count = len(nodes)
    if not count:
        return {}

    teleport = {node: max(personalization.get(node, 0.0), 0.0) for node in nodes}
    total = sum(teleport.values())
    if total <= 0.0:
        teleport = {node: 1.0 / count for node in nodes}
    else:
        teleport = {node: value / total for node, value in teleport.items()}

    rank = dict(teleport)
    outgoing = {
        node: sum(weight for _, weight, _ in edges.get(node, ())) for node in nodes
    }

    for _ in range(iterations):
        updated = {node: (1.0 - damping) * teleport[node] for node in nodes}
        dangling = 0.0
        for node in nodes:
            total_weight = outgoing[node]
            if total_weight <= 0.0:
                dangling += rank[node]
                continue
            share = damping * rank[node] / total_weight
            for destination, weight, _ident in edges.get(node, ()):
                updated[destination] += share * weight
        if dangling:
            for node in nodes:
                updated[node] += damping * dangling * teleport[node]

        delta = sum(abs(updated[node] - rank[node]) for node in nodes)
        rank = updated
        if delta < tolerance:
            break

    return rank


def _rank_reference_graph(
    file_paths: list[str],
    symbols: dict[str, dict[str, Any]],
    keywords: set[str],
) -> tuple[list[tuple[str, float]], list[dict[str, Any]]]:
    """Rank files, and the context lines for them, from the reference graph.

    Returns ``(ranked_files, entries)``. ``entries`` are pre-formatted,
    highest-ranked first, and each is either a definition, a "references ..."
    line for a call site, or a bare path for a file that only defines.

    Scoring is query-anchored: only identifiers the query actually names (after
    snake/camel splitting) contribute, so a file that merely defines a lot of
    referenced helpers cannot outrank the module the query is about. Files the
    ranking has no direct evidence for are left out entirely rather than pulled
    in as a discounted second hop — measured on the v1 fixtures, that hop bought
    one extra gold file but cost a third of the precision budget (see the PR
    description), and a repo map is supposed to spend its tokens on evidence.
    """
    defines: dict[str, set[str]] = defaultdict(set)
    references: dict[str, list[str]] = defaultdict(list)
    defs_by_file: dict[str, list[dict[str, Any]]] = {}
    lines: dict[tuple[str, str], int] = {}

    for file_path in file_paths:
        table = symbols.get(file_path, {"defs": [], "refs": [], "imports": []})
        defs_by_file[file_path] = table.get("defs", [])
        for definition in table.get("defs", []):
            name = str(definition.get("name", ""))
            if not name:
                continue
            defines[name].add(file_path)
            lines.setdefault((file_path, name), int(definition.get("line") or 0))
        for reference in table.get("refs", []):
            references[reference].append(file_path)

    nodes = list(file_paths)
    edges: dict[str, list[tuple[str, float, str]]] = defaultdict(list)

    target_idents = {
        ident
        for ident in defines
        if ident.lower() in keywords or keywords.intersection(_split_identifier(ident))
    }
    if not target_idents:
        return [], []

    for ident in set(defines) & set(references):
        weight = _ident_weight(ident, target_idents, len(defines[ident]))
        for referencer, occurrences in Counter(references[ident]).items():
            for definer in defines[ident]:
                # sqrt so a symbol mentioned 100 times does not drown out a
                # symbol that is structurally central.
                edges[referencer].append((definer, weight * math.sqrt(occurrences), ident))

    for ident, definers in defines.items():
        if ident in references:
            continue
        for definer in definers:
            edges[definer].append((definer, 0.1, ident))

    personalization: dict[str, float] = {}
    for file_path in nodes:
        score = 0.0
        components = {part.lower() for part in Path(file_path).parts}
        components.update(_split_identifier(Path(file_path).stem))
        if keywords.intersection(components):
            score += 1.0
        for definition in defs_by_file.get(file_path, []):
            if keywords.intersection(_split_identifier(str(definition.get("name", "")))):
                score += 10.0
        personalization[file_path] = score

    rank = _personalized_pagerank(nodes, edges, personalization)

    definition_ranked: dict[tuple[str, str], float] = defaultdict(float)
    for source in nodes:
        total_weight = sum(weight for _, weight, _ in edges.get(source, ()))
        if total_weight <= 0.0:
            continue
        source_rank = rank.get(source, 0.0)
        for destination, weight, ident in edges.get(source, ()):
            definition_ranked[(destination, ident)] += source_rank * weight / total_weight

    ident_importance: dict[str, float] = defaultdict(float)
    for (_file_path, ident), value in definition_ranked.items():
        ident_importance[ident] += value
    peak = max((ident_importance.get(ident, 0.0) for ident in target_idents), default=0.0)

    importance = {
        ident: (ident_importance.get(ident, 0.0) / peak if peak > 0.0 else 0.0)
        for ident in target_idents
    }
    if peak <= 0.0:
        # No reference evidence at all: fall back to a flat prior so a
        # definition-only hit still outranks everything unrelated.
        importance = {ident: 1.0 for ident in target_idents}

    score_by_file: dict[str, float] = defaultdict(float)
    defined_by_file: dict[str, list[str]] = defaultdict(list)
    referenced_by_file: dict[str, list[str]] = defaultdict(list)
    for ident in target_idents:
        weight = importance[ident]
        for file_path in defines[ident]:
            score_by_file[file_path] += weight
            defined_by_file[file_path].append(ident)
        for file_path in set(references.get(ident, ())):
            if file_path in defines[ident]:
                continue
            score_by_file[file_path] += 0.8 * weight
            referenced_by_file[file_path].append(ident)

    if not score_by_file:
        return [], []

    ranked = sorted(score_by_file.items(), key=lambda item: (-item[1], item[0]))

    def entries() -> Iterator[dict[str, Any]]:
        """Yield context lines lazily so a small budget does not build them all."""
        for file_path, _score in ranked:
            defined = sorted(
                defined_by_file.get(file_path, []),
                key=lambda ident: (-importance.get(ident, 0.0), ident),
            )
            referenced = sorted(
                referenced_by_file.get(file_path, []),
                key=lambda ident: (-importance.get(ident, 0.0), ident),
            )
            for ident in defined:
                line_number = lines.get((file_path, ident), 0)
                yield {
                    "file": file_path,
                    "kind": "def",
                    "ident": ident,
                    "line": line_number,
                    "text": (
                        f"  {file_path}:{line_number}  {ident}"
                        if line_number
                        else f"  {file_path}  {ident}"
                    ),
                }
            if referenced:
                joined = ", ".join(referenced[:3])
                yield {
                    "file": file_path,
                    "kind": "ref",
                    "ident": joined,
                    "line": 0,
                    "text": f"  {file_path}  references {joined}",
                }
            if not defined and not referenced:
                yield {
                    "file": file_path,
                    "kind": "file",
                    "ident": "",
                    "line": 0,
                    "text": f"  {file_path}",
                }

    return ranked, entries()


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
        symbol_parser: Callable[[str, str], dict[str, Any] | None] | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.symbol_parser = symbol_parser
        self._symbol_index: dict[str, dict[str, Any]] | None = None
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

        keywords = _query_keywords(query)
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

    def build_symbol_index(
        self,
        repo_map: dict[str, Any] | None = None,
        refresh: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """Return ``{file_path: {"defs": [...], "refs": [...], "imports": [...]}}``.

        Definitions carry ``name``, ``kind`` and ``line``. Python uses ``ast``
        (real syntax), every other language uses the lexer; a supplied
        ``symbol_parser`` takes precedence and falls back silently on failure.

        The index is cached per ``RepoMap`` instance so repeated queries do not
        re-read the tree. Pass ``refresh=True`` after files change.
        """
        if self._symbol_index is not None and not refresh:
            return self._symbol_index

        built = repo_map if repo_map is not None else self.build_map()
        index: dict[str, dict[str, Any]] = {}
        for rel_path in built["files"]:
            full_path = self.repo_path / rel_path
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            table = _extract_symbol_table(str(full_path), content, self.symbol_parser)
            if table["defs"] or table["refs"]:
                index[rel_path] = table

        self._symbol_index = index
        return index

    def rank_files_graph(
        self,
        query: str,
        repo_map: dict[str, Any] | None = None,
        symbols: dict[str, dict[str, Any]] | None = None,
    ) -> list[tuple[str, float]]:
        """Rank files by syntax-aware symbol and reference relevance.

        Unlike :meth:`rank_files`, which matches query keywords against paths
        and identifier names, this walks the definition/reference graph: a file
        scores for defining a matching symbol *and* for calling one that the
        graph considers important.
        """
        if repo_map is None:
            repo_map = self.build_map()
        keywords = _query_keywords(query)
        if not keywords:
            return []
        if symbols is None:
            symbols = self.build_symbol_index(repo_map)

        ranked, _ = _rank_reference_graph(repo_map["files"], symbols, keywords)
        return [(file_path, score) for file_path, score in ranked if score > 0]

    def render_context(
        self,
        query: str,
        budget_tokens: int,
        repo_map: dict[str, Any] | None = None,
        symbols: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        """Render ranked definitions for *query* within *budget_tokens*.

        One line per entry, highest ranked first::

            app/retry.py:24  function compute_backoff
            app/transport.py:31  function send_request

        The budget is enforced with :func:`estimate_tokens`, the same counter
        the keyword renderer uses, so both strategies are comparable.
        """
        if repo_map is None:
            repo_map = self.build_map()
        keywords = _query_keywords(query)
        if not keywords or budget_tokens <= 0:
            return ""
        if symbols is None:
            symbols = self.build_symbol_index(repo_map)

        _ranked_files, entries = _rank_reference_graph(
            repo_map["files"], symbols, keywords
        )

        rendered: list[str] = []
        used = 0
        for entry in entries:
            cost = estimate_tokens(entry["text"])
            if used + cost > budget_tokens:
                break
            rendered.append(entry["text"])
            used += cost

        return "\n".join(rendered)

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
#  Token accounting — dependency-free approximation
#
#  Ranking and context rendering must agree on the size of a payload so a
#  caller-supplied budget means the same thing for every strategy. A real BPE
#  tokenizer (tiktoken) is deliberately avoided: it is a heavy optional
#  dependency and the repo map must work in a bare checkout. Counting word runs
#  plus individual punctuation is within ~10-20% of BPE counts on code and,
#  more importantly, is deterministic and monotonic.
# ──────────────────────────────────────────────────────────────────────────────

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]")


def estimate_tokens(text: str) -> int:
    """Return an approximate token count for *text* (stdlib only)."""
    if not text:
        return 0
    return len(_TOKEN_PATTERN.findall(text))


def _query_keywords(query: str) -> set[str]:
    """Split *query* into lowercase search keywords, dropping stopwords."""
    return {
        word.lower()
        for word in re.findall(r"[A-Za-z_]\w*", query)
        if len(word) > 2 and word.lower() not in _STOPWORDS
    }


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
    context_p.add_argument("--query", "-q", default="", help="Ranked definitions for a query")
    context_p.add_argument("--budget", type=int, default=120, help="Token budget for --query")

    rank_p = sub.add_parser("rank", help="Rank files by relevance")
    rank_p.add_argument("path", nargs="?", default=".", help="Path to git repo root")
    rank_p.add_argument("query", help="Search query")
    rank_p.add_argument(
        "--strategy", choices=("keyword", "graph"), default="keyword",
        help="ranking strategy (default: keyword)",
    )

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
            if args.query:
                rendered = RepoMap(args.path).render_context(args.query, args.budget)
                print(rendered)
            else:
                ctx = get_repo_context(args.path, args.file)
                print(ctx)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "rank":
        try:
            rm = build_repo_map(args.path)
            if args.strategy == "graph":
                ranked = RepoMap(args.path).rank_files_graph(args.query, rm)
            else:
                ranked = rank_files_by_relevance(args.query, rm)
            if ranked:
                print(f"Top files for '{args.query}' ({args.strategy}):")
                for f, score in ranked[:20]:
                    print(f"  {score:6.2f}  {f}")
            else:
                print("No matches found.")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()