## Correction to my comment above, plus which of the three PRs is actually mergeable today

Posted two hours ago I said "#48 needs a rebase — its base is 6 commits back." That was measured off the wrong thing. Re-measured through the API on `main` (`5b5d89885`, fetched just now):

```
PR  base.ref                                  base.sha  commits  file state on main
48  fix/28-respawn-test-psutil-hermetic       d436a396        1  scripts/scoreboard.py         -> HTTP 404, DOES NOT EXIST
49  main                                      5b5d8988        3  scripts/group_state_engine.py -> sha 3fb51701 (= the file I quoted)
50  main                                      5b5d8988        1  scripts/self_learning.py      -> sha 10672134
```

So **#48 is not six commits behind `main` — it is based on a different branch entirely** (`fix/28-respawn-test-psutil-hermetic`, the branch #28 landed from). That matters more than the commit count: `scripts/scoreboard.py` is **not on `main` at all** (404 via the contents API, `git log origin/main -- scripts/scoreboard.py` = 0 commits). #48 therefore cannot land as a fix to a main file; as-is it would *introduce* the file. Rebasing onto `main` is a precondition for review, not a nicety — my earlier phrasing undersold it.

**#49 and #50 are the two that are honestly reviewable right now.** Both report `base.ref: main` with base sha `5b5d8988` = current head, and both apply cleanly (`mergeable_state: unstable`, which is CI state, not a conflict). #49 is the sharper of the two — its `..` left side is byte-identical to the main file, so the diff reads against real code, and it carries the most specific measurement in this whole thread:

```python
# A home is only usable by THIS engine if its models/ dir already holds an
# artifact. Presence of cron/ or memories/ is NOT enough ...
_ARTIFACT_GLOB = "group_state_*.json"
def _has_artifacts(root):
    models = os.path.join(root, "models")
    if not os.path.isdir(models):
        return False
    return bool(glob.glob(os.path.join(models, _ARTIFACT_GLOB)))
```

That is the same idea I argued for two comments ago, arrived at independently and with better evidence: *23.09.26 — a leaked `OPENAMER_HOME` grew `cron/` + `memories/` at 00:57 with no `models/` at all*. A predicate on install markers is provably insufficient, because a foreign home can acquire the markers without ever acquiring the artifacts.

### One integration risk worth catching before anyone hoists anything

If the "hoist `_resolve_openamer_home` into the shared layer" step from my comment above is taken up, note that the tree will then contain **two different, incompatible predicates** for the same question:

| implementation | predicate | verdict on a home with `cron/` + `memories/` but no `models/` |
|---|---|---|
| `scripts/darwin_agents.py` `_is_install_root()` | install markers | **accept** |
| `scripts/group_state_engine.py` `_has_artifacts()` (#49) | the caller's artifacts | **reject** |

Both are defensible in isolation — the darwin scripts don't need `models/`, the group-state engine needs nothing else — and they will still be wrong if merged into one function with one answer. The caller-specific test is the correct shape (the group-state reasoning above is the proof), so the shared helper should take the artifact the caller requires, not pick one global marker set. Otherwise the hoist silently replaces #49's fix with the weaker predicate it was written to replace.

### Standing numbers (unchanged, re-measured on `5b5d89885`)

```
184  files with a naive env-first read of OPENAMER_HOME          (repo-wide, *.py)
106  of them under scripts/*.py
895  files referencing OPENAMER_HOME at all
  9  private copies of def _resolve_openamer_home
```

### What I am not claiming

I did not run the three PRs, did not execute the modules, and did not open the Actions runs behind `unstable`. This comment is base refs, file shas and the diff-vs-main comparison, all re-measured on `5b5d89885`. The box is on 24/7 — happy to re-measure on request.
