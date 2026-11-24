---
name: upstream-porting-workflow
description: "Use for upstream porting: discover, brand, validate, commit, and sync the runtime tree."
---

# Upstream Porting Workflow

Port features from upstream repos into OpenAmer with full branding, validation, and clean history.

**A port is not DONE until the runtime tree has it and the canonical test proves it.**
Three closing steps that this skill treats as part of the job, not extras:

1. `scripts/runtime_tree_parity.py --from-git <your-commits>` → exit 0 (sync any
   REAL diff; the running install lags silently and green repo tests prove nothing
   about it).
2. Run the **ported test** (the consumer's real call shape) — not a probe you wrote
   after reading the code, which shares your blind spot. See trap 4 below.
3. **Prove what actually reached the REMOTE.** This checkout's `main` is its own
   divergent lineage, so the commits pile up locally and the work *feels* landed:
   every commit is real, every test is green, and none of it has left the machine.

   Measured 2026-10-12 — asked "did you push everything", the answer was **62
   unpushed commits on local `main`**, plus 15 uncommitted files that included two
   finished product fixes (a verified 8-red-test port and a verified 4-test product
   fix). The five PR branches were current; the lineage holding most of the day's
   work was not. A cluster of green runs says nothing about this.

   ```bash
   git log --oneline origin/main..HEAD | head    # unpushed on this branch
   git status --short | wc -l                    # uncommitted
   gh pr list --state open --limit 10            # what actually reached the remote
   ```

   Run all three before the word "pushed". And when the answer is "no", separate the
   two reasons, because they call for opposite handling: commits on the divergent
   lineage *should* go out (as a PR — never a direct push to `main`), while a
   working-tree file that came from **another** process (cron auto-commits, the
   Darwin loops writing `darwin-status.json` / `session_to_brain*`) must NOT be swept
   into yours. Naming which is which is the whole value of the check.

 Three measured additions (2026-10-13) — the remote is a second, independent
 failure surface from the lineage:

 **An EMPTY cherry-pick onto `origin/main` means upstream ALREADY HAS IT: the
 fix is local, do not push it.** Repairing `plugins/platforms/feishu/adapter.py`
 (methods it called but never defined — see the recurrence section above)
 produced `nothing added to commit but untracked files present` when
 cherry-picked onto `origin/main`, because `origin/main` defines both methods at
 lines 2870/2888. That silence *is* the signal: the defect is a port **loss in
 this lineage**, not an upstream bug, and the commit belongs on the local branch
 only. A non-empty cherry-pick is the opposite — upstream needs it. Either way,
 say which direction it is instead of assuming "every bug here is a bug for
 everyone".

 **Never build the PR branch from local HEAD.** Measured: `git branch -f <name>
 HEAD` put **76 commits over `origin/main`** on the remote in one command — the
 entire divergent lineage, not the one fix. Build it on the upstream tip and
 carry only your own work:

 ```bash
 git worktree add -f C:/Users/<you>/wt-pr origin/main     # shares the object DB
 cd C:/Users/<you>/wt-pr
 git checkout -B <branch> origin/main                     # detached -> named tip
 git cherry-pick <sha> [<sha> ...]                        # only YOUR commits
 git diff --stat origin/main...HEAD                       # expect your files only
 ```

 **The same trap, second form (live 2026-11-07): a PR branch carrying CRON
 REPORT FILES can never merge.** A docs+audit PR opened from a long-lived
 feature branch flipped to `mergeStateStatus: DIRTY` / `CONFLICTING` the moment
 `main` moved — because the branch carried ~40 cron-generated
 `reports/darwin-*.json` + `reports/trend-scout-*.md` files that `main` also
 has, plus an unrelated feature. **The fix is the worktree recipe above, not a
 rebase** — a rebase onto a moving `main` just conflicts in the *generated*
 report files (no correct merge exists; `git checkout --theirs` + `git add` +
 `GIT_EDITOR=true git rebase --continue` is the only way through, and the next
 cron tick overwrites them anyway). Cherry-picking onto `origin/main` in a
 fresh worktree sidesteps it entirely.

 **Under MSYS, `git worktree add /c/tmp/x` lands at `C:/c/tmp/x` — and
 `cd /c/tmp/x` then fails with "No such file or directory".** Use the native
 `C:/tmp/x` form when creating, and always read the real path back from
 `git worktree list` before `git worktree remove` (which rejects the MSYS
 spelling with "is not a working tree"). Re-read `git worktree list` after
 every worktree op — a leftover entry keeps the branch locked.

 **A dirty working tree is the reason to use a worktree, not to stash.** In a
 cron-committing repo `git checkout <branch>` fails with "Your local changes …
 would be overwritten"; the untracked leftovers are foreign (`nul`,
 `_tmp_*.ps1`, fresh `reports/trend-scout-*.md`). A worktree gives the branch
 without touching the dirty tree at all. Related: an untracked file that
 already exists on `origin/main` blocks a rebase too — diff it against
 `git show origin/main:<path>` BEFORE deleting it; identical means redundant,
 different means it is real work and must be moved aside, never deleted.

 Full trap list, the `gh pr merge --admin` path, the merge-verification
 (`merge-base --is-ancestor` + reading `origin/main:<file>`), and the
 end-to-end reliable sequence: `references/pr-branch-hygiene-on-a-busy-main.md`.

 **A patch you hand-apply onto the `origin/main` worktree needs its ANCHORS re-verified — the local lineage is NOT the base.** Measured 2026-10-13 (a learner gate fix, local `main` 90 ahead / 86 behind `origin/main`): an insertion anchor that held in the running copies (`…_is_site_nav_chain(text):` / `return True` immediately before `return False`) was **not last** in `origin/main`, where other checks follow it — same anchor text, different neighbours, so a blind apply either aborts on the assert or splices into the wrong place. Grep every anchor against the WORKTREE copy before applying, and prefer an anchor at the TOP of the insertion region (the *first* check of a long dispatch function exists in every version). Also read the true size of the commit with `git show --stat HEAD`: the bare `git commit` echo printed a whole-file rewrite (`19428+ / 19316-`) from the CRLF/LF boundary while the real change was `112+ / 0-`.

