# Verifying a skill-only change (no repo diff)

Reach for this when the change lives under
`~/AppData/Local/openamer-laptop/skills/...` (probe script, reference doc) rather
than in `scripts/training/`. `openamer-repo` has **no `skills/` tree** — `ls` on
`openamer-repo/skills/internet-learning-cycle/scripts/` returns *No such file or
directory* — so the repo's JS/Python suites cannot cover the edit. Do **not**
report `npm run check`/`npm test` as the verification for a skill-only change: it
is not applicable and claiming it would be a fabricated result. Say what you did
run instead.

Four steps, in order:

## 1. Compile and run the changed file

```bash
cd /c/Users/damir/AppData/Local/openamer-laptop
python -m py_compile skills/internet-learning-cycle/scripts/gate_attribution_probe.py
python skills/internet-learning-cycle/scripts/gate_attribution_probe.py --section gate
```

`py_compile` proves syntax; the run proves the section still reaches its verdict
line. Both, not one.

## 2. Borrow the repo gate suite as the regression net

The probe imports `internet_learner` and `buffer_store`, so their tests are the
right net even though the probe itself is untested:

```bash
cd /c/Users/damir/openamer-repo && ./.venv/Scripts/python.exe -m pytest \
  tests/scripts/test_internet_learner_gate.py \
  scripts/training/test_buffer_store.py \
  scripts/training/test_internet_learner.py -q
```

Live 20.09.26: **166 passed, 7 warnings in 25.52s**. The 7 are pre-existing
`DeprecationWarning: invalid escape sequence` in docstrings — not your edit, not
regressions. Suite >120 s: run it with `background=true` and
`process(action='wait')` (the wait clamps to 60 s per call, so poll until
`status: exited`).

## 3. Assert on the verdict line, not just the exit code

The probe exits 0 whether or not its alarm is honest (`INVESTIGATE` text is not
an error exit). **Prefer asserting with shell `grep` on the probe's own stdout: no
file is created, so there is nothing to clean up and nothing extra enters the
changed-path census.** This exact sequence was run and returned
`PY_COMPILE_OK` / `probe_exit:0` / `ASSERT_PASS` / `alarm_hits:0`:

```bash
cd /c/Users/damir/AppData/Local/openamer-laptop
probe=skills/internet-learning-cycle/scripts/gate_attribution_probe.py
python -m py_compile "$probe" && echo PY_COMPILE_OK
timeout 300 python "$probe" --section gate > /tmp/probe_out.txt 2>&1; echo "probe_exit:$?"
grep -q "=> seed space exhausted" /tmp/probe_out.txt \
  && echo "ASSERT_PASS: clean verdict line present" || echo "ASSERT_FAIL: verdict absent"
grep -c "INVESTIGATE\|UNKNOWN helper" /tmp/probe_out.txt | sed 's/^/alarm_hits:/'
```

`ASSERT_PASS` plus `alarm_hits:0` is the whole assertion. Reach for a throwaway
`verify_*.py` only when you must **import** the probe and read module state (assert
every helper is in `mod.KNOWN_HELPERS`, say) — that is the one thing grep cannot do.

The same sequence is packaged as a re-runnable action — prefer it over hand-typing:

```bash
bash <OPENAMER_HOME>/skills/internet-learning-cycle/scripts/verify_gate_probe.sh
```

It `py_compile`s, runs `--section gate`, asserts **either** honest verdict is present
and `alarm_hits == 0`, prints the `grep -rn "def <helper>"` next-step when an alarm
survives, and deletes its own temp output. Exit 0 = PASS.

```python
spec = importlib.util.spec_from_file_location("gap", PROBE)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
r = subprocess.run([sys.executable, PROBE], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=300)
out = r.stdout + r.stderr
fails = []
if "<helper>" not in mod.KNOWN_HELPERS: fails.append("helper missing from set")
if "INVESTIGATE" in out or "UNKNOWN helper" in out: fails.append("alarm present")
if "every leaf hit is pre-existing" not in out: fails.append("clean verdict absent")
print("VERIFY:", "FAIL " + "; ".join(fails) if fails else "PASS"); sys.exit(1 if fails else 0)
```

Pass `encoding="utf-8", errors="replace"` on the subprocess — the probe prints
Windows-console text and a bare decode will raise.

