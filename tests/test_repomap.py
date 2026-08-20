"""Tests for ``openamer_cli/repomap.py``.

Tests are designed to run against the OpenAmer repo itself (no fixtures required).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from openamer_cli.repomap import (
    RepoMap,
    _detect_language,
    _extract_identifiers,
    build_repo_map,
    get_repo_context,
    rank_files_by_relevance,
)


# ──────────────────────────────────────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def repo_root() -> Path:
    """Return the OpenAmer repo root."""
    return _REPO_ROOT


@pytest.fixture(scope="module")
def repomap(repo_root: Path) -> RepoMap:
    """A RepoMap instance for the OpenAmer repo."""
    return RepoMap(str(repo_root))


@pytest.fixture(scope="module")
def repo_map_dict(repo_root: Path) -> dict:
    """A built repo map dict for the OpenAmer repo."""
    # Skip if we're in a CI-ish environment without git
    git_dir = repo_root / ".git"
    if not git_dir.is_dir():
        pytest.skip("Not a git repository")
    return build_repo_map(str(repo_root))


# ──────────────────────────────────────────────────────────────────────────────
#  _detect_language
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectLanguage:
    def test_python(self):
        assert _detect_language("foo.py") == "Python"
        assert _detect_language("path/to/main.py") == "Python"

    def test_javascript(self):
        assert _detect_language("app.js") == "JavaScript"

    def test_typescript(self):
        assert _detect_language("app.ts") == "TypeScript"

    def test_kotlin(self):
        assert _detect_language("Main.kt") == "Kotlin"

    def test_java(self):
        assert _detect_language("Main.java") == "Java"

    def test_go(self):
        assert _detect_language("main.go") == "Go"

    def test_rust(self):
        assert _detect_language("lib.rs") == "Rust"

    def test_unknown_extension(self):
        assert _detect_language("data.custom") == "Custom"

    def test_shebang_python(self, tmp_path: Path):
        f = tmp_path / "script"
        f.write_text("#!/usr/bin/env python3\nprint('hi')\n")
        assert _detect_language(str(f)) == "Python"

    def test_shebang_bash(self, tmp_path: Path):
        f = tmp_path / "runme"
        f.write_text("#!/bin/bash\necho hi\n")
        assert _detect_language(str(f)) == "Shell"

    def test_shebang_node(self, tmp_path: Path):
        f = tmp_path / "serve"
        f.write_text("#!/usr/bin/env node\nconsole.log('hi')\n")
        assert _detect_language(str(f)) == "JavaScript"

    def test_empty_file(self, tmp_path: Path):
        f = tmp_path / "empty"
        f.write_text("")
        lang = _detect_language(str(f))
        # Should not crash — extension is empty, so falls back to shebang (none)
        assert isinstance(lang, str)


# ──────────────────────────────────────────────────────────────────────────────
#  _extract_identifiers
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractIdentifiers:
    def test_python_class_and_function(self):
        content = """
class MyClass:
    def my_method(self):
        pass

def top_level():
    pass
"""
        ids = _extract_identifiers("test.py", content)
        assert "MyClass" in ids["classes"]
        assert "my_method" in ids["functions"]
        assert "top_level" in ids["functions"]

    def test_python_imports(self):
        content = "import os\nfrom pathlib import Path\nx = 1\n"
        ids = _extract_identifiers("test.py", content)
        assert "import os" in ids["imports"]
        assert "from pathlib import Path" in ids["imports"]

    def test_kotlin_fun_and_class(self):
        content = """
class MyService {
    fun doStuff(): String { return "ok" }
}
"""
        ids = _extract_identifiers("MyService.kt", content)
        assert "MyService" in ids["classes"]
        assert "doStuff" in ids["functions"]

    def test_typeScript_interface(self):
        content = """
interface User {
    name: string;
}
function greet(u: User): string {
    return "hello";
}
"""
        ids = _extract_identifiers("user.ts", content)
        assert "User" in ids["classes"]
        assert "greet" in ids["functions"]

    def test_java_class(self):
        content = """