**Check the count before the push and the ref after it.** `git rev-list
 --count origin/main..<branch>` must equal the number of commits you intended
 (1, or the PR's stack). Then `git ls-remote --heads origin <branch>` and compare
 the SHA. Correct a wrong push with `--force-with-lease` (never a bare `--force`,
 and only on your own branch); when upstream has moved, rebase the branch on the
 freshly fetched `origin/main` and force-push the same way, then restate the new
 base and HEAD. Report `origin/main...HEAD` ahead/behind plus `git status
 --short` when asked "is everything pushed" — the answer is three numbers, not a
 word.

## Steps

**Prefer the repo's own port tool over hand-rolled `curl | sed`.** OpenAmer ships
`scripts/port_from_upstream.py`: it applies the rebrand from one ordered `RENAMES`
table and **fails loudly on any leftover upstream token** — a hand-rolled `sed`
silently misses cases. `--dry-run` first (prints `would write <path> (N lines)`,
refuses on a leak):

```bash
.venv/Scripts/python.exe scripts/port_from_upstream.py --file tools/terminal_scope.py --dry-run
.venv/Scripts/python.exe scripts/port_from_upstream.py --file tools/terminal_scope.py
# cross-tree rename: --file hermes_cli/x.py --to openamer_cli/x.py
# whole-tree leak audit: --check-only
```

### The rename table's generic catch-all destroys real identifiers

`RENAMES` ends with `("hermes", "openamer")`. That is the correct general rule
**and** the place where a rename breaks the code it renames: any identifier that
legitimately *contains* the upstream string gets rewritten too.

Measured live 2026-11-07: the npm scope `@hermes/plugin-sdk` became
`@openamer/plugin-sdk` — **a package that does not exist on npm**. Worse, the
branding guard then no longer saw the upstream string in that line, so it
reported **no leak** and the broken import would have shipped silently.

```python
KEEP_PATTERN = re.compile(r"hermes-(?:parser|estimator)|@hermes/")

def rebrand(text: str) -> str:
    kept: list[str] = []

    def _stash(match):
        kept.append(match.group(0))
        return f"\x00KEEP{len(kept) - 1}\x00"

    text = KEEP_PATTERN.sub(_stash, text)      # protect BEFORE the rename
    for src, dst in RENAMES:
        text = text.replace(src, dst)
    for i, value in enumerate(kept):           # restore AFTER
        text = text.replace(f"\x00KEEP{i}\x00", value)
    return text
```

**Order is the whole fix.** Protect → rename → restore. A keep-pattern applied
*after* the rename can never match, because the string it looks for is already
gone — so the protection silently does nothing.

**Before shipping a rename, enumerate which identifiers legitimately contain
the upstream string** — npm scopes, Python module paths, env-var prefixes,
file names, third-party package names — and protect each explicitly. Then pin
it:

```python
assert rebrand("hermes-parser") == "hermes-parser"
assert rebrand("@hermes/plugin-sdk") == "@hermes/plugin-sdk"
```

### Keep the rename table in ONE module

The table was duplicated across the port tool and two audit scripts with three
slightly different versions (the audits lacked one entry; the port tool lacked
the keep-protection). Two tools that "apply the same rename" but don't will
report different verdicts about the same file, and neither looks wrong.

Extract it to `scripts/upstream_rebrand.py` and have every consumer import it:

```python
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from upstream_rebrand import rebrand   # noqa: E402
```

Pin the sharing in a test so it cannot drift back.

### `--check-only` must separate REAL leaks from deliberate attribution

A whole-tree grep for the upstream name produces **false positives by
construction**: worktrees, archived snapshots and scratch directories live
*inside* the checkout and get scanned as if they were shipped code. Measured:
**177 hits, 0 real**.

Three separations are needed, and the output must say which is which:

```python
SKIP_DIRS = frozenset({"tests", "node_modules", "venv", ".venv", "website",
                        "tmp", "out", "reports", "wt-gate179", "oa-v28"})
TOOLING_FILES = frozenset({"scripts/port_from_upstream.py", ...})
ATTRIBUTION_FILES = frozenset({"openamer_cli/_early_recovery.py", ...})
```

```
leftover hermes tokens: 0
attributed upstream mentions: 13
```

**Make the exit code depend on the leak count only** — otherwise every
legitimate attribution permanently blocks the gate.

Manual path, if the tool doesn't cover the case:

1. **Discover:** `curl -sL "https://api.github.com/repos/ORG/REPO/git/trees/main?recursive=1" | python -c "import json,sys; d=json.load(sys.stdin); [print(i['path']) for i in d['tree'] if 'KEYWORD' in i['path'].lower() and i['type']=='blob']"`
2. **Download + Brand:** `curl -sL "RAW_URL" | sed 's/hermes/openamer/g; s/Hermes/OpenAmer/g; s/HERMES/OPENAMER/g' > TARGET`
3. **Validate:** `python -c "import ast; ast.parse(open('PATH').read()); print('OK')"`
4. **Verify the import actually resolves — syntax-OK is NOT enough.** A ported file
   can parse cleanly and still die at import on a *name* the base module here never
   received (the wave-lag class below):

```bash
.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'.')
for m in ['tools.terminal_scope','tools.kanban_tools']:
    try: __import__(m); print('OK  ', m)
    except Exception as e: print('FAIL', m, type(e).__name__, e)
"
```

5. **Commit — SCOPED staging, never `git add -A`.** This is a **shared checkout
   that background crons commit into**; `git add -A` sweeps another job's
   uncommitted work into your commit. Name your paths explicitly:
   `git add path/a.py path/b.py && git commit -m "port(upstream): <subsystem> — <why>" && git push`

## The wave-lag class: callers landed, the base they import never did

**A productive diagnostic — but gate it on trap 0 below first.** If the "missing"
module is a *parallel implementation* of something this tree already has, porting
it is the wrong move (17 files wasted, 2026-09-16). Run the three probes in trap 0
before trusting this recipe.

**The single most productive diagnostic for a freshly-ported tree.** The symptom
is a `ModuleNotFoundError` / `ImportError: cannot import name` for something that
plainly *should* exist. The cause is almost always the same: an earlier port wave
landed the **users** of a symbol but not the symbol itself, or not yet.

Read it as a chain, not N separate bugs — each fix uncovers the next link:

```
tests/... → plugins/platforms/feishu/adapter.py:86
          → gateway.platforms.base_exec_approval   (module absent) → port it
          → from gateway.platforms.base import ExecApprovalPrompt  (name absent) → add it
          → from gateway.platforms.base import cache_*_from_bytes_async (name absent) → add it
          → gateway.platforms.event                (module absent) → port it
```

Bidirectional probes that settle it in one pass, before you touch anything:

```bash
# A) does the module exist here at all, and does upstream have it? (port vs write)
test -f tools/terminal_scope.py && echo HERE || echo ABSENT
ls "$UPSTREAM/tools/terminal_scope.py"                  # UPSTREAM=C:/Users/damir/AppData/Local/hermes/hermes-agent

# B) was it EVER committed here? (never = port lag; deleted = a regression)
git log --oneline --all -- tools/terminal_scope.py

# C) for a missing NAME: is the mechanism present under a different name?
grep -nE "_check_fn_cache|def no_cache_check_fn" tools/registry.py
#   → cache machinery present, only the decorator absent ⇒ add the small piece,
#     do NOT re-port the whole upstream registry over a locally-evolved one

# D) which consumers are broken, i.e. what does the fix actually unblock?
grep -rn "ExecApprovalPrompt" --include="*.py" gateway/ plugins/ | head
```

Rules that fell out of a real repair (2026-09-16, 3 modules / 340 red tests):

- **Divergence is normal — port the missing piece, don't overwrite the file.**
  OpenAmer's `gateway/platforms/base.py` is *larger* than upstream's (6060 vs 4454
  lines); the trees evolved apart. `port_from_upstream.py` writes a whole file, so
  for a *name-level* gap add the symbol in place and match the surrounding style.
- **Read the diff SIGN before porting a whole file — "differs" ≠ "upstream is ahead".**
  Live 2026-10-12: `tools/file_tools.py` was taken from `origin/main` on the
  assumption that upstream was newer. The numstat had said `+7  -34` — the
  upstream file is 27 lines **shorter** — and those missing lines were a
  device-path guard only *this* lineage had. Taking the file wholesale deleted the
  guard and turned 8 green tests (`TestDevicePathBlocking`) red. Two habits:
  1. Numstat **the test file AND its product dependencies** before touching either.
     A red test may be explained by product code the test file does not reveal:
     `tests/tools/test_spotify_client.py` was byte-identical with upstream while
     `plugins/spotify/client.py` was 8 methods behind. An import-resolving scan of
     the test alone would have missed it.
  2. When the local file is the *longer* one, assume you are **AHEAD** until proven
     otherwise — add the missing names in place, never overwrite.
  A wholesale copy needs either the full suite or a per-file before/after count for
  **every** consumer; the 8 regressions above were invisible in a total that
  simultaneously fixed 20 other failures. The cheap detector is a per-file diff of
  the runner's own output against a saved baseline, not the headline sum.
- **Copy upstream's semantics exactly, and verify the behaviour, not the import.**
  `_exec_approval_actions(smart_denied=True)` must offer **only** once+deny — a
  smart deny is a one-operation owner override. Assert the list, not just `import OK`:
  `[('Allow Once','once','primary'),('Deny','deny','danger')]`.
- **A missing private helper means the decorator's *effect* was never available.**
  `no_cache_check_fn` keeps a config-backed availability gate out of the `check_fn`
  TTL cache; without it, enabling a toolset stays invisible until the cache expires.
  Port the semantics (add `_NO_CACHE_CHECK_FNS` + an uncached branch), not just a stub.
- **`git log` for a *never-committed* file prints the next path** when you pass
  several (`git log -- f1 f2 f3` output ran two paths together and read as if one
  existed). Query **one path per call**, or `--name-only`.
- **`sys.path` shadowing explains "the module is there but the test can't import it".**
  With an editable install, `repo/.venv/Scripts/python.exe -c "import acp"` resolves
  the package from the *live install's* `site-packages` — it works in-process and in a
  subprocess, yet collection still failed under the 32-worker runner. Before blaming
  the code: `python -c "import pkg; print(pkg.__file__)"` and check the path is inside
  the venv you think you're using (see `failure-attribution` → the venv-lending trap).
  Reproduce flaky-per-run collection in isolation before chasing it.

## Reconstruct vs. copy: the owner's rule, and how to tell which case you're in

The wave-lag recipe above says "port the missing piece" and the rules say "copy
upstream's semantics exactly". That is correct for a **ported module that needs a
missing dependency** — you are completing a port that was already decided.

It is **wrong** for a helper set that OpenAmer's own code calls and no wave ever
landed. Live 2026-10-04: 15 symbols (`_fire_dispatch_tick_hook`, `_retry_status_for_run`,
`_row_get`, …) were missing from `openamer_cli/kanban_db.py` while
`kanban_db_dispatch.py` called them every tick. Upstream (`hermes_cli/kanban_db.py`)
had all of them verbatim, paste-ready. The owner **rejected the copy**:

> "keine hermes, openamer muss eigenes System sein"

Copying would make OpenAmer a fork of that project and import its assumptions
wholesale — the sibling's names, its env vars, its defaults. Deciding which case
you are in:

| Question | Port upstream | Reconstruct locally |
|---|---|---|
| Was the *module* already ported and only a dependency is missing? | ✅ | |
| Is OpenAmer's own new code the only consumer? | | ✅ |
| Does the symbol's contract come from how *this* tree calls it? | | ✅ |
| Do this tree's existing neighbours already define the pattern to mirror? | | ✅ |
| Would copying import the sibling's naming/env-var conventions? | | ✅ (reject) |

**How to reconstruct:** read every call site, derive the signature from the
arguments passed and the return consumed, then mirror the module's *existing*
neighbours (its real hook-firer, its real `txn`/event helpers) so the new code
reads as native. Keep `OPENAMER_*` naming throughout. The sibling is a
**cross-check after writing** ("did I miss an edge case?") — never a source.
Delete any scratch extraction of it so it cannot leak into a commit.

**A dropped port is tree-wide, so scan — don't chase crashes.** One reported
`AttributeError` hid 36 real losses (`scripts/scan-missing-symbols.py` in
`api-drift-recovery` finds them in one pass; `symbol_census.py` here does the
same census for imports). Fixing one symbol per restart means one restart per
symbol.

**A ported subsystem also needs its SCHEMA.** The same tick died on
`OperationalError: no such column: worker_started_at`: a lost column needs three
places to agree, and only the first is obvious — `CREATE TABLE` (new DBs), the
additive migration (`_add_column_if_missing`) for existing DBs, and whatever
writes it at runtime. A fresh test DB passes with only the first, so prove the
migration against a legacy DB built *without* the column.

**POSIX-only helpers must be restored as correct no-ops, not skipped.** Helpers
wrapping systemd/`/proc` were never ported because the mechanism does not exist on
Windows. The wrong fix ignores the caller's `require_*` demand; the right one
satisfies it trivially and says why, or raises.

## A port can drop METHODS, not just modules — scan the class body for `self.<x>(`

The wave-lag recipes above look for **module-level** losses (`from X import Y`,
`module.attr`). A rebuilt adapter file drops a different, quieter class: **methods
the rest of the file still calls on itself**. The symptom is
`AttributeError: 'SomeAdapter' object has no attribute '_flush_text_batch'` — and
`grep -rn "def _flush_text_batch"` finds nothing anywhere.

Two scans that MISS this — do not stop at them:

- a `from X import Y` / `importlib` scan never sees a `self._x()` call;
- scanning **the test file** for `adapter.<attr>` calls finds only what the tests
  touch directly. A method called purely from its own class is invisible to it.

Live 2026-10-08 (`plugins/platforms/feishu/adapter.py`, port commit `8e6a3629c`):
the test-file scan named exactly **one** missing method. Diffing in-class calls
against the file's `def`s then found **four more**, including the
`_flush_text_batch` / `_flush_text_batch_now` pair that three
`TestFeishuAdaptiveDelay` tests depended on — and CI confirmed it: the branch went
**112 → 91** failing tests, the 21 recovered including those three.

```python
src   = open(path, encoding="utf-8").read()
i     = src.index(f"class {Cls}")                 # scope to the class under repair
body  = src[i:]
defined = set(re.findall(r"def ([_a-zA-Z]\w*)\s*\(", src))   # module + class defs
calls   = set(re.findall(r"self\.([_a-zA-Z]\w*)\s*\(", body))
# subtract names the base class provides (hasattr(base, c)) before trusting the list:
missing = sorted(c for c in calls if c not in defined)
```

A name defined in a **different file of the same plugin** is a real hit, not
noise — check each candidate before declaring the file repaired.

**Restore from the pre-port revision, not from imagination.** When the port
dropped a method, the original is one command away:

```bash
git show <port_commit>^:<path> | grep -n "def <name>"     # exact signature + logic
git show <port_commit>^:<path> | sed -n '<start>,<end>p'
```

Rebuild faithfully against the helpers that still exist in the new file (a generic
`_delayed_flush`, a module-level `_build_markdown_post_payload`, the state object's
already-bound attributes) — the rebuilt method should read like its surviving
neighbours, not like a fresh invention. Only author from call sites when the method
never existed before.

**Same class, second recurrence (2026-10-13, sourced from `origin/main` rather than
from a port commit).** The very `_flush_text_batch` / `_flush_text_batch_now` pair
named above went missing *again* from `plugins/platforms/feishu/adapter.py`, this
time with `_text_batch_key` as a third — three methods, suite `22 → 19` failing.
Five disciplines; #3 is the one a scripted edit gets wrong.

1. **Source the block from the git OBJECT, never by hand-transcription.**
   `git show origin/main:<path>` and slice it — a retyped body drifts in whitespace
   and comments, and then you cannot *prove* it matches. `origin/main` is the correct
   source when the file already exists in this lineage; the port commit's parent is
   for a file the port itself rebuilt.
2. **Prove byte-identity instead of eyeballing it:**
   `assert local.count(upstream_block) == 1`. That one assertion is the difference
   between "ported verbatim" and "ported something similar", and it is cheap.
3. **`sed -n 'A,Bp'` and a Python slice of `split("\n")` are OFF BY ONE from each
   other.** Measured: `up_lines[2808:2817]` silently dropped the block's closing line
   (`        )`), leaving `return build_session_key(` unterminated — the file died
   with `SyntaxError: '(' was never closed` / ruff `Expected ')', found newline`.
   Correct slice is `[2808:2818]`. Then **run `ruff check <file>` + `py_compile`
   BEFORE the sweep**: a byte-level scripted edit gets no editor syntax check, so the
   linter is the only thing between it and a wasted multi-minute test run.
4. **Keep the local mechanism's PLACEMENT — insert, don't relocate.** The local file
   already carried `_reschedule_batch_task` with a byte-identical body, merely sited
   differently (after `_schedule_text_batch_flush`; upstream sites it after
   `_flush_text_batch_now`). Inserting the two flush methods between them and leaving
   the existing helper where it was produced `38 insertions(+), 0 deletions(-)`. A
   pure port's `git diff --stat` should read exactly that shape — **deletions mean you
   moved or rewrote something you did not need to.**
5. **Report the class you fixed and the classes you did NOT, separately.** A red file
   is rarely one bug. Of the 19 survivors here: `_build_post_payload` was missing (a
   *different* dropped method — present upstream, absent locally), `_is_duplicate` is
   `async` in **both** lineages while the test asserts on the un-awaited coroutine (a
   test-side async mismatch), and the rest are connect / hydration / bot-name
   failures. Naming which failures belong to which root cause is the deliverable — a
   bare "22 → 19" invites the reader to assume the remaining 19 share the cause you
   just fixed. Categorise by reading the `E       ` lines of the failure block, not by
   re-running per test.

See `references/verbatim-block-extraction.md` for the full recipe: the programmatic
extract + byte-identity assertion, the CRLF-preserving round-trip with its own
assertion, and the `cat -A` blindness that makes line-ending verification lie.

See `references/pre-port-target-check.md` for **Step 0 — verify the target already has the feature before porting it** (measured 2026-10-18: an assignment to port Hermes' Batch-Trajectory-Runner and MoA aggregation found both already present in OpenAmer, more deeply integrated than upstream — the batch runner feeds the Brain→LoRA pipeline rather than just exporting, and MoA has a fuller preset schema; the only real defect was a 2-line CLI bug in the existing runner).

**If the dropped method is called from `connect()` and is absent everywhere**, it
is a base-class hook, not an adapter method: add it as a documented **no-op** on
the base class so adapters that bind vendor-SDK callbacks can override it. Live:
`_wire_plugin_handlers` was called from `connect()` in **two** adapters (feishu AND
homeassistant) and defined in neither — one base-class no-op unblocked both.

## A port can also drift a shared LIST CONSTANT — subset tests go silently blind

The dropped-module and dropped-method scans above both miss the quietest port
artifact: a **shared list of string identifiers** that composite/bundle
definitions are built from. Nothing imports it, no `def` names it, so every
import / `ast` / `grep "def "` census reports green — yet that constant *is* the
membership contract a subset test consults.

Live 2026-10-10 (`toolsets.py`). `_OPENAMER_CORE_TOOLS` is the shared tool-name
list behind `openamer-cli` / `openamer-cron` / `openamer-telegram` / … . The
`browser` leaf toolset grew `browser_vault` during the port but the shared list
never received it, so `set(browser_tools).issubset(core_tools)` went `False` and
`browser` stopped expanding on **two** consumers at once:

- `openamer_cli/tools_config.py::_get_platform_tools` — composite→leaf subset
  inference, in both the explicit-config and the default branch;
- `tools/delegate_tool.py::_expand_parent_toolsets` — sub-agent parent-toolset
  intersection.

One missing string, two suites red, and the assertion names a *feature*
(`AssertionError: 'browser' not found in {...}`) rather than a member — which is
why it reads as an expansion-logic bug instead of a one-line list drift.

**Probe the sets directly instead of reasoning about the logic** — the offender
prints in one line:

```bash
.venv/Scripts/python.exe -c "
from toolsets import TOOLSETS
core = set(TOOLSETS['openamer-cli']['tools'])     # the shared list's composite
leaf = set(TOOLSETS['browser']['tools'])          # the leaf toolset
print('missing from shared list:', sorted(leaf - core))   # -> ['browser_vault']
"
```

Rules:

- **The fix belongs in the shared list, not the leaf.** The leaf toolset is the
  feature's own definition (upstream carries its `browser_vault*` tools in *its*
  core list too); add the missing identifier to the composite everyone builds
  from. Never delete an identifier from the leaf to make the subset test pass.
- **A composite that GAINS a member is the mirror bug.** Same session: the
  `openamer-api-server` composite carried five `asi_*` identifiers no other
  composite had, so the non-configurable `asi` toolset became auto-recoverable
  and leaked into a user's explicit override
  (`['asi','terminal','web'] != ['terminal','web']`). The framing is symmetric —
  *composite membership must match what the platform is supposed to bundle*:
  a missing member = a capability silently gone; an extra member = a capability
  leaking past an explicit restriction.
- **Check the whole class in both directions, not the one member the assertion
  named.** Dump every leaf's set-difference against its composite, and every
  non-configurable toolset the config layer auto-recovers per platform.
  `references/composite-toolset-drift.md` has the ready-made probe.
- **Where each half of the fix belongs — two directions, two DIFFERENT homes
  (measured 2026-10-10, second pass).** Putting either in the other place fails a
  different suite:
  - a **missing member** of the shared list → add it to the shared list, beside
    the tool's own family (`browser_vault` next to `browser_dialog`; `code_kernel`
    next to `execute_code`). The leaf already carries it; removing it from the
    leaf to satisfy the subset test deletes the feature.
  - a **local-only toolset leaking** into explicit configs → add it to
    `_DEFAULT_OFF_TOOLSETS`, NOT to the composite. That set means "off unless opted
    in", and the module's own sibling rule for `x_search` states the contract
    verbatim: *once the user has saved an explicit list, that list is
    authoritative — auto-enable does NOT fire*. The feature survives because it is
    enabled by NAMING it, while an explicit override stops collecting extras.
    Listing `asi` there also keeps it out of every other platform's schema at once.
