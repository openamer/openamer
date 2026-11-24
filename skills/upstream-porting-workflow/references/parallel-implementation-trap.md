# The parallel-implementation trap

A `ModuleNotFoundError` that is **not** a port gap, and the ~4000 lines wasted by
treating it as one. 2026-09-16.

## The setup

`tests/acp/test_server.py` failed at **collection**:

```
acp_adapter/server.py:1034: __getattr__
    from openamer_cli.plugin_compat import warn_once
ModuleNotFoundError: No module named 'openamer_cli.plugin_compat'
```

Real gap #1 (worth porting): 19 first-party files carry `PLUGIN-COMPAT`
`__getattr__` blocks calling `warn_once` on the lazy path. Ported
`openamer_cli/plugin_compat.py` (332 lines) + `compat_manifest.json` (2091
entries, 0 residual upstream tokens) + the guard script. Correct call.

With that fixed, the file ran but the MCP tests failed:

```
FAILED ...TestRegisterSessionMcpServers::test_registers_stdio_servers
E   AssertionError: assert 'test-server' in {}
WARNING acp_adapter.server:server.py:421 Session …: failed to register ACP MCP servers
ModuleNotFoundError: No module named 'tools.mcp_tool_discovery'
```

## The wrong turn

`acp_adapter/server.py:417` does
`from tools.mcp_tool_discovery import register_mcp_servers`, inside a
`try/except Exception` that logs the warning above and returns. I wrote an
**import-chain resolver** (`port -> retry import -> next missing module`) and let
it run to fixpoint. It ported, in order:

```
tools/mcp_tool_common.py     tools/mcp_tool_config.py
tools/mcp_tool_errors.py     tools/mcp_tool_lifecycle.py
tools/mcp_tool_loop.py       tools/mcp_tool_registration.py
tools/mcp_tool_handlers.py   tools/mcp_tool_content.py
tools/mcp_tool_schema.py     tools/mcp_tool_scope.py
tools/tool_output_truncate.py
+ (second pass) agent / health / sampling / server_run / transport
```

17 files, ~4000 lines — and it still didn't work:

```
AttributeError: module 'tools.mcp_tool' has no attribute '_ensure_mcp_sdk'
```

The split modules read origin state through an `_OriginProxy` that defers to the
**facade** `tools/mcp_tool.py`. Upstream's facade is 734 lines; ours is a
**6412-line monolith**. The split set expects a decomposed tree this repo is not.

## The evidence that should have stopped it

```bash
# 17 call sites use the monolith — and two import PRIVATE state
git grep -n "from tools.mcp_tool import" -- '*.py'
#   cli.py        -> shutdown_mcp_servers, discover_mcp_tools, _servers, _lock
#   gateway/run.py-> shutdown_mcp_servers, discover_mcp_tools, _servers, _lock
#   agent/turn_context.py, cron/scheduler.py, openamer_cli/{main,banner,...}.py …

# The monolith ALREADY defines both symbols the broken caller wants
grep -n "def register_mcp_servers\|def refresh_agent_mcp_tools" tools/mcp_tool.py
#   5607: def register_mcp_servers(...)
#   5991: def refresh_agent_mcp_tools(...)

# THE DECIDER — what the failing test patches
grep -n 'patch("tools.mcp_tool\.' tests/acp/test_server.py
#   2258:  with patch("tools.mcp_tool.register_mcp_servers", side_effect=capture_register)
```

`_servers` / `_lock` are **private module state** — the monolith is load-bearing.
And the test patches the monolith path, so a split implementation *cannot* pass it
by construction. Porting was not merely redundant; it was unsatisfiable.

## The correct fix — two lines in the caller

```python
# acp_adapter/server.py  (the file was ported POST-decomposition)
- from tools.mcp_tool_discovery import register_mcp_servers
+ from tools.mcp_tool import register_mcp_servers

- from tools.mcp_tool_agent import refresh_agent_mcp_tools
+ from tools.mcp_tool import refresh_agent_mcp_tools
```

Result: `13 failed, 79 passed` → `10 failed, 82 passed`, and **all three**
`TestRegisterSessionMcpServers` cases green (`grep -c TestRegisterSessionMcpServers`
on the failures = 0). The remaining 10 were unrelated session/prompt/slash cases.

## Lessons

1. **Count the tree's own consumers before porting a module into it.** 17 call
   sites on an existing implementation = you are about to duplicate, not fill a gap.
2. **Private-state imports (`_servers`, `_lock`) are the tell** that a monolith is
   structural. A decomposed rewrite cannot satisfy them.
3. **Grep the failing test for `patch("...")` early.** It names the module the
   test considers authoritative — the ground truth for where the fix belongs.
4. **`try/except Exception` hides this entire class.** The symptom is a missing
   feature + one WARNING, never a traceback. Read the captured-log section.
5. **A chain resolver is a great tool with a dangerous default.** It will happily
   port an entire parallel subsystem. Gate it: if the first `git grep` for the
   module's consumers shows a populated existing implementation, stop and check
   whether you're fixing the caller instead.
6. **Revert loudly.** The corrective commit named the wrong turn explicitly so the
   next agent doesn't re-port the split set from the same evidence. Leaving it as
   a silent deletion invites the same mistake.

## Related: the guard script's own blind spot

`scripts/check_compat_pointers.py` used `ROOT.rglob("*.py")` skipping only a
**root-level** venv. This tree keeps `.venv` (22857 `.py` files) AND a local
`Python/` interpreter install (1128) at the repo root; CI has neither — which is
why upstream never hit it. It scanned **27887** files and took **>6 minutes**.

Fix: match `SKIP_DIRS` on **any path component**, not just `parts[0]`, and add
`.venv`, `venv`, `site-packages`, `.tox`, `.nox`, `dist`, `egg-info`, `Python`.
Runtime dropped to ~40s, revealing the real verdict: **2123 in-tree sites still
resolve compat pointers directly** (a genuine backlog, not a clean bill).

**Lesson:** a repo-local venv/interpreter at the root silently poisons any
whole-tree walk. When a scan is inexplicably slow, print the file count and a
per-top-level-dir histogram *before* optimising anything:

```python
import collections, os
c = collections.Counter()
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if f.endswith(".py"):
            c[os.path.relpath(dp, ROOT).split(os.sep)[0]] += 1
print(sum(c.values()), c.most_common(10))
```
