# Organ audit — MISSING, ORPHANED, DEAD subsystem scripts (live 05.10.26)

When asked "which organs does the system still need?", audit in three passes.
An "organ" = a subsystem script the heartbeat (or a cron) is supposed to run.

## Pass 1 — MISSING (never built)

```bash
for organ in homeostasis immune attention salience metacognit calibration \
             conscience ethics value regret reputation trust aging dream; do
  n=$(ls scripts/*${organ}*.py scripts/training/*${organ}*.py \
         openamer-agent/scripts/*${organ}*.py 2>/dev/null | wc -l)
  [ "$n" = "0" ] && echo "  ✗ MISSING: $organ"
done
```
Found missing: `attention/salience`, `conscience/ethics`, `regret`,
`reputation`, `aging`, `endocrine`.

**A missing value-gate is the highest-priority gap.** An agent with drives but no
conscience has a will and no values — it will pursue any drive it feels. The fix
is a deterministic pre-action value-gate (`allow` / `warn` / `block`, no LLM),
consulted BEFORE a goal is pursued: a blocked want is *felt but not acted on*.
An unreachable gate must fail to `warn`, never to `allow`. (Built this session as
`scripts/training/conscience.py`; the pattern is documented in the user-owned
`intrinsic-drives` skill — run `openamer curator adopt intrinsic-drives` if you
want it curator-managed.)

## Pass 2 — ORPHANED (exists, but in no subsystem and no cron)

**An organ is dead if no cron runs it AND no heartbeat subsystem lists it.** The
scripts run fine by hand — which is why nobody notices they were never scheduled.

```bash
python -c "
import re
src=open('openamer-agent/tools/asi/heartbeat.py',encoding='utf-8').read()
for name,body in re.findall(r'self\.subsystems\[\"([a-z_0-9]+)\"\]\s*=\s*Subsystem\((.*?)\n        \)', src, re.S):
    print(f'  {name:12} -> {re.findall(chr(34)+r\"([a-z0-9_./-]+\.py)\"+chr(34), body)}')
"
for s in homeostasis calibration metacognition; do
  echo "  $s: $(grep -c $s openamer-agent/tools/asi/heartbeat.py) hits"   # 0 = orphaned
done
```
Found orphaned: `homeostasis.py`, `calibration.py`, `metacognition.py`.

## Pass 3 — DEAD-cron check: read output, not exit code

```bash
timeout 60 python scripts/homeostasis.py   # exit 1 on WARN is EXPECTED, not a bug
```
False alarm this session: `homeostasis`/`calibration` looked "broken" only
because they exit 1 on their `OVERALL: WARN` verdict. `WARN` means it worked.

## Wiring an orphan back in (and the timeout it needs)

```python
self.subsystems["meta"] = Subsystem(
    name="meta", category="meta", cadence_minutes=60,
    scripts=[ ..., "homeostasis.py", "calibration.py", "metacognition.py",
              "training/conscience.py" ],   # no-arg = self-audit
    timeout=180,   # ⚠️ REQUIRED — 15 scripts exceed the flat 60 s TICK_TIMEOUT
)
```

**The heartbeat runs each script as a bare subprocess with NO arguments.** So the
script must do its useful work on a no-arg call (never fall through to
`print_help()` = the silent no-op of `asi-heartbeat-repair` Symptom 1). Heavy
organs need the subsystem's own `timeout=`, or the flat 60 s default abandons
them mid-run.

Verify by ticking ONE subsystem with the override and watching wall-time vs
`sub.timeout`:
```python
h = Heartbeat(); sub = h.subsystems["meta"]
r = h._tick_with_timeout(sub, force=True)
```

## Pitfall

`any_success: None` is NOT a failure — a subsystem whose scripts print reports
and exit non-zero can still have done its work. Judge from `results[].output`.