- **Two members can be missing, and the assertion reveals them one run at a
  time.** `for ts in ("terminal", "file", "web", "browser", …, "code_execution"): assert ts in enabled`
  stops at the first failure — so fixing `browser_vault` made `code_execution`
  surface on the NEXT run and read like a fresh regression. Read the assertion's
  FULL tuple and diff the whole set in one probe:
  `[t for t in want if t not in enabled]`. Both were real:
  `TOOLSETS["code_execution"]` lists `["execute_code", "code_kernel"]` while the
  core list carried only `execute_code`.
- **Separate real drift from legitimate absence in the same dump.** A
  set-difference against the core list also flags every PLUGIN toolset (`spotify`,
  `discord`, `feishu_doc` / `feishu_drive`, `yuanbao`) — those are correctly
  absent from a native core list. Only a *native/shared* name missing is a bug;
  reporting the plugin rows as findings wastes the next reader's time.

## Restore vs. revert: one probe decides, and the port's structure is not the bug

When a port *rebuilt* a file and dropped names, two repairs both work — but one is
usually right. Decide mechanically, in this order:

**1. Did the TEST move with the port?** One command settles "restore the code" vs
"amend the test" before you read either version:

```bash
git diff <port_commit>^:tests/tools/test_x.py HEAD:tests/tools/test_x.py
# EMPTY     -> the test predates the port. It is ground truth; the IMPLEMENTATION
#              regressed. Restore behaviour, touch no assertion.
# NON-EMPTY -> the test travelled with the port; the assertion itself may be drift
#              (see trap 2).
```

Live 2026-10-10: empty for all four failing groups (spotify client methods,
homeassistant `_HASS_TOKEN`, the managed-gateway token field, the image-gen schema
strings). That one command decided every one of them without reading both versions.

**2. Size the diff before reaching for `git checkout`.** Measured: reverting two
spotify files wholesale was `889 + / 512 −` (≈1400 lines) and threw away an
intentional decomposition; restoring the dropped API *into* the new structure was
~50 lines and lost nothing. **The port's new structure is not the bug — the dropped
NAMES are.** Keep the dispatcher/`_schema`/`PLUGIN-COMPAT` scaffolding and re-add
behaviour. Revert wholesale only when the ported file brought no structure worth
keeping (then `git checkout <port>^ -- <paths>` is the faithful one-liner).

