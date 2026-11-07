"""Provenance marker helper for OpenAmer files that derive from upstream work.

The marker is a machine-readable line that the upstream-independence audit
looks for, so a derived file can never be mistaken for original work and a
file that lost its attribution can be detected mechanically.

Format (one line, at the top of the module docstring):

    Upstream-Derived: <path> @ <commit> (MIT)

Usage in a module docstring:

    \"\"\"Short description.

    Upstream-Derived: openamer_cli/archive_safe.py @ bf1300b27c (MIT)
    \"\"\"
"""

from __future__ import annotations

import re

MARKER_RE = re.compile(
    r"^\s*Upstream-Derived:\s*(?P<path>\S+)\s*@\s*(?P<commit>[0-9a-f]{7,40})\s*\((?P<license>[^)]+)\)",
    re.MULTILINE,
)


def find_marker(text: str) -> dict[str, str] | None:
    """Return the provenance marker found in ``text``, or None."""
    match = MARKER_RE.search(text)
    if not match:
        return None
    return match.groupdict()


def has_marker(text: str) -> bool:
    """Return whether ``text`` carries an upstream provenance marker."""
    return MARKER_RE.search(text) is not None


def render(path: str, commit: str, license_name: str = "MIT") -> str:
    """Render the marker line for a module docstring."""
    return f"Upstream-Derived: {path} @ {commit} ({license_name})"
