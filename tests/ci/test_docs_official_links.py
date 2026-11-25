"""Every download link in the docs must point at the official repository.

Measured 2026-11-25: 27 links across 14 files (en landing page, installation
guide and 12 translated landing pages) pointed at
`github.com/openamer-max/desktop/...` — a repository that is not this project.
A visitor following "download the installer" left the project. The release
workflow now also publishes the installer under the stable name
`OpenAmer-Setup.exe`, so the official link keeps resolving across releases.

These tests pin both halves: no foreign repository in a download link, and the
stable alias documented where the docs point.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBSITE = REPO_ROOT / "website"
OFFICIAL_REPO = "https://github.com/openamer/openamer"
STABLE_SETUP = f"{OFFICIAL_REPO}/releases/latest/download/OpenAmer-Setup.exe"

DOCS = [
    p
    for p in list(WEBSITE.rglob("*.md")) + list(WEBSITE.rglob("*.mdx"))
    if "node_modules" not in p.parts and "build" not in p.parts
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_no_docs_file_links_to_a_foreign_repository_checkout() -> None:
    offenders = [str(p.relative_to(REPO_ROOT)) for p in DOCS if "openamer-max" in _text(p)]
    assert not offenders, (
        "these files link to a repository that is not github.com/openamer/openamer: "
        f"{offenders}"
    )


def test_every_installer_link_uses_the_official_repo() -> None:
    pattern = re.compile(r"https://github\.com/([^/\s)\"']+)/[^/\s)\"']+")
    bad: list[str] = []
    for path in DOCS:
        for match in pattern.finditer(_text(path)):
            href = match.group(0)
            if "OpenAmer-Setup" not in href and "releases" not in href:
                continue
            if not href.startswith(OFFICIAL_REPO):
                bad.append(f"{path.relative_to(REPO_ROOT)} -> {href}")
    assert not bad, f"installer links outside {OFFICIAL_REPO}: {bad}"


def test_the_stable_installer_alias_is_what_the_docs_point_at() -> None:
    hits = [str(p.relative_to(REPO_ROOT)) for p in DOCS if STABLE_SETUP in _text(p)]
    assert len(hits) >= 14, (
        "the stable installer URL should appear on the landing page, the install "
        f"guide and the 12 translated landing pages; found {len(hits)}: {hits}"
    )


def test_the_release_workflow_publishes_the_stable_alias() -> None:
    workflow = _text(REPO_ROOT / ".github" / "workflows" / "release-daily.yml")
    assert "OpenAmer-Setup.exe" in workflow, (
        "release-daily.yml must upload the installer a second time under the stable "
        "name, otherwise every docs download link 404s after the next release"
    )


def test_docs_show_no_other_products_ui() -> None:
    """Screenshots and copy of a different agent's UI must not ship here.

    Measured 2026-11-25: website/static/img/kanban-tutorial/ held 10 screenshots
    of another product's board (sidebar "HERMES AGENT", footer "HERMESTEAL").
    """
    banned = ("hermes", "nous research")
    hits = [f"{p.relative_to(REPO_ROOT)}: {w}" for p in DOCS for w in banned if w in _text(p).lower()]
    assert not hits, hits
    assert not (WEBSITE / "static" / "img" / "kanban-tutorial").exists()
