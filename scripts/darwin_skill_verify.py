#!/usr/bin/env python3
"""darwin_skill_verify.py - run the check a skill claims, and record whether it passes.

Why this exists
---------------
Darwin's fitness already carries an outcome term: the probe score from
scripts/darwin_skill_probe.py, which asks whether the artifacts a SKILL.md
names still exist on disk. That question was sharp once, but the live
population has saturated it - almost every skill that survived earlier
generations references only files that resolve, so the average probe score is a
flat 1.0. A signal that reads 1.0 for every member of a population cannot rank
its members, and fitness that cannot rank cannot select. The probe is now
measuring the wrong thing.

The probe measured *static* facts: a path in the text either exists or it does
not. This verifier measures a *dynamic* one:

    when a skill writes down how to check that it works, does that check
    actually pass?

A SKILL.md that claims ``python -m pytest tests/test_x.py -q`` is making a
falsifiable promise. Running the command the skill itself declares is the only
way to turn that promise into a fact without an LLM, a human, or any tokens.
This is the distinguishing yardstick the probe no longer is: half the
population declares no runnable check at all, and of those that do, the ones
whose check fails are genuinely unfit.

Safety, not coverage
--------------------
Executing prose from a file is a large capability, and the skills directory is
not a trusted source: skills are generated, mutated and crossed by the Darwin
engine itself, and a mutated SKILL.md is code a language model wrote. So
execution is gated behind a strict allowlist - pytest, ``python [path.py]`` and
``bash/sh [script.sh]`` where every referenced path exists in the repo - and
nothing else ever runs. Everything not on the allowlist is recorded as
``not-allowlisted`` and never handed to a shell. This deliberately under-runs:
a skill whose check is a curl, a docker compose, or an ``openamer`` subcommand
is left unmeasured rather than guessed at. Unmeasured must never be scored as
failure (see Scoring), so under-running costs us signal, not correctness.

``subprocess.run`` is always called with an argv *list* and without
``shell=True``: the command is never re-parsed by a shell, so a ``|``, ``;`` or
``$(...)`` smuggled into a SKILL.md has no interpreter to reach. Combined with
the allowlist, the only thing that can ever execute is an argv whose first
token is one of the three sanctioned programs and whose path arguments all
exist.

One command per skill
---------------------
A verification section may list several commands. Running them all would make
the pass cost grow with population size and, worse, would let a flaky tail
command drag down a skill whose primary check is green. So at most the first
allowlisted command per skill is run; later ones are simply never reached.

Scoring
-------
score = 1.0 when ``passed`` is True,  1.0 when ``passed`` is None,
        0.0 when ``passed`` is False.

The ``passed is None`` case is the one that matters. A skill that declares no
check, or declares one this verifier refuses to run, is *unmeasurable* - it is
not a failure. Collapsing None into False would punish the entire half of the
population that documents itself in prose, which is exactly the population the
probe already fails to differentiate. None therefore scores 1.0, matching the
probe's "unmeasurable is not punished" rule.

Output: reports/darwin-verify.json

    {"updated": iso,
     "skills": {"<name>": {"declared": bool, "executed": bool, "allowed": bool,
                           "command": str|null, "returncode": int|null,
                           "passed": bool|null, "score": float, "reason": str}}}

CLI:
    python scripts/darwin_skill_verify.py           # scan, write report, summary
    python scripts/darwin_skill_verify.py --json    # also print the full report
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("OPENAMER_HOME") or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
SKILLS_DIR = HOME / "skills"
REPORT = REPO / "reports" / "darwin-verify.json"

# The per-command wall clock. 120s is generous enough for a real pytest file and
# short enough that a hung interpreter cannot stall a full-population sweep for
# long: with one command per skill the worst case is bounded by the population
# size, not by anything the command itself decides to do.
TIMEOUT_SECONDS = 120

# Canonical headings that mark a verification section. A heading matches when
# it *is* one of these, or when it *begins* with one followed by a separator -
# "Verification", "Verification Checklist", "Verify:" and "Verify, don't guess"
# are all the same promise. Matching only the bare word would have skipped
# "Verification Checklist", which is the single most common form in the live
# population and unambiguously a verification section.
_VERIFY_HEADINGS = ("verification", "verifikation", "verify", "validation", "testing")

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
_INLINE_RE = re.compile(r"`([^`\n]+)`")

# Interpreter spellings that count as "python" for the allowlist. The bare names
# are what SKILL.md files write; the .exe forms appear when a skill documents a
# Windows venv path explicitly.
_PYTHON_PROGS = ("python", "python3", "python.exe", "python3.exe")


# ─────────────────────────────────────────────────────────────────────────────
# Section discovery - find the block of a SKILL.md that promises a check
# ─────────────────────────────────────────────────────────────────────────────


def _normalise_heading(heading: str) -> str:
    """Strip markdown decoration so `**Verification:**` reads as `verification`."""
    text = heading.strip().strip("*_` ").strip()
    return text.lower()


def is_verification_heading(heading: str) -> bool:
    """True when a section heading announces a check (see _VERIFY_HEADINGS)."""
    normalised = _normalise_heading(heading)
    if not normalised:
        return False
    if normalised in _VERIFY_HEADINGS:
        return True
    first = normalised.split()[0].rstrip(":!.,")
    return first in _VERIFY_HEADINGS


def verification_sections(text: str) -> list[str]:
    """Return the body of every verification section, in document order.

    A section runs until the next heading *of the same or a higher level*, so a
    ``### Verify RED`` step nested inside ``## Verification`` stays part of the
    parent rather than truncating it. Cutting at any next heading would have
    dropped exactly the step-by-step subsections that carry the real commands.
    """
    lines = text.splitlines()
    sections: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        m = _HEADING_RE.match(lines[i])
        if m and is_verification_heading(m.group(2)):
            level = len(m.group(1))
            body: list[str] = []
            j = i + 1
            while j < n:
                nxt = _HEADING_RE.match(lines[j])
                if nxt and len(nxt.group(1)) <= level:
                    break
                body.append(lines[j])
                j += 1
            sections.append("\n".join(body))
            i = j
        else:
            i += 1
    return sections


# ─────────────────────────────────────────────────────────────────────────────
# Command extraction - code blocks and inline backticks only
# ─────────────────────────────────────────────────────────────────────────────


def _clean_candidate(line: str) -> str | None:
    """Turn one raw line into a candidate command, or None if it cannot be one.

    Prompts (`$ `, `> `, `PS>`) are stripped because a reader copies the command
    without them. Comment and prose lines are dropped: they are never runnable
    and letting them through only clutters the not-allowlisted bucket.
    """
    line = line.strip()
    if not line:
        return None
    # Comments are dropped before prompts are stripped: `# comment` must not be
    # mistaken for a `# ` prompt prefix and resurrected as the bare word
    # "comment". A `#` only ever means a comment here.
    if line.startswith(("#", "//", "<!--")):
        return None
    for prompt in ("$ ", "> ", "PS> ", "% "):
        if line.startswith(prompt):
            line = line[len(prompt):].strip()
            break
    if not line:
        return None
    return line


def extract_commands(text: str) -> list[str]:
    """Pull every runnable-looking command out of a SKILL.md body.

    Two sources, both explicitly demanded by the contract: fenced code blocks
    (one candidate per line) and inline backtick spans. Extraction is
    deliberately permissive - it does not try to decide what is a command -
    because the allowlist is the security boundary, not this function. A too
    broad extractor only produces more `not-allowlisted` entries, which are
    inert; a too narrow one loses signal.
    """
    commands: list[str] = []
    in_fence = False
    for raw in text.splitlines():
        if _FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            candidate = _clean_candidate(raw)
            if candidate:
                commands.append(candidate)
            continue
        for span in _INLINE_RE.findall(raw):
            candidate = _clean_candidate(span)
            if candidate:
                commands.append(candidate)

    deduped: list[str] = []
    for cmd in commands:
        if cmd not in deduped:
            deduped.append(cmd)
    return deduped


# ─────────────────────────────────────────────────────────────────────────────
# Allowlist - the security boundary
# ─────────────────────────────────────────────────────────────────────────────


def _path_exists(token: str, repo: Path) -> bool:
    """Is *token* a path that exists, resolved against the repo root?

    The repo root is the cwd the command will run in, so a repo-relative token
    is exactly what the shell-less executor will see. ``path::test_name`` is
    split first: pytest's node-id syntax names a real file plus a selector.
    """
    token = token.split("::", 1)[0].strip().strip("\"'")
    if token.startswith("./"):
        token = token[2:]
    if not token:
        return False
    candidate = Path(token)
    if candidate.is_absolute():
        return candidate.exists()
    return (repo / token).exists()


def _paths_exist(tokens: list[str], repo: Path) -> bool:
    # An empty path list is *not* a pass. `pytest -q` with no target would run
    # the whole suite, which is not the scoped check the skill claims and is far
    # too blunt to attribute to one skill; `python -m pip install x` has no
    # .py path at all. Both are left unmeasured rather than run on trust.
    if not tokens:
        return False
    return all(_path_exists(t, repo) for t in tokens)


def allowlisted(command: str, repo: Path = REPO) -> tuple[bool, list[str] | None]:
    """Decide whether *command* may run, returning (allowed, argv).

    The argv is returned alongside the verdict so the caller runs the exact
    tokens this function validated - re-splitting later would reopen a gap
    between what was checked and what executed.
    """
    try:
        # comments=True gives shell semantics for a trailing `#` comment, which
        # SKILL.md code blocks carry constantly ("pytest x.py -q   # 6 tests").
        # Without it the comment words become path arguments, fail the existence
        # check, and a perfectly runnable command is silently dropped as
        # not-allowlisted - the single biggest source of lost signal in a live
        # sweep. shlex only treats `#` as a comment when it starts a word, so a
        # `#` inside a quoted string survives.
        toks = shlex.split(command, comments=True)
        # Shell operators are a false-negative class, not a filter to relax.
        # `python a.py && echo ok` cannot work with an argv list, so running it
        # records a failure that says nothing about the skill. Refusing it is the
        # honest verdict - and honouring `&&` would mean invoking a shell, which
        # is exactly what the allowlist exists to avoid.
        if any(t in {"&&", "||", "|", ";", ">", ">>", "<"} for t in toks):
            return False, None
    except ValueError:
        # Unbalanced quote: not a command we understand, so not one we run.
        return False, None
    if not toks:
        return False, None

    # Compare on the basename so `./pytest` and `C:/.../python.exe` are still
    # recognised as their program; anything else keeps its full token and falls
    # through to "not allowlisted".
    prog = Path(toks[0]).name
    rest = toks[1:]

    if prog == "pytest" or (prog in _PYTHON_PROGS and rest[:2] == ["-m", "pytest"]):
        args = rest[2:] if prog in _PYTHON_PROGS else rest
        paths = [a for a in args if not a.startswith("-")]
        return (_paths_exist(paths, repo), toks)

    if prog in _PYTHON_PROGS:
        py_paths = [a for a in rest if a.split("::", 1)[0].endswith(".py")]
        return (_paths_exist(py_paths, repo), toks)

    if prog in ("bash", "sh"):
        sh_paths = [a for a in rest if a.split("::", 1)[0].endswith(".sh")]
        return (_paths_exist(sh_paths, repo), toks)

    return False, None


# ─────────────────────────────────────────────────────────────────────────────
# Execution
# ─────────────────────────────────────────────────────────────────────────────


def _run(argv: list[str], repo: Path) -> tuple[int | None, str | None]:
    """Run *argv* without a shell. Returns (returncode, error_reason).

    No ``shell=True`` and no string is ever built and handed to a shell: the
    argv from ``allowlisted`` is passed through verbatim. The environment is
    inherited (no ``env=``) so the check runs under the same interpreter and
    PATH as the caller - a skill's own documented command expects that.
    """
    try:
        proc = subprocess.run(
            argv,
            cwd=str(repo),
            timeout=TIMEOUT_SECONDS,
            capture_output=True,
            text=True,
        )
        return proc.returncode, None
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except OSError as exc:  # interpreter or program missing
        return None, f"launch-error: {exc}"


def _score(passed: bool | None) -> float:
    """Score semantics - see the module docstring. None is never punished."""
    return 0.0 if passed is False else 1.0


def verify_text(text: str, repo: Path = REPO) -> dict:
    """Verify the check a SKILL.md body declares.

    Split from the file reader so Darwin can judge a candidate that exists only
    in memory: mutate() produces a variant body and can ask "does *this* claim
    hold?" before deciding whether to keep it.
    """
    sections = verification_sections(text)
    if not sections:
        return {
            "declared": False,
            "executed": False,
            "allowed": False,
            "command": None,
            "returncode": None,
            "passed": None,
            "score": 1.0,
            "reason": "no verification section",
        }

    commands: list[str] = []
    for section in sections:
        for cmd in extract_commands(section):
            if cmd not in commands:
                commands.append(cmd)

    if not commands:
        return {
            "declared": True,
            "executed": False,
            "allowed": False,
            "command": None,
            "returncode": None,
            "passed": None,
            "score": 1.0,
            "reason": "verification section declares no command",
        }

    # At most the first allowlisted command runs. Later commands are never
    # reached on purpose (one-command budget, see module docstring).
    for command in commands:
        allowed, argv = allowlisted(command, repo)
        if not allowed:
            continue
        returncode, error = _run(argv, repo)
        if error is not None:
            return {
                "declared": True,
                "executed": True,
                "allowed": True,
                "command": command,
                "returncode": returncode,
                "passed": False,
                "score": 0.0,
                "reason": error,
            }
        passed = returncode == 0
        return {
            "declared": True,
            "executed": True,
            "allowed": True,
            "command": command,
            "returncode": returncode,
            "passed": passed,
            "score": _score(passed),
            "reason": "ran",
        }

    return {
        "declared": True,
        "executed": False,
        "allowed": False,
        "command": commands[0],
        "returncode": None,
        "passed": None,
        "score": 1.0,
        "reason": "not-allowlisted",
    }


def verify_skill(skill_md: Path, repo: Path = REPO) -> dict:
    """Verify the SKILL.md at *skill_md*."""
    return verify_text(skill_md.read_text(encoding="utf-8", errors="replace"), repo)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print the full report")
    args = ap.parse_args()

    if not SKILLS_DIR.is_dir():
        print(f"error: no skills directory at {SKILLS_DIR}", file=sys.stderr)
        return 1

    skills: dict[str, dict] = {}
    # rglob, not iterdir: skills live in category subdirectories too, and
    # iterating only the top level measured 81 of the 714 SKILL.md files on this
    # machine. Same defect the probe carried - fixed there first, mirrored here.
    for md in sorted(SKILLS_DIR.rglob("SKILL.md")):
        skills.setdefault(md.parent.name, verify_skill(md))

    report = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "skills_dir": str(SKILLS_DIR),
        "total": len(skills),
        "skills": skills,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    declared = [s for s in skills.values() if s["declared"]]
    executed = [s for s in skills.values() if s["executed"]]
    passed = [s for s in executed if s["passed"]]
    failed = [s for s in executed if s["passed"] is False]

    print(
        f"skills: {len(skills)} | declared a check: {len(declared)} | "
        f"executed: {len(executed)} | passed: {len(passed)} | failed: {len(failed)}"
    )
    for name, entry in skills.items():
        if entry["passed"] is False:
            print(f"  FAIL {name}: rc={entry['returncode']} {entry['command']}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())