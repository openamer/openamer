# Pre-Port Target Check — measure before you port

**When a task says "port feature X from upstream into OpenAmer", the first action is to
verify the target does not already have X.** A porting assignment can be a complete
no-op, and the honest deliverable is measurements saying so — not a diff.

## The lesson (measured 2026-10-18)

An assignment asked to port two Hermes capabilities into OpenAmer: a
Batch-Trajectory-Runner and MoA aggregation. Both already existed in OpenAmer, more
deeply integrated than upstream:

| Feature | Hermes | OpenAmer | Verdict |
|---|---|---|---|
| Batch-Trajectory-Runner | `batch_runner.py` exports trajectories only | `openamer-agent/batch_runner.py` (1321 lines, 16 toolset distributions, checkpointing, `--resume`, ShareGPT format) feeds `daemon-trajectories.jsonl` → `openamer-brain.jsonl` → `auto_retrain.py` (LoRA) | already present, **more integrated** |
| MoA aggregation | `moa_reference` + `moa_aggregator` blocks | `agent/moa_loop.py` (2126 lines) + `openamer_cli/moa_config.py` (full preset schema: `reference_models`, `aggregator`, `reference_temperature`, `aggregator_temperature`, `fanout`, `privacy_filter`, `degraded_reference_policy`) | already present, **more configurable** |

The only real defect found was a 2-line CLI bug in the already-existing runner
(`list_distributions` parameter shadowed the imported function →
`TypeError: 'bool' object is not callable` on `--list_distributions`). Fixed and
verified: `16 passed in 2.44s`.

## The recipe

Before writing a single line of port code:

```bash
# 1. Does the target already have a file named for the feature?
find <target> -iname "*<keyword>*" -name "*.py" | grep -v __pycache__ | grep -v venv

# 2. Does it import cleanly and expose the expected API?
cd <target> && python -c "import <module>; print('OK')"

# 3. Does the feature's config block exist in the target's config?
grep -n "<keyword>" <target>/config.yaml

# 4. Does the target's own test suite cover it?
find <target>/tests -iname "*<keyword>*"

# 5. Smoke-test the actual call shape (no network, no key):
python -c "import <module>; <module>.main(<safe_flag>=True)"
```

**A feature that already exists is not a gap — it is a finding.** Report it with the
measurements; do not re-port it. Re-porting an existing, locally-evolved
implementation overwrites OpenAmer's own conventions (see
`wave-lag-repair-2026-09-16.md` for the cost of porting a parallel implementation).

## The "it's already there" signature

The assignment's framing ("nummer 2 und drei", "port Hermes' X") presupposed a gap.
The tell that the premise is wrong is not a missing file — it is that the target's
*integration* is deeper than upstream's. Hermes' batch runner **exports** trajectories
for an external RL trainer; OpenAmer's feeds its own Brain → LoRA pipeline. That
integration is the evidence, not the file count.

When the target's pipeline already consumes the upstream feature's output format,
the port is not needed — the target is ahead on that axis. Say so, and name the axis.

## Related

- `wave-lag-repair-2026-09-16.md` — the cost of porting a *parallel* implementation
  when the target already has one (17 files / ~4000 lines, all reverted).
- `parallel-implementation-trap.md` — the three probes that settle "port vs. fix the
  caller" before touching anything.
- The `upstream-porting-workflow` SKILL.md "Steps" section: this check is Step 0,
  before "Discover".