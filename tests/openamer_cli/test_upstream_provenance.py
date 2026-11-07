"""Contract: every upstream-derived file carries a machine-readable provenance marker.

A derived file that loses its attribution is a license and honesty problem, so
the marker is not a comment convention -- it is checked here.

The test also asserts the marker points at a real upstream path/commit shape,
so a typo in a commit hash cannot pass silently.
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from openamer_cli.upstream_provenance import find_marker  # noqa: E402

# Files the independence audit proved are byte-identical to upstream after the
# rebrand. Every one of them must carry the marker.
DERIVED_FILES = [
    "agent/interrupt_compat.py",
    "openamer_cli/archive_safe.py",
    "openamer_cli/kanban_db_graph.py",
    "openamer_cli/kanban_swarm.py",
]

COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
PATH_RE = re.compile(r"^(agent|hermes_cli)/[A-Za-z0-9_/]+\.py$")


def test_every_derived_file_has_marker():
    missing = []
    for rel in DERIVED_FILES:
        path = REPO / rel
        assert path.is_file(), f"derived file missing from tree: {rel}"
        marker = find_marker(path.read_text(encoding="utf-8"))
        if marker is None:
            missing.append(rel)
    assert not missing, (
        "upstream-derived files without a provenance marker: " + ", ".join(missing)
    )


def test_marker_shape_is_valid():
    for rel in DERIVED_FILES:
        marker = find_marker((REPO / rel).read_text(encoding="utf-8"))
        assert marker is not None, rel
        assert COMMIT_RE.match(marker["commit"]), (
            f"{rel}: commit {marker['commit']!r} is not a hex sha"
        )
        assert PATH_RE.match(marker["path"]), (
            f"{rel}: upstream path {marker['path']!r} has an unexpected shape"
        )
        assert marker["license"].upper() == "MIT", (
            f"{rel}: unexpected license {marker['license']!r}"
        )


def test_notice_lists_every_derived_file():
    notice = (REPO / "NOTICE").read_text(encoding="utf-8")
    for rel in DERIVED_FILES:
        assert rel in notice, f"NOTICE does not mention derived file {rel}"


def test_marker_regex_matches_render_helper():
    from openamer_cli.upstream_provenance import render

    line = render("hermes_cli/archive_safe.py", "abcdef1", "MIT")
    assert find_marker(line) is not None
    assert "Upstream-Derived" in line