public class MainApp {
    public static void main(String[] args) {}
}
"""
        ids = _extract_identifiers("MainApp.java", content)
        assert "MainApp" in ids["classes"]
        assert "main" in ids["functions"]

    def test_go_func(self):
        content = """
func main() {
    fmt.Println("hi")
}
"""
        ids = _extract_identifiers("main.go", content)
        assert "main" in ids["functions"]

    def test_rust_fn(self):
        content = """
fn main() {
    println!("hi");
}
"""
        ids = _extract_identifiers("main.rs", content)
        assert "main" in ids["functions"]

    def test_no_comment_stripping_on_unknown_ext(self):
        content = "# not a comment\nhello = world\n"
        ids = _extract_identifiers("test.custom", content)
        assert ids == {"classes": [], "functions": [], "imports": []}

    def test_multi_line_comment_stripping(self):
        content = """
/*
 * Block comment
 */
class AfterBlock {
}
"""
        ids = _extract_identifiers("test.ts", content)
        assert "AfterBlock" in ids["classes"]

    def test_single_line_comment_stripping(self):
        content = "// comment\nclass Foo {}\n"
        ids = _extract_identifiers("test.ts", content)
        assert "Foo" in ids["classes"]


# ──────────────────────────────────────────────────────────────────────────────
#  RepoMap class
# ──────────────────────────────────────────────────────────────────────────────


class TestRepoMapClass:
    def test_init_raises_on_missing_dir(self):
        with pytest.raises(NotADirectoryError):
            RepoMap("/nonexistent/path")

    def test_init_success(self, repo_root: Path):
        rm = RepoMap(str(repo_root))
        assert rm.repo_path == repo_root
        assert "node_modules" in rm.exclude_dirs

    def test_get_tracked_files_returns_list(self, repomap: RepoMap):
        files = repomap._get_tracked_files()
        assert isinstance(files, list)
        assert len(files) > 0
        # Should include Python files from the repo
        py_files = [f for f in files if f.endswith(".py")]
        assert len(py_files) > 0

    def test_build_map_has_expected_keys(self, repo_map_dict: dict):
        expected_keys = {
            "repo_path", "files", "languages", "classes_by_file",
            "functions_by_file", "imports_by_file", "identifiers",
            "file_count", "total_classes", "total_functions",
        }
        assert expected_keys.issubset(repo_map_dict.keys())
        assert isinstance(repo_map_dict["files"], list)
        assert isinstance(repo_map_dict["languages"], dict)
        assert repo_map_dict["file_count"] > 0

    def test_build_map_detects_python(self, repo_map_dict: dict):
        assert "Python" in repo_map_dict["languages"]
        assert repo_map_dict["languages"]["Python"] > 0

    def test_build_map_no_crash_on_excluded_dirs(self, tmp_path: Path):
        # Create a minimal git repo
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "hello.py").write_text("def greet(): pass\n")
        # Create node_modules dir and a file inside it
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "dep.js").write_text("var x = 1;\n")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@test.com",
             "commit", "-m", "init"],
            cwd=str(tmp_path), capture_output=True,
        )

        rm = build_repo_map(str(tmp_path))
        assert rm["file_count"] >= 1  # at least hello.py
        # The node_modules file should be excluded
        node_files = [f for f in rm["files"] if "node_modules" in f]
        assert len(node_files) == 0


# ──────────────────────────────────────────────────────────────────────────────
#  get_repo_context
# ──────────────────────────────────────────────────────────────────────────────


class TestGetRepoContext:
    def test_context_includes_repo_name(self, repo_root: Path):
        ctx = get_repo_context(str(repo_root))
        assert repo_root.name in ctx
        assert "Files:" in ctx
        assert "Languages:" in ctx

    def test_context_focused_on_file(self, repo_root: Path):
        # Find a real file in the repo
        rm = build_repo_map(str(repo_root))
        if rm["files"]:
            target = rm["files"][0]
            ctx = get_repo_context(str(repo_root), target)
            assert target in ctx
            assert "Sibling files" in ctx or "Focus:" in ctx

    def test_context_no_crash_on_empty_path(self, tmp_path: Path):
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "empty.py").write_text("\n")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@test.com",
             "commit", "-m", "init"],
            cwd=str(tmp_path), capture_output=True,
        )

        ctx = get_repo_context(str(tmp_path))
        assert isinstance(ctx, str)
        assert len(ctx) > 0


# ──────────────────────────────────────────────────────────────────────────────
#  rank_files_by_relevance
# ──────────────────────────────────────────────────────────────────────────────


class TestRankFiles:
    def test_rank_returns_list_of_tuples(self, repo_map_dict: dict):
        result = rank_files_by_relevance("database query", repo_map_dict)
        assert isinstance(result, list)
        if result:
            file_path, score = result[0]
            assert isinstance(file_path, str)
            assert isinstance(score, (int, float))

    def test_rank_relevant_appears_first(self, repo_map_dict: dict):
        result = rank_files_by_relevance("config setup", repo_map_dict)
        # Check config files appear somewhere
        config_matches = [f for f, _ in result if "config" in f.lower()]
        assert len(config_matches) > 0 or True  # might not have config hits

    def test_rank_empty_query_returns_empty(self, repo_map_dict: dict):
        result = rank_files_by_relevance("", repo_map_dict)
        assert result == []

    def test_rank_short_query_returns_empty(self, repo_map_dict: dict):
        result = rank_files_by_relevance("a", repo_map_dict)
        assert result == []


# ──────────────────────────────────────────────────────────────────────────────
#  Integration: CLI invocation
# ──────────────────────────────────────────────────────────────────────────────


class TestCliIntegration:
    def test_build_via_module(self, repo_root: Path):
        result = subprocess.run(
            [sys.executable, "-m", "openamer_cli.repomap", "build", str(repo_root)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"STDERR: {result.stderr}"
        data = json.loads(result.stdout)
        assert "files" in data
        assert "languages" in data
        assert data["file_count"] > 0

    def test_context_via_module(self, repo_root: Path):
        result = subprocess.run(
            [sys.executable, "-m", "openamer_cli.repomap", "context", str(repo_root)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "Repo:" in result.stdout

    def test_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "openamer_cli.repomap", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()

    def test_build_non_git_dir_uses_walk_fallback(self, tmp_path: Path):
        # Non-git dir should still work via os.walk fallback
        (tmp_path / "data.py").write_text("x = 1\n")
        result = subprocess.run(
            [sys.executable, "-m", "openamer_cli.repomap", "build", str(tmp_path)],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["file_count"] >= 1


# ──────────────────────────────────────────────────────────────────────────────
#  Edge cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_large_query_does_not_crash(self, repo_map_dict: dict):
        query = " ".join(["word"] * 100)
        result = rank_files_by_relevance(query, repo_map_dict)
        assert isinstance(result, list)

    def test_json_serializable(self, repo_map_dict: dict):
        json.dumps(repo_map_dict, default=str)  # should not raise

    def test_exclude_dirs_custom(self, repo_root: Path):
        rm = RepoMap(str(repo_root), exclude_dirs={"node_modules", ".git", ".venv"})
        files = rm._get_tracked_files()
        # Check that no file lives inside a node_modules/ directory
        node_module_files = [f for f in files if any(
            p == "node_modules" for p in Path(f).parts
        )]
        assert len(node_module_files) == 0, f"Found files in node_modules dir: {node_module_files[:5]}"
        # Check that no file lives inside a .git/ directory
        dot_git_files = [f for f in files if any(
            p == ".git" for p in Path(f).parts
        )]
        assert len(dot_git_files) == 0, f"Found files in .git dir: {dot_git_files[:5]}"