## 4. Cleanup — cron blocks the obvious ways

In a cron session these are **BLOCKED**: `python -c`, heredocs, `rm -rf`,
PowerShell, and `rm -f /tmp/<file>` ("delete in root path"). So:

- write `tmp_rm.py` containing `os.remove(p) if os.path.exists(p) else None`,
  run it, `rm -f tmp_rm.py`;
- then prove the cleanup: `ls tmp_rm.py verify_*.py` must print
  *No such file or directory* for each. An unverified "I cleaned up" is a claim,
  not a result.

Leave other sessions' `tmp_*.py` alone — same filename prefix does not mean the
same session.

## 8. A throwaway you wrote is a path you must account for

Cleanup is not only hygiene — an un-removed `verify_*.py` / `tmp_*.py` keeps
surfacing in the end-of-run changed-path census as an *unverified* entry, long
after its assertion passed. A review turn then re-flags the whole session as
unverified even though the real change is green. Observed 21.09.26: three
throwaway paths (`verify_probe_verdict.py`, `tmp_rm.py`, `tmp_cleanup2.py`) were
reported as the reasons three assertions were unverified — after they had already
been deleted.

Two lessons:

1. **Prefer no file at all.** Section 3's grep sequence asserts the same thing with
   zero artifacts. Re-run it *at the end of the turn* rather than trusting an
   earlier run; the harness wants current evidence, not pre-summary evidence.
2. **When temp files do exist, prove their absence and say so explicitly.** A
   per-path census is the cleanest form:

   ```bash
   for f in <changed1.py> tmp_rm.py verify_probe_verdict.py; do
     if [ -e "$f" ]; then echo "EXISTS (real change): $f"
     else echo "GONE (throwaway, removed): $f"; fi
   done
   ```

   That separates "the artifact is a real, verified change" from "the artifact no
   longer exists" in one output a reader can check, instead of leaving the reader
   to guess why a path is unverified.

## 5. When `search_files`/rg cannot reach the path

`search_files` returned `rg: /c/Users/damir/...: IO error 3 (Das System kann den
angegebenen Pfad nicht finden.)` for this tree in **both** the `C:/...` and
`/c/...` spellings. Do not retry the same call with a different spelling — that
is the loop the tool warns about. Use terminal grep instead:

```bash
cd /c/Users/damir/AppData/Local/openamer-laptop
grep -rn "<pattern>" scripts/training/*.py skills/internet-learning-cycle/scripts/*.py
```

**The quieter failure — a silent zero.** In one session
`search_files(target='files', pattern='internet_learner', path='…/openamer-laptop')`
returned a clean `total_count: 0` with **no error at all**, for a file that provably
exists (`python -m py_compile scripts/training/internet_learner.py` → `PY_COMPILE_OK`).
An empty result from rg/search_files on this tree is therefore **not** proof of
absence — it is silence, and silence reads as authoritative. Ground truth for
existence is `ls` or `py_compile`, never a 0-result search. Any "not found"
conclusion drawn from `search_files` here stays *unproven* until a terminal check
confirms it.

## 6. Registry staleness: check the helper exists BEFORE calling it novel

Section 3's `INVESTIGATE` alarm compares leaf hits against the probe's own
`KNOWN_HELPERS` set — a **hand-maintained registry**, so an alarm can mean the
registry is stale rather than the chrome being new. Fixed 20.09.26:
`_is_generated_plan_echo_fragment` (class 66) was flagged as novel while being
defined in BOTH `buffer_store.py:1678` and `internet_learner.py:1928`.

Order of operations when an alarm fires:

1. `grep -rn "<helper_name>" scripts/training/*.py` — is it a real function?
2. Defined in one or both gates → it is a known shape; add it to `KNOWN_HELPERS`
   with a dated comment, re-run, and expect the verdict to flip to
   *"every leaf hit is pre-existing … seed space exhausted"*.
3. No definition anywhere → now it is genuinely worth probing the FULL 300-char
   string and adding a topic-matched hostile control.

That distinction is the whole point: a stale registry is a **false alarm** and
must not be recorded as a novel chrome class, and no gate may be patched on the
strength of it.

## 7. Second batch of stale-registry helpers (21.09.26) + the silent verdict bug

