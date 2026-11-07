"""Canonical upstream -> OpenAmer rebrand map.

One source of truth for the rename, shared by the porting tool and the
independence audits. The audits must apply the *exact* map the porting tool
applies, otherwise a file the port tool calls "rebranded upstream" is
audited under different rules and the two disagree.

The JS toolchain names (``hermes-parser``, ``@hermes/...``) are real npm
package names, not OpenAmer branding, so they are protected BEFORE the
generic rename. Renaming them would point the code at packages that do not
exist on npm.
"""

from __future__ import annotations

import re

# Ordered: longest / most specific first so partial renames can't fire early.
RENAMES: tuple[tuple[str, str], ...] = (
    ("hermes_cli", "openamer_cli"),
    ("hermes_constants", "openamer_constants"),
    ("hermes_state", "openamer_state"),
    ("hermes_logging", "openamer_logging"),
    ("hermes_platform", "openamer_platform"),
    ("get_hermes_home", "get_openamer_home"),
    ("get_default_hermes_root", "get_default_openamer_root"),
    ("hermes_home_key", "openamer_home_key"),
    ("set_hermes_home_override", "set_openamer_home_override"),
    ("reset_hermes_home_override", "reset_openamer_home_override"),
    ("get_hermes_home_override", "get_openamer_home_override"),
    ("HERMES_HOME", "OPENAMER_HOME"),
    ("HERMES_KANBAN", "OPENAMER_KANBAN"),
    ("HERMES_", "OPENAMER_"),
    ("`hermes ", "`openamer "),
    ("hermes-agent", "openamer-agent"),
    ("HermesAgent", "OpenAmerAgent"),
    ("HermesCLI", "OpenAmerCLI"),
    ("hermes_pkce", "openamer_pkce"),
    ("Hermes", "OpenAmer"),
    ("hermes", "openamer"),
)

KEEP_PATTERN = re.compile(r"hermes-(?:parser|estimator)|@hermes/")


def rebrand(text: str) -> str:
    """Apply the canonical rename, protecting the JS toolchain package names."""
    kept: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        kept.append(match.group(0))
        return f"\x00KEEP{len(kept) - 1}\x00"

    text = KEEP_PATTERN.sub(_stash, text)
    for src, dst in RENAMES:
        text = text.replace(src, dst)
    for index, value in enumerate(kept):
        text = text.replace(f"\x00KEEP{index}\x00", value)
    return text


def leftover_hermes(text: str, source_name: str) -> list[str]:
    """Return one report line per genuine upstream name left in ``text``."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if "hermes" not in line.lower():
            continue
        stripped = KEEP_PATTERN.sub("", line)
        if "hermes" in stripped.lower():
            hits.append(f"{source_name}:{lineno}: {line.strip()[:120]}")
    return hits
