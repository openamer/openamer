# cua-driver Session Recovery Fix

## The problem

On Windows, `scroll(delivery_mode="foreground")` on a Chromium window (Brave,
Chrome) kills the cua-driver daemon-side session. The next tool call returns:

```
this session has ended; call start_session explicitly
```

This happens because foreground-mode actions briefly swap the active window,
and something in that path resets cua-driver's per-session state. The MCP
stdio connection remains open (ClientSession is healthy), but the server-side
session is dead.

## How Hermes fixed it first

Hermes (the upstream of OpenAmer) had the same bug and fixed it in
`_CuaDriverSession.call_tool()`. Three methods were added:

| Method | Purpose |
|--------|---------|
| `_logical_error_text()` | Flatten MCP error result to string for classification |
| `_is_ended_session_result()` | Detect "this session has ended" in tool result text |
| `_revive_declared_session_once()` | Re-register `start_session` + retry the original call |

And one attribute: `_declared_session_id` — persisted from the first
successful `start_session` call so we can reuse it to revive.

## The fix (OpenAmer commit f36672486)

Ported from Hermes into `tools/computer_use/cua_backend.py`. The flow:

```
call_tool(name, args)
  └→ _bridge.run(_call_tool_async(name, args))
     └→ result = MCP tool response
  └→ if name == "start_session" and ok:
       self._declared_session_id = args["session"]  # saved!
  └→ if _is_ended_session_result(result):
       _revive_declared_session_once(name, args, result, timeout)
         └→ _bridge.run("start_session", {session: id})
         └→ if ok: _bridge.run(name, args)
  └→ return result
```

Key design decisions:
- Recovery is in `call_tool()`, not in individual action methods — covers ALL
  tools (capture, click, scroll, type, list_windows) transparently.
- Only retries ONCE — a second "session ended" is surfaced as a real error.
- `start_session` and `end_session` calls are excluded from recovery to
  avoid infinite loops.
- The fix does NOT require a cua-driver update — it's purely on the
  OpenAmer side.

## Verification

All `tests/computer_use/` tests pass (57 passed, 2 skipped).

## Related fixes

### CI: release-daily workflow missing uv (commit 6b041ed37)

The GitHub Actions `release-daily.yml` workflow calls `scripts/daily-release.py` which
runs `uv lock` after version bumping. The ubuntu-24.04 runner does not have `uv`
pre-installed. Fixed by adding `astral-sh/setup-uv@v10.0.1` before the release step.

### .gitignore: stray Windows temp files (commit 628304321)

`git add -A` on Windows can pick up files with absolute Windows paths mangled into
filenames like `C:UsersdamirAppDataLocalTemp...`. Added `C:*` to `.gitignore` to
prevent these from being tracked.