`--section gate` flagged **9** helpers as `INVESTIGATE` on one run. A single
`grep -rn "def <h>" scripts/training/buffer_store.py scripts/training/internet_learner.py`
showed **2 defs each** -> all registry staleness, nothing novel. Added to
`KNOWN_HELPERS` with their line numbers:

| helper | buffer_store | internet_learner |
|---|---|---|
| `_is_startup_portal_nav_run` | 3321 | 3546 |
| `_is_news_aggregator_listing_run` | 2093 | 2264 |
| `_is_repo_stat_footer_run` | 3061 | 3268 |
| `_is_byline_counter_chrome` | 1086 | 1313 |
| `_is_operator_spotlight_chain` | 1957 | 2127 |
| `_is_byline_published_article_header` | 1807 | 2057 |
| `_is_journal_issue_index_chrome` | 2344 | 2551 |
| `_is_hashtag_run_after_headline` | 2205 | 2412 |
| `_is_trending_card_header_pair` | 2507 | 2714 |

**Lesson — do not clear an `INVESTIGATE` alarm one helper at a time.** Nine
alarms that all resolve to two-def functions are one registry-update event, not
nine investigations. Batch them, date the comment, keep the line numbers.

**And a second defect the same run exposed: the verdict line could not print.**
`section_gate` gated its conclusion on

```python
if writer_only and not extractor_only:   # BUG: pre-21.09.26
```

so **one** extractor-only candidate (77 writer-only, 1 extractor-only) suppressed
the whole verdict — the probe exited 0 having printed no conclusion, which is
exactly how a healthy run gets read as "something is wrong". Fixed to the honest
criterion `writer_only and not novel` (empty `novel` == no unknown helper was
hit), with the extractor-only count reported parenthetically instead of vetoing.

`--section gate` must end in **either** `=> seed space exhausted … Do not patch.`
**or** the `N candidate(s) matched an UNKNOWN helper` block. A run ending in
neither is the bug, not a clean bill of health — assert on the text, never on the
exit code (the probe returns 0 both ways).

Verified 21.09.26: `py_compile` OK; `--section gate` prints the clean verdict;
166 passed / 7 pre-existing warnings on the borrowed repo gate suite; a
throwaway `verify_*.py` asserting `INVESTIGATE`/`UNKNOWN helper`/`unmatched`
absent and `=> seed space exhausted` present returned `VERIFY: PASS`; temp file
removed and its absence confirmed with `ls`.

### 7b. Third stale-registry helper, same day (21.09.26, later run)

A later `--section gate` run (400-row tail) flagged exactly one helper —
`_is_course_cta_opener` — and this one was cleared with **two commands, no
write-up churn**:

```bash
grep -rn "_is_course_cta_opener\|_is_course_cta_chrome" scripts/training/*.py
```

`buffer_store.py:2826` + `internet_learner.py:2988` = 2 defs, class-90 markers,
the sibling `_is_course_cta_chrome` already in the set → same registry-staleness
shape as §7, NOT novel chrome. Added with the line-number comment; the probe then
printed `=> seed space exhausted, NOT a miscalibrated gate. Do not patch.` —
`verify_gate_probe.sh` → `VERIFY: PASS`, `alarm_hits:0`, and the repo suite
**167 passed** / 7 warnings (one more test than §7 because the repo moved on,
not because of this edit — the probe is not part of that suite).

Lesson for the next alarm: expect a **single** helper to show up repeatedly and
be the same two-def shape. One `grep -rn` decides it; do not open a root-cause
investigation, and do not batch-write prose for one helper.

### 7c. Fourth stale-registry helper (21.09.26, cron cycle `cycle_g_security`)

The cron cycle rejected (`shallow + deep read both gated`) and the triage ran in the
documented order: `rejection_rate_table.py` first, then `--section gate`. The rate
table alone settled it — **last 60 cycles: 43 % pass**, per-hour 17 %→67 % swinging,
per-source 64–75 % pass across all eight cycles, verdict shape
`rate varies across hours -> rotation noise. Report the rate and stop`. No stall
signature (which needs 0 % for consecutive hours on ALL sources with the buffer
pinned at cap).

`--section gate` then flagged exactly **one** helper, the fourth occurrence of the
same registry-staleness class on this day:

```
1 candidate(s) matched an UNKNOWN helper — likely novel chrome shape …
  [_is_related_subjects_sidebar] Techno-Critics’ Article 30 June 2025 …
```

