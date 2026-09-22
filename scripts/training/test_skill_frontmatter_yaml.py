#!/usr/bin/env python3
"""Regression tests for SKILL.md frontmatter writer + repair.

The bug these guard (measured 2026-09-22): `auto_skill_creation.py` wrote
frontmatter values RAW, so any insight containing ": " (or a leading "-",
"[", "{", "*", "&", or a quote) produced YAML that PyYAML refuses to parse.
45 of the 97 files under `skills/auto-generated/` were unparseable, and the
strict consumer `website/scripts/generate-skill-docs.py` aborted on the first
one — killing the CI job "Docs Site / docs-site-checks" in the step
"Regenerate per-skill docs pages + catalogs" (that job has 0 successes in its
history; the workflow has been red since the writer landed).

Two halves are tested, because fixing only one half just moves the breakage:

  1. the WRITER emits YAML that parses strictly, for every shape that used to
     break it (incl. the four whose frontmatter was structurally mangled);
  2. the REPAIR script turns a broken file into an equivalent good one —
     values preserved as the runtime parser reads them, body untouched.

Run:  python scripts/training/test_skill_frontmatter_yaml.py
"""
import os
import subprocess
import sys
import tempfile

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

import auto_skill_creation as asc  # noqa: E402
import repair_skill_frontmatter as rep  # noqa: E402

_REPO = os.path.dirname(os.path.dirname(_HERE))

# The exact insight shapes that produced broken files on `main`. The first four
# are the ones whose `description` was multi-line/structured (a markdown list, a
# JSON fragment, a "user\n[..." tool-call echo) and therefore could not be
# repaired by quoting alone.
BREAKING_CASES = [
    ("Competitor intelligence: Crush: Glamourous AI coding agent for the terminal",
     "GitHub - skyiron/crushAIcodingAgent: The glamourous AI coding agent. "
     "The quickest way to get started: grab an API key."),
    ('The "AI agent hit piece" situation clarifies how dumb we are acting',
     'We are dealing with "low quality" contributions: a surge in spam.'),
    ("What makes a self-improving system safe?",
     "[\n  \"Question:\nuser\n[\n  \"Self-critique: a prompt\n\n* bullet\n- dash"),
    ("How does energy efficiency relate to intelligence scalability?",
     "1.  **Deconstruct the Query**:\n    *   Core subject 1: Energy efficiency (AI)."),
    ("Find the structural connection between tool use and planning",
     "Both\nuser\n[{\"tool\": \"web_search\", \"params\": {\"query\": \" x\"}}]"),
    ("Plain question", "A" * 200),
]


def _sandbox():
    d = tempfile.mkdtemp(prefix="skillfm_test_")
    asc.AUTO_SKILLS = os.path.join(d, "skills")
    asc.REGISTRY = os.path.join(d, "registry.json")
    os.makedirs(asc.AUTO_SKILLS, exist_ok=True)
    return asc.AUTO_SKILLS


def _frontmatter_of(text):
    """Split the way the strict consumer does."""
    parts = text.split("---", 2)
    assert len(parts) >= 3, "no frontmatter fences"
    return parts[1]


def test_writer_output_parses_strictly_for_every_breaking_shape():
    skills = _sandbox()
    for q, a in BREAKING_CASES:
        assert asc.create_skill_from_insight(q, a, "test") is not None, q
    checked = 0
    for root, _dirs, files in os.walk(skills):
        for name in files:
            if name != "SKILL.md":
                continue
            text = open(os.path.join(root, name), encoding="utf-8").read()
            fm = yaml.safe_load(_frontmatter_of(text))
            assert isinstance(fm, dict), f"{root}: frontmatter is not a mapping"
            assert fm["name"] and fm["description"], f"{root}: empty name/description"
            checked += 1
    assert checked == len(BREAKING_CASES), checked


def test_writer_keeps_the_value_the_runtime_parser_reads():
    """`description` must survive the round-trip, not be quoted into itself."""
    skills = _sandbox()
    q = "Question with a colon: here"
    a = "Answer with a colon: and an inner \"quote\"."
    asc.create_skill_from_insight(q, a, "test")
    path = os.path.join(skills, os.listdir(skills)[0], "SKILL.md")
    fm = yaml.safe_load(_frontmatter_of(open(path, encoding="utf-8").read()))
    assert fm["description"].startswith("Answer with a colon:"), fm["description"]
    assert not fm["description"].startswith('"'), fm["description"]
    assert "quote" in fm["description"]


