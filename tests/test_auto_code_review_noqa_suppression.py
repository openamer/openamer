"""Tests for ``scripts/auto-code-review.py``'s ``# noqa:SEC`` suppression span.

Regression for a false-positive class that kept the review cron red.

The security scan resolves a finding's suppress comment by checking whether the
matched line carries ``# noqa:SEC``. It read that line from the match's *start*
only — ``file_lines[match_start_line - 1]``. A multi-line statement puts its
closing comment on the *last* line of the call, so every correctly annotated
multi-line call was still reported:

    conn.execute(                 <- match starts here: no comment
        f\"\"\"INSERT OR IGNORE ...
           WHERE task_id IN ({placeholders})
        \"\"\",  # noqa:SEC placeholders is a string of '?' only   <- comment here

Live evidence (cron, 2026-09-17T05:26): ``openamer_cli/kanban_db.py:3295``,
``SQL_RAW_QUERY_STRING`` at severity HIGH — a single false positive that made
the Auto Code Review job exit 2 (the security-alarm code) on every run, for
hours, while the same file's *other* annotated calls (line 2683, 2701) were
suppressed correctly because their comment happened to sit on the match line.

The invariant pinned here: a suppress comment silences the statement it closes
— the whole statement, and no more than that statement.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "auto-code-review.py"
_spec = importlib.util.spec_from_file_location("auto_code_review_noqa", _PATH)
if _spec is None or _spec.loader is None:  # pragma: no cover - import guard
    raise ImportError(f"Failed to load {_PATH}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

scan_file_for_security = _mod.scan_file_for_security
statement_suppressed = _mod.statement_suppressed


def _scan(tmp_path: Path, source: str) -> list[dict]:
    """Run the security scan over ``source`` as if it were a file in a repo."""
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    return scan_file_for_security("sample.py", tmp_path)


def _lines(source: str) -> list[str]:
    return source.split("\n")


# ── the live bug ─────────────────────────────────────────────────────────────


def test_multiline_call_with_trailing_noqa_is_not_reported(tmp_path):
    """The real shape: `conn.execute(` opens, the f-string spans, noqa closes it.

    Before the fix the scan read only line 1 of the match, found no comment, and
    reported a HIGH SQL-injection finding on correctly-annotated code.
    """
    source = (
        "def inherit(conn):\n"
        "    conn.execute(\n"
        '        f"""\n'
        "        INSERT OR IGNORE INTO kanban_notify_subs\n"
        "            (task_id, platform)\n"
        "        SELECT ?, platform\n"
        "          FROM kanban_notify_subs\n"
        "         WHERE task_id IN ({placeholders})\n"
        '        """,  # noqa:SEC placeholders is a string of \'?\' only; values are bound\n'
        "        (child_id,),\n"
        "    )\n"
    )

    assert _scan(tmp_path, source) == []


def test_the_very_finding_that_kept_the_cron_red(tmp_path):
    """Same statement, minus the comment: it must still be reported."""
    source = (
        "def inherit(conn):\n"
        "    conn.execute(\n"
        '        f"""\n'
        "        INSERT OR IGNORE INTO t SELECT ? FROM t WHERE task_id IN ({placeholders})\n"
        '        """,\n'
        "        (child_id,),\n"
        "    )\n"
    )
    findings = _scan(tmp_path, source)

    assert len(findings) == 1
    assert findings[0]["pattern_id"] == "SQL_RAW_QUERY_STRING"
    assert findings[0]["line"] == 2  # the `conn.execute(` line


def test_single_line_call_with_trailing_noqa_stays_suppressed(tmp_path):
    """The behaviour that already worked must not regress."""
    source = 'def f(conn, t):\n    conn.execute(f"DROP TABLE {t}_legacy")  # noqa:SEC fixed allowlist\n'

    assert _scan(tmp_path, source) == []


# ── the bound: it must not over-suppress ─────────────────────────────────────


def test_noqa_on_the_following_statement_does_not_suppress(tmp_path):
    """An unrelated commented statement below must not silence this finding.

    Without the indentation bound the walk would run on, meet the next
    statement's ``# noqa``, and silence a genuinely un-annotated call — trading a
    false positive for a false negative on the exact check that guards SQL
    injection.
    """
    source = (
        "def f(conn, t):\n"
        '    conn.execute(f"DROP TABLE {t}")\n'
        "    other = compute()  # noqa:SEC unrelated, documents something else\n"
    )

    findings = _scan(tmp_path, source)

    assert len(findings) == 1
    assert findings[0]["line"] == 2


def test_dedented_statement_ends_the_span(tmp_path):
    """A comment after the function body is not part of the call."""
    source = (
        "def f(conn, t):\n"
        '    conn.execute(f"DROP TABLE {t}")\n'
        "\n"
        "\n"
        "def g():  # noqa:SEC documents g\n"
        "    return 1\n"
    )

    findings = _scan(tmp_path, source)

    assert any(f["line"] == 2 for f in findings)


# ── statement_suppressed in isolation ────────────────────────────────────────


@pytest.mark.parametrize(
    "source, expected",
    [
        # marker on the opening line
        (["conn.execute(f\"DROP {t}\")  # noqa:SEC x"], True),
        # marker on the closing line of a multi-line call (the live case)
        (["conn.execute(", '    f"""SELECT"""', '"\"",  # noqa:SEC x'], True),
        # no marker anywhere
        (["conn.execute(", '    f"""SELECT"""', '",'], False),
        # closing paren at base indent still belongs to the statement
        (["conn.execute(", '    f"SELECT"', ")  # noqa:SEC x"], True),
        # a deeper-indented continuation without a marker
        (["conn.execute(", "        payload,", "    )"], False),
    ],
)
def test_statement_suppressed_spans(source, expected):
    assert statement_suppressed(source, 1) is expected


def test_statement_suppressed_is_bounds_safe():
    """Out-of-range starts must abstain, not raise."""
    assert statement_suppressed([], 1) is False
    assert statement_suppressed(["x = 1"], 999) is False


def test_blank_lines_inside_the_call_do_not_end_it():
    """A blank line with a deeper-indented continuation keeps the span open."""
    source = [
        "conn.execute(",
        '    f"SELECT"',
        "",
        "    ,  # noqa:SEC values bound",
    ]

    assert statement_suppressed(source, 1) is True


# ── the real file, when the repo is present ──────────────────────────────────


def test_kanban_db_has_no_security_findings_if_present():
    """The file the live failure came from, scanned as-is."""
    repo = Path(__file__).resolve().parents[1]
    target = repo / "openamer_cli" / "kanban_db.py"
    if not target.exists():  # pragma: no cover - checkout-dependent
        pytest.skip("kanban_db.py not in this checkout")

    findings = scan_file_for_security("openamer_cli/kanban_db.py", repo)

    assert findings == []