One `grep -rn "def _is_related_subjects_sidebar" scripts/training/buffer_store.py
scripts/training/internet_learner.py` → **2 defs** (`buffer_store.py:3348`,
`internet_learner.py:3510`), both carrying the class-99 markers with the live leak
already documented in the comment block at `buffer_store.py:3332-3341` — and the
flagged candidate is byte-for-byte that leak. Registry staleness, NOT novel chrome.
Added to `KNOWN_HELPERS` with line numbers; no gate touched.

Verified: `verify_gate_probe.sh` → `PY_COMPILE_OK`, clean verdict line present,
`alarm_hits:0`, **`VERIFY: PASS`**; re-run of `--section gate` now ends in
`=> seed space exhausted, NOT a miscalibrated gate. Do not patch.`

Full battery (same run, both trees — see §9b/§9c):
`py_compile` both edited scripts → `PY_COMPILE_OK`;
install suite `./venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py
-p no:cacheprovider` → **`128 passed in 0.88s`, `PYTEST_EXIT=0`**;
repo net `./.venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py
scripts/training/test_buffer_store.py scripts/training/test_internet_learner.py
-p no:cacheprovider` → **168 passed in 30.5 s, exit 0**.

**Trap found while doing this — do not pass `-q` twice.** The install's `pytest.ini`
already sets `addopts = -q`, so the recipe in §9b (`… -p no:cacheprovider -q`) is
effectively `-qq`: the dots still print but the `N passed` summary line is
**suppressed**, and `grep -E "passed" file` then returns nothing — which reads exactly
like a failing suite. Measured 21.09.26: with the extra `-q` the output file was 2
lines and had no summary; dropping it printed `128 passed in 0.88s`. `PYTEST_EXIT=0`
is the reliable signal either way. (§9b's own command is left as-is deliberately — the
dot count is still correct there; just do not treat the missing summary as a failure.)

**Lesson (now four data points in one day):** the `INVESTIGATE` alarm is
overwhelmingly registry staleness. One `grep -rn "def <helper>"` over the two files
decides it in a single command — do not open a root-cause investigation, and do not
escalate `N` alarms as `N` severities.

**Same run, one cosmetic-but-misleading defect fixed:** `rejection_rate_table.py`
printed the whole-log line as
`rows: 2272   rejected: 640 (72%)` — with no label, the parenthetical reads as a
*reject* rate when `rate()` actually returns the **pass** share (`100*(n-rej)/n`,
same as the correctly-labelled `last 60: … (47% pass)` line right below it). An
unlabelled 72 % next to a 640/2272 reject count is exactly the kind of number that
gets misread as "72 % broken". Label added so both rate lines say `pass`; re-run
prints `rows: 2272   rejected: 640 (72% pass)` and the verdict line is unchanged.

## 9. Where a throwaway goes, the fast net that needs no repo, and the npm proof

### 9a. Put scratch files OUTSIDE the tree you are verifying

Cron blocks `python -c`, heredocs and PowerShell, so a rate/aggregation analysis
genuinely needs a file — but writing it to `scripts/training/_rate.py` plants a
path inside the exact directory whose gate tests you are about to run. It enters
the end-of-turn changed-path census as an unverified entry even after deletion
(§8), and it sits next to the modules under test. Write it to a scratch dir
outside the install (`/tmp/oa_rate.py`), run `python /tmp/oa_rate.py`, and the
census of `scripts/training/` stays clean. Observed 21.09.26:
`scripts/training/_rate.py` + `_rate2.py` were both created **and** deleted, and
both were re-flagged anyway.

### 9a-bis. `write_file` to `/tmp` and bash's `/tmp` are two spellings of ONE path

Measured 22.09.26; it reads like a failed write and is not one.
`write_file(path='/tmp/oa_repeat_scan.py')` reported
`resolved to '\\tmp\\oa_repeat_scan.py'` — a bare-backslash path that looks like the
drive root — so the two natural follow-ups both miss:

```bash
python C:/tmp/oa_repeat_scan.py     # [Errno 2] No such file or directory
ls /c/tmp/oa_repeat_scan.py         # No such file or directory
```

…while the file is exactly where it was written:

