"""Tests for ``scripts/auto-code-review.py``'s long-function detector.

Regression for a false-positive class that turned the review cron into noise.

The detector's function pattern begins ``^\\s*``, and ``\\s`` matches newlines as
well as spaces. When the line above a ``def`` is blank — the normal style between
class methods and a mandatory one between top-level functions — the match starts
on that *blank* line. ``len(line) - len(line.lstrip())`` then reads the indent
from an empty string, i.e. 0, so the end-of-function walk never sees a line
"less indented than the def" and runs on until the next real col-0 line. A
5-line method inside a long class body was reported as a 700-line offender.

Live evidence (cron, 2026-09-16T20:51): 36 such findings in one 1043-line file,
each reported length plus its reported line summing to the same constant — the
signature of "measured to the end of the enclosing block", not of length.

The invariant pinned here: a reported length is the *function's* length, and the
reported line is the ``def`` line — not the blank line above it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "auto-code-review.py"
_spec = importlib.util.spec_from_file_location("auto_code_review", _PATH)
if _spec is None or _spec.loader is None:  # pragma: no cover - import guard
    raise ImportError(f"Failed to load {_PATH}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check_long_functions = _mod.check_long_functions
check_missing_type_hints = _mod.check_missing_type_hints


def _scan(tmp_path: Path, source: str) -> list[dict]:
    """Run the detector over ``source`` as if it were a file in a repo."""
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    return check_long_functions("sample.py", tmp_path)


def _by_name(findings: list[dict]) -> dict[str, dict]:
    return {f["message"].split("'")[1]: f for f in findings}


def _body(prefix: str, lines: int) -> str:
    return "\n".join(f"{prefix}pass" for _ in range(lines))


# ── the live bug ─────────────────────────────────────────────────────────────


def test_short_methods_in_a_long_class_body_are_not_reported(tmp_path):
    """The real shape: methods at indent 4, then a long class body, no col-0 line.

    Before the fix the walk ran from the blank line above each method to the end
    of the file, so both short methods were reported as ~77-line offenders.
    """
    source = (
        "class Big:\n"
        "\n"
        "    def first(self):\n"
        "        return 1\n"
        "\n"
        "    def second(self):\n"
        "        return 2\n"
        "\n"
        + "".join(f"    attr{i} = {i}\n" for i in range(70))
    )

    assert _scan(tmp_path, source) == []


def test_reported_line_is_the_def_line_not_the_blank_above_it(tmp_path):
    """A genuinely long function is reported at its own ``def``, with its own length."""
    source = (
        "def small():\n    return 1\n"
        "\n\n"
        f"def big():\n{_body('    ', 80)}"
        "\n\n"
        "def after():\n    return 2\n"
    )
    findings = _scan(tmp_path, source)

    assert [f["line"] for f in findings] == [5]  # `big`'s `def`, not the blank line 4
    assert "is 81 lines long" in findings[0]["message"]  # `def` + 80 body lines
    assert findings[0]["pattern_id"] == "LONG_FUNCTION"


def test_reported_length_describes_the_function_not_the_enclosing_block(tmp_path):
    """The bogus-length signature: line + length must not be a constant."""
    nested = f"def outer():\n\n    def inner():\n{_body('        ', 60)}"
    by_name = _by_name(_scan(tmp_path, nested))

    assert by_name["inner"]["line"] == 3  # not the blank line 2
    assert "is 61 lines long" in by_name["inner"]["message"]
    assert by_name["outer"]["line"] == 1
    # Each length is its own span — the old code gave both the same span end.
    assert {f["line"] + int(f["message"].split("is ")[1].split(" ")[0]) for f in _scan(tmp_path, nested)} == {1 + 63, 3 + 61}


# ── behaviour that must keep working ─────────────────────────────────────────


def test_short_functions_are_not_reported(tmp_path):
    assert _scan(tmp_path, "def a():\n    return 1\n\n\ndef b():\n    return 2\n") == []


def test_blank_lines_inside_a_function_do_not_end_it(tmp_path):
    """Blank lines *inside* a function are body, not a terminator."""
    findings = _scan(tmp_path, f"def padded():\n{_body('    ', 30)}\n\n\n{_body('    ', 30)}")

    assert len(findings) == 1
    # `def` + 2×30 body lines + the 2 interior blanks = 63.
    assert "is 63 lines long" in findings[0]["message"]


def test_async_functions_are_detected(tmp_path):
    findings = _scan(tmp_path, f"async def long_one():\n{_body('    ', 60)}")

    assert len(findings) == 1
    assert findings[0]["message"].startswith("Function 'async long_one'")


def test_missing_type_hint_points_at_the_def_line(tmp_path):
    """Same ``^\\s*`` bug in the sibling check: it reported the blank line above."""
    source = "def a(): return 1\n\n\ndef b(): return 2\n"
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")

    lines = [f["line"] for f in check_missing_type_hints("sample.py", tmp_path)]

    assert lines == [1, 4]  # `def b` is on 4, not the blank line 2
    for f in check_missing_type_hints("sample.py", tmp_path):
        assert f["line_content"].strip().startswith("def ")


@pytest.mark.parametrize("indent", ["", "    ", "\t"])
def test_exactly_fifty_lines_is_not_reported(tmp_path, indent):
    """Boundary: the rule is ``> 50``, so a 50-line function passes."""
    assert _scan(tmp_path, f"def f():\n{_body(indent, 49)}") == []
