"""Persistent, symbol-level repository index with incrementally-updated storage.

This is the codebase-index capability: index a repository once, then ask for
the files and symbols relevant to a question without grepping the tree again.

What it stores
--------------
A single small JSON file at ``<repo>/.openamer/index/code-index.json`` holding,
per tracked source file, only:

  * the relative path,
  * the file's ``mtime`` and ``size`` (the incremental-update key),
  * a detected language,
  * a ``symbols`` list of ``{name, kind, line, doc}`` entries,
  * how the symbols were obtained (``ast`` or ``heuristic``).

No file bodies, no full text: the index stays small and is a *map*, not a copy.

Accuracy — stated honestly
--------------------------
The index is NOT uniformly precise, and the code says so per file:

  * ``.py`` files are parsed with the stdlib :mod:`ast`. Symbols there are
    real: classes, functions, methods (with their enclosing class), plus a
    one-line docstring head. ``source`` is ``"ast"``.
  * every other language is scanned with a **regex heuristic** over keyword
    patterns (``function``, ``func``, ``fn``, ``const``, ``interface``,
    ``type``, ``class``, ...). That over- and under-matches — it can pick up
    string literals or miss unusual declaration forms. ``source`` is
    ``"heuristic"`` and callers should treat those symbols as hints, not facts.

Bounded by construction
-----------------------
This runs on a CPU-only machine, so a scan must stay cheap:

  * skip directories: ``.git/``, ``node_modules/``, ``.venv/``, ``venv/``,
    ``__pycache__/``, ``dist/``, ``build/``, ``.openamer/`` and friends,
  * skip binary files (NUL byte in the head) and files over
    :data:`MAX_FILE_BYTES`,
  * cap the number of indexed files at :data:`MAX_FILES`,
  * incremental: a file whose ``(mtime, size)`` is unchanged since the last
    build is *reused as-is* and never re-read — no parse, no open.

Ranking
-------
:func:`query_index` scores symbols and paths against the query tokens:

  * symbol-name match outranks a path-only match (a file that *defines*
    ``parse_config`` beats a file merely named ``config_thing.py``),
  * exact token match outranks prefix, which outranks substring,
  * a file where *all* query tokens match somewhere gets a coverage bonus.

It is deliberately simple and bag-of-tokens based: no stemming, no
embeddings, no synonyms. Weak spots are documented in the skill and in
:func:`query_index`.
"""

from __future__ import annotations

import ast
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "build_index",
    "query_index",
    "index_stats",
    "index_path",
    "confidence_notes",
    "INDEX_VERSION",
    "MAX_FILE_BYTES",
    "MAX_FILES",
    "MAX_SECONDS",
    "MAX_SYMBOLS_PER_FILE",
    "SKIP_DIRS",
]

INDEX_VERSION = 1
INDEX_DIR = os.path.join(".openamer", "index")
INDEX_FILENAME = "code-index.json"

#: Files larger than this are skipped (assumed generated / minified / data).
MAX_FILE_BYTES = 512 * 1024

#: Hard cap on indexed files per repository — keeps a scan bounded.
MAX_FILES = 5000

#: Wall-clock budget for one build, in seconds. Once exceeded the scan stops
#: spending time on unparsed files and returns ``partial=True``; the next run
#: reuses what was already parsed (cheaply) and reaches further, so the index
#: converges run over run instead of forcing minutes on a CPU-only box.
MAX_SECONDS = 20.0

#: Cap on symbols recorded per file — bounds index size on generated files.
MAX_SYMBOLS_PER_FILE = 500

#: Directory names never descended into.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".openamer",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "dist",
        "build",
        "target",
        ".next",
        ".nuxt",
        "coverage",
        "htmlcov",
        ".idea",
        ".vscode",
        "site-packages",
        ".cache",
        "vendor",
    }
)

#: Extension -> language label. Anything not listed is not indexed.
LANGUAGES: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".php": "php",
    ".swift": "swift",
    ".scala": "scala",
    ".lua": "lua",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".ps1": "powershell",
    ".sql": "sql",
    ".r": "r",
    ".dart": "dart",
    ".ex": "elixir",
    ".exs": "elixir",
    ".clj": "clojure",
    ".vue": "vue",
    ".svelte": "svelte",
}

