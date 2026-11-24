---
name: a2a-brain-meshlearn-verify
description: Run the recurring `openamer a2a brain collect` + `meshlearn auto` learning pass and VERIFY it actually landed. Use whenever a cron/scheduled job collects sessions into the brain dataset and triggers mesh learning, or when checking mesh-learning health.
---

# A2A brain collect + meshlearn auto — run AND verify

Two known failure modes make these commands print SUCCESS while doing nothing.
Never trust the exit code or the "Learned+adopted" line. Always verify artifacts.

## Known failure modes (verified 2026-09-18)

### 1. Silent no-op in `meshlearn auto` (title de-dupe collision)
`selflearn.auto_learn()` falls back to the fixed title **`"Learned from task"`**
when `--title` is not given. `meshlearn.adopt()` de-dupes with:

    if insight.title in cur:   # openamer_cli/a2a/meshlearn.py:96
        return True            # reports success, writes NOTHING

If the memory file already contains that literal title (it does, from the
`#mesh:a2a: Learned from task — ...` line), **every** subsequent untitled
`auto` run is swallowed as a false duplicate. Exit 0, "sig: True", no write.

**Fix:** always pass a unique `--title`.
**Verify:** mtime of the memory file must change, and the new line must appear.

### 2. Path mismatch between writer and reader
- `meshlearn auto` defaults to `~/.openamer/MEMORY-official-mesh.md`
  (hardcoded via `pathlib.Path.home()`, subcommands/a2a.py:_cmd_meshlearn).
- `brain collect` reads `$OPENAMER_HOME/MEMORY-official-mesh.md`
  (defaults to `C:/Users/damir/AppData/Local/openamer-laptop/...`).

With `OPENAMER_HOME` set (as here), the default writer file and the default
reader file are **different files**. An insight adopted into `~/.openamer`
never reaches the collected dataset.

**Fix:** pass `--memory` explicitly to both, pointing at the same file —
preferably the one `brain collect` reads, so insights end up in the dataset.

### 3. `Envelope.verify()` conflates freshness with authenticity → "invalid signature" lie
(verified 2026-09-25 against the live public mesh directory)

`core.Envelope.verify()` is `AUTH and FRESH`:

    @dataclass
    class Envelope:
        ...

    def verify(self, sender_public_key_hex: str) -> bool:
        return self._verify_signature(sender_public_key_hex) and self._fresh()

`_fresh()` uses the module constant `_REPLAY_TOLERANCE_SECONDS = 300`. Any
envelope that was signed more than 5 minutes ago — i.e. **every stored,
serialized or committed one** — fails `verify()` *even though the Ed25519
signature is perfectly valid*. The relay directory is by definition a store of
envelopes, so it reads back 100 % unverifiable.

Worse, the `tolerance` argument on the callers is dead code, so you get the
**wrong reason**: `relay.verify_note()` branches on `stale` at line 208, but
`env.verify()` at line 206 has already returned False and it reports
`invalid signature`.

    relay.verify_note(note, tolerance=300)        -> {'ok': False, 'reason': 'invalid signature'}
    relay.verify_note(note, tolerance=30*24*3600) -> {'ok': False, 'reason': 'invalid signature'}

**Diagnosis:** never trust `verify()` alone for stored objects. Separate the two
questions by calling the private signature check:

    from openamer_cli.a2a import core
    env = core.Envelope.from_dict(note["envelope"])
    print("authentic:", env._verify_signature(note["sender_pubkey"]))   # Ed25519 only
    print("acceptable:", env.verify(note["sender_pubkey"]))             # Ed25519 + freshness

**Live measurement (30 committed envelopes on `main`):**
`raw signature valid 30/30` vs `Envelope.verify() 0/30`, envelope age
518 s – 2 497 495 s against a 300 s tolerance. `verify_note()`'s own separate
stale check can never fire.

**Blind spot:** the whole suite passes (24/24 in `test_a2a.py` +
`test_a2a_relay.py`) because fixtures are always signed and verified in the same
call, so `ts ≈ now`. `test_envelope_reject_future` (`ts=9999999999`) actually
locks in the freshness-inside-`verify()` design as intended behaviour. Test the
**store → serialize → reload → verify** path if you touch this.

**Divergent tolerances to expect:** `Envelope` 300 s, `meshlearn.Insight` 30 days,
`registry.Announcement` 300 s — each object class carries its own idea of fresh.

