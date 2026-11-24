# Repairing a foreign-schema record in a shared JSONL store

Live 12.09.26 — cron `longterm-memory-indexer`
(`python scripts/longterm_memory.py index`). Real transcript, real fix.

## Symptom

```
Traceback (most recent call last):
  File ".../scripts/longterm_memory.py", line 140, in <module>
    print("indexed:", index_brain())
  File ".../scripts/longterm_memory.py", line 91, in index_brain
    have = {e["text"][:200] for e in eps}
KeyError: 'text'
```
Exit 1. The store itself was fine for 3012 of 3013 records.

## Diagnosis (one pass, no guessing)

Dump the keysets instead of eyeballing a 50 MB file:

```python
keysets = collections.Counter()
for line in open(STORE, encoding="utf-8"):
    keysets[tuple(sorted(json.loads(line).keys()))] += 1
```
Result:
```
3012 ('embedding', 'kind', 'meta', 'text', 'ts')
   1 ('action_needed', 'summary', 'timestamp', 'type')
```
The one outlier was a Discord-blocker event another cron had appended:
`{'timestamp': '2026-09-12T04:39:36', 'type': 'discord_blocker',
'summary': 'Discord Cron-Job c3305ad493fc: Kein Login…', 'action_needed': …}`.

**Root cause is architectural, not a corrupt file:** the episode store is a
shared append target. Two independent writers, two unrelated schemas, and
`_load()` trusted every parsed dict.

## Repair recipe (in this order)

1. **Back up the store** — `shutil.copy2(STORE, STORE + ".bak-<ts>")` before any write.
2. **Classify, don't edit**: keep every record with both `text` AND `embedding`;
   move everything else to `longterm_episodes.quarantine.jsonl` (append). Nothing
   is deleted — foreign records are another job's data, quarantine preserves them.
3. **Harden the loader**, not just the symptom line:
   - `_load()` keeps only valid episodes (`isinstance(e, dict) and "text" in e and "embedding" in e`).
   - `index_brain()` uses `e.get("text", "")[:200]`.
   Both, because a future writer can add a partially-shaped record that passes one check.
4. **Verify with the real command**: `python scripts/longterm_memory.py index` → `indexed: 3012`, exit 0.

## Regression proof (do this, don't just assert it)

Append a foreign-schema line to the **real** store, run `stats` + `index`
(must be exit 0, no traceback), then restore the byte-identical original from a
`cp` taken before the injection — and confirm the line count is unchanged:

```bash
S=memory/longterm_episodes.jsonl
cp "$S" /tmp/before.jsonl
printf '{"timestamp":"...","type":"discord_blocker","summary":"x","action_needed":"none"}\n' >> "$S"
python scripts/longterm_memory.py stats   # was KeyError, must now exit 0
python scripts/longterm_memory.py index   # idempotent, exit 0
cp /tmp/before.jsonl "$S" && wc -l < "$S" # back to the original count
```

Plus a hermetic unit check (temp store, monkeypatched `lm.STORE`): one good
record + one foreign-schema + one malformed-JSON line → `_load()` returns 1,
`stats()['total'] == 1`.

## Honest reading of the result

`indexed: 3012` is the **total**, not the delta. Nothing new was added because
`~/.openamer/a2a/openamer-brain.jsonl` (2862 lines, mtime 30.08.) had not grown —
the store was already fully indexed. To distinguish "worked, nothing new" from
"silently did nothing", compare store line count vs. the brain file's
mtime/line count. Do not report a delta you did not measure.

## Verification without a test harness

- `grep -r longterm_memory <repo>/tests/` → **0 hits**; no unit suite exists for
  this module. The repo's `package.json` has **no `test` script** (only
  `check`/`fix`/`install:*`), so `npm run test` prints `npm error Missing script:
  "test"` — quote that real output instead of claiming the command is inapplicable.
- Lint **differentially**: `ruff check` on the edited file AND on the pre-edit
  copy. Both flagged the same 2 pre-existing errors (E401 line 17 multi-import,
  E741 line 63 `l` loop var) → 0 new errors introduced. Pre-existing findings are
  not your regression and not your cleanup job mid-incident.
- Evidence set that actually proves the change: `py_compile` OK, differential
  lint clean, real `index`/`stats`/`query` runs, injection regression, temp-store
  unit check.

## Durable guard (recommended)

A `test_*.py` that writes a mixed-schema temp store and asserts `_load()` returns
only valid episodes — that turns this incident class into a build failure instead
of a 06:00 cron error. (`autonomous-learning-architecture` §"never make the same
mistake twice": a guard test is the only thing that prevents recurrence.)