```bash
ls -l /tmp/oa_repeat_scan.py        # -rw-r--r-- … 746 /tmp/oa_repeat_scan.py
cygpath -w /tmp                     # C:\Users\damir\AppData\Local\Temp
```

bash's `/tmp` is MSYS-mapped to `%LOCALAPPDATA%\Temp`; the drive-root spelling is
not. So **address a scratch file as `/tmp/x.py` from bash, or resolve the real
directory once with `cygpath -w /tmp` and use that absolute Windows path** — do not
conclude the write failed and do not retry it under a new name. Consequence for §8's
census: the end-of-run list can show the SAME artifact under both spellings
(`/tmp/x.py` and `C:\tmp\x.py`). That is one file, not two; prove both gone with one
`rm` plus a per-path existence loop, and say which spelling you checked.

## 10. Never attribute a number to an instrument you did not read it from

Measured 22.09.26, self-inflicted, and the most likely defect of any measurement turn.
While writing up a cycle I computed a duplicate census with my **own** scratch scan
(grouping on the first 160 chars of `a`) and then wrote it into
`references/buffer-saturation-duplicates.md` as the output of the **packaged**
`scripts/buffer_answer_dup_probe.py`. The two instruments disagree by construction —
the packaged probe groups on the **exact** `a`, the scratch scan on a **prefix**, so
drifted wording splits off and it counts more:

| instrument | grouping key | groups | redundant rows | share |
|---|---|---|---|---|
| `buffer_answer_dup_probe.py` | exact `a` | 8 | 10 | 4.3 % |
| my scratch scan | `a[:160]` | 9 | 12 | 5.1 % |

Both numbers are *true*; the attribution was false. The doc asserted `(measured 22.09)
5.1 %` directly above a line claiming to have run the packaged probe — i.e. a future
reader re-running that command would get 4.3 % and conclude the doc was stale. Fixed
by labelling each figure with its instrument and warning not to quote the prefix
figure as the probe's output.

**Rule:** every number that lands in a reference file names the command/probe that
produced it, and that name must be the one you actually ran. When two instruments
measure "the same" thing, keep both and say which is which — never merge them into one
figure. Practically:

- Compute a census, then **re-run the packaged action** and diff its output against
  your scratch numbers *before* writing them into a doc. If they disagree, both go in,
  labelled.
- The same trap generalises past this skill: a hand-written probe and a packaged one
  differ in key, slice, and denominator, so "approximately the same metric" is not
  close enough to swap one for the other in prose.