### 4. Every `openamer a2a mesh` subcommand crashed — three names the coordinator never had
(fixed 2026-10-11, PR #155, `main` `b3aee1b5c`; re-verified live on this machine)

`openamer a2a mesh learn|publish|stats` are the *cross-node* surface (distinct
from `a2a meshlearn`): stage an insight, publish it for the swarm, import peers'.
All three were dead on arrival, one bug class — the CLI calls into
`MeshLearningCoordinator` and the name it calls does not exist:

    $ openamer a2a mesh stats
    AttributeError: no attribute '_IMPORTED_DIR'          # __init__ set no such attr
    $ openamer a2a mesh learn
    AttributeError: no attribute 'run_mesh_learning_cycle' # method never written
    $ openamer a2a mesh publish --title x --body y
    TypeError: MeshLesson.__init__() missing 3 required positional arguments:
               'source', 'source_pubkey', 'ts'             # _sign_lesson fills them AFTER ctor

If any resurfaces, check `tests/a2a/test_mesh_learning.py` — 7 tests there fail on
the pre-fix module with exactly those three errors. Never trust the CLI's "cycle
complete" line alone: verify `a2a/mesh/publish/*.json` exists and carries a
non-empty `signature` + `source_pubkey`.

**Correct usage (verified):**

    openamer a2a meshlearn learn "<title>" "<body>" --topic <t>   # stages ~/.openamer/a2a/insights/
    openamer a2a mesh learn     # publish local + import peers; IDEMPOTENT by title slug
    openamer a2a mesh stats     # published / imported / memory entries / skills / topics
    openamer a2a mesh import    # list peer lessons

**Paths (all under `_base_dir()` = `$OPENAMER_HOME` or `~/.openamer`):** insights
`a2a/insights/*.json` → publish `a2a/mesh/publish/` → imported `a2a/mesh/imported/`.
Note the same `$OPENAMER_HOME` mismatch as failure mode 2: `meshlearn learn`
writes to `~/.openamer/a2a/insights` while the coordinator reads
`$OPENAMER_HOME/a2a/insights`, so a staged insight is only picked up by
`mesh learn` when both resolve to the same base.

**Two guards that are easy to undo by accident:** publishing is slug-keyed
idempotent (a second cycle publishes 0), and the cycle applies a lesson only when
it sets `applies_to` — `apply_lesson_to_skills()`'s scan-all fallback would
otherwise append the lesson to *every* `SKILL.md` in an install with 100+ skills.

## Correct run (verified working)

    # 1. collect first (reads $OPENAMER_HOME/MEMORY-official-mesh.md)
    openamer a2a brain collect

    # 2. learn with a UNIQUE title and an explicit --memory
    openamer a2a meshlearn auto --topic auto \
      --memory "C:/Users/damir/.openamer/MEMORY-official-mesh.md" \
      --title "Automatischer Insight-Sammellauf $(date +%Y-%m-%d)" \
      "Automatischer Insight-Sammellauf: Neue Sessions wurden in den Brain-Datensatz aufgenommen."

## Verification checklist (all must pass)

    F="C:/Users/damir/.openamer/MEMORY-official-mesh.md"
    stat -c '%y | %s' "$F"        # mtime must be NOW (not yesterday)
    grep -n "Sammellauf" "$F"     # new line must be present
    grep -c '^#mesh:' "$F"        # count must have increased by 1

Then confirm the insight is really in the dataset — count `engine=="insight"`
records, not raw grep hits (a bare grep also matches trajectories):

    python3 -c "
    import json
    p=r'C:/Users/damir/AppData/Local/openamer-laptop/a2a/openamer-brain.jsonl'
    n=sum(1 for l in open(p,encoding='utf-8',errors='replace')
          if json.loads(l).get('engine')=='insight')
    print('insights:',n)"

## Notes
- `openamer a2a meshlearn` has only `{learn,auto,adopt}` — there is no `stats`.
  For counts use the *other* subtree: `openamer a2a mesh` has
  `{learn,publish,import,stats}` (stats works since PR #155, 2026-10-11).
- `openamer a2a brain` has only `{collect,publish,autolog,share}` — no `stats`.
- `braindata.build_dataset` reads only `$OPENAMER_HOME/trajectories|logs|data/**/*trajector*.jsonl`
  plus the memory file. It does **not** read `$OPENAMER_HOME/sessions`.
- `brain collect` rewrites the dataset from scratch; a healthy dataset is large
  (144 MB / ~7500 records as of 2026-09-18), overwhelmingly `trajectory`.
- `openamer a2a status` / `fingerprint` are trustworthy self-consistency checks:
  `fingerprint == sha256(pubkey_hex)[:16]` (`core.pubkey_fingerprint`). This
  machine measured `cf971ad884b74297`, stable across runs.
- `openamer a2a delegate ping --wait 120` is a **real end-to-end round-trip**
  (re-verified 2026-10-12: fingerprint `cf971ad884b74297`, reply `ok: True`,
  `from: nodeworker`, `runner: runnervmmprz5`, worker pubkey `6c67c254cd79`,
  matched by Actions run `38200061761` `repository_dispatch` /
  `completed/success`; earlier round-trip re-verified 2026-10-11): it prints `queued ping to remote worker (sender
  <fp>)` + `dispatched a2a-worker workflow`, then the worker's `=== A2A result
  (signed+verified, from remote worker) ===` block with `ok: True`, `from:
  nodeworker`, a `runner:` name and the worker pubkey. Cross-check the GitHub
  Actions run: `gh run list --workflow=a2a-worker.yml --limit 1` must show a
  fresh `a2a-task` run with `conclusion: success` whose `createdAt` matches the
  call. Do NOT report success from the upload/204 lines alone — the proof is the
  signed reply block PLUS the matching run.
- The old "no fresh signed reply within wait window" failure was the freshness
  half of `Envelope.verify()`: a reply that lands >300 s after dispatch reads
  back as `reason: "invalid signature"`. A live round-trip normally arrives
  inside the window, so it verifies; a **stored/committed** relay envelope never
  does (see failure mode 3). If you suspect the timeout is a timing artefact,
  widen `--wait` before blaming the crypto.
