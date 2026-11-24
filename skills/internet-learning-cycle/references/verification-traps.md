# Verifying learner/gate changes — the two traps measured 21.09.26

Run this before reporting any verification result for `scripts/training/` work.

## Trap 1 — a root `npm run test` NOW EXISTS and is baseline noise

The skill body's older note ("no root `test` script, `npm run test` prints
`Missing script`") is **stale**. `openamer-laptop/package.json` gained `test`
(plus `test:research`), so `npm run test` succeeds in resolving and broadcasts to
the workspaces → runs `apps/desktop`'s vitest.

Measured 21.09.26:

```
Test Files  10 failed | 326 passed | 1 skipped (337)
     Tests  24 failed | 2996 passed | 2 skipped (3022)
```

**Those 24 failures are pre-existing, not yours.** Evidence, not assertion — this
host has **no `.git` at the repo root**, so `git diff` is unavailable and mtime is
the discriminator:

| Failing file | mtime |
|---|---|
| `electron/ssh-config.test.ts` | 08-22_19:44 |
| `electron/ssh-connection.test.ts` | 08-22_19:44 |
| `electron/update-relaunch.test.ts` | 08-22_19:44 |
| `electron/windows-openamer-path.test.ts` | 08-22_19:44 |
| `src/app/messaging/index.test.tsx` | 08-22_19:44 |
| `src/app/skills/index.test.tsx` | 08-22_19:44 |
| `src/i18n/context.test.tsx` | 08-22_19:44 |
| `src/i18n/languages.test.ts` | 08-22_19:44 |

All dated a month before the Python work. The stale side is the TEST, provably:
`src/i18n/languages.test.ts:26` asserts `normalizeLocale('de') === 'en'` ("de"
unsupported) while the shipped code correctly returns `'de'` —
`AssertionError: expected 'de' to be 'en'`.

**Reconcile the count before you panic:** the summary says `10 failed` FILES but
`24 failed` TESTS. Those are **8 test files + 2 failed *suites*** —
`scripts/before-pack.test.mjs` and `scripts/stage-native-deps.test.mjs`, both
also mtime `08-22_19:44`. 8 + 2 = 10. All ten pre-existing; none is yours.

**Extract the failing set reproducibly** (verified):
```bash
cd "$OPENAMER_HOME" && npm run --workspaces --if-present test > /tmp/npm.log 2>&1
tr '\r' '\n' < /tmp/npm.log > /tmp/npm.txt
grep -a " FAIL " /tmp/npm.txt | grep -aoE "(src|electron|scripts)/[a-zA-Z0-9/_.-]+\.(ts|tsx|mjs)" | sort -u
grep -aE "Test Files|Tests " /tmp/npm.txt | tail -2
```
Pitfall: `grep -E "^ ❯|failed)"` and `^ FAIL` return **EMPTY** — vitest indents the
`❯` summary lines and pads ` FAIL ` with three leading spaces, so anchor on the
bare ` FAIL ` substring. And do NOT grep `-iE "probe"` to find your own leftovers:
it matches *passing* test NAMES (`resolveVenvOpenAmerCommand: probes the venv
python …`), producing a phantom "my file is in the suite" reading. Check your
paths against the extracted failing set, not against the console log.

**Rule:** a learner/gate change is verified by the **pytest** suites. An
`npm run test` baseline of `24 failed / 2996 passed` is noise; never report it as
a regression caused by Python edits, and never try to "fix" those 24 to go green.

Prove your own edits left no trace with: (a) the changed paths' mtimes, and
(b) zero references to them from production code.

## Trap 2 — the gate suite must run ONE FILE PER PROCESS

The gate suite exists at TWO paths with the SAME basename:
`scripts/training/test_internet_learner_gate.py` and
`tests/scripts/test_internet_learner_gate.py`. Passing both in one `pytest`
invocation aborts the entire run:

```
import file mismatch:
HINT: remove __pycache__ / .pyc files and/or use a unique basename for your
test file modules
ERROR tests/scripts/test_internet_learner_gate.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

That is a **collection error, not a test failure** — and note that each file
passes fine on its own (133 tests), which is what makes it look mysterious.

Run one file per process:

```bash
cd "$OPENAMER_HOME"
for f in scripts/training/test_internet_learner.py \
         scripts/training/test_internet_learner_gate.py \
         scripts/training/test_buffer_store.py \
         tests/scripts/test_internet_learner_gate.py; do
  printf "%-46s " "$f"
  timeout 400 venv/Scripts/python.exe -m pytest "$f" -p no:cacheprovider 2>&1 \
    | tr '\r' '\n' | grep -E "^[0-9]+ passed|failed|error" | tail -1
done
```

Measured green 21.09.26 (pytest 9.1.1, Python 3.11.15, live venv):

```
scripts/training/test_internet_learner.py      24 passed in 0.16s
scripts/training/test_internet_learner_gate.py 133 passed in 0.82s
scripts/training/test_buffer_store.py          15 passed in 2.48s
tests/scripts/test_internet_learner_gate.py    133 passed in 0.71s
```

= **305 passed, 0 failed.** This is the evidence to quote for a learner change.

**Counts GROW — re-measure, never quote a remembered number (12.10.26).** The
same `tests/scripts/test_internet_learner_gate.py` now reads **213 passed**
(it was 133 on 21.09.26). A remembered count that no longer matches its file
reads exactly like a regression, so run it every time:

```bash
cd "$OPENAMER_HOME"
uv run --with pytest python -m pytest tests/scripts/test_internet_learner_gate.py -p no:xdist
# -> 213 passed in 1.15s   (12.10.26)
```

`uv run --with pytest` is the one-command alternative when neither the install
venv nor `openamer-repo/.venv` is on PATH: bare `python -m pytest` from
`OPENAMER_HOME` resolves to `openamer-agent/venv`, which has **no pytest**
(`No module named pytest`) — a wrong-interpreter line that reads like a red
suite (see `signal-vs-regression-triage.md` §2). `-p no:xdist` replaces the
`-p no:cacheprovider` above because the install's `pytest.ini` loads xdist and
its `-n` auto mode HANGS on this host (see `timeout-notes.md`).

Pitfall: `grep -oE "…passed"` on that output returns EMPTY — pytest writes the
summary on a `\r`-bearing line. Always pipe through `tr '\r' '\n'` first, or you
will read a green run as "no result".