**3. The squashed-history trap.** This repo's real history is a giant dump commit
(`9cb4dc471 a2a worker: replies` adds ~10k files), so path history misleads:

```bash
git log --oneline --follow -- plugins/spotify/client.py   # -> one ancient commit. Useless.
git log --oneline --all -S "def get_devices" -- <path>    # -> names the commits that touched it
git merge-base --is-ancestor <port_commit> HEAD           # may say NOT ancestor
git diff <port_commit>:<path> HEAD:<path>                 # ...yet byte-identical. Use THIS.
```

**Ancestry is not content.** `git log <c>:<path> | grep -nE "def "` is the fastest
inventory of what the pre-port revision had.

**4. `compat_manifest.json` is a contract no test enforces.** Every name the
"Sep 2026 decomposition" kept importable from an old path is listed there (12.5k
lines), implemented by `# ---- BEGIN PLUGIN-COMPAT ----` blocks + a PEP 562
`__getattr__`. `grep -n "<module>" compat_manifest.json` before renaming or removing
a public symbol, and preserve the block when you revert a file — nothing else warns
you, because a missing entry turns no suite red.

**The manifest is a CLAIM, not a measurement — it can also falsely record a restore
that never landed.** Live 2026-10-10: for the spotify and home-assistant groups it
lists the very methods whose absence made their tests fail. The port advertised
`restored` and dropped the bodies. So it has two failure directions, and neither is
detected by anything:

```bash
# direction A: a name you removed is gone from the manifest (external callers break)
grep -n "<module>" compat_manifest.json
# direction B: the manifest says "restored" but the symbol is not there — check the CODE
git show <port_commit> -- compat_manifest.json | grep -nE "^\+.*<symbol>"
python -c "import <module> as m; print(hasattr(m, '<symbol>'))"   # the arbiter
```

Never cite the manifest, or the port commit's message, as evidence a symbol exists.
The evidence is `hasattr` / the real import / the covering test — the manifest only
tells you what someone *intended*.

**5. A rebrand leftover looks exactly like a dropped symbol.** Majority rules:
rename the *consumer*, not the field.

```bash
grep -rn "nous_user_token" --include=*.py .       # 2 hits, both in one consumer
grep -rn "openamer_user_token" --include=*.py .   # 7+ modules already on the new name
```

Trap: a test that sets the stale attribute on a `MagicMock`/`SimpleNamespace` still
passes because the read path is never reached on that branch. Only the test that
takes the real path (a real frozen dataclass) exposes it — never read a green test
as proof the attribute name is right.

**The rebrand can also be half-done *inside one object*, and it goes stale in BOTH
directions — so grep identifiers AND strings, then let each side's own test decide.**
Live 2026-10-10, three separate sites:

```python
# (a) one dataclass field renamed, the reader left on the old name
tools/managed_tool_gateway.py:26   openamer_user_token: str        # the field
tools/image_generation_tool.py:81  managed_gateway.nous_user_token # the reader -> AttributeError
# (b) a registry entry contradicting itself on adjacent lines
agent/credential_sources.py:22x    provider="openamer",  description="auth.json providers.nous"
# (c) a test setting a field that no longer exists -> it asserts nothing
tests/tools/test_image_generation.py:476   managed_gateway.nous_user_token = "test-token"
```

```bash
# strings, not just identifiers — (b) is invisible to an attribute grep
grep -rn "providers\.nous\|nous_user_token\|nous\." --include=*.py agent/ openamer_cli/ tools/ plugins/
# and for each hit, ask which side the OWNING test pins:
grep -rn "openamer_user_token\|nous_user_token" tests/
```

The direction is not "old → new" by fiat. Each occurrence is decided by its
neighbourhood: a reader whose dataclass says `openamer_*` is stale (fix the reader);
a registry line whose own `provider=` says `openamer` is stale (fix the string); and
a **test** naming a field that does not exist is not "the test being amended to pass"
— it is exercising nothing, so align it with the real field. State that reasoning in
the commit, because it is the difference between repairing drift and bending a test.

**6. Restoring an override seam a config migration removed.** When the port swapped
env access for a secret store and dropped the module globals the tests patch
(`_HASS_TOKEN` / `_HASS_URL`), do NOT revert the migration — restore the override as
a **precedence layer**: `_HASS_TOKEN or get_secret("HASS_TOKEN", "")`. Wire it into
the availability gate too, or the tool stays hidden while the header reader works.

**7. A stale test MOCK encodes the pre-port API shape — and `except Exception` swallows the proof.** When the port changed a method's *return shape*, the tests that mock it keep the old shape and fail with a symptom that names no cause. Live 2026-10-10:

```python
# tests/agent/test_anthropic_adapter.py — five mocks, all pre-port shape
_available_entries=lambda **_kwargs: [pool_entry],        # flat list
# agent/anthropic_adapter.py — post-port, the resolver UNPACKS
entries, _pending = pool._available_entries(clear_expired=False, refresh=False)
```

Unpacking a 1-element list raises `ValueError`, which the resolver's own `except Exception` caught and turned into `return None`. So the test failed as `assert None == 'pool-oauth-token'` — reading as *logic*, when it was an unpack of a stale mock. **The production fix was already correct; the mocks were the drift.**

```bash
# every mock of a changed method, in one pass — the shape is what to read
grep -rn "_available_entries" tests/
#   lambda **_kwargs: [entry],     <- flat, pre-port
#   def f(**kwargs): return [e]    <- flat, pre-port
```

Rule: when a port changes a *shape* (list → tuple, positional → keyword, single → `(value, state)`), grep the **tests** for that method before touching production. Fix the mocks to the real shape and add a one-line comment saying why, or the next agent "simplifies" them back. And prefer reading the value the caller unpacks rather than the assertion text: `assert None == X` under a broad `except` means *an exception was swallowed*, not that `X` was never computed — prove which by single-threading the test with `--tb=long` and reading the real traceback.

---

## `git diff --check` is a FALSE POSITIVE on this repo's CRLF files

The repo is committed with **CRLF line endings** (`core.autocrlf=false`, and
the blobs in git really contain `\r\n` — verified: `git show HEAD:run_agent.py`
counts 7007 CRLF and 0 bare LF). Git therefore treats every added line in a
CRLF file as ending in whitespace, and `git diff --check` prints
`trailing whitespace.` for each one.

Measured 2026-11-01: a clean, additive change to `agent/memory_manager.py`
produced **84** `trailing whitespace.` lines; the baseline commit for the same
file produced **7007** — the same complaint exists in history, so it is a
property of the repo's line endings, not of the change.

**Do NOT "fix" it** (rewriting to LF would rewrite the whole file) and do NOT
treat it as a gate failure. Prove the change is clean with three checks that
separate real trailing spaces from the CRLF artefact:

```bash
git diff --numstat                 # expect "N  0" per file for a pure addition
git diff -w --stat                 # real insertions only, EOL churn invisible
python - <<'PY'
import subprocess
d = subprocess.run(["git","diff","-U0"],capture_output=True,text=True).stdout
bad = [l for l in d.splitlines() if l.startswith("+") and not l.startswith("+++")
       and l.rstrip("\r").endswith((" ","\t"))]
print("added lines with real trailing space:", len(bad))
PY
```

Only a non-zero count from the third check is a real finding. `ruff check`
(the CI gate, `select = ["PLW1514"]`) is the authority on style; a clean ruff
run plus zero real trailing spaces means the diff is clean.

**Corollary when adding a NEW file:** match the line endings of the tree you
are joining. In this repo `run_agent.py` / `tools/*.py` are CRLF while
`openamer_cli/a2a/*.py` are LF — the per-directory convention is what keeps
the next person's diff readable.

## When upstream REFACTORED the thing you're porting: four traps

A port is not always "copy the file". Where the two trees evolved apart, the
right move is a deliberate divergence — and the wrong move reads as correct.

### 0. STOP — a `ModuleNotFoundError` is NOT automatically a port gap