#: Heuristic keyword patterns for non-Python languages, per language group.
#: These are HINTS, not a parser. See the module docstring.
_HEURISTIC_PATTERNS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "javascript": [
        ("function", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)")),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()")),
        ("class", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)")),
        ("method", re.compile(r"^\s*(?:async\s+)?(?:static\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{")),
        ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)")),
        ("type", re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=")),
    ],
    "typescript": [
        ("function", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)")),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()")),
        ("class", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)")),
        ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)")),
        ("type", re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=")),
        ("enum", re.compile(r"^\s*(?:export\s+)?(?:const\s+)?enum\s+([A-Za-z_$][\w$]*)")),
    ],
    "go": [
        ("function", re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)")),
        ("type", re.compile(r"^\s*type\s+([A-Za-z_]\w*)\s+(?:struct|interface|func|=)")),
        ("const", re.compile(r"^\s*const\s+([A-Za-z_]\w*)")),
    ],
    "rust": [
        ("function", re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)")),
        ("struct", re.compile(r"^\s*(?:pub\s+)?struct\s+([A-Za-z_]\w*)")),
        ("enum", re.compile(r"^\s*(?:pub\s+)?enum\s+([A-Za-z_]\w*)")),
        ("trait", re.compile(r"^\s*(?:pub\s+)?trait\s+([A-Za-z_]\w*)")),
        ("impl", re.compile(r"^\s*impl(?:<[^>]*>)?\s+([A-Za-z_]\w*)")),
    ],
    "ruby": [
        ("function", re.compile(r"^\s*def\s+([A-Za-z_]\w*[?!=]?)")),
        ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)")),
        ("module", re.compile(r"^\s*module\s+([A-Za-z_]\w*)")),
    ],
    "java": [
        ("class", re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(?:abstract\s+)?(?:class|interface|enum|record)\s+([A-Za-z_]\w*)")),
        ("method", re.compile(r"^\s*(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?[\w<>\[\],\s.?]+\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{")),
    ],
    "kotlin": [
        ("class", re.compile(r"^\s*(?:public|private|internal|open|abstract|data|sealed)?\s*(?:class|interface|object|enum class)\s+([A-Za-z_]\w*)")),
        ("function", re.compile(r"^\s*(?:public|private|internal|override|suspend|open|inline)?\s*fun\s+(?:<[^>]*>\s*)?([A-Za-z_]\w*)")),
    ],
    "csharp": [
        ("class", re.compile(r"^\s*(?:public|private|internal|protected)?\s*(?:static\s+)?(?:sealed\s+)?(?:abstract\s+)?(?:partial\s+)?(?:class|interface|enum|struct|record)\s+([A-Za-z_]\w*)")),
        ("method", re.compile(r"^\s*(?:public|private|internal|protected)\s+(?:static\s+)?(?:async\s+)?(?:virtual\s+)?[\w<>\[\],\s.?]+\s+([A-Za-z_]\w*)\s*\(")),
    ],
    "c": [
        ("function", re.compile(r"^[A-Za-z_][\w\s*]*\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{")),
        ("struct", re.compile(r"^\s*(?:typedef\s+)?struct\s+([A-Za-z_]\w*)")),
    ],
    "cpp": [
        ("function", re.compile(r"^[A-Za-z_][\w\s:<>,*&]*\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{")),
        ("class", re.compile(r"^\s*(?:template\s*<[^>]*>\s*)?(?:class|struct)\s+([A-Za-z_]\w*)")),
    ],
    "php": [
        ("function", re.compile(r"^\s*(?:public|private|protected|static)?\s*function\s+([A-Za-z_]\w*)")),
        ("class", re.compile(r"^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+([A-Za-z_]\w*)")),
    ],
    "swift": [
        ("function", re.compile(r"^\s*(?:public|private|internal|fileprivate|open)?\s*(?:static\s+)?func\s+([A-Za-z_]\w*)")),
        ("class", re.compile(r"^\s*(?:public|private|internal)?\s*(?:final\s+)?(?:class|struct|enum|protocol|extension)\s+([A-Za-z_]\w*)")),
    ],
    "scala": [
        ("function", re.compile(r"^\s*(?:private|protected|override)?\s*def\s+([A-Za-z_]\w*)")),
        ("class", re.compile(r"^\s*(?:case\s+)?(?:class|trait|object)\s+([A-Za-z_]\w*)")),
    ],
    "lua": [
        ("function", re.compile(r"^\s*(?:local\s+)?function\s+([A-Za-z_][\w.:]*)")),
    ],
    "shell": [
        ("function", re.compile(r"^\s*function\s+([A-Za-z_]\w*)")),
        ("function", re.compile(r"^\s*([A-Za-z_]\w*)\s*\(\s*\)\s*\{")),
    ],
    "powershell": [
        ("function", re.compile(r"^\s*(?:function|filter)\s+([A-Za-z_][\w-]*)")),
    ],
    "sql": [
        ("table", re.compile(r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w.\"]+)", re.I)),
        ("function", re.compile(r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\s+([\w.\"]+)", re.I)),
    ],
    "dart": [
        ("function", re.compile(r"^\s*(?:Future|Stream|void|int|String|bool|double)?<?[\w>?]*>?\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*(?:async\s*)?\{")),
        ("class", re.compile(r"^\s*(?:abstract\s+)?class\s+([A-Za-z_]\w*)")),
    ],
    "elixir": [
        ("function", re.compile(r"^\s*def(?:p)?\s+([A-Za-z_]\w*[?!]?)")),
        ("module", re.compile(r"^\s*defmodule\s+([A-Za-z_][\w.]*)")),
    ],
    "clojure": [
        ("function", re.compile(r"^\s*\(defn-?\s+([\w*+!?<>=-]+)")),
        ("data", re.compile(r"^\s*\(def\s+([\w*+!?<>=-]+)")),
    ],
    "r": [
        ("function", re.compile(r"^\s*([A-Za-z._][\w.]*)\s*(?:<-|=)\s*function")),
    ],
}

# Fallback for languages without a dedicated pattern set (e.g. .vue/.svelte):
_GENERIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("function", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)")),
    ("class", re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)")),
    ("const", re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=")),
]

_TOKEN_SPLIT = re.compile(r"[^A-Za-z0-9]+")
_CAMEL_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


# ──────────────────────────────────────────────────────────────────────────────
#  Paths
# ──────────────────────────────────────────────────────────────────────────────


def index_path(repo_path: str | os.PathLike[str]) -> Path:
    """Return the JSON index path for *repo_path* (``<repo>/.openamer/index/...``).

    The index belongs to the repository, not to ``OPENAMER_HOME`` — it travels
    with the checkout and is covered by the repo's own ``.gitignore``.
    """
    return Path(repo_path).resolve() / INDEX_DIR / INDEX_FILENAME


def _detect_language(name: str) -> str | None:
    return LANGUAGES.get(Path(name).suffix.lower())


# ──────────────────────────────────────────────────────────────────────────────
#  Symbol extraction
# ──────────────────────────────────────────────────────────────────────────────


def _sym(
    name: str, kind: str, line: int, doc: str = "", parent: str = ""
) -> dict[str, Any]:
    """Build one symbol record, omitting empty ``doc``/``parent`` fields.

    Most symbols have neither and the index is meant to stay small — so an
    absent key means "none", not "unknown".
    """
    rec: dict[str, Any] = {"name": name, "kind": kind, "line": line}
    if doc:
        rec["doc"] = doc
    if parent:
        rec["parent"] = parent
    return rec


def _doc_head(node: ast.AST, limit: int = 120) -> str:
    """First non-empty line of a node's docstring, trimmed to *limit* chars."""
    try:
        doc = ast.get_docstring(node, clean=True)
    except Exception:
        return ""
    if not doc:
        return ""
    first = doc.strip().splitlines()[0].strip()
    return first[:limit]


def extract_python_symbols(source: str) -> list[dict[str, Any]]:
    """Parse *source* with :mod:`ast` and return real symbol records.

    Classes, functions and methods (methods carry their class in ``parent``).
    A syntax error yields ``[]`` rather than raising — one bad file must not
    abort a repo scan.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return []

    symbols: list[dict[str, Any]] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(_sym(node.name, "class", node.lineno, _doc_head(node)))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(
                        _sym(child.name, "method", child.lineno, _doc_head(child), node.name)
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(_sym(node.name, "function", node.lineno, _doc_head(node)))

    return symbols


def extract_heuristic_symbols(source: str, language: str) -> list[dict[str, Any]]:
    """Regex-scan *source* for declaration-like lines.

    THIS IS A HEURISTIC, not a parser: it matches by keyword shape, so it can
    report a name from a string literal or miss an unusual declaration form.
    Records carry ``{"source": "heuristic"}`` upstream so callers can weigh
    them accordingly.
    """
    patterns = _HEURISTIC_PATTERNS.get(language, _GENERIC_PATTERNS)
    symbols: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    for lineno, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "#", "*", "/*", "--")):
            continue
        for kind, pattern in patterns:
            m = pattern.match(line)
            if not m:
                continue
            name = m.group(1).strip().strip("\"'`")
            if not name or len(name) > 120:
                continue
            key = (name, lineno)
            if key in seen:
                continue
            seen.add(key)
            symbols.append(_sym(name, kind, lineno))
            break  # first matching pattern wins for this line

    return symbols


def _read_text(path: Path) -> str | None:
    """Read *path* as UTF-8 text, or ``None`` if it looks binary / undecodable.

    NUL byte in the first 8 KiB ⇒ binary. Errors are replaced, never raised:
    an index must tolerate one unreadable file.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(8192)
        if b"\x00" in head:
            return None
    except OSError:
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _parse_file(abs_path: Path, language: str) -> tuple[list[dict[str, Any]], str]:
    """Return ``(symbols, source_label)`` for one file."""
    text = _read_text(abs_path)
    if text is None:
        return [], "binary"
    if language == "python":
        return extract_python_symbols(text), "ast"
    return extract_heuristic_symbols(text, language), "heuristic"


# ──────────────────────────────────────────────────────────────────────────────
#  Scan + build
# ──────────────────────────────────────────────────────────────────────────────


def _iter_candidate_files(root: Path, max_files: int) -> tuple[list[Path], bool]:
    """Walk *root* collecting indexable files, pruning :data:`SKIP_DIRS`.

    Returns ``(files, truncated)`` — ``truncated`` is True when the
    :data:`MAX_FILES` cap stopped the walk early.
    """
    files: list[Path] = []
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")
        ]
        for fname in filenames:
            if _detect_language(fname) is None:
                continue
            abs_path = Path(dirpath) / fname
            if abs_path.is_symlink():
                continue
            files.append(abs_path)
            if len(files) >= max_files:
                truncated = True
                return files, truncated

    return files, truncated


def _load_raw(path: Path) -> dict[str, Any]:
    """Load an existing index, or return an empty shell."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"version": INDEX_VERSION, "files": {}}
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        return {"version": INDEX_VERSION, "files": {}}
    return data


def build_index(
    repo_path: str | os.PathLike[str] = ".",
    *,
    incremental: bool = True,
    max_files: int = MAX_FILES,
    max_file_bytes: int = MAX_FILE_BYTES,
) -> dict[str, Any]:
    """Build (or incrementally refresh) the persistent index for *repo_path*.

    With ``incremental=True`` (the default) a file whose ``(mtime, size)``
    matches the stored record is reused verbatim — it is never opened. The
    result reports ``files_parsed`` vs ``files_reused`` so the saving is
    measurable rather than assumed.

    Returns a summary dict including ``duration_ms`` and writes
    ``<repo>/.openamer/index/code-index.json`` atomically (temp file + replace).
    """
    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    started = time.perf_counter()
    out_path = index_path(root)
    previous = _load_raw(out_path) if incremental else {"files": {}}
    prev_files: dict[str, Any] = previous.get("files") or {}

    candidates, truncated = _iter_candidate_files(root, max_files)

    files_out: dict[str, Any] = {}
    parsed = 0
    reused = 0
    skipped_binary = 0
    skipped_large = 0

    for abs_path in candidates:
        try:
            stat = abs_path.stat()
        except OSError:
            continue
        if stat.st_size > max_file_bytes:
            skipped_large += 1
            continue

        rel = abs_path.relative_to(root).as_posix()
        mtime = stat.st_mtime
        size = stat.st_size

        cached = prev_files.get(rel)
        if (
            isinstance(cached, dict)
            and cached.get("mtime") == mtime
            and cached.get("size") == size
            and isinstance(cached.get("symbols"), list)
        ):
            files_out[rel] = cached
            reused += 1
            continue

        language = _detect_language(abs_path.name)
        assert language is not None  # filtered by _iter_candidate_files
        symbols, source_label = _parse_file(abs_path, language)
        if source_label == "binary":
            skipped_binary += 1
            continue

        files_out[rel] = {
            "mtime": mtime,
            "size": size,
            "lang": language,
            "source": source_label,
            "symbols": symbols,
        }
        parsed += 1

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "version": INDEX_VERSION,
        "repo": str(root),
        "created": previous.get("created") or now,
        "updated": now,
        "files": files_out,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"), sort_keys=True)
    os.replace(tmp_path, out_path)

    duration_ms = (time.perf_counter() - started) * 1000.0
    symbol_count = sum(len(f.get("symbols") or []) for f in files_out.values())

    return {
        "ok": True,
        "repo": str(root),
        "index_path": str(out_path),
        "files_indexed": len(files_out),
        "files_parsed": parsed,
        "files_reused": reused,
        "symbols": symbol_count,
        "skipped_binary": skipped_binary,
        "skipped_large": skipped_large,
        "truncated": truncated,
        "duration_ms": round(duration_ms, 2),
        "index_bytes": out_path.stat().st_size if out_path.exists() else 0,
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Query
# ──────────────────────────────────────────────────────────────────────────────


def _tokenize(text: str) -> list[str]:
    """Split *text* into lowercase tokens, cracking snake_case and camelCase."""
    tokens: list[str] = []
    for chunk in _TOKEN_SPLIT.split(text):
        if not chunk:
            continue
        for part in _CAMEL_SPLIT.split(chunk):
            part = part.lower()
            if len(part) >= 2:
                tokens.append(part)
    return tokens


def _name_score(name: str, token: str) -> float:
    """Score one symbol name against one query token."""
    low = name.lower()
    if low == token:
        return 10.0
    pieces = _tokenize(name)
    if token in pieces:
        return 7.0
    if low.startswith(token):
        return 6.0
    if token in low:
        return 4.0
    return 0.0


def _path_score(rel_path: str, token: str) -> float:
    """Score one file path against one query token (weaker than a symbol hit)."""
    low = rel_path.lower()
    stem = Path(rel_path).stem.lower()
    if stem == token:
        return 3.0
    if token in _tokenize(Path(rel_path).name):
        return 2.5
    if token in low:
        return 1.5
    return 0.0


def query_index(
    repo_path: str | os.PathLike[str] = ".",
    query: str = "",
    *,
    limit: int = 20,
) -> dict[str, Any]:
    """Rank indexed files/symbols against *query* and return the top *limit*.

    Ranking (per query token, summed over the file's symbols and its path):

    ``symbol name exact`` 10 > ``name piece`` 7 > ``name prefix`` 6 >
    ``name substring`` 4 > ``path stem exact`` 3 > ``path piece`` 2.5 >
    ``path substring`` 1.5 > ``doc substring`` 0.5.

    A file matching *every* query token gets a 1.25x coverage multiplier.

    Honest weak spots: bag-of-tokens only — no stemming (``configs`` won't
    match ``config``), no synonyms, no embeddings, and non-Python symbols come
    from a regex heuristic so a name here is a hint, not proof.
    """
    root = Path(repo_path).resolve()
    index = _load_raw(index_path(root))
    files: dict[str, Any] = index.get("files") or {}

    tokens = _tokenize(query)
    if not tokens:
        return {"ok": True, "repo": str(root), "query": query, "tokens": [], "results": []}

    results: list[dict[str, Any]] = []

    for rel, record in files.items():
        if not isinstance(record, dict):
            continue
        symbols = record.get("symbols") or []
        total = 0.0
        matched_tokens: set[str] = set()
        # keyed by (name, line) so a symbol matched by two tokens is reported
        # once with its best score instead of once per matching token.
        best_by_symbol: dict[tuple[str, int], dict[str, Any]] = {}

        for token in tokens:
            token_hit = False
            for sym in symbols:
                if not isinstance(sym, dict):
                    continue
                name = str(sym.get("name") or "")
                s = _name_score(name, token)
                if s > 0:
                    token_hit = True
                    total += s
                    line = int(sym.get("line") or 0)
                    key = (name, line)
                    entry = best_by_symbol.get(key)
                    if entry is None or s > entry["score"]:
                        best_by_symbol[key] = {
                            "name": name,
                            "kind": sym.get("kind", ""),
                            "line": line,
                            "score": round(s, 2),
                        }
                elif sym.get("doc"):
                    d = str(sym["doc"]).lower()
                    if token in d:
                        token_hit = True
                        total += 0.5
            p = _path_score(rel, token)
            if p > 0:
                token_hit = True
                total += p
            if token_hit:
                matched_tokens.add(token)

        if total <= 0:
            continue

        if len(matched_tokens) == len(tokens) and len(tokens) > 1:
            total *= 1.25

        best_symbols = sorted(best_by_symbol.values(), key=lambda s: (-s["score"], s["name"]))
        results.append(
            {
                "path": rel,
                "score": round(total, 2),
                "lang": record.get("lang", ""),
                "source": record.get("source", ""),
                "matched_symbols": best_symbols[:5],
                "symbol_count": len(symbols),
            }
        )

    results.sort(key=lambda r: (-r["score"], r["path"]))

    return {
        "ok": True,
        "repo": str(root),
        "query": query,
        "tokens": tokens,
        "total_matches": len(results),
        "results": results[: max(0, limit)],
    }


# ──────────────────────────────────────────────────────────────────────────────
#  Stats
# ──────────────────────────────────────────────────────────────────────────────


def index_stats(repo_path: str | os.PathLike[str] = ".") -> dict[str, Any]:
    """Summarise the stored index: language mix, symbol kinds, sources, size.

    Returns ``{"exists": False, ...}`` when no index has been built yet.
    """
    root = Path(repo_path).resolve()
    out_path = index_path(root)

    if not out_path.exists():
        return {
            "ok": True,
            "exists": False,
            "repo": str(root),
            "index_path": str(out_path),
            "files_indexed": 0,
            "symbols": 0,
            "index_bytes": 0,
        }

    try:
        raw_size = out_path.stat().st_size
    except OSError:
        raw_size = 0

    index = _load_raw(out_path)
    files: dict[str, Any] = index.get("files") or {}

    by_lang: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_source: dict[str, int] = {}
    symbol_total = 0

    for record in files.values():
        if not isinstance(record, dict):
            continue
        lang = str(record.get("lang") or "unknown")
        by_lang[lang] = by_lang.get(lang, 0) + 1
        source = str(record.get("source") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1
        for sym in record.get("symbols") or []:
            if not isinstance(sym, dict):
                continue
            symbol_total += 1
            kind = str(sym.get("kind") or "unknown")
            by_kind[kind] = by_kind.get(kind, 0) + 1

    return {
        "ok": True,
        "exists": True,
        "repo": str(root),
        "index_path": str(out_path),
        "version": index.get("version"),
        "created": index.get("created"),
        "updated": index.get("updated"),
        "files_indexed": len(files),
        "symbols": symbol_total,
        "index_bytes": raw_size,
        "by_language": dict(sorted(by_lang.items(), key=lambda kv: -kv[1])),
        "by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
        "by_source": dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
    }


def confidence_notes(stats: dict[str, Any]) -> list[str]:
    """Return human-readable honesty notes about the index's precision mix.

    Used by the CLI so output states plainly how much of the index is
    AST-exact versus regex-guessed instead of implying uniform precision.
    """
    by_source = stats.get("by_source", {}) or {}
    ast_files = int(by_source.get("ast", 0))
    heuristic_files = int(by_source.get("heuristic", 0))
    notes: list[str] = []
    if heuristic_files:
        if ast_files:
            notes.append(
                f"{ast_files} file(s) parsed with ast (exact); "
                f"{heuristic_files} file(s) scanned by regex heuristic (approximate)."
            )
        else:
            notes.append(
                f"all {heuristic_files} file(s) were scanned by regex heuristic "
                "(approximate symbols — no Python files indexed)."
            )
    elif ast_files:
        notes.append(f"all {ast_files} file(s) parsed with ast (exact symbols).")
    return notes
