## Correction + fresh measurement: the shared resolver already exists — nine times over

I re-derived this on **current `main` (`5b5d89885`)** instead of repeating my own numbers from earlier in this thread. Two things came out different, and one of them is wrong on my side.

### 1. My earlier figures here are stale — measured replacement below

The claim was "124 modules reference `OPENAMER_HOME`, 76 of them read it naively." Measured today against `origin/main` (not the working tree — that is a feature branch, so a working-tree count is a different number):

```
git grep -lE 'os\.environ(\.get)?\(["'"'"']OPENAMER_HOME' origin/main -- '*.py' | wc -l
184        # naive env-first reads, repo-wide
git grep -l "OPENAMER_HOME" origin/main -- '*.py' | wc -l
895        # files referencing the variable at all
git grep -lE 'os\.environ(\.get)?\(["'"'"']OPENAMER_HOME' origin/main -- 'scripts/*.py' | wc -l
106        # naive env-first reads under scripts/ only
```

I am not going to paper over the delta: my prior numbers came from a different HEAD with a narrower pattern, and they under-count. The direction is the point, and it is worse, not better — the class is roughly 2.4x the size I reported. Treat the numbers above as the ones to work from.

### 2. The resolver I argued for is already in the tree — 9 private copies, no shared one

This changes the shape of the fix from "add a helper" to "hoist the helper that already exists":

```
$ git grep -l "def _resolve_openamer_home" origin/main -- '*.py' | wc -l
9
$ git grep -l "def _resolve_openamer_home" origin/main -- '*.py'
agent/goal_engine.py
scripts/autonomous_loop.py
scripts/darwin_agents.py
scripts/darwin_gate.py
scripts/darwin_metacognition.py
scripts/darwin_promote.py
scripts/darwin_synthesize.py
scripts/swarm_os.py
tools/credential_files.py
```

And `scripts/darwin_agents.py` already implements exactly the guard I asked for in the comment above — rejects the doubled-drive artefact, requires the candidate to exist, and refuses any directory that is not an install root:

```python
if cand is None or not cand.exists():
    return default
# An existing directory is not enough: a scratch dir adopted as the install
# silently evolves an empty population while the real home is untouched.
if _is_install_root(cand):
    return cand
print(f"[home] WARNING: OPENAMER_HOME={cand} exists but is not an OpenAmer "
      f"install root; falling back to {default}.", file=sys.stderr)
```

So the primitive exists, it is correct, and it is copy-pasted nine times while 184 sites still read the env directly. The ask is smaller than what I proposed: **hoist `_resolve_openamer_home` + `_is_install_root` into the shared layer and point the nine private copies at it.** No new design, and the reference implementation is already in-tree.

### 3. The three PRs this thread is about — #48 has drifted

Measured against `origin/main` (`5b5d89885`) just now:

| PR | base | commits behind main | touches |
|---|---|---|---|
| #48 | `d436a396` | **6** | `scripts/scoreboard.py`, `tests/scripts/test_scoreboard.py` |
| #49 | `5b5d8988` | 0 | `scripts/group_state_engine.py`, `scripts/test_group_state_engine.py` |
| #50 | `5b5d8988` | 0 | `scripts/measure_nonderivable_goal.py`, `scripts/self_learning.py`, `tests/scripts/test_self_learning_verdict.py` |

#49 and #50 are based on current head and still apply cleanly; **#48 needs a rebase before it can be judged on its merits** — its base is 6 commits back.

The env-first read is still on main at HEAD — re-read through the API at `5b5d89885`, `scripts/group_state_engine.py` L42–45 is byte-identical to what I quoted earlier:

```python
DEFAULT_DIR = os.path.join(
    os.environ.get("OPENAMER_HOME",
                   os.path.join(os.path.expanduser("~"), "AppData", "Local",
                                "openamer-laptop")),
    "models")
```

### What I am not claiming

I did not re-run these modules end-to-end against the leaked env this time, and I am not adding new behavioural evidence for the downstream `None` / `0` symptom — the two comments before this one established that. This comment is counts, file states, and PR base drift, all of it re-measured on `5b5d89885`. The box is on 24/7; happy to re-measure on request.