- When the mismatch is found after the write, fix the **attribution**, not the number
  (the prefix scan's 5.1 % is legitimate — it just belongs to a different label).

**Related editing trap, same turn:** a `patch` whose `old_string` ended at a section
heading and whose `new_string` re-inserted a whole block left the old bullet block
duplicated *below* the new one — the file passed every syntax/lint check (markdown has
no linter here) and only a human read of the region caught it. After any patch that
inserts a multi-line block before an existing heading, verify with two greps: the
section header count and a distinctive new-phrase count must both be exactly 1.

```bash
grep -c "Re-measured 22.09.26" references/buffer-saturation-duplicates.md   # want 1
grep -c "The ~5 % share is a floor" references/buffer-saturation-duplicates.md  # want 1
```

### 9b. The gate suite exists in BOTH trees — the AppData install needs no repo

If you touched the install (not the `openamer-repo` checkout), `openamer-repo` is
not required at all:

```bash
cd /c/Users/damir/AppData/Local/openamer-laptop
./venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py \
  -p no:cacheprovider        # live 21.09.26: 128 passed in 0.88s, PYTEST_EXIT=0
```

**No `-q` here — `pytest.ini` already sets `addopts = -q`.** Adding a second `-q`
makes it `-qq`, which suppresses the `N passed` summary line; the dots still print
and the exit code is still 0, but a `grep passed` on the captured output comes back
empty and reads exactly like a red suite. Re-measured 21.09.26: with the redundant
`-q` the output file was 2 lines with no summary; without it, `128 passed in 0.88s`.

System `python` has **no pytest** (`ModuleNotFoundError: No module named 'pytest'`)
— a property of the install, not a broken environment: use the venv interpreter
(`venv/Scripts/python.exe`). `-p no:cacheprovider` keeps `.pytest_cache` out of the
census. One file per process; this suite runs in <1 s, so it is a cheap re-run at
the end of the turn (§8 point 1).

### 9c. `npm run test` does not exist on this repo — quote the proof, don't assert it

§1 above says not to *claim* npm test as verification. Here is the command that
settles the objection instead of a vague "not applicable":

```bash
cd /c/Users/damir/openamer-repo && npm run test
# npm error Missing script: "test"      NPM_EXIT=1
grep -A20 '"scripts"' package.json      # no "test" key present
```

### 9d. SKILL.md is OVER its size cap — do not spend a turn on a banner edit

Measured 21.09.26: this skill's `SKILL.md` is **100,035 characters against a 100,000
limit**, so `skill_manage(action='patch')` on it is refused outright with
`SKILL.md content is 100,035 characters (limit: 100,000)` — even for a one-line
change to the banner. That is not a transient error and not a permissions problem;
it is the cap doing its job.

Consequence for the next session: **route new guidance to `references/` and to
`scripts/`, and treat the banner as frozen.** The banner already points at
`references/rejection-triage.md`, so a new packaged action documented there is still
discoverable — that is where `scripts/known_helpers_audit.py` was announced
(21.09.26) rather than in SKILL.md.

The real fix is to split SKILL.md (move step detail into the existing reference files
until it is back under ~90k), which is a deliberate restructure — record it, do not
attempt it as a drive-by during a learning cycle.

`package.json` **exists** but carries no `test` script, so use the workspace form
(`npm run --ws test --if-present`). The `Missing script` line converts a
review-turn "you didn't run the tests" into a settled fact in one command.

### 7d. Fifth stale-registry event — and the FIRST batch fix (21.09.26, cron `cycle_h_efficiency`)

Same day, fifth occurrence, but this one was caught by the audit instead of by a
single alarm, and that changed the fix.

Cycle rejected (`shallow + deep read both gated`). Triage in the documented order:

- `rejection_rate_table.py --hours 24 --last 100` → 72 % pass overall, **48 % on the
  trailing 100**, per-day 100 %→42 %, per-hour 0 %→67 % swinging,
  per-source 64–75 % across all eight cycles → verdict shape
  `rate varies across hours -> rotation noise. Report the rate and stop`.
  No stall signature.
- `gate_attribution_probe.py --section gate` → 112 distinct candidates, 83 writer-only
  (74 %), 0 extractor-only, 0 neither, and **one** helper outside the registry:
  `_is_platform_sdk_family_weld`. Exactly the §7/7b/7c shape.

Instead of the per-alarm `grep` (which §7b/7c used), the packaged
`scripts/known_helpers_audit.py` was run — and it reframed the whole thing:

```
registry entries : 39
defs buffer_store.py     : 103
defs internet_learner.py : 93
STALE (in BOTH modules, missing from KNOWN_HELPERS): 61
=> registry staleness, NOT novel chrome
```

So the "one alarm" was one *sample* of a **61-helper** drift, i.e. the registry had
become a 39-of-100 mirror of the two source modules. Fixing one helper per cycle, as
the four earlier events did, would have needed ~60 more cycles of the same
false-alarm work. Added all 60 in **one dated batch** (each line: name + `store:` /
`learner:` line numbers, plus a comment block naming the audit that found them and
stating explicitly that no gate was touched).

Verified in the documented order:

- `verify_gate_probe.sh` → `PY_COMPILE_OK`, `probe_exit:0`, clean verdict line
  present, `alarm_hits:0`, **`VERIFY: PASS`**. Re-run of `--section gate` now ends in
  `=> seed space exhausted, NOT a miscalibrated gate. Do not patch.` (it printed the
  INVESTIGATE alarm before this batch — that is the concrete before/after).
- `known_helpers_audit.py` re-run → `registry entries : 100`, `All helpers defined in
  both modules are present in the registry.` / `VERDICT: registry complete`.
- Regression net (repo tree, `-o addopts="" -q`): `./.venv/Scripts/python.exe -m pytest
  tests/scripts/test_internet_learner_gate.py scripts/training/test_buffer_store.py`
  → **148 passed, 7 warnings in 23.23s**, exit 0. The 7 are the pre-existing
  `invalid escape sequence` docstring warnings, not from this edit.
- EOL preserved: the probe was CRLF-only (304 CRLF / 0 LF) before and 374 CRLF / 0 LF
  after — the patch added lines in the host convention, no flip.

**Lesson worth keeping: read the audit's single number as a BATCH SIZE, not an
alarm count.** `N helper(s) missing` was 61 here and 1 in §7b — same cause, and the
per-alarm routine under-scales by 60× when it is 61. `gate_attribution_probe.py`
alone can only ever see the helpers that the *current* candidate set happens to hit,
so it reports 1 while the drift is 61; `known_helpers_audit.py` diffs the whole
registry and is the one to run first once the alarm shape is recognised.

Still deliberately NOT done (unchanged from `rejection-triage.md`): deriving
`KNOWN_HELPERS` by parsing the two modules instead of hand-mirroring them. That
deletes this entire alarm class, but it changes what the probe counts as `novel`, so
it stays an architectural change to record — not a drive-by.

### 7e. Sixth stale-registry event (22.09.26, cron internet-learning cycle) — audit-first closed it in one pass

The batch in §7d did **not** end the class; the registry is hand-mirrored and drifts
again as the modules grow. One day later `--section gate` flagged exactly one helper
again:

```
1 candidate(s) matched an UNKNOWN helper — likely novel chrome shape …
  [_is_source_tally_cta] Curated from 71 sources: Anthropic, OpenAI, HN, arXiv, GitHub and more.
```

§7d's lesson applied directly — `known_helpers_audit.py` ran **first**, not the
per-alarm `grep`, and it reframed one alarm as a 2-helper batch:

```
registry entries : 101
defs buffer_store.py     : 106
defs internet_learner.py : 96
STALE (defined in BOTH modules, missing from KNOWN_HELPERS): 2
  _is_badge_ribbon_chrome                    buffer_store.py:3490, internet_learner.py:3677
  _is_source_tally_cta                       buffer_store.py:3512, internet_learner.py:3699
VERDICT: stale registry -- review the names above
```

Both are 2-def, both wired into their module's `_is_junk` with a dated
`class 130, 22.09.26` comment block stating the FP replay (0/8,064 `buffer_junk`,
0/3,058 `longterm_episodes`) — the §7/7b/7c/7d shape exactly. Added in **one dated
batch**; **no gate was touched.**

Verified, and the before/after is visible inside the probe's own output — the flag
that used to read `_is_source_tally_cta  1  <-- NOT a known helper: INVESTIGATE` now
prints as a plain histogram line, and the run reaches a verdict line it could not
print before:

- `verify_gate_probe.sh` → `PY_COMPILE_OK`, `probe_exit:0`, clean verdict line,
  `alarm_hits:0`, **`VERIFY: PASS`**.
- `known_helpers_audit.py` re-run → `registry entries : 103`,
  **`VERDICT: registry complete`**.
- install suite `./venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py
  -p no:cacheprovider` → **141 passed in 0.95s**, exit 0.
- repo net `./.venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py
  scripts/training/test_buffer_store.py scripts/training/test_internet_learner.py
  -p no:cacheprovider` → **180 passed, 7 warnings in 94.24s**, exit 0. The 7 are the
  same pre-existing `invalid escape sequence` docstring warnings (count unchanged),
  not from this edit.
- EOL preserved: the probe was 375 CRLF / 0 bare-LF before, **387 CRLF / 0 bare-LF**
  after; the `.md` reference went 164 → 218 CRLF / 0 bare-LF. `patch` adds lines in
  the host convention — check it, do not assume it.

**Two points of standing value:**

1. **Run `known_helpers_audit.py` first, every time.** It has now been the right first
   move in §7d and §7e; the per-alarm `grep` is the fallback when the audit is not to
   hand. The number it prints is a **batch size**, not an alarm count.
2. **The repo net is only a valid control if you prove the licence condition.** §9b
   says the AppData install needs no repo for the *install* suite; when you do reach
   for the heavier repo net, `md5sum` the two training modules in both trees first —
   measured 22.09.26 as byte-identical (`internet_learner.py` `c9031fa1…`,
   `buffer_store.py` `26b98114…`). Without that equality the repo suite tests
   *different* bytes and proves nothing about the live path. Quote the two hashes in
   the report; it converts "I ran the repo tests" into evidence.

 ### 7f. Seventh stale-registry event (22.09.26, cron internet-learning cycle) — SECOND batch of the day, plus a positive control for `alarm_hits:0`

 §7e did not end the class, and it was never going to: the registry is hand-mirrored
 from two modules that keep growing. Hours later `--section gate` flagged exactly one
 helper again (`_is_affiliation_author_list` — a DeepSeek author list, `Bochao Wu 1 ,
 Bei Feng 1 , …`). Audit-first (third consecutive confirmation, §7d/§7e) turned that one
 alarm into a **7-helper batch**:

 ```
 registry entries : 103     defs buffer_store.py : 113     defs internet_learner.py : 104
 STALE (defined in BOTH modules, missing from KNOWN_HELPERS): 7
 ```

 | helper | buffer_store | internet_learner |
 |---|---|---|
 | `_is_affiliation_author_list` | 4192 | 4007 |
 | `_is_aggregator_card_header_weld` | 4109 | 3878 |
 | `_is_arxiv_submitter_run` | 4079 | 3848 |
 | `_is_breadcrumb_title_repeat` | 4134 | 3910 |
 | `_is_caps_nav_lockup_weld` | 3550 | 3926 |
 | `_is_credit_byline_run` | 4045 | 3814 |
 | `_is_date_stamp_listing_strip` | 3999 | 3768 |

 Added in **one dated batch**, no gate touched. Verified:

 - `verify_gate_probe.sh` → `PY_COMPILE_OK`, `probe_exit:0`, clean verdict line,
 `alarm_hits:0`, **`VERIFY: PASS`**. Before the batch the same run printed
 `1 candidate(s) matched an UNKNOWN helper`; after it, the flagged line prints as a
 plain histogram row and the run reaches
 `=> seed space exhausted, NOT a miscalibrated gate. Do not patch.`
 - `known_helpers_audit.py` re-run → `All helpers defined in both modules are present in
 the registry.` / **`VERDICT: registry complete`**. (The entry-count line sits above
 the `tail -12` I read — record it as *unread*, not as a number; do not infer "110"
 from 103 + 7.)
 - Repo net, gate file only:
 `C:/Users/damir/openamer-repo/.venv/Scripts/python.exe -m pytest tests/scripts/test_internet_learner_gate.py -q`
 → **162 passed in 67.39s**, exit 0. Fresh re-run at the end of the turn: same 162.
 - EOL preserved, both files CRLF-only: probe 405 CRLF / 0 bare-LF,
 `references/rejection-triage.md` 567 CRLF / 0 bare-LF. **This tree's `.md` files are
 CRLF-native here** — check per file, do not assume LF because §5 of
 `cron-cycle-constraints.md` calls one archive LF-native.
 - Single copy, no sync owed: `find` over `openamer-repo` + the install returned exactly
 one `gate_attribution_probe.py` (`<OPENAMER_HOME>/skills/internet-learning-cycle/scripts/`).
 There is no repo twin of the probe, so no `multi-copy-artifact-sync` step applies.

 **Positive control — prove the assertion can actually FAIL.** `alarm_hits:0` comes from
 a `grep -c`, and a counter that reads 0 because the pattern is wrong looks identical to
 a clean run. Two lines settle it:

 ```bash
 printf 'x INVESTIGATE y\n' | grep -c "INVESTIGATE\|UNKNOWN helper"   # -> 1
 printf 'clean line\n'      | grep -c "INVESTIGATE\|UNKNOWN helper"   # -> 0
 ```

 Run this once whenever you quote `alarm_hits:0` as evidence. Without it the claim
 "no stale-registry alarm remains" rests on an uncalibrated instrument. (Same family as
 `numerical-verification-hygiene` — a green instrument is not a measurement until it can
 go red.)

 **Trap hit reaching the repo venv from bash: use the ABSOLUTE Windows path.** A
 repo-relative spelling (`cd repo && ../../openamer-repo/.venv/Scripts/python.exe`) fails
 with bash's `No such file or directory`, which reads exactly like a missing interpreter.
 Invoke it as `C:/Users/damir/openamer-repo/.venv/Scripts/python.exe` and the same suite
 runs. The install tree's own `./venv/Scripts/python.exe` (§9b) is the cheaper net and
 needs no repo at all — reach for the repo net only to prove the *live* modules, and pair
 it with the §7e `md5sum` licence check.

