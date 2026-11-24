# Proving (and enforcing) that the tree is your OWN system

Session 2026-11-07. The owner read the public README and said:

> "das gefaelt mir nicht das wir hermes architektur weiter stehen, wir muessen
> eigen alles haben, wir muessen openamer sein"

This is the **lineage-audit** class: not "port a file", but *"prove with numbers
that the shared parts are accounted for"*. The method, the metric bugs, and the
enforcement mechanism.

## The method: rebrand → diff → classify

Every upstream file is taken, run through the **same** rebrand map the port
tool applies, and diffed against the local counterpart:

| class | meaning |
|---|---|
| `IDENTICAL` | byte-identical after rebrand — still upstream, only renamed |
| `COSMETIC` | only header/import/docstring noise changed |
| `MINOR` | <10% of upstream lines changed |
| `SUBSTANTIVE` | real logic divergence |

Python core (`agent/`, `openamer_cli/`), measured over 210,738 upstream lines:

```
IDENTICAL       0 files       0 lines   0.00%
COSMETIC        0 files       0 lines   0.00%
MINOR          14 files    3,885 lines   1.84%
SUBSTANTIVE   373 files  206,853 lines  98.16%
openamer-only files: 841
```

Desktop (`apps/desktop/src/`), 934 same-path files of 3,593 upstream vs 1,045
local — 2,659 upstream-only files dropped, 111 local-only files:

```
IDENTICAL     163 files    12,259 lines   3.56%   <- before the marker pass
SUBSTANTIVE   654 files   309,260 lines  89.87%
```

**The desktop number is lower and that is the honest one.** A React component
library, a Zustand-style store and pure helpers have nothing product-specific
to differentiate — a fork keeps them, and rewriting them would cost lines
without buying behaviour. Report the asymmetry instead of averaging it away.

What the tree *dropped* from upstream is the stronger signal than what it kept:

| upstream dir | files dropped | what it was |
|---|---|---|
| `plugin-catalog/` | 977 | the plugin registry |
| `evals/` | 236 | the eval suite |
| `pm/` | 93 | the package manager |
| `hermes_platform/` | 30 | the platform abstraction |

## Three metric bugs the audit's own test caught

**1. `unified_diff` double-counts.** It emits a `-` AND a `+` line for every
modification, so a modified line counted twice and borderline files crossed the
10% threshold (5 changed lines in 100 → 10 "changes" → `SUBSTANTIVE` instead of
`MINOR`). Use `SequenceMatcher` opcodes and count a modified block once:

```python
matcher = difflib.SequenceMatcher(None, a, b)
for tag, i1, i2, j1, j2 in matcher.get_opcodes():
    if tag == "equal": continue
    removed, new = (a[i1:i2], b[j1:j2]) if tag == "replace" else ...
    upstream_changed += _substantive(removed)
    added           += _substantive(new)
return max(upstream_changed, added), added     # a modified block counts ONCE
```

The metric that survives is *"upstream lines that no longer survive unchanged"*
— the honest denominator for "how much of upstream is still here".

**2. The keep-pattern must run BEFORE the rename.** `@hermes/plugin-sdk` became
`@openamer/plugin-sdk` — a package that does not exist on npm — and the
branding guard then saw no upstream string in that line, so it reported **no
leak** and the broken import would have shipped. Protect → rename → restore.
(Already in SKILL.md; it is the same trap in a different costume.)

**3. A `--check-only` whole-tree grep produces false positives by
construction.** Worktrees, archived snapshots and scratch dirs live *inside* the
checkout. Measured: **177 hits, 0 real**. Separate three categories and make
the exit code depend on the leak count only:

```
leftover hermes tokens: 0
attributed upstream mentions: 13
```

## The coupling scan (the second half of the claim)

Line-level divergence does not prove independence if the runtime still imports
upstream. Scan the core tree for three things:

1. runtime imports of upstream module names → **NONE** (3,375 files scanned)
2. network/git pulls from the upstream repo → **NONE** (no updater, no CI path)
3. residual upstream token → 5 files, all non-runtime

Those 5 are legitimate and must stay documented, not deleted:

