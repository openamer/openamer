# Runtime-tree parity and probe bypasses (2026-09-17)

Follow-up to `wave-lag-repair-2026-09-16.md`. That session established *sync the
runtime tree*. This one found the three ways that still goes wrong, plus the
verification mistake that made a broken fix look green.

## 1. The runtime tree lags silently — 67 commits

Every repo test passed; the running agent had none of the fixes. Green repo tests
are not evidence about production:

```bash
cd "$OPENAMER_HOME/openamer-agent"
git fetch origin main
git rev-list --count HEAD..origin/main      # 67
```

`git fetch` + `git checkout origin/main -- <paths>` works even though the two
histories have no common root — the divergent root blocks `pull`/`merge-base`,
not content transfer. Prefer it over `cp`: it applies the repo's EOL policy.

## 2. Partial sync — sources without tests

The dangerous middle state. I synced the **source** files and left the **test**
files and the runner behind, so the live tree ran *new code against old
expectations* and reported failures the repo did not have:

| Tree | `test_setup_feishu` |
|---|---|
| repo | 18 passed / 0 failed |
| runtime (sources synced, tests stale) | 15 passed / **3 failed** |
| runtime (after syncing tests + `run_tests.sh`) | **18 passed / 0 failed** |

**Check every artifact class, not just the obvious one:**

- source modules
- the tests that assert on them
- the **runner itself** (`scripts/run_tests.sh` — its hermetic-env handling was
  part of the fix; a stale runner silently re-breaks the tests it should run)
- config/schema if the change touched it

## 3. Distinguishing EOL drift from real drift

Seven files "differed". Five were only CRLF-vs-LF; **two were genuinely missing my
hunk**. `git hash-object` cannot tell these apart, and neither can `git status` in
the runtime tree (which reports everything dirty regardless of relevance).

Compare with line endings normalised, then print the first differing line:

```python
a = (repo / rel).read_bytes().replace(b"\r\n", b"\n")
b = (live / rel).read_bytes().replace(b"\r\n", b"\n")
if a != b:
    la, lb = a.split(b"\n"), b.split(b"\n")
    i = next(k for k, (x, y) in enumerate(zip(la, lb)) if x != y)
    print(f"line {i+1}\n  repo: {la[i][:90]!r}\n  live: {lb[i][:90]!r}")
```

Output that settled it:

```
SAME(crlf-normalised)  agent/delegation_context.py
SAME(crlf-normalised)  openamer_cli/kanban_db.py
REAL DIFF              tests/gateway/test_feishu_approval_buttons.py  (line 423)
      repo: b'            token="tok_normal",  # noqa:SEC test fixture value, not a credential'
      live: b'            token="tok_normal",'
```

Packaged as `scripts/runtime_tree_parity.py` (exit 1 when a real diff remains).

## 4. Stale background runs report against an old tree

A verification job launched **before** the sync finished and reported failures
that the sync had already fixed — and, more dangerously, its "passes" would have
told me nothing. Before trusting a background test log, check it started **after**
the last write:

```bash
ls -la /tmp/<log>          # mtime vs when you last synced/committed
grep -c "EXIT=" /tmp/<log> # 0 = still running, results incomplete
```

Re-run rather than reasoning about whether the timing overlapped.

## 5. The probe-bypass trap (the real mistake)

Adding `create_task(creator_task_id=…)` required wiring the kwarg into
`inherit_creator_origin`, which imports a private helper this tree never received.
My probe passed `creator_task_id=None` — and the callee **early-returns** on a
falsy id:

```python
def inherit_creator_origin(conn, task_id, creator_task_id, *, created_at):
    if not creator_task_id:
        return                                   # <-- probe never got past here
    from openamer_cli.kanban_db import _inherit_notify_subs   # ImportError
```

So the probe returned a clean `{ok: true, …}` and I reported the happy path as
working. The real test — which passes `creator_task_id=self_tid`, exactly like
`tools/kanban_tools.py:889` — failed:

```
ImportError: cannot import name '_inherit_notify_subs'
  openamer_cli.kanban_db_graph.py:15
```

**Why a hand-written probe cannot catch this:** I wrote the probe *after reading
the code*, so it inherited my blind spot. The ported test encodes the consumer's
real call shape. Rules:

- Derive probe arguments from the **call site**, not from intuition:
  `grep -n "create_task(" tools/kanban_tools.py`
- Any new optional parameter whose falsy path is trivial **must be probed
  truthy** — that is where the real branch lives.
- Run the canonical test as the arbiter; the probe is a convenience, never the
  evidence.
- Report the miss explicitly rather than silently re-running.

## 6. A new parameter drags in the callee's dependencies

Wiring one kwarg reached a third missing symbol one level deeper:

```
create_task(creator_task_id=…)          ← added here
  └─ inherit_creator_origin              ← existed
       └─ _inherit_notify_subs           ← absent here, present upstream
```

Before calling a ported parameter done, walk the callee one level and check every
name it imports from a sibling:

```bash
grep -rn "def inherit_creator_origin" -A12 openamer_cli/ | grep -nE "import "
grep -c "def _inherit_notify_subs" openamer_cli/kanban_db.py   # 0 = still missing
```

Same wave-lag discipline, applied recursively — `symbol_census.py` catches it in
one pass if re-run after each batch.

## 7. Don't report a "feature gap" without the two-command proof

I claimed `Task.completion_contract` and `create_task(creator_task_id)` were a
*feature gap* (upstream semantics absent here). Wrong — both exist upstream and
were simply never ported. The deciding check is cheap:

```bash
git log --oneline -S"completion_contract" -- openamer_cli/kanban_db.py  # empty = never here
grep -c "completion_contract" "$UPSTREAM/hermes_cli/kanban_db.py"       # 6 = exists upstream
```

Name exists upstream ⇒ **port gap, build it**. Only absent-upstream or
semantics-diverged counts as a feature gap.
