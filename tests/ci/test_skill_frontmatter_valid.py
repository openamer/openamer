"""Every SKILL.md this repo ships must parse as YAML frontmatter.

The `Docs Site / docs-site-checks` job runs
`website/scripts/generate-skill-docs.py`, which `raise`s on the first malformed
frontmatter and fails the build. A bare `description: <text>` containing ": " is
enough to trigger it: that shipped 49 unparseable files once, three of them
(`skills/auto-generated/auto-internet-learning-*`) survived the cleanup and kept
Docs Site red on every run until they were repaired by hand.

This test is the guard that makes the class unrepeatable: the generator already
emits `json.dumps(...)` (a valid double-quoted YAML scalar), so a regression here
means something wrote frontmatter by hand.
"""
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SKILL_ROOTS = ("skills", "optional-skills")
_FM = re.compile(r"^---\r?\n(.*?)\r?\n---", re.S)


def _skill_files():
    for name in SKILL_ROOTS:
        root = REPO / name
        if root.is_dir():
            for p in sorted(root.rglob("SKILL.md")):
                if "node_modules" in p.parts:
                    continue
                yield p


def test_every_packaged_skill_has_parseable_frontmatter():
    files = list(_skill_files())
    assert files, "no SKILL.md found - are the roots right?"

    broken = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        match = _FM.match(text)
        if not match:
            broken.append((path, "no frontmatter"))
            continue
        try:
            front = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            broken.append((path, f"YAML error: {str(exc).splitlines()[0]}"))
            continue
        if not isinstance(front, dict) or not front.get("name"):
            broken.append((path, "frontmatter has no `name`"))

    assert not broken, "unparseable SKILL.md frontmatter:\n" + "\n".join(
        f"  {p.relative_to(REPO)}: {why}" for p, why in broken
    )