- the porting tool and the audit scripts themselves
- `scripts/update-safe.ps1` — a **protective** filter that refuses to kill
  upstream processes so the separate local upstream install is shielded from
  our update cycle
- `openamer_cli/identity.py` — a guard that *forbids* the upstream name from
  appearing as a claimed lineage in the identity file
- one upstream-derived skill reference

## The provenance marker: making it machine-checkable

A claimed lineage is worth nothing. A **marker** is worth something, because it
can be enforced by a test.

```
# Python — inside the module docstring
Upstream-Derived: hermes_cli/archive_safe.py @ bf1300b27c (MIT)

# TypeScript — leading line comment
// Upstream-Derived: apps/desktop/src/lib/json-format.ts @ e0325cf76 (MIT)
```

One regex finds both:

```python
MARKER_RE = re.compile(
    r"^\s*(?://\s*)?Upstream-Derived:\s*(?P<path>\S+)\s*@\s*"
    r"(?P<commit>[0-9a-f]{7,40})\s*\((?P<license>[^)]+)\)", re.MULTILINE)
```

### The commit must be the file's LAST upstream change — verify, don't guess

```bash
git -C "$UPSTREAM" log -1 --format=%H -- apps/desktop/src/<rel>
```

Then confirm the recorded sha really is the file's last state:

```python
at_sha = subprocess.run(["git","-C",str(UP),"show",f"{sha}:{up_rel}"], ...).stdout
cur    = (UP/up_rel).read_text(...)
assert at_sha == cur        # else the sha is stale, not the file's last change
```

Measured: 163/163 confirmed.

### Marker placement must respect the language

| rule | why |
|---|---|
| after a `'use client'` / `"use strict"` prologue | a directive must stay at the very top of the file to take effect — measured 5 desktop files |
| after an existing leading license/comment block | don't bury the licence header |
| otherwise as the first line | — |

**Insertion is byte-level and preserves each file's line endings** (CRLF vs
LF), so it can never rewrite a file wholesale. And it is **idempotent** — a
second run writes nothing.

### The marker must NOT shift the classification

The marker is a comment. If the audit counts it as a content change, every
marked file moves a class (e.g. `COSMETIC` → `MINOR`) and the numbers stop
meaning anything. Treat a marker line as noise:

```python
MARKER_LINE = re.compile(r"^\s*(?://\s*)?Upstream-Derived:\s*\S+\s*@\s*[0-9a-f]{7,40}\s*\([^)]+\)\s*$")
```

After the marker pass the desktop tree reports **0.00% verbatim** — every
previously-shared file is `COSMETIC`, differing by exactly one line.

## Enforcement: the contract test is the deliverable

The marker is worthless if a file can silently lose it. Pin it:

- every known derived file carries a marker
- the marker names a real upstream path and a hex commit
- `NOTICE` lists every derived file
- the shipped tree carries **zero unattributed** upstream names

**Read the marked-file list from the audit report, not from a hard-coded list**
— a hard-coded list drifts away from what the audit actually found, and the test
then passes on a stale set.

### The trap the contract test caught

`git checkout <file>` on a file whose marker was never committed **silently
removed the marker** — the file reverted to HEAD, which predates the pass. The
contract test caught it immediately (`2 failed`). Two lessons:

1. After any bulk edit, re-run the contract test **before** committing.
2. A `git checkout` "restore" is not a restore if the file was never committed —
   diff against what you intended, not against HEAD.

## The artefacts

Committed in the repo (so the claim is reproducible, not a one-off):

| path | role |
|---|---|
| `scripts/upstream_rebrand.py` | the ONE rebrand map (port tool + both audits import it) |
| `scripts/audit_upstream_independence.py` | Python core audit |
| `scripts/audit_upstream_independence_desktop.py` | desktop audit |
| `scripts/audit_upstream_coupling.py` | import/network/token scan |
| `scripts/insert_provenance_marker.py` | idempotent, byte-level marker insertion |
| `openamer_cli/upstream_provenance.py` | marker format + regex (single source) |
| `reports/upstream-independence-audit{,-desktop}.{json,md}` | the evidence |

`NOTICE` gained a section naming the derived group and pointing at the JSON
report for the per-file list — the attribution lives in **three** places (the
file, `NOTICE`, the report) and all three must agree.
