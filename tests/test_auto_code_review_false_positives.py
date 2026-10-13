"""Tests for ``scripts/auto-code-review.py``'s false-positive filters.

Regression for the finding class that kept the Auto Code Review cron red.

Live evidence (cron, 2026-09-20): 128 files scanned, ``Security issues: 21,
Max severity: critical``, exit 2 — and only 2 of the 21 were real code:

* ``docs/generated/CHANGELOG.md`` L6783/L10092 (``shell=True``), L1174
  (``eval (``), L5964/L8491/L8890 (``exec (``) — markdown documentation that
  *talks about* those calls. Prose, not code.
* ``gateway/platforms/qqbot/adapter.py`` L13 ``client_secret: "your-secret"``
  and L22 ``apiKey: "your-...key"`` — shipped config *examples*.
* ``cli.py`` L9673 ``self.api_key = "moa-virtual-provider"`` — an internal
  sentinel, not a credential.
* ``openamer_cli/main.py`` L65 (a comment) and L10161 (an update docstring) —
  prose describing ``shell=True`` / ``exec()``.
* ``openamer_cli/main.py`` L14486/14487 — the regex matched *across* the
  newline inside ``getpass.getpass("  Password: ")`` prompt strings.
* ``scripts/training/smart_router.py`` L17 — the regex matched the tail of
  ``line.startswith("OPENROUTER_API_KEY=")``.

The invariant pinned here: the scanner reports *credentials*, not the words
around them. A real secret must survive every one of those filters.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "auto-code-review.py"
_spec = importlib.util.spec_from_file_location("auto_code_review_fp", _PATH)
if _spec is None or _spec.loader is None:  # pragma: no cover - import guard
    raise ImportError(f"Failed to load {_PATH}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

is_documentation_path = _mod.is_documentation_path
is_placeholder_secret = _mod.is_placeholder_secret
secret_match_is_placeholder = _mod.secret_match_is_placeholder
prose_line_numbers = _mod.prose_line_numbers
scan_file_for_security = _mod.scan_file_for_security


def _scan(tmp_path: Path, source: str, name: str = "sample.py") -> list[dict]:
    (tmp_path / name).write_text(source, encoding="utf-8")
    return scan_file_for_security(name, tmp_path)


# ── (1) documentation paths ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "filepath",
    [
        "docs/generated/CHANGELOG.md",
        "docs/guide/setup.md",
        "README.md",
        "CONTRIBUTING.es.md",
        "docs/api.rst",
        "website/notes.txt",
    ],
)
def test_documentation_paths_are_recognised(filepath):
    assert is_documentation_path(filepath) is True


@pytest.mark.parametrize(
    "filepath",
    [
        "cli.py",
        "gateway/platforms/qqbot/adapter.py",
        "docs/snippets/example.py",  # a real file inside a docs tree
        "scripts/auto-code-review.py",
    ],
)
def test_code_paths_are_not_treated_as_documentation(filepath):
    assert is_documentation_path(filepath) is False


def test_markdown_changelog_is_not_security_scanned(tmp_path):
    """The exact file/shape that produced 6 of the 21 findings."""
    source = (
        "# Changelog\n"
        "\n"
        "- fix: stop passing `shell=True` to the installer\n"
        "- replace `eval (` with a parser\n"
        "- removed `exec (` from the loader\n"
    )

    assert _scan(tmp_path, source, "CHANGELOG.md") == []


def test_python_snippet_inside_docs_is_still_scanned(tmp_path):
    """Excluding documentation must not create a hole for real code."""
    source = 'import subprocess\n\n\ndef f(c):\n    subprocess.run(c, shell=True)\n'

    findings = _scan(tmp_path, source, "example.py")

    assert [f["pattern_id"] for f in findings] == ["SHELL_TRUE"]


# ── (2) placeholder secrets ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        "your-secret",
        "your-...key",
        "your_api_key",
        "moa-virtual-provider",
        "changeme",
        "replace-me",
        "xxx",
        "XXX",
        "<your-key>",
        "{{token}}",
        "${API_KEY}",
        "placeholder",
        "example-value",
        "my-api-key-value",
        "sample-token-here",
        "test-token",
        "",
    ],
)
def test_placeholders_are_recognised(value):
    assert is_placeholder_secret(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "hunter2",
        "supersecretpassword",
        "sk-live-abcdefghijklmnop",
        "AKIAIOSFODNN7EXAMPLE",
        "aB3kL9mN2pQ7rS4tU8vW1xY",
        "abc123XYZdef456ghi789jkl",
        "P@ssw0rd123",
    ],
)
def test_real_secret_shapes_are_never_placeholders(value):
    assert is_placeholder_secret(value) is False


def test_config_example_placeholders_are_not_reported(tmp_path):
    """The real ``gateway/platforms/qqbot/adapter.py`` shape."""
    source = (
        '"""\n'
        "Configuration in config.yaml:\n"
        '    client_secret: "your-secret"     # or QQ_CLIENT_SECRET env var\n'
        '    apiKey: "your-...key"     # or set QQ_STT_API_KEY env var\n'
        '"""\n'
    )

    assert _scan(tmp_path, source) == []