def test_repair_fixes_a_broken_file_and_preserves_name_and_body():
    d = tempfile.mkdtemp(prefix="skillfm_rep_")
    body = "\r\n\r\n# Title\r\n\r\n## Trigger\r\nUse when: x\r\n"
    broken = (
        "---\r\n"
        "name: auto-demo\r\n"
        "description: GitHub - a/b: something with a colon and an unclosed \"quote\r\n"
        "auto_generated: true\r\n"
        "created: 2026-09-10\r\n"
        'source_insight: "Question: with a colon"\r\n'
        "status: draft\r\n"
        "wins: 0\r\n"
        "---" + body
    )
    sub = os.path.join(d, "skills", "demo")
    os.makedirs(sub)
    p = os.path.join(sub, "SKILL.md")
    open(p, "wb").write(broken.encode("utf-8"))

    fm_text, _ = rep.split_frontmatter(open(p, "rb").read().decode("utf-8"))
    assert not rep.parses_strictly(fm_text), "fixture must start broken"

    rc = subprocess.run(
        [sys.executable, os.path.join(_HERE, "repair_skill_frontmatter.py"),
         "--write", "--root", os.path.join(d, "skills")],
        capture_output=True, text=True, cwd=_REPO,
    )
    assert rc.returncode == 0, rc.stdout + rc.stderr

    after = open(p, "rb").read().decode("utf-8")
    fm = yaml.safe_load(_frontmatter_of(after))
    assert fm["name"] == "auto-demo"
    assert fm["description"].startswith("GitHub - a/b: something with a colon")
    assert fm["source_insight"] == "Question: with a colon", fm["source_insight"]
    # The body is not the repair's to touch — and the closing fence must still
    # be on its own line, or agent/skill_utils.parse_frontmatter silently
    # returns {} and the skill loses its name entirely (live defect: "wins: 0---").
    assert after.split("---", 2)[2] == body, repr(after.split("---", 2)[2])
    assert "wins: 0---" not in after


def test_repair_is_idempotent():
    d = tempfile.mkdtemp(prefix="skillfm_idem_")
    sub = os.path.join(d, "skills", "demo")
    os.makedirs(sub)
    p = os.path.join(sub, "SKILL.md")
    open(p, "wb").write(
        b'---\nname: auto-demo\ndescription: a: b\ncreated: 2026-09-10\n'
        b'source_insight: "q: r"\nwins: 0\n---\n\nbody\n'
    )
    cmd = [sys.executable, os.path.join(_HERE, "repair_skill_frontmatter.py"),
           "--write", "--root", os.path.join(d, "skills")]
    assert subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO).returncode == 0
    once = open(p, "rb").read()
    assert subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO).returncode == 0
    assert open(p, "rb").read() == once, "second pass changed the file"


def test_repair_does_not_touch_already_valid_files():
    d = tempfile.mkdtemp(prefix="skillfm_valid_")
    sub = os.path.join(d, "skills", "demo")
    os.makedirs(sub)
    p = os.path.join(sub, "SKILL.md")
    good = b'---\nname: auto-ok\ndescription: "fine: yes"\ncreated: 2026-09-10\n---\n\nbody\n'
    open(p, "wb").write(good)
    rc = subprocess.run(
        [sys.executable, os.path.join(_HERE, "repair_skill_frontmatter.py"),
         "--write", "--root", os.path.join(d, "skills")],
        capture_output=True, text=True, cwd=_REPO,
    )
    assert rc.returncode == 0, rc.stdout
    assert open(p, "rb").read() == good, "a valid file was rewritten"


def test_every_tracked_skill_md_parses_strictly():
    """The end state the CI step needs: no SKILL.md aborts the strict parser."""
    bad = []
    for root in ("skills", "optional-skills"):
        base = os.path.join(_REPO, root)
        for r, _dirs, files in os.walk(base):
            for name in files:
                if name != "SKILL.md":
                    continue
                rel = os.path.relpath(os.path.join(r, name), _REPO)
                text = open(os.path.join(r, name), "rb").read().decode("utf-8")
                fm_text, _body = rep.split_frontmatter(text)
                if fm_text is None or not rep.parses_strictly(fm_text):
                    bad.append(rel)
    assert not bad, f"strict-YAML failures: {bad}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001 - report, don't mask
            failed += 1
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
