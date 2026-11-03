"""Retrieval contract tests for the repo map symbol/reference ranking.

The fixture corpus under ``tests/fixtures/repomap_retrieval`` is versioned and
its gold labels name the files that define or call the queried symbol. These
tests assert behaviour (definitions and call sites are found within a fixed
token budget) rather than a particular score value.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from openamer_cli.repomap import (  # noqa: E402
    RepoMap,
    _extract_symbol_table,
    _split_identifier,
    build_repo_map,
    estimate_tokens,
    rank_files_by_relevance,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "repomap_retrieval"


@pytest.fixture(scope="module")
def fixture_data() -> dict:
    return json.loads((_FIXTURES / "queries.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def corpus(tmp_path_factory, fixture_data: dict) -> Path:
    """Copy of the fixture corpus without a .git directory (walk enumeration)."""
    root = tmp_path_factory.mktemp("repomap-retrieval")
    staged = root / "corpus"
    shutil.copytree(_FIXTURES / fixture_data["corpus"], staged)
    return staged


@pytest.fixture(scope="module")
def graph_map(corpus: Path):
    repo_map = RepoMap(str(corpus))
    built = repo_map.build_map()
    repo_map.build_symbol_index(built)
    return repo_map, built


def _mean_file_recall(strategy: str, graph_map, fixture_data: dict) -> float:
    repo_map, built = graph_map
    budget = fixture_data["token_budget"]
    recalls = []
    for entry in fixture_data["queries"]:
        if strategy == "graph":
            text = repo_map.render_context(entry["query"], budget, built)
        else:
            text = "\n".join(
                f"  - {path}"
                for path, score in repo_map.rank_files(entry["query"], built)
                if score > 0
            )
        normalised = text.replace("\\", "/")
        hits = [f for f in entry["gold_files"] if f in normalised]
        recalls.append(len(hits) / len(entry["gold_files"]))
    return sum(recalls) / len(recalls)


# ──────────────────────────────────────────────────────────────────────────────
#  Fixture integrity
# ──────────────────────────────────────────────────────────────────────────────


class TestFixture:
    def test_fixture_is_versioned(self, fixture_data: dict):
        assert fixture_data["version"] == 1
        assert fixture_data["token_budget"] > 0
        assert fixture_data["queries"]

    def test_every_query_has_gold_labels(self, fixture_data: dict):
        for entry in fixture_data["queries"]:
            assert entry["gold_files"], entry["id"]
            assert entry["gold_symbols"], entry["id"]
            assert all(len(pair) == 2 for pair in entry["gold_symbols"]), entry["id"]


# ──────────────────────────────────────────────────────────────────────────────
#  Measured behaviour: references are retrieved, not just definitions
# ──────────────────────────────────────────────────────────────────────────────


class TestRetrieval:
    def test_graph_finds_call_sites_keyword_misses(self, graph_map, fixture_data):
        """The discriminating case: callers that never name the symbol lexically."""
        repo_map, built = graph_map
        entry = next(q for q in fixture_data["queries"] if q["id"] == "compute-backoff-callers")
        text = repo_map.render_context(entry["query"], fixture_data["token_budget"], built)
        normalised = text.replace("\\", "/")
        for gold_file in entry["gold_files"]:
            assert gold_file in normalised, f"{gold_file} missing from:\n{text}"

    def test_graph_recall_is_not_worse_than_keyword(self, graph_map, fixture_data):
        graph = _mean_file_recall("graph", graph_map, fixture_data)
        keyword = _mean_file_recall("keyword", graph_map, fixture_data)
        assert graph >= keyword, f"graph={graph:.4f} keyword={keyword:.4f}"

    def test_graph_recall_covers_all_gold_files(self, graph_map, fixture_data):
        assert _mean_file_recall("graph", graph_map, fixture_data) >= 0.99

    def test_budget_is_never_exceeded(self, graph_map, fixture_data):
        repo_map, built = graph_map
        budget = fixture_data["token_budget"]
        for entry in fixture_data["queries"]:
            text = repo_map.render_context(entry["query"], budget, built)
            assert estimate_tokens(text) <= budget

    def test_smaller_budget_yields_prefix(self, graph_map, fixture_data):
        repo_map, built = graph_map
        query = fixture_data["queries"][0]["query"]
        wide = repo_map.render_context(query, 120, built)
        narrow = repo_map.render_context(query, 20, built)
        assert estimate_tokens(narrow) <= 20
        assert wide.startswith(narrow)


# ──────────────────────────────────────────────────────────────────────────────
#  Syntax-aware extraction and graceful degradation
# ──────────────────────────────────────────────────────────────────────────────


class TestSymbolExtraction:
    def test_ast_records_attribute_references(self, corpus: Path):
        table = _extract_symbol_table(
            "transport.py", (corpus / "app" / "transport.py").read_text(encoding="utf-8")
        )
        assert table["parser"] == "ast"
        # ``self.policy.compute_backoff(...)`` is an attribute access: a plain
        # keyword scan would never connect it to the definition in retry.py.
        assert "compute_backoff" in table["refs"]
        assert "RetryPolicy" in table["refs"]
        names = {definition["name"] for definition in table["defs"]}
        assert {"HttpClient", "send_request"} <= names
        assert all(definition["line"] > 0 for definition in table["defs"])

    def test_malformed_python_falls_back_to_lexer(self):
        table = _extract_symbol_table(
            "broken.py", "class Broken(:\n    def nope(self)\n", parser=None
        )
        assert table["parser"] == "lexer"
        assert isinstance(table["refs"], list)

    def test_raising_parser_falls_back(self):
        def explode(_path: str, _content: str):
            raise RuntimeError("parser unavailable")

        table = _extract_symbol_table("module.ts", "function ok() {}\n", parser=explode)
        assert table["parser"] == "lexer"
        assert "ok" in {definition["name"] for definition in table["defs"]}

    def test_malformed_parser_result_falls_back(self):
        def broken(_path: str, _content: str):
            return {"defs": "not-a-list", "refs": None}

        table = _extract_symbol_table("module.ts", "function ok() {}\n", parser=broken)
        assert table["parser"] == "lexer"
        assert "ok" in {definition["name"] for definition in table["defs"]}

    def test_injected_parser_is_used(self):
        def custom(_path: str, _content: str):
            return {
                "defs": [{"name": "injected", "kind": "function", "line": 3}],
                "refs": ["injected"],
                "imports": [],
                "parser": "tree-sitter",
            }

        table = _extract_symbol_table("anything.custom", "irrelevant", parser=custom)
        assert table["parser"] == "tree-sitter"
        assert table["defs"][0]["name"] == "injected"

    def test_prose_files_are_not_indexed(self, graph_map):
        repo_map, repo_dict = graph_map
        symbols = repo_map.build_symbol_index(repo_dict)
        assert "docs/architecture.md" not in symbols

    def test_split_identifier(self):
        assert _split_identifier("compute_backoff") == ["compute", "backoff"]
        assert _split_identifier("CacheStore") == ["cache", "store"]
        assert _split_identifier("HTTPClient") == ["http", "client"]


# ──────────────────────────────────────────────────────────────────────────────
#  Cache freshness
# ──────────────────────────────────────────────────────────────────────────────


class TestSymbolIndexCache:
    def test_index_is_cached_until_refreshed(self, tmp_path: Path):
        root = tmp_path / "repo"
        shutil.copytree(_FIXTURES / "corpus", root)
        repo_map = RepoMap(str(root))
        first = repo_map.build_symbol_index()
        assert "app/retry.py" in {path.replace("\\", "/") for path in first}

        added = root / "app" / "fresh.py"
        added.write_text("def brand_new_helper():\n    pass\n", encoding="utf-8")

        cached = repo_map.build_symbol_index()
        assert "app/fresh.py" not in {path.replace("\\", "/") for path in cached}

        refreshed = repo_map.build_symbol_index(refresh=True)
        assert "app/fresh.py" in {path.replace("\\", "/") for path in refreshed}

    def test_new_instance_sees_current_tree(self, tmp_path: Path):
        root = tmp_path / "repo"
        shutil.copytree(_FIXTURES / "corpus", root)
        (root / "app" / "added.py").write_text("def added_symbol():\n    pass\n")
        fresh = RepoMap(str(root))
        index = fresh.build_symbol_index()
        assert "app/added.py" in {path.replace("\\", "/") for path in index}


# ──────────────────────────────────────────────────────────────────────────────
#  Degenerate inputs
# ──────────────────────────────────────────────────────────────────────────────


class TestDegenerateInputs:
    def test_empty_query_renders_nothing(self, graph_map):
        repo_map, built = graph_map
        assert repo_map.render_context("", 120, built) == ""
        assert repo_map.rank_files_graph("", built) == []

    def test_unknown_symbol_renders_nothing(self, graph_map):
        repo_map, built = graph_map
        assert repo_map.render_context("totally_absent_symbol", 120, built) == ""

    def test_zero_budget_renders_nothing(self, graph_map):
        repo_map, built = graph_map
        assert repo_map.render_context("compute_backoff", 0, built) == ""

    def test_rank_graph_without_prebuilt_map(self, corpus: Path):
        ranked = RepoMap(str(corpus)).rank_files_graph("compute_backoff")
        assert ranked
        assert ranked[0][0].replace("\\", "/") == "app/retry.py"


# ──────────────────────────────────────────────────────────────────────────────
#  CLI surface
# ──────────────────────────────────────────────────────────────────────────────


class TestCli:
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "openamer_cli.repomap", *args],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_rank_graph_strategy(self, corpus: Path):
        result = self._run("rank", str(corpus), "compute_backoff", "--strategy", "graph")
        assert result.returncode == 0, result.stderr
        assert "(graph)" in result.stdout
        assert "app" in result.stdout

    def test_rank_default_strategy_is_keyword(self, corpus: Path):
        result = self._run("rank", str(corpus), "compute_backoff")
        assert result.returncode == 0, result.stderr
        assert "(keyword)" in result.stdout

    def test_context_query_budget(self, corpus: Path):
        result = self._run(
            "context", str(corpus), "--query", "compute_backoff", "--budget", "40"
        )
        assert result.returncode == 0, result.stderr
        assert "retry" in result.stdout.lower()

    def test_context_without_query_still_works(self, corpus: Path):
        result = self._run("context", str(corpus))
        assert result.returncode == 0, result.stderr
        assert "Repo:" in result.stdout


# ──────────────────────────────────────────────────────────────────────────────
#  Windows-specific enumeration
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(os.name != "nt", reason="Windows path separators")
def test_windows_paths_are_ranked(graph_map, fixture_data):
    repo_map, built = graph_map
    text = repo_map.render_context("compute_backoff", fixture_data["token_budget"], built)
    assert "app\\retry.py" in text


def test_keyword_ranking_still_available(corpus: Path):
    """The pre-existing strategy keeps working unchanged."""
    built = build_repo_map(str(corpus))
    ranked = rank_files_by_relevance("compute_backoff", built)
    assert ranked[0][0].replace("\\", "/") == "app/retry.py"