def test_internal_sentinel_is_not_reported(tmp_path):
    """The real ``cli.py`` shape: an internal sentinel, not a credential."""
    source = 'def f(self):\n    self.api_key = "moa-virtual-provider"\n'

    assert _scan(tmp_path, source) == []


def test_a_real_hardcoded_secret_is_still_reported(tmp_path):
    """The check that must keep working — this is why the cron exits 2."""
    source = 'API_KEY = "sk-live-abcdefghijklmnop"\n'

    findings = _scan(tmp_path, source)

    assert [f["pattern_id"] for f in findings] == ["HARDCODED_API_KEY"]
    assert findings[0]["severity"] == "critical"


# ── (3) code fragments and prose ────────────────────────────────────────────


def test_keyword_inside_a_larger_string_is_not_reported(tmp_path):
    """The real ``scripts/training/smart_router.py`` L17 shape.

    The pattern matched ``API_KEY=") and len(line.split("`` — inside the string
    ``"OPENROUTER_API_KEY="``, i.e. never an assigned credential value.
    """
    source = (
        "def _load(env_path):\n"
        "    for line in open(env_path):\n"
        '        if line.startswith("OPENROUTER_API_KEY=") and len(line.split("=", 1)[1]) > 10:\n'
        "            return line\n"
    )

    assert _scan(tmp_path, source) == []


def test_password_prompt_string_is_not_reported(tmp_path):
    """The real ``openamer_cli/main.py`` L14486/14487 shape (match spans lines)."""
    source = (
        "import getpass\n"
        "\n"
        "\n"
        "def setup():\n"
        "    username = input('  Username [admin]: ').strip() or 'admin'\n"
        "    password = getpass.getpass('  Password: ')\n"
        "    confirm = getpass.getpass('  Confirm password: ')\n"
    )

    assert _scan(tmp_path, source) == []


def test_credential_passed_as_keyword_argument_is_still_reported(tmp_path):
    """A real literal in argument position is an assignment-shaped value."""
    source = 'conn.authenticate(password="hunter2xyz123")\n'

    findings = _scan(tmp_path, source)

    assert [f["pattern_id"] for f in findings] == ["HARDCODED_PASSWORD"]


def test_comment_only_lines_are_prose(tmp_path):
    """The real ``openamer_cli/main.py`` L65 shape."""
    source = (
        "# it shells out `cmd /c ver` (shell=True, no CREATE_NO_WINDOW), so\n"
        "# any dependency touching platform.uname() flashes a console.\n"
        "import os\n"
    )

    assert _scan(tmp_path, source) == []


def test_docstring_lines_are_prose(tmp_path):
    """The real ``openamer_cli/main.py`` L10161 shape."""
    source = (
        '"""Update helpers.\n'
        "\n"
        "1. SIGHUP is SIG_IGN. POSIX preserves it across exec(), so pip and git\n"
        "   subprocesses also stop dying on hangup.\n"
        '"""\n'
    )

    assert _scan(tmp_path, source) == []


def test_trailing_comment_does_not_hide_real_code(tmp_path):
    """A line with real code to the left of the comment is NOT prose."""
    source = 'import subprocess\n\n\ndef f(c):\n    subprocess.run(c, shell=True)  # documented pitfall\n'

    findings = _scan(tmp_path, source)

    assert [f["pattern_id"] for f in findings] == ["SHELL_TRUE"]


def test_secret_in_a_comment_is_still_reported(tmp_path):
    """The escape hatch: a leaked credential is a leak wherever it sits."""
    source = '# API_KEY = "sk-live-abcdefghijklmnop"\n'

    findings = _scan(tmp_path, source)

    assert [f["pattern_id"] for f in findings] == ["HARDCODED_API_KEY"]


def test_prose_line_numbers_for_python(tmp_path):
    source = "# comment\ndef f():\n    return 1  # trailing\n"
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")

    assert prose_line_numbers(source, "sample.py") == {1}


# ── (4) the statement_suppressed regression guard must still hold ────────────


def test_real_shell_true_call_is_not_suppressed_by_the_new_filters(tmp_path):
    """``scripts/system-snapshot.py`` L68 — a genuine finding, kept on purpose."""
    source = (
        "import subprocess\n"
        "\n"
        "\n"
        "def run_cmd(cmd, timeout=10):\n"
        "    r = subprocess.run(\n"
        "        cmd, capture_output=True, text=True, timeout=timeout,\n"
        "        shell=True, cwd=None\n"
        "    )\n"
        "    return r.stdout\n"
    )

    findings = _scan(tmp_path, source)

    assert [f["pattern_id"] for f in findings] == ["SHELL_TRUE"]