**Read this before acting on the wave-lag recipe above, and before running any
import-chain resolver.** Chain-walking ("missing module → port it → next missing
module") is seductive and *wrong* when the missing module is a **parallel
implementation** of something this tree already has. Real cost (2026-09-16):
17 files / ~4000 lines ported to satisfy **one** import, then all reverted in a
follow-up commit. The tree ended up with two divergent MCP clients.

Three probes, in this order, before you port anything:

```bash
# 1. What does the REST of this tree import for this capability?
git grep -n "from tools.mcp_tool import\|import tools.mcp_tool" -- '*.py'
#    → 17 call sites, TWO of them importing PRIVATE state (`_servers`, `_lock`)

# 2. Does the implementation this tree already has provide the symbol the caller wants?
grep -n "def register_mcp_servers\|def refresh_agent_mcp_tools" tools/mcp_tool.py

# 3. What does the TEST SUITE patch? This is the decider.
grep -n 'patch("tools.mcp_tool\.' tests/acp/test_server.py
```

**The decider is #3.** A test that patches `tools.mcp_tool.X` can *never* be
satisfied by a split re-implementation — so the fix is the **caller** (2 lines),
not a second client. #1 is the corroborating signal: private-state imports
(`from tools.mcp_tool import _servers, _lock`) prove the monolith is
load-bearing, not vestigial.

**The shape that produces this trap:** the tree is at upstream's
**pre-decomposition** state (monolith, 6412 lines) and the ONE broken caller was
ported **post**-decomposition, so its imports name modules this tree never had.
Grep the caller's import line against the tree's actual layout before trusting it.

> When the answer is "fix the caller", say so plainly in the commit and **name the
> wrong turn you nearly took** — otherwise the next agent re-ports the split set
> from the same evidence. See `references/parallel-implementation-trap.md`.

### 0b. Suspect `try/except Exception` when an import failure is INVISIBLE

Both real cases this session were invisible for the same reason — the bad import
sat inside a broad `except` that logged and returned:

```python
try:
    from tools.mcp_tool_discovery import register_mcp_servers   # resolves to nothing
    ...
except Exception:
    logger.warning("failed to register ACP MCP servers", exc_info=True)
    return                                                      # silent no-op
```

The symptom was **behavioural**, not a traceback: `assert "test-server" in {}`
plus one WARNING line in the captured-log section. When a feature "just doesn't
happen" after a port:

```bash
grep -n "except Exception" -A3 <caller>     # is the failure being swallowed?
.venv/Scripts/python.exe -m pytest -q --tb=long <one_test>::<case>
#   → read the CAPTURED LOG section, not just the assertion
```

A hard `ModuleNotFoundError` at collection time is the *lucky* variant of this bug.
Corollary: an import that resolves to nothing costs you a whole test file, but the
**collection error** is the easy half — always single-thread the failing file
in isolation before believing a bare `N failed` count.

### 1. Never port a dataclass verbatim when field ORDER changed

`gateway/platforms/event.py` upstream extracted `MessageEvent` into a leaf module
**and** reordered its fields (`user_id` / `user_name` at positions 3–4, where this
tree has `source`). Two failure modes, both silent:

- Copying it verbatim shifts every **positional** construction site (11 of them
  across `gateway/`, `plugins/`). Keyword callers are safe; positional ones are not.
- Defining the classes in *both* places creates **two distinct class objects**, so
  `isinstance(event, MessageEvent)` is `False` across the two import paths, and
  `except`/identity comparisons quietly stop matching.

Do the census before deciding — order-sensitivity is measurable:

```bash
# how many call sites would a reorder break?
grep -rn "MessageEvent(" --include="*.py" gateway/ plugins/ tests/ \
  | grep -vE "MessageEvent\(\)|class MessageEvent" | head -20
```

**The fix that preserves both invariants: make the new module a re-export shim.**

```python
# gateway/platforms/event.py — one definition, two import paths
from gateway.platforms.base import (  # noqa: F401
    MessageEvent, MessageType, ProcessingOutcome)
__all__ = ["MessageEvent", "MessageType", "ProcessingOutcome"]
```

Prove it, don't assume it:

```python
from gateway.platforms.base import MessageEvent as A
from gateway.platforms.event import MessageEvent as B
assert A is B                                        # not merely == ; same object
assert isinstance(A(text="x"), B)                    # isinstance holds cross-path
```

Document *why* in the module docstring (upstream's extraction, the field-order
delta, and that migrating the definitions across is a separate mechanical refactor
which must first convert the 11 positional call sites to keyword). Otherwise the
next agent "tidies" the shim away and reintroduces the bug.

### 2. A red test that arrived from upstream may be SUPERSEDED, not failing

A test asserting an old rule can outlive the rule itself. Real case: a test
demanded `fail closed` for an empty allowlist while the shipping code returns
`True` for an empty allowlist — because upstream deliberately abandoned that rule.

Before you "fix" it in either direction, check whether upstream still has the test:

```bash
# does upstream still carry it?
grep -c "empty_allowlists_fail_closed" "$UPSTREAM/tests/.../test_file.py"   # 0 = superseded
# where did it come from, and is the handler still on that path?
git log --oneline -S"empty_allowlists_fail_closed" -- tests/path/to/test_file.py
git show <that-commit> --stat
```

Then compare the *production* file byte-for-byte against upstream. If the code
matches upstream and the test does not exist upstream, the **test** is the drift.

When replacing it, port upstream's **current** guard rather than deleting the
assertion — the security property usually still exists under a narrower trigger
(here: "a click carrying no operator identity is refused" instead of "an empty
allowlist rejects a named operator"). Deleting it would have dropped real coverage.

### 2b. The TEST half of a port can land alone — its SUBJECT never came

Trap 2 above is a red test that is **superseded**. Its sibling: the test is current
and correct, but the thing it tests never crossed into this lineage. The symptom
names no import chain and no missing module:

```
AttributeError: module 'autonom_watchtower' has no attribute '_install_python'
  tests/scripts/test_autonom_watchtower.py:112
```

Measured 2026-10-13. `53a1dd4631 test: port origin/main's Windows gates into this
lineage (16 files)` brought the TEST; the module half stayed behind. Four commands
settle the class before any repair:

```bash
git log --oneline -1 -- <test-file>                        # which commit brought the test
git cat-file blob origin/main:<module> | grep -c <symbol>  # 2 -> upstream HAS it
git cat-file blob HEAD:<module>        | grep -c <symbol>  # 0 -> this lineage never got it
git diff --stat HEAD origin/main -- <module>               # +21/-3 -> size the port
```

Rules:

- **Grep the symbol in the BLOB, not in whichever tree is open.** All copies on
  disk agreeing (0 hits in the repo, in the vendor snapshot dir, in the runtime
  tree) is what rules out "someone deleted it locally" and makes this clean **port
  lag** instead of a regression.
- **Do not fix it by overwriting the file with upstream's.** Read the SIGN of the
  delta first (see "Restore vs. revert", step 2); a name-level gap takes the named
  symbol in place.
- **Never sweep it into an unrelated unattended run.** When the working tree
  already carries other work, or the run's mandate is something else entirely, the
  correct output is the handoff — the failing test id, the port commit, the delta
  size — not a blind patch. A red suite is a *finding*; an unrelated patch inside a
  dirty tree is a second problem you created.

### 3. Prove the attribution before blaming your own patch

When a gate goes red right after your change, check whether it was already red:

```bash
git diff HEAD~1 -- <file> | grep -E "^@@"      # are my hunks even near the finding?
git diff HEAD~1 --stat -- <file>
# then re-run the scanner against the PARENT commit tree
```

Live case: a CRITICAL secret finding landed on `test_...py:L423` while all my hunks
were at lines 757–854. On the parent commit the scanner found **4** existing
findings — pre-existing, not mine. (The scanner had no test-path exclusion, so
fixture strings like `token="tok_normal"` trip the secret rule; treat that as a
scanner gap to report, not a test to rewrite.)

### 4. Verify through the path the CALLER takes — a bypass probe is not evidence

The most dangerous form of false green: you probe the new code with arguments that
skip the very branch you just added, get a clean result, and report the feature as
working.

Live case (2026-09-17). Adding `create_task(creator_task_id=…)` meant wiring the
new kwarg into `inherit_creator_origin`, which itself imports a private helper this
tree never received. My probe called `create_task` with `creator_task_id=None` —
and `inherit_creator_origin` **early-returns** on a falsy id, so the broken import
was never reached. I reported "happy path returns `{ok: true, …}`". The real test,
which passes `creator_task_id=self_tid` exactly like `tools/kanban_tools.py` does,
failed:

```
ImportError: cannot import name '_inherit_notify_subs' from 'openamer_cli.kanban_db'
  openamer_cli.kanban_db_graph.py:15
```

Rules that fall out of it:

- **Read the call site before writing the probe.** Take the arguments from the
  consumer (`grep -n "create_task(" tools/kanban_tools.py`) and pass the *same*
  ones — especially optional ids/flags whose main effect is selecting a branch.
- **A guard that early-returns on falsy input hides the whole downstream chain.**
  Any new parameter whose `None` path is trivial must be probed **non-None**.
- **Run the canonical test, not just your own probe.** The runner is the arbiter:
  `.venv/Scripts/python.exe -m pytest -q <file>::<that_test>`. A probe you wrote
  after reading the code shares your blind spot; the ported test does not.
- **When you catch yourself doing it, say it plainly** — "my earlier verification
  used a probe that bypassed the broken path" — instead of quietly re-running.

### 5. A new parameter often drags in the CALLEE's dependencies

Wiring a kwarg is not a one-line change when the callee needs helpers that are also
missing. `creator_task_id` → `inherit_creator_origin` → `_inherit_notify_subs`
(absent here, present upstream at `hermes_cli/kanban_db.py:1430`). Before declaring
a ported parameter done, walk the callee one level:

```bash
grep -rn "def inherit_creator_origin" -A12 openamer_cli/ | grep -nE "^.*import "
# any name it imports from a sibling must exist here too — check each one
grep -c "def _inherit_notify_subs" openamer_cli/kanban_db.py   # 0 = still missing
```

This is the wave-lag class one level deeper: the *caller* landed, you added the
*symbol* it calls, and that symbol imports a third thing. Same census discipline,
applied recursively — and the runnable `scripts/symbol_census.py` above catches it
in one pass if you re-run it after each batch instead of trusting a single probe.

## A PARTIAL port: the module landed, its dependency chain did not

The wave-lag class above is one level (a caller landed, the module it imports
never did). This is the same disease one level **deeper and quieter**: the ported
module landed, but the modules *it* imports were never brought along — and a
broad `except ImportError` inside the ported function turns that into **silent
empty output** instead of a traceback.

Live (2026-09-22): `acp_adapter/model_catalog.py` arrived with the ACP wave. Its
`_named_custom_provider_catalogs()` opens with:

```python
try:
    from openamer_cli.config import (get_compatible_custom_providers, ...)
    from openamer_cli.model_switch import _declared_model_ids, ...
    from openamer_cli.model_switch_providers import _NativePickerModelList, ...   # module never ported
    from openamer_cli.models_local import should_use_ollama_native_catalog       # module never ported
    from openamer_cli.providers import custom_provider_slug
except ImportError:
    return []          # <- every dependency failure becomes "no data"
```

So the tests reported `AssertionError: assert [] == [('custom:bed…')]` — an
assertion about *data*, which reads as a logic bug. The cause was three missing
dependencies, invisible by construction.

**Probe the ported module's import BLOCK name-by-name — `import module` proves
nothing here.** The file imports fine; it is the *names* that fail:

```python
import sys; sys.path.insert(0, ".")
MODS = [("openamer_cli.model_switch", ["_declared_model_ids", "_entry_models_discovered"]),
        ("openamer_cli.model_switch_providers", ["_NativePickerModelList", "_discover_flag"]),
        ("openamer_cli.models_local", ["should_use_ollama_native_catalog"])]
for mod_name, names in MODS:
    try:
        mod = __import__(mod_name, fromlist=["x"])
    except Exception as e:
        print(f"  {mod_name}: IMPORT FAIL {type(e).__name__}: {e}"); continue
    missing = [n for n in names if not hasattr(mod, n)]
    print(f"  {mod_name}: {'MISSING ' + str(missing) if missing else 'OK'}")
```

**Size the port BEFORE copying a line** — the transitive closure decides whether
this is a 4-file fix or a subtree. `scripts/port_closure.py` in this skill walks
`from <prefix>.X import` / `from .X import` upstream and reports what is genuinely
absent here:

```bash
python skills/upstream-porting-workflow/scripts/port_closure.py \
  "$UPSTREAM" <repo> hermes_cli openamer_cli model_switch_providers
# TO PORT (6): model_switch_providers 1235, models_local 689, models_pricing 591,
#              models_profile_cache 32, models_reasoning_caps 306, nous_account 628
# already present (7): auth config inventory model_switch models providers urllib_security
```

`3481 lines` vs the `1` function that looked broken: that gap is exactly why the
closure runs first. Ask "is this port even in scope for this task?" before
committing to it — the honest answer is sometimes "report it, do not port it".

### Closing the cascade: use PYTHON as the oracle, not an AST heuristic

When you resolve a partial port by appending the missing symbols, do **not** build
the "which names are missing" detector out of the `ast` module. It cannot know
scope, and every miss becomes a bogus "definition" you then append.

Measured 22.09.26 — the AST orphan finder reported:

```
round 1: 6895 orphan name(s) across 1845 file(s)     # before scope handling
round 1: 5240 orphan name(s) across 1503 file(s)     # after adding Lambda/arg/comprehension
```

Both numbers are noise. The real count was **51**. The false positives are
lambda/comprehension/walrus/`except ... as` bindings and closure-free names that
`ast.walk` sees as `Load` with no matching `Store` in the visited subtree —
`acp_adapter/tools.py: ['_child', '_depth', '_flush', '_line', 'deco', 'wrapper']`
is a decorator factory, not a gap.

**Let Python answer instead** — import each module in a subprocess and read the
real exception. `scripts/check_all_imports.py` does exactly this:

```bash
python skills/upstream-porting-workflow/scripts/check_all_imports.py \
  --root <repo> --python <venv>/bin/python --filter openamer_cli
# === 295 import OK, 45 FAIL (of 340) ===
#   openamer_cli.auth
#     NameError: name 'TURN_LIMIT_UNLIMITED' is not defined
#        File "<string>", line 4, in <module>
#        File ".../openamer_cli/config.py", line 9568, in <module>   <- the file AND line
```

The traceback hands you the **exact file and line** — no guessing. One probe,
340 modules, authoritative. It also cleanly separates environment gaps
(`No module named 'fastapi'` → install it, not a port gap) from real port gaps
(`NameError` / `cannot import name` → a symbol to land). Iterate until it reads
`N import OK, 0 FAIL`.

Use `symbol_census.py` for a *first* orientation, but treat its output as a
candidate list only — the subprocess import scan is the arbiter, and the two
disagree by two orders of magnitude.

**The exception: a `NameError` already names the module, so a one-FILE `ast` pass
is legitimate there.** The warning above is about TREE-WIDE orphan hunting, where
the walker over-reports by two orders of magnitude. When the traceback hands you
`NameError: name 'os' is not defined` at `openamer_cli/send_cmd.py:292`, the search
space is one file and the question is narrow — *which names are loaded here but
never bound?* — so the walker is a fine instrument:

```python
import ast, builtins
tree = ast.parse(open(path, encoding="utf-8").read())
bound, used = set(), set()
for n in ast.walk(tree):
    if isinstance(n, ast.Name):
        (bound if isinstance(n.ctx, ast.Store) else used).add(n.id)
    elif isinstance(n, (ast.Import, ast.ImportFrom)):
        for a in n.names:
            bound.add((a.asname or a.name).split(".")[0])
    elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        bound.add(n.name)
    elif isinstance(n, ast.arg):
        bound.add(n.arg)
print(sorted(used - bound - set(dir(builtins))))
```

Measured: it returned `['os', 'exc']` for that file — `os` real (`os.environ` read
*and written* with no `import os`, so a scalar the command was meant to bridge into
the environment was silently never bridged; adding the word fixed 21 tests), `exc`
a **walker gap**, because `ExceptHandler.name` is not recorded. The discipline is
the same as everywhere else here: treat the list as candidates, then check each
reported LINE. A name introduced by an `as` clause (`except … as exc`,
`with … as x`, `match … as`) is a false positive — and saying which candidate you
discarded, and why, belongs in the report.

### An appended definition must land BEFORE its first use, not at end-of-file

Appending to end-of-file is fine for a function. It is **wrong for a module
constant that appears in a default argument**, because defaults are evaluated at
import time:

```python
def resolve_turn_limit(raw: Any, default: int = TURN_LIMIT_UNLIMITED) -> int:
                                                                  # ^ NameError at import
...
TURN_LIMIT_UNLIMITED = sys.maxsize        # appended at EOF — too late
```

The file parses, `py_compile` passes, and *every* module importing it dies with
`NameError` — 45 of 340 here. Insert the constant immediately above the first
consumer (`read_raw_config_readonly` / `resolve_turn_limit`), not at the tail.

### Make the append tool IDEMPOTENT, or it will duplicate without bound

The first version appended by name with no "already defined" check. Re-running it
across rounds turned **3** missing constants into **351 duplicate lines** in
`config.py` (10,306 lines) before it was caught. An auto-porter is a loop; a loop
without a guard is a corruption generator.

```python
def def_start(lines, name):                       # the guard that was missing
    pat = re.compile(rf"^{re.escape(name)}\s*=")
    return next((i for i, l in enumerate(lines) if pat.match(l)), None)

if def_start(lines, name) is not None:
    print(f"already present (skipped): {name}")   # never append twice
```

Prove it by running the tool **twice**: the second run must report
`to append: []` / `already present: [...]` and write nothing. Recovering from a
bad append is `git checkout HEAD -- <file>` — measure the damage first
(`grep -c "^TURN_LIMIT_UNLIMITED = "` → 351 told the whole story).

### A CRLF file with a few lone-LF lines breaks `split("\r\n")`

After the port tool wrote some blocks with `\n` into a CRLF file, a
`raw.split("\r\n")` merged those lines into their neighbours, so an exact
`^NAME\s*=` match found **nothing** and the tool reported
`NOT DEFINED in file: ['TURN_LIMIT_UNLIMITED', ...]` for names that were visibly
present.

```bash
python -c "d=open('f','rb').read(); print('CRLF',d.count(b'\r\n'),'loneLF',d.count(b'\n')-d.count(b'\r\n'))"
# CRLF True  lone_lf 74   <- 74 lines are LF-only inside a CRLF file
```

`splitlines()` sees both, but re-joining with one `nl` then rewrites those 74
into CRLF and can scramble indentation (`IndentationError: unexpected indent`).
For a **surgical** edit prefer the `patch` tool (it matches on content, EOL
agnostic) over a hand-written split/rejoin. If you must script it, split on
`\r\n|\n` with a regex and re-join each line with the EOL you removed.

### A Windows path literal is invisible when the script runs under WSL python

`Path(r"C:\Users\...")` resolves to nothing under `/mnt/c` python: every
`.is_file()` returns `False` and the tool reports `NOT-UPSTREAM` for **100% of
symbols**, which reads as "upstream doesn't have any of these" rather than a path
bug. Make every root a CLI argument and assert it:

```python
p.add_argument("--upstream", default=str(UPSTREAM))
...
if not UPSTREAM.is_dir():
    print(f"ABORT: upstream tree not visible at {UPSTREAM}"); sys.exit(1)
```

Pass `/mnt/c/...` when invoking with WSL python, `C:/...` for the repo venv. The
`ABORT` guard is what turns a silent all-missing result into one clear line.

### A test file that ran 0 tests before and reports N failures after is NOT a regression

Expect this shape immediately after repairing a broken import: a file that showed
`1e` (collection error, **0 tests ran**) now reports `5 failed`. That is **masking
lifted, not damage added** — the tests were always going to fail, you just made
them reachable. Say so explicitly in the commit, and prove the direction:

```
origin/main (<sha>) tests/acp/test_named_provider_catalogs.py
    COLLECTION ERROR -- 0 tests ran ("1e")
this branch, same file
    5 tests ran, 5 failed on a REAL assertion (assert [] == [...])
```

The same reading applies to a cluster that *shrinks*: `977 → 0` occurrences of one
`AttributeError` while the file's `9 failed, 3 passed` total is **unchanged** means
you removed one error class and exposed/kept a different, pre-existing one. Report
the error kinds, not just the pass/fail count:

```
BASELINE (origin/main) error kinds:      WITH my fix:
  7x CancelledError                        6x CancelledError
  7x TimeoutError                          6x TimeoutError
  1x IndexError                            2x AssertionError  <- newly reachable
  1x AssertionError                        1x IndexError
  3863 lines mention `from_row`            0 lines mention `from_row`   <- the real win
```

### Re-exporting a moved symbol: check whether a PEP 562 shim already covers it

When a port extracts helpers out of a module and a consumer still imports them
from the old path (`from acp_adapter.server import _named_custom_provider_catalogs`),
the fix is usually to add the name to the module's existing `from <sibling> import`
line — the module already re-exports what it imports, and a sibling test depends
on that behaviour.

**But do not add a name that is served by a lazy plugin-compat shim:**

```python
_PLUGIN_COMPAT_LAZY = {
    'ACP_MAX_MODELS_PER_PROVIDER': ('acp_adapter.model_catalog', 'ACP_MAX_MODELS_PER_PROVIDER'),
}
def __getattr__(name):  # PEP 562 — lazy so no import cycles
    target = _PLUGIN_COMPAT_LAZY.get(name)
    ...
    warn_once(__name__, name, *target)
    return getattr(importlib.import_module(target[0]), target[1])
```

Importing such a name eagerly **silently retires a deprecation contract** — the
shim exists to warn external plugins the path moved, and its docstring states that
`-W error` is meant to catch it in tests. Grep for `_PLUGIN_COMPAT_LAZY` /
`# ---- END PLUGIN-COMPAT ----` before widening an import line, and prove both
halves afterwards:

```
_named_custom_provider_catalogs  -> <class 'function'>        (eager, no shim)
ACP_MAX_MODELS_PER_PROVIDER      -> 200 via lazy shim, warning intact
```

**Runnable:** `scripts/check_all_imports.py` — imports every module in a repo
(each in its own subprocess) and prints the REAL failure with file:line. This is
the arbiter for "is the port complete" — the AST census overshoots by two orders
of magnitude (6895 reported vs 51 real). Use it to close a cascade, and to
separate environment gaps (`No module named 'fastapi'`) from real port gaps:

```bash
python skills/upstream-porting-workflow/scripts/check_all_imports.py \
  --root /mnt/c/Users/<u>/repo --python ~/oav/bin/python --filter openamer_cli
# === 295 import OK, 45 FAIL (of 340) ===
```

**Runnable:** `scripts/port_symbols.py` — append named upstream definitions to a
local module **idempotently** (a re-run prints `to append: []`), rebranding via
the repo's own `port_from_upstream.rebrand`. Use `--before-first-use <anchor>` for
a constant referenced from a default argument, which must precede its consumer or
every importer dies with `NameError`:

```bash
python skills/upstream-porting-workflow/scripts/port_symbols.py \
  --module openamer_cli/config.py --upstream hermes_cli/config.py \
  --symbols TURN_LIMIT_UNLIMITED _UNLIMITED_SPELLINGS \
  --before-first-use "def resolve_turn_limit" \
  --root <repo> --upstream-root <upstream>          # then re-run without --apply
```

**Runnable:** `scripts/port_closure.py` — transitive dependency closure for a set
of upstream modules, so a partial port is sized before any file is copied.

## Cross-stack CONCEPT ports: the runtime is not the deliverable

Everything above ports *files* into OpenAmer. A third class exists: the upstream
ships a **capability as a runtime script** (TypeScript/JS) and the port must
re-express it in the target's native language.

Measured 2026-11-05, porting `deepseek-harness`'s `packages/workflow`: upstream
runs a **plain-JavaScript** orchestration body with top-level `await` and hooks
`agent()` / `parallel()` / `pipeline()` / `phase()` / `log()`. OpenAmer is
Python. The port was a **Python** script body with the same five hooks.

**The decision to make explicitly: re-express the script language, or ship a JS
runtime?** Re-express, when the target already has the primitives:

| question | answer for this port |
|---|---|
| does the target have a scripting language the model already writes? | yes — `execute_code` runs Python |
| does the target have the *concurrency primitive*? | yes — `delegate_task` already fans out |
| would shipping a JS runtime add a dependency to the core? | yes — and the AGENTS.md "narrow waist" rule forbids it |

The re-expressed port was **352 lines** and shipped with zero new
dependencies, while the upstream shipped a whole sandboxed Node runtime
(`workflow-ptc`) to run the same shape.

**The four things that transfer, and the one that does not:**

1. **The hook contract** — the names, the arguments, the return shapes. These
   are the model's interface; port them literally. Upstream's `parallel()`
   preserved order; so did mine.
2. **The script ergonomics** — upstream's "top-level `await` + a trailing
   `return`" is the whole appeal. Python has no top-level await, so the port
   wraps the body in an `async def` and compiles it as one:

   ```python
   wrapped = "async def __workflow_body__():\n" + _indent_body(source)
   namespace = {"__builtins__": _SAFE_BUILTINS, "agent": ..., "parallel": ...}
   exec(compile(wrapped, "<workflow>", "exec"), namespace)
   result = await namespace["__workflow_body__"]()
   ```

3. **The safety envelope** — upstream sandboxes the script in a PTC runtime.
   The Python port instead **restricts the namespace**: a small builtins
   allowlist, and `import` / `open` / `eval` / `exec` / `__import__` rejected
   by an AST walk *before* execution. State honestly which guarantee you
   provide: "the script runs with the parent's permissions, but cannot import
   or open files" is a different claim from "the script is sandboxed".
4. **The error contract** — a failing script must return an **error**, never a
   partial success. Both ports agreed here, and it is the kind of detail that
   silently changes when the language changes.
5. **What does NOT transfer:** the upstream's *runtime infrastructure*
   (the sandboxed Node process, its own tool schema, its own plugin system).
   Those exist to serve a TypeScript core; in a Python core they are dead
   weight. Port the capability, not the machinery.

**The ported capability must reuse the target's OWN delegation path**, not a
parallel one. The workflow port called the same
`_build_child_agent` / `_run_single_child` helpers `delegate_task` uses, so
every existing limit (max concurrency, spawn depth, the pause kill switch,
credential leasing) applied for free. A second delegation path would have
drifted from the first within a week.

**And a new model-facing tool carries the narrow-waist cost.** Measure the
schema cost before shipping it: `len(json.dumps(schema)) // 4` tokens per API
call, for every turn, for every session. The workflow tool measured **547
tokens**, then **436** after the description was compressed from prose to a
dense hook table — the same knobs, half the price. `delegate_task` was 401;
`terminal` was 1410. If your new tool's schema costs more than `terminal`,
compress it before you ship it.

**The port must also register the tool in every place the ecosystem expects
it** — this is the part that gets forgotten and produces a tool that exists
but is invisible:

| place | why |
|---|---|
| the tool registry (`registry.register(...)`) | without it the tool does not exist |
| the toolset definition (`TOOLSETS[...]`) | without it no surface exposes it |
| the shared core-tool list (`_OPENAMER_CORE_TOOLS`) | without it the *platform* composites miss it |
| the GUI toolset list (`CONFIGURABLE_TOOLSETS`) | without it `openamer tools` cannot toggle it |
| the plan-mode mutating set | without it the gate is bypassable — a tool that writes for you must be gated like the one that already does |
| the delegation blocked-tool set | without it, subagents can recurse into the fan-out |
| the display labels | without it the TUI prints a raw tool name |

A **new tool that fans out subagents** must appear in the plan-mode mutating
set (like `delegate_task`) and in the subagent blocked-tool set — both are
easy to miss and both are security-relevant, not cosmetic.

## Proving the tree is OUR OWN system, not a renamed upstream

The owner will eventually read the public README and ask whether the project is
still a fork in disguise ("wir muessen eigen alles haben, wir muessen openamer
sein"). When that question lands, the answer is a **measurement**, not a
paragraph: rebrand → diff → classify every upstream file, scan for runtime
coupling, and put a machine-checkable provenance marker on every file that
remains shared.

Full method, the three metric bugs the audit's own contract test caught (a
double-counting change counter, a keep-pattern that must run BEFORE the rename,
a whole-tree grep that produced 177 false positives), the marker format for
both Python and TypeScript, and the enforcement contract:
`references/upstream-independence-audit.md`.

The short shape:

| step | tool | result to report |
|---|---|---|
| line-level divergence | `scripts/audit_upstream_independence.py` | Python core **98.16%** substantive, **0** verbatim |
| desktop surface | `scripts/audit_upstream_independence_desktop.py` | desktop **88.09%** substantive; the lower number is honest — a React component library has nothing product-specific to differentiate |
| runtime coupling | `scripts/audit_upstream_coupling.py` | **no** upstream imports, **no** upstream pulls in updater/CI |
| attribution | `scripts/insert_provenance_marker.py` | every shared file carries `Upstream-Derived: <path> @ <commit> (MIT)` |
| enforcement | `tests/openamer_cli/test_upstream_provenance.py` | a file that loses its marker **fails the suite** |

**Report the asymmetry, not an average.** The Python verdict (98%) and the
desktop verdict (88%) differ because the UI layer is where a fork keeps the
most shared code. Averaging them hides the honest finding.

**What the tree DROPPED is the stronger signal than what it kept** — 2,659
upstream desktop files (plugin-catalog, evals, pm, hermes_platform) removed and
replaced by different designs. List the dropped directories by name.

**The marker must not shift the classification.** It is a comment; if the audit
counts it as a content change, every marked file moves class and the numbers
stop meaning anything. Treat a marker line as noise.

**`NOTICE` and the marker must agree, and the contract test enforces it.** The
attribution lives in three places — the file, `NOTICE`, the audit report — and
all three must be regenerated together.

## Report the TOTAL, not a cluster-by-cluster narration

A long repair campaign invites reporting in slices — "openamer_cli is green now",
"the update cluster is 0", "tests/tools 107 → 28". Every one may be true, and the
user still cannot tell whether the thing they asked for is done. Measured
2026-10-12: six cluster reports across a long session and **no current total** —
the last full-suite figure predated most of the work. The user's verdict was
"you tried everything all day and achieved nothing", and on *their* criterion that
was accurate.

- **Measure the whole suite before the campaign and again after it.** One long run
  is the only honest answer to "how far along are we"; a dozen cluster runs are not
  a substitute.
- **Never let a cluster number stand in for the total.** State both: "that cluster
  is 0; the suite as a whole is unmeasured since <time> and was N then".
- **Give the denominator.** "21 files green" means nothing without "of 2,566 test
  files". A count with no base reads as a boast and invites the exact doubt this
  section exists to prevent.
- **Report the regression count too, not just the wins.** When a total *is*
  available, pair it with a per-file diff against the saved baseline (above) so an
  improvement and a regression cannot cancel out silently in the headline.

## Forking a whole third-party project (not a file port)

Everything above ports *files* into OpenAmer. A different job is adopting a whole
external project as our own product: fork it, rebrand it, keep it building, and
stay a drop-in replacement for the upstream it replaces. Measured 2026-10-26 on
`morluto/rea` → `openamer/openamer-re` (504k LOC TS, 2,139 files + 995 test files).
Full transcript and numbers: `references/fork-rebrand-identity-boundary.md`.

**1. Split the identity into two layers BEFORE touching a line, and only rename one.**

| Layer | Examples | Rename? |
|---|---|---|
| Product surface | repo, package name, `bin` aliases, display name, bundled skill name, README, LICENSE/NOTICE | ✅ yes — this is the point of the fork |
| Protocol identity | MCP server key, package specifier recorded inside existing client registrations, Evidence/predicate namespaces (`rea.*`), provider ids in error payloads | ❌ no |

Renaming the protocol layer orphans every registration the upstream ever wrote:
setup plans nothing at all (empty progress), doctor reports *our own* registrations
as `unmanaged`, uninstall refuses to remove them. Measured: one key rename turned
`dshClientConfiguration.test.ts` from **99 green to 54 red** while nothing about
the capability changed. Say this out loud in `NOTICE.md` as a deliberate boundary —
otherwise the next agent "finishes" the rename and breaks every existing install.

**2. Then make the fork a drop-in replacement, deliberately.** A fork must treat the
upstream's names as its own, or switching products strands the old registrations:

```ts
const LEGACY_PACKAGE_NAMES = ["rea-agents"] as const;   // upstream npm package
const LEGACY_CLI_BINARIES  = ["rea"] as const;          // upstream binary
```

That one addition turned `setupClientConfigCleanupOwnership.test.ts` from 4 red to
34 green — and it is real migration behaviour, not a test accommodation. Keep the
list additive; it *is* the migration surface between the two products.

**3. A bundled file list is a contract with three consumers.** Adding one reference
file to a packaged skill needs the installer's `MANAGED_SKILL_FILES`, the ledger
generator's directory walk, and the doctor all to agree. The conformance test failed
because it carried its own *copy* of the list. Fix the class, not the instance:
derive the test's list from the exported constant (`[...MANAGED_SKILL_FILES].sort()`)
so drift cannot recur.

**4. Build gates that fail with a warning-shaped message.** `npm run build` exited 1
printing only `… native controls are unavailable: Missing packaged Windows native
file native/windows/build/manifest.json`. The real cause: those artefacts are build
outputs, gitignored, and the owned-process supervisor cannot load without them —
so every `scripts/run-exclusive.mjs` command dies, turbo never runs. Copy both files
from the published upstream tarball (the error text says so) and the same command
goes green. When a wrapper exits 1 with no turbo output, run the underlying task
directly (`node scripts/run-turbo.mjs run <task>`) — it prints the truth.

**5. Respect the pinned toolchain instead of fighting it.** `.nvmrc` + `engine-strict=true`
means `npm install` refuses on a 4-patch-older Node. Install the pinned version
**portably** (`nodejs.org/dist/v<ver>/node-v<ver>-win-x64.zip` unpacked into a tools
dir, absolute path in `--command`) rather than mutating the system interpreter —
and record that absolute path in the MCP registration, or the server starts under
the wrong Node later.

**6. Never claim the fork is done on the strength of its own tests.** Fork tests
inherit host failures. Baseline first (see `failure-attribution`): same files on a
pristine upstream worktree, own `dist`, per-file counts. Here 115 of the observed
failures were pre-existing Windows defects; the ones that were mine appeared as an
exact delta (54, 4, 3). Report the delta, never the raw red count.

## Pitfalls

- **MSYS Path Bug (Windows):** `python.exe C:\\c\\Users\\...` — double drive letter. Fix: `.bat` wrapper + `cmd.exe /c`.
- **mv to existing dir:** Moves src inside dst (`mv hermes_cli openamer_cli` where `openamer_cli/` exists = `openamer_cli/hermes_cli/`). Fix: `mv src/* dst/ && rmdir src` or check target doesn't exist first.
- **Branding in commits:** Zero "hermes" allowed. Use "upstream". Grep-check before push.
- **Commit messages with brand names:** Even "Remove brand-name 'hermes' from README" contains the word — rephrase to "docs: clean upstream references". Rebase + force-push if already committed.
- **Large files >2 GB:** GitHub Releases has a 2 GB/file limit. For GGUF models (3.76 GB), use the llama.cpp offical converter instead of DIY gguf-py scripts which may produce malformed metadata.

## Large porting waves reference
In one session (2026-09-15), ~25,000 lines were ported in 6 waves:
1. Free Tier (3 files, error_classifier + vault_login + tool_result)
2. Credential Pools (4 files, pool + admin + sources + persistence)
3. ACP adapter (14 files, IDE protocol)
4. HA + Image Gen + Video + Spotify + Feishu (21 files)
5. Kanban system (17 files, CLI + gateway + tools)
6. Branding fix + rebase (rename hermes_cli, clean commit history)

## References
See `references/msys-path-bug.md` for MSYS diagnostics and `references/porting-session-2026-09-15.md` for a complete 50-file example.
See `references/wave-lag-repair-2026-09-16.md` for the wave-lag repair recipe: the module-name census grep that collapses 1246 failures into 5 groups, the 3 missing modules + `no_cache_check_fn` prerequisite, the name-level chain that followed (`ExecApprovalPrompt` → exec-approval block → 3 async cache wrappers → `gateway.platforms.event`), and the two groups that only *looked* like port lag.
See `references/runtime-tree-parity-2026-09-17.md` for the follow-up: the runtime tree **67 commits behind** while all repo tests passed, the **partial-sync trap** (sources synced but tests + runner stale → the live tree runs new code against old expectations), how to tell **EOL drift from real drift** (5 of 7 "differences" were just CRLF), why a **stale background test log** tells you nothing, and the **probe-bypass mistake** where a falsy argument hit an early return and made a broken port look green.
See `references/parallel-implementation-trap.md` for the counter-case: **when a `ModuleNotFoundError` is NOT a port gap.** The 17-file / ~4000-line port that had to be reverted, the three probes (consumer census → existing-symbol check → what the test patches) that settle it in one pass, the `try/except Exception` signature that makes the failure invisible, and the root-level-venv blind spot that made the compat guard take 6 minutes instead of 40s.
See `references/dropped-methods-restore-vs-revert.md` for the *repair* side: the one
`git diff <port>^:tests/... HEAD:tests/...` probe that decides "restore the code" vs
"amend the test" (empty output = the test predates the port = ground truth), the
squashed-history archaeology (`git log --follow` lies; compare trees with
`git diff <c>:<path> HEAD:<path>` — ancestry is not content), the measured
surgical-vs-revert sizing (≈50 lines vs ≈1400), the `compat_manifest.json` contract
no test enforces, the `nous_*` → `openamer_*` rebrand leftover, and restoring an
env-override seam as a precedence layer instead of reverting a config migration.
See `references/pr-branch-hygiene-on-a-busy-main.md` for the **PR-branch
hygiene** class measured 2026-11-07: a PR branch carrying cron report files
that can never merge clean, rebasing onto a moving `main` and conflicting in
*generated* files (no correct merge exists), MSYS turning `/c/tmp/x` into
`C:/c/tmp/x` so the worktree can't be `cd`-ed into or removed, a dirty tree
that blocks `git checkout` (use a worktree, don't stash), an untracked file
that already exists upstream blocking a rebase (diff before deleting), and
why a raw `pytest` sweep showing 52 `F` is not a verdict when the canonical
runner says 0 failed — plus the reliable end-to-end sequence through
`gh pr merge --admin` and the post-merge verification.

See `references/upstream-independence-audit.md` for the **lineage-audit** class
measured 2026-11-07: how to answer "is this still a fork in disguise?" with
numbers instead of prose (rebrand → diff → classify, the coupling scan, the
machine-checkable `Upstream-Derived:` marker for Python and TypeScript, and
the contract test that fails when a shared file loses its attribution) — plus
the three metric bugs the audit's own test caught (a change counter that
double-counted, a keep-pattern that had to run BEFORE the rename, and a
whole-tree grep with 177 false positives).
See `references/crlf-normalization-windows.md` for the CRLF trap when syncing between the live OpenAmer tree and the canonical repo on Windows with `core.autocrlf=true` — the unstaged diff shows 1600+ lines of noise while the staged diff is clean additive.

See `references/composite-toolset-drift.md` for the **list-constant drift** family:
the leaf toolset that grew `browser_vault` while the shared `_OPENAMER_CORE_TOOLS`
composite list did not (2 suites red, assertion names the *feature* not the
member), the mirror case of an `openamer-api-server` composite carrying five
`asi_*` identifiers no other composite had (a non-configurable toolset leaking
into an explicit `platform_toolsets` override), the per-platform table of
auto-recovered toolsets, the three candidate fixes and why the composite edit is
the intended one, and the scratch-probe tooling note (cp1252 decode failure when
inlining probes vs. a `.py` file run through `terminal`).

**Runnable:** `scripts/composite_toolset_drift.py` — one-pass probe for the whole
list-constant family: (A) every configurable leaf whose static tools are NOT a
subset of the platform composite meant to bundle it, and (B) every
non-configurable toolset the config layer auto-recovers per platform (i.e. what
leaks past an explicit override). Exit 1 when drift is found, so it gates a commit:

```bash
.venv/Scripts/python.exe skills/upstream-porting-workflow/scripts/composite_toolset_drift.py --root <worktree>
```

**Runnable:** `scripts/port_closure.py` — transitive dependency closure for a set
of upstream modules (`port_closure.py <upstream-root> <local-root> <up-pkg>
<local-pkg> <mod>...`). Sizes a PARTIAL port before any file is copied: reports
`TO PORT (N modules, M lines)` vs `already present`, and flags modules absent on
both sides as "not a port gap". Use it whenever a ported module's own imports
might not have come along.

**Runnable:** `scripts/symbol_census.py` — the static census that finds every
missing import in ONE pass (separates "port the file" from "add the symbol"), so
you stop finding the gap one ImportError at a time. Run it before touching
anything and again after each batch:

```bash
.venv/Scripts/python.exe skills/upstream-porting-workflow/scripts/symbol_census.py --roots gateway plugins
```

**Runnable:** `scripts/runtime_tree_parity.py` — proves which files actually differ
between the repo and the runtime agent tree, **CRLF-normalised**, and prints the
first differing line when they truly differ. Exit 1 gates your DONE claim. Use it
instead of eyeballing `git status` in the runtime tree:

```bash
.venv/Scripts/python.exe skills/upstream-porting-workflow/scripts/runtime_tree_parity.py \
    --from-git HEAD~7..HEAD
```

**Runnable:** `scripts/port_block.py` — ports named method blocks **verbatim** from
a git revision into a local file. Extracts by SYMBOL (so the `sed` vs Python-slice
off-by-one cannot happen), preserves the target's EOL, refuses a mixed-EOL file,
asserts byte-identity after writing, and is idempotent (a symbol already defined in
the target is skipped; a second run writes nothing). Pair it with `ruff check` +
`py_compile` before running the sweep, and read
`references/verbatim-block-extraction.md` for the measured trap that motivated it:

```bash
.venv/Scripts/python.exe skills/upstream-porting-workflow/scripts/port_block.py \
    --path plugins/platforms/feishu/adapter.py --rev origin/main \
    --symbol _flush_text_batch --symbol _flush_text_batch_now \
    --insert-before "    @staticmethod" --occurrence 2      # add --dry-run first
```

## Inherited Trigger (from `upstream-porting`)
Also handles topics previously covered by the absorbed skill `upstream-porting`.
