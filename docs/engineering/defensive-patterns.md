# Defensive Patterns

Bug-class rules for OpenAmer. Each entry is a class of defect that actually shipped
or nearly shipped here; the rule is what prevents its recurrence. Read this before
writing lifecycle, concurrency, subprocess, teardown, or credential code.

These patterns are OpenAmer's take on the hard-won rules large agent harnesses
codify (see the reference list at the bottom). They exist so a defect that was
expensive to find once never comes back as a regression.

## Report orthogonal outcomes independently

A result can be several things at once. A subprocess can time out AND exit 0
because it trapped the signal. A wait can hit its deadline AND observe a ready
marker written by a stale process. Report each independent fact
(`timed_out`, `signal`, `returncode`) on its own field; never nest one flag's
report inside another's branch, or a caller reads a cut-short run as a clean
success.

OpenAmer precedent: `run_tests.sh` / the test runner previously let a Windows
`UnicodeEncodeError` on a progress print look like a test failure, and the
ci runner mis-read skip/exit states. Keep `duration`, `exit_code`, and
`errored` as separate facts end to end.

## Honor public contracts on BOTH sides

When an implementation receives several representations of one outcome,
normalize them before returning through the public API. A tool wrapper may
raise, return `isError`, or emit a partial result; the caller-facing layer must
expose exactly one normalized contract so consumers never guess whether an
exception came from the tool, a hook, or their own assembly. Document the
normalized contract at the type/function definition, and exercise every source
form through the real consumer in tests.

OpenAmer precedent: the computer-use capture path had a `FakeProc.stdout` that
was invalid JSON on Windows (`C:\Users\...` has an invalid `\U` escape), which
only failed under `json.loads` on Windows. Every consumer that parses tool
output must be exercised on both the platform's path separators and the
Windows escape rules.

## Async/spawned state is not synchronous state

A background job's completion can race lifecycle boundaries. `reader.close()`
may fire for both EOF and disposal; a restart may discard unstarted work. Never
treat one observed transition as the sole result of one follow-up. If a caller
truly owns a run, define its interval explicitly and describe any selected
output as interval-wide, not causally attributed to a single message. The guard
cuts both ways: if the awaited transition can never occur, the wait hangs — so
handle the "nothing to wait for" branch explicitly.

OpenAmer precedent: `openamer update` must not read "no new commits" as "venv
is healthy" — uv can retain the same CPython patch while the embedded SQLite
changes underneath. The update path re-probes the venv independently of the
git commit count.

## Dispose must reach quiescence, not just request it

A teardown that issues kills/aborts but returns before the work stops leaves
orphans. Make cleanup async and await the children's exit (`kill` → await
`done`), and close listener/notification registries BEFORE killing so late
completions stay silent. Reserve recursive removal for known real directories.

OpenAmer precedent: the venv quarantine path renames live shims to `*.exe.old.*`
and only a later sweep cleans them; teardown must not leak either the shims or a
running update half-applied. The `.update-incomplete` / `.lazy-refresh-incomplete`
markers exist so a killed update is finished on the next launch instead of
leaving a half-built venv.

## Contain callback exceptions in the dispatcher

A user-supplied listener that throws must not reject the promise/call it runs
inside or starve the listeners after it. Wrap the dispatch loop in
try/except and log; one bad subscriber never breaks core lifecycle.

OpenAmer precedent: `_early_recovery.py` is dependency-light and must never
raise during import — if recovery can't self-heal it prints the manual command
and leaves the relevant marker so the user's next launch retries.

## Never hand untrusted output the ambient environment or predictable paths

Spawned commands get a scrubbed environment: drop `*KEY*` / `*SECRET*` /
`*TOKEN*` / `*PASSWORD*` and OpenAmer-internal provider vars so harness
credentials cannot leak into output, `env`, or spill files. Temp/spill files
use a private dir, random names, and exclusive owner-only opens; predictable
world-readable paths invite symlink races and disclosure.

OpenAmer precedent: `tools/environments/local.py::_sanitize_subprocess_env`
filters OpenAmer-managed secrets before any subprocess; `env_loader.py`
tracks `_API_KEY` / `_TOKEN` / `_SECRET` / `_KEY` suffix credentials and their
sources. A2A privacy redacts phone/password/email/card/keys before persistence.
Use these, never a raw `env=os.environ` passthrough when the child may observe
provider credentials.

## Unlink link-shaped paths safely

A path that may be a symlink or Windows junction must be removed with
`lstat().is_symlink()` then `unlink()`: unlink deletes only the link and
refuses a real directory, so it never follows the link into its target.
Windows `rmtree()` on a junction can descend through it into the target.
Reserve recursive removal for known real directories.

## Validate ownership before quarantine, never blanket-mutate a working dir

A repair/refresh routine must confirm it targets the intended venv/project
before renaming or deleting live artifacts. A test or maintenance tool that
renames shims based on a guessed scripts dir can corrupt a developer's working
venv (see the mark-down of `.venv/Scripts/python.exe` → `*.exe.old.*`). When a
test exercises such a path, isolate the target to a tmp dir first, or neutralize
the mutation (autouse fixtures in `tests/openamer_cli/conftest.py`).

## References / provenance

- DeepSeek Harness `docs/defensive-patterns.md` (MIT) — the bug-class catalog
  this document is adapted from, in particular "report orthogonal outcomes",
  "honor public contracts on both sides", "dispose to quiescence", "contain
  callback exceptions", and "never hand untrusted output the ambient
  environment".
- OpenAmer internal: `tools/environments/local.py`, `openamer_cli/env_loader.py`,
  `openamer_cli/_early_recovery.py`, `tests/openamer_cli/conftest.py`.
