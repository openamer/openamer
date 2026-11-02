"""The CI duration-merge step must survive concatenated artifacts.

``actions/download-artifact`` with ``merge-multiple: true`` downloads every
same-named artifact into ONE file, concatenated. So ``durations/
test_durations.json`` contains a SEQUENCE of JSON objects, not a single one —
and ``json.load()`` on it raises ``JSONDecodeError: Extra data``.

Measured 2026-11-02 on a real run: the ``save-durations`` job failed with
``Extra data: line 213 column 1 (char 11498)`` and took the whole run red.
The merge step in ``.github/workflows/tests.yml`` must therefore decode every
object in the stream.

This test runs the SAME merge logic that the workflow executes, so the two
cannot drift apart.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import textwrap

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "tests.yml"


def _merge_step_source() -> str:
    """Extract the python program the workflow's merge step runs."""
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = "python3 -c \""
    start = text.index(marker) + len(marker)
    end = text.index("\"", start)
    raw = text[start:end]
    # The YAML block scalar keeps the shell's indentation. Dedent so the
    # program can be compiled as a standalone module.
    return textwrap.dedent(raw)


def _run_merge(tmp_path: Path, source: str, artifacts: dict[str, str]) -> dict:
    """Execute the workflow's merge program against the given artifacts."""
    durations = tmp_path / "durations"
    durations.mkdir()
    for name, content in artifacts.items():
        (durations / name).write_text(content, encoding="utf-8")
    program = source.replace("os.environ['GITHUB_OUTPUT']", "str(tmp_path / 'out')")
    namespace: dict = {"glob": __import__("glob"), "json": json, "tmp_path": tmp_path}
    # The program writes 'test_durations.json' relative to the working
    # directory, exactly as it does on the CI runner.
    previous = Path.cwd()
    os.chdir(tmp_path)
    try:
        exec(compile(program, "<merge-step>", "exec"), namespace)  # noqa: S102
    finally:
        os.chdir(previous)
    output = tmp_path / "out"
    assert output.exists(), "the merge step must write the GITHUB_OUTPUT count"
    count = dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if "=" in line
    )
    merged = json.loads((tmp_path / "test_durations.json").read_text(encoding="utf-8"))
    assert int(count["count"]) == len(merged)
    return merged


def test_merge_step_handles_concatenated_artifacts(tmp_path):
    """The real failure: two artifacts concatenated into one file."""
    source = _merge_step_source()
    first = json.dumps({"tests/a.py": 1.5, "tests/b.py": 2.5}, indent=2)
    second = json.dumps({"tests/c.py": 3.5}, indent=2)

    merged = _run_merge(tmp_path, source, {"test_durations.json": first + "\n" + second})

    assert merged == {"tests/a.py": 1.5, "tests/b.py": 2.5, "tests/c.py": 3.5}


def test_merge_step_handles_a_single_artifact(tmp_path):
    source = _merge_step_source()
    only = json.dumps({"tests/a.py": 1.5}, indent=2)
    merged = _run_merge(tmp_path, source, {"test_durations.json": only})
    assert merged == {"tests/a.py": 1.5}


def test_merge_step_handles_many_concatenated_artifacts(tmp_path):
    source = _merge_step_source()
    parts = [json.dumps({f"tests/file_{i}.py": float(i)}) for i in range(12)]
    merged = _run_merge(tmp_path, source, {"test_durations.json": "\n".join(parts)})
    assert len(merged) == 12


def test_merge_step_ignores_non_dict_payloads(tmp_path):
    """A stray non-object payload must not crash the merge."""
    source = _merge_step_source()
    payload = json.dumps({"tests/a.py": 1.0}) + "\n" + json.dumps([1, 2, 3]) + "\n"
    merged = _run_merge(tmp_path, source, {"test_durations.json": payload})
    assert merged == {"tests/a.py": 1.0}


@pytest.mark.parametrize("bad", ["", "   \n", "not json at all"])
def test_merge_step_tolerates_unparsable_artifact(tmp_path, bad):
    """A corrupt artifact must not take the whole CI run down."""
    source = _merge_step_source()
    merged = _run_merge(tmp_path, source, {"test_durations.json": bad})
    assert merged == {}
