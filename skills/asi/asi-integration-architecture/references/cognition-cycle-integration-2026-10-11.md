# Cognition Cycle Integration — 2026-10-11

## What We Built

An integrated cognitive cycle (`tools/asi/cognition.py`) that chains **world_model + prediction + self_model in ONE pass** — the first time failed predictions become corrections.

## The Problem It Solved

Before: `training/predict_validate.py` and `training/self_model.py` ran in SEPARATE subsystems (learning). Result:
- World model: 168 predictions, **0 corrections**
- Calibration: 19/204 correct = 9.3% → adjustment floored at 0.3
- No loop closure — predictions never saw their outcomes

After: Single `cycle()` run does `perceive → recall → predict(calibrated) → score → correct → validate → reflect`

## Key Implementation Decisions

### Native Subsystem (not cron wrapper)
- Registered in `tools/asi/heartbeat.py` as `Subsystem(name="cognition", cron_ids=[], native=True, scripts=["cognition_cycle.py"], cadence_minutes=30, timeout=300)`
- `native=True` → `_reconcile_scripts` skips it, explicit script list used
- `native_map` routes `"cognition_cycle.py" -> "tools.asi.cognition.cycle"` (direct import, no subprocess)
- Runs in-process in the heartbeat tick

### Corrections Path Proven
```bash
# Inject a miss (sim 0.429) -> first correction in system history
./openamer.exe asi cycle --situation "X" --effect "Y"
# Logs: correction written (edges 652 -> 653 -> 652 after cleanup)
# First `corrected: true` edge in world_model.jsonl
```

### API Fixes Required (wrappers didn't match real modules)
| Wrapper | Missing / Wrong | Fixed |
|---------|----------------|-------|
| `tools/asi/world_model.recall` | No `exclude` param | Added `exclude=Set[str]` |
| `tools/asi/prediction` | Exposed `apply_confidence_adjustments` | Real name: `apply_confidence_to_new_predictions()` |
| `tools/asi/world_model` | Edge self-match (cosine 1.0) | Added `edge_key` exclusion + temporal filter (only earlier edges) |

## Traps Discovered During Integration

### 1. Signature Drift Between Wrappers and Real Modules
**Nothing noticed** because the blocks were never called in a chain. **Chain them and their signatures diverge.** Check signatures before wiring.

### 2. Self-Match in Nearest-Neighbour Recall
An edge is always its own nearest neighbour (cosine 1.0). Fix needs **BOTH**:
- `recall(..., exclude={edge_key})`  
- Temporal filter: drop priors whose `ts` is not strictly older than the observation
Either alone still self-confirms.

### 3. Script Directory on `sys.path[0]` Causes Recursion
`python tools/asi/<module>.py` puts `tools/asi/` on `sys.path[0]`, so a wrapper's `importlib.import_module("<name>")` re-imports ITSELF → `RecursionError`. Fix: remove the script directory from `sys.path` first.

### 4. `OPENAMER_HOME` Must Be Native Path
An MSYS `/c/...` value makes every `SCRIPTS_TRAINING` lookup miss → `ModuleNotFoundError: world_model`. Always use `C:/Users/...` form.

### 5. Native Function Called Bare by Tick Must Be Safe With No Args
The heartbeat calls `cycle()` with nothing; every parameter needs a default.

## Shipping to Canonical Repo

### Cross-Tree Sync (Live Tree → Canonical Repo)
The live tree (`C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent`) is **not a git repo**. The canonical repo is `C:\Users\damir\openamer-repo`.

1. Copy files directly: `cp live/tools/asi/cognition.py repo/tools/asi/cognition.py`
2. In repo: `git add` — normalizes CRLF→LF automatically (`core.autocrlf=true`)
3. Verify staged diff: `git diff --cached --stat` should show purely additive changes
4. **Before ship.py**: restore cron artifacts to HEAD (`git restore reports/darwin-*.json*`)
5. Run `scripts/ship.py` — it runs verify → branch → commit → push → PR → merge

### CRLF Trap
Unstaged diff shows 1600+ lines of noise; staged diff is clean. See `upstream-porting-workflow/references/crlf-normalization-windows.md`.

### Rebase Discipline
When main advances during CI wait:
1. `git fetch origin main`
2. `git rebase origin/main` — resolve conflicts (keep ours for our files, theirs for cron)
3. `git push --force`
4. Wait for CI, merge

### PR #163 Result
- Merge commit: `1ebd42479f`  
- 8 files changed, 840 insertions(+), 33 deletions(-)
- All 6 new/modified files on `origin/main`
- 67 tests pass on `origin/main` (canonical runner)

## Verification Commands

```bash
export OPENAMER_HOME="C:/Users/<u>/AppData/Local/openamer-laptop"  # native path!
cd <install>/openamer-agent

# CLI cycle
./venv/Scripts/openamer.exe asi cycle --status
./venv/Scripts/openamer.exe asi cycle --limit 6                      # autonomous
./venv/Scripts/openamer.exe asi cycle --situation "X" --effect "Y"   # proves correction path

# Heartbeat tick
./venv/Scripts/openamer.exe asi heartbeat --tick --system cognition --force

# Tests (canonical runner)
<laptop-venv>/Scripts/python.exe -m pytest tests/tools/test_asi_cognition.py -q
bash scripts/run_tests.sh tests/tools/test_asi_cognition.py tests/tools/test_asi_heartbeat.py ...
```