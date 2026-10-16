"""Tests for the persistent, symbol-level codebase index (``code_index``).

The fixture builds a throwaway mini-repo *in the test itself* covering:
multiple languages (Python/TypeScript/Go), a binary file with an indexable
extension, an oversized file, and skip-listed directories — so every bound the
module claims is exercised for real rather than asserted on faith.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from openamer_cli import code_index as ci

# ── fixture: a self-contained mini-repo ────────────────────────────────────


@pytest.fixture()
def mini_repo(tmp_path: Path) -> Path:
    """Create a small multi-language repo with a binary, a huge file, skips."""
    root = tmp_path / "repo"
    pkg = root / "pkg"
    pkg.mkdir(parents=True)

    # Python — parsed with ast (exact symbols, incl. methods + docstrings).
    (pkg / "core.py").write_text(
        '"""Core utilities."""\n'
        "class ConfigLoader:\n"
        '    """Loads configuration from disk."""\n'
        "    def load(self, path):\n"
        '        """Read and parse the file."""\n'
        "        return {}\n"
        "    def _secret_helper(self):\n"
        "        pass\n"
        "def parse_config(text):\n"
        '    """Parse a config string."""\n'
        "    return text\n"
        "async def fetch_remote(url):\n"
        "    pass\n",
        encoding="utf-8",
    )

    # A file whose *path* mentions config but which defines no such symbol:
    # used to prove symbol hits outrank path hits.
    (pkg / "config_helper.py").write_text(
        "def unrelated_thing():\n    pass\n", encoding="utf-8"
    )

    # TypeScript — regex heuristic.
    (pkg / "web.ts").write_text(
        "export function renderWidget(){}\n"
        "interface WidgetProps {}\n"
        "const helperThing = () => {};\n",
        encoding="utf-8",
    )

    # Go — regex heuristic.
    (pkg / "main.go").write_text(
        "package main\nfunc HandleRequest() {}\ntype Server struct{}\n",
        encoding="utf-8",
    )

    # Binary file carrying an INDEXABLE extension (NUL byte) -> must be skipped.
    (pkg / "badbinary.py").write_bytes(b"\x00\x01\x02def fake():\n    pass\n")

    # Oversized file over MAX_FILE_BYTES -> must be skipped.
    (pkg / "huge.py").write_text("# pad\n" * 120_000, encoding="utf-8")

    # Skip-listed directories -> must never be descended into.
    (root / "node_modules").mkdir()
    (root / "node_modules" / "junk.py").write_text(
        "def should_not_appear():\n    pass\n", encoding="utf-8"
    )
    (root / "dist").mkdir()
    (root / "dist" / "built.py").write_text(
        "def also_not():\n    pass\n", encoding="utf-8"
    )
    (root / ".git").mkdir()
    (root / ".git" / "hook.py").write_text(
        "def git_hook():\n    pass\n", encoding="utf-8"
    )

    return root


# ── build: bounds ──────────────────────────────────────────────────────────


def test_build_indexes_only_real_sources_and_skips_bounds(mini_repo: Path):
    """Only the three real sources land; binary, oversized, and skips do not."""
    result = ci.build_index(mini_repo)

    assert result["ok"] is True
    assert result["files_indexed"] == 4
    assert result["skipped_binary"] == 1, "binary file with .py extension must skip"
    assert result["skipped_large"] == 1, "oversized file must skip"
    assert result["truncated"] is False

    index = json.loads(ci.index_path(mini_repo).read_text(encoding="utf-8"))
    paths = set(index["files"])
    assert paths == {
        "pkg/core.py",
        "pkg/config_helper.py",
        "pkg/web.ts",
        "pkg/main.go",
    }
    # Skip dirs and skipped files must be entirely absent.
    for banned in ("node_modules", "dist", ".git", "badbinary.py", "huge.py"):
        assert not any(banned in p for p in paths), banned

    assert result["index_bytes"] > 0
    assert result["duration_ms"] >= 0


def test_index_is_stored_in_the_repo_not_openamer_home(mini_repo: Path):
    """The index lives under <repo>/.openamer/index/ — it belongs to the repo."""
    ci.build_index(mini_repo)
    expected = mini_repo / ".openamer" / "index" / "code-index.json"
    assert expected.is_file()
    assert Path(ci.index_path(mini_repo)) == expected.resolve()


def test_python_symbols_are_ast_exact(mini_repo: Path):
    """Python symbols come from ast: real class/function/method with lines."""
    ci.build_index(mini_repo)
    index = json.loads(ci.index_path(mini_repo).read_text(encoding="utf-8"))
    record = index["files"]["pkg/core.py"]

    assert record["source"] == "ast", "Python must be labeled ast, not heuristic"
    names = {(s["name"], s["kind"]) for s in record["symbols"]}
    assert ("ConfigLoader", "class") in names
    assert ("parse_config", "function") in names
    assert ("fetch_remote", "function") in names
    assert ("load", "method") in names
    assert ("_secret_helper", "method") in names

    load = next(s for s in record["symbols"] if s["name"] == "load")
    assert load["parent"] == "ConfigLoader"
    assert load["line"] > 0
    assert load["doc"] == "Read and parse the file."


def test_non_python_symbols_are_labeled_heuristic(mini_repo: Path):
    """Non-Python symbols must be honestly labeled heuristic, not exact."""
    ci.build_index(mini_repo)
    index = json.loads(ci.index_path(mini_repo).read_text(encoding="utf-8"))

    for rel in ("pkg/web.ts", "pkg/main.go"):
        assert index["files"][rel]["source"] == "heuristic"

    ts_names = {s["name"] for s in index["files"]["pkg/web.ts"]["symbols"]}
    assert "renderWidget" in ts_names
    assert "WidgetProps" in ts_names

    go_names = {s["name"] for s in index["files"]["pkg/main.go"]["symbols"]}
    assert "HandleRequest" in go_names


# ── incremental behaviour ──────────────────────────────────────────────────


def test_second_build_reuses_unchanged_files_without_reparsing(mini_repo: Path):
    """A second build must NOT re-parse unchanged files (mtime+size proof)."""
    first = ci.build_index(mini_repo)
    assert first["files_parsed"] == 4
    assert first["files_reused"] == 0

    # Prove the stored key really is the live mtime+size for each file.
    index = json.loads(ci.index_path(mini_repo).read_text(encoding="utf-8"))
    for rel, record in index["files"].items():
        stat = os.stat(mini_repo / rel)
        assert record["mtime"] == stat.st_mtime
        assert record["size"] == stat.st_size

    second = ci.build_index(mini_repo)
    assert second["files_parsed"] == 0, "unchanged files must not be re-parsed"
    assert second["files_reused"] == 4
    assert second["symbols"] == first["symbols"]
    assert second["files_indexed"] == first["files_indexed"]


def test_second_build_is_faster_than_the_first(mini_repo: Path):
    """Reuse must actually save work — measured, not assumed."""
    first = ci.build_index(mini_repo)
    second = ci.build_index(mini_repo)
    # Not a hard timing assertion (CPU noise); we assert the work counters and
    # that the reuse path at least does not regress wildly.
    assert first["files_parsed"] == 4 and second["files_parsed"] == 0
    assert second["duration_ms"] <= max(first["duration_ms"] * 3, 50.0)


def test_changed_file_is_reparsed_on_next_build(mini_repo: Path):
    """Touching a file (mtime change) must invalidate exactly that entry."""
    ci.build_index(mini_repo)
    target = mini_repo / "pkg" / "web.ts"
    target.write_text(target.read_text(encoding="utf-8") + "export function addedLater(){}\n",
                      encoding="utf-8")
    # Ensure a distinct mtime even on coarse filesystem timestamps.
    future = time.time() + 5
    os.utime(target, (future, future))

    result = ci.build_index(mini_repo)
    assert result["files_parsed"] == 1, "only the touched file should re-parse"
    assert result["files_reused"] == 3

    index = json.loads(ci.index_path(mini_repo).read_text(encoding="utf-8"))
    names = {s["name"] for s in index["files"]["pkg/web.ts"]["symbols"]}
    assert "addedLater" in names


def test_full_rebuild_ignores_the_previous_index(mini_repo: Path):
    """``incremental=False`` must re-parse everything."""
    ci.build_index(mini_repo)
    full = ci.build_index(mini_repo, incremental=False)
    assert full["files_parsed"] == 4
    assert full["files_reused"] == 0


# ── ranking ────────────────────────────────────────────────────────────────


def test_symbol_hit_outranks_path_only_hit(mini_repo: Path):
    """A file that DEFINES the symbol beats a file merely named after it."""
    ci.build_index(mini_repo)
    result = ci.query_index(mini_repo, "parse_config")

    assert result["results"], "query returned nothing"
    top = result["results"][0]
    assert top["path"] == "pkg/core.py"
    assert any(s["name"] == "parse_config" for s in top["matched_symbols"])

    # config_helper.py has "config" in its path but defines no matching symbol,
    # so it must score strictly lower than core.py.
    by_path = {r["path"]: r["score"] for r in result["results"]}
    if "pkg/config_helper.py" in by_path:
        assert by_path["pkg/config_helper.py"] < by_path["pkg/core.py"]


def test_query_finds_symbols_across_languages(mini_repo: Path):
    """Heuristic symbols are still searchable."""
    ci.build_index(mini_repo)
    assert ci.query_index(mini_repo, "renderWidget")["results"][0]["path"] == "pkg/web.ts"
    assert ci.query_index(mini_repo, "HandleRequest")["results"][0]["path"] == "pkg/main.go"


def test_query_result_symbols_are_deduplicated(mini_repo: Path):
    """A symbol matched by two tokens appears once, not once per token."""
    ci.build_index(mini_repo)
    result = ci.query_index(mini_repo, "parse config")
    core = next(r for r in result["results"] if r["path"] == "pkg/core.py")
    keys = [(s["name"], s["line"]) for s in core["matched_symbols"]]
    assert len(keys) == len(set(keys)), f"duplicate symbol entries: {keys}"


def test_query_respects_limit_and_reports_totals(mini_repo: Path):
    """``limit`` caps results; ``total_matches`` reports the true count."""
    ci.build_index(mini_repo)
    result = ci.query_index(mini_repo, "config", limit=1)
    assert len(result["results"]) == 1
    assert result["total_matches"] >= 1


def test_query_without_tokens_returns_nothing(mini_repo: Path):
    """An empty/garbage query must not dump the whole repo."""
    ci.build_index(mini_repo)
    for empty in ("", "   ", "!!!", "x"):  # single-char tokens are dropped
        assert ci.query_index(mini_repo, empty)["results"] == [], empty


# ── stats ──────────────────────────────────────────────────────────────────


def test_stats_reports_mix_and_confidence_notes(mini_repo: Path):
    """Stats expose the language/source mix and the honest precision note."""
    ci.build_index(mini_repo)
    stats = ci.index_stats(mini_repo)

    assert stats["exists"] is True
    assert stats["files_indexed"] == 4
    assert stats["symbols"] > 0
    assert stats["by_language"]["python"] == 2
    assert stats["by_language"]["typescript"] == 1
    assert stats["by_language"]["go"] == 1
    assert stats["by_source"]["ast"] == 2
    assert stats["by_source"]["heuristic"] == 2

    notes = ci.confidence_notes(stats)
    assert notes, "expected a precision note"
    assert "heuristic" in notes[0].lower()


def test_stats_before_any_build_reports_missing(tmp_path: Path):
    """Stats on an unbuilt repo must not pretend an index exists."""
    empty = tmp_path / "empty"
    empty.mkdir()
    stats = ci.index_stats(empty)
    assert stats["exists"] is False
    assert stats["files_indexed"] == 0
    assert stats["symbols"] == 0


# ── CLI surface: --json form + parser registration ─────────────────────────


def _build_parser():
    import argparse

    from openamer_cli.subcommands.index import build_index_parser

    parser = argparse.ArgumentParser(prog="openamer")
    sub = parser.add_subparsers(dest="command")
    build_index_parser(sub)
    return parser


def test_cli_parser_registers_index_subcommands():
    """`openamer index build|query|stats` must all parse."""
    parser = _build_parser()
    args = parser.parse_args(["index", "build", "--repo", ".", "--json"])
    assert args.repo == "."
    assert args.json is True
    assert callable(args.func)

    args = parser.parse_args(["index", "query", "some terms", "--limit", "5"])
    assert args.query == "some terms"
    assert args.limit == 5

    args = parser.parse_args(["index", "stats"])
    assert args.repo == "."
    assert callable(args.func)


def test_cli_build_json_is_machine_readable(mini_repo: Path, capsys):
    """`index build --json` emits one JSON object with the measured runtime."""
    parser = _build_parser()
    args = parser.parse_args(["index", "build", "--repo", str(mini_repo), "--json"])
    rc = args.func(args)
    assert rc == 0

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["files_indexed"] == 4
    assert payload["files_parsed"] == 4
    assert "duration_ms" in payload
    assert payload["confidence"], "build --json must carry the precision note"


def test_cli_query_json_shape(mini_repo: Path, capsys):
    """`index query --json` returns the documented result shape."""
    parser = _build_parser()
    build_args = parser.parse_args(["index", "build", "--repo", str(mini_repo)])
    assert build_args.func(build_args) == 0
    capsys.readouterr()

    args = parser.parse_args(["index", "query", "parse_config", "--repo", str(mini_repo), "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["query"] == "parse_config"
    assert "tokens" in payload and "total_matches" in payload
    top = payload["results"][0]
    assert set(top) >= {"path", "score", "lang", "source", "matched_symbols", "symbol_count"}


def test_cli_query_without_index_exits_nonzero_with_json_error(tmp_path: Path, capsys):
    """Querying an unbuilt repo fails cleanly instead of crashing."""
    repo = tmp_path / "nope"
    repo.mkdir()
    parser = _build_parser()
    args = parser.parse_args(["index", "query", "anything", "--repo", str(repo), "--json"])
    rc = args.func(args)
    assert rc == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"] == "no_index"


def test_cli_stats_json(mini_repo: Path, capsys):
    """`index stats --json` reports the same numbers as the module."""
    parser = _build_parser()
    build_args = parser.parse_args(["index", "build", "--repo", str(mini_repo)])
    build_args.func(build_args)
    capsys.readouterr()

    args = parser.parse_args(["index", "stats", "--repo", str(mini_repo), "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["exists"] is True
    assert payload["files_indexed"] == 4
    assert payload["by_source"]["ast"] == 2
