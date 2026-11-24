# Publishing an own OpenAmer plugin repo — measured 2026-11-22

Worked example: `openamer/openamer-plugin-browser-health` (v0.1.0). Everything
below was executed, not planned.

## 1. Repo shape — two files are the plugin

```
plugin.yaml          # name, version, description, author   (plugin.yaml ONLY — no json/yml manifest)
__init__.py          # register(ctx) -> ctx.register_tool(...)
README.md            # install + output example
LICENSE              # MIT
pytest.ini           # testpaths = tests
tests/test_*.py      # canonical check
```

`plugin.yaml` for the example:

```yaml
name: browser-health
version: 0.1.0
description: "Report the local CDP browser stack read-only: ..."
author: "openamer"
```

The `name` becomes the install directory (`<OPENAMER_HOME>/plugins/browser-health`)
and the `enable/disable` key — treat it as the identity, not a label. A trailing
`plugin.yaml` with no `version` installs, but `plugins list` then shows a blank
version column, so always set it.

## 2. Create the repo — the namespace decides the endpoint

```python
# POST https://api.github.com/user/repos         -> 201, lands under the account
# POST https://api.github.com/orgs/openamer/repos -> 404 "Not Found"
```

`openamer` is a **user** account on GitHub, so the org endpoint 404s. The
`/user/repos` call produced `openamer/openamer-plugin-browser-health` directly.

Body used:

```json
{"name": "openamer-plugin-browser-health",
 "description": "OpenAmer plugin: ...",
 "private": false,
 "has_issues": true, "has_wiki": false, "has_projects": false,
 "auto_init": false}
```

`auto_init: false` + a local `git init` push avoids the empty-commit merge dance.

## 3. Push, then tag the catalog entry

```bash
git branch -M main
git remote add origin https://github.com/openamer/openamer-plugin-browser-health.git
git push -u origin main
```

```python
# PUT /repos/openamer/openamer-plugin-browser-health/topics
{"names": ["openamer-plugin", "openamer", "cdp", "chrome"]}
# -> ['cdp', 'chrome', 'openamer', 'openamer-plugin']
```

Topic **is** the discovery index: `_github_plugin_search` queries
`topic:openamer-plugin` first. Verified after setting it:

```
q=''        -> [text-stats, browser-health]
q='browser' -> [browser-health]
q='health'  -> [browser-health]
```

Before the topic, the same query for `browser` returned **0**.

## 4. Install from GitHub into the live install

```bash
python -c "from openamer_cli.main import main; main()" plugins install openamer/openamer-plugin-browser-health
# Cloning ... -> ✓ Installed: <OPENAMER_HOME>\plugins\browser-health
python -c "from openamer_cli.main import main; main()" plugins enable browser-health
```

`enable` prints an override prompt: "Allow this plugin to replace built-in tools?
… browser-health may not override built-in tools." Non-interactively that is the
*denied* branch and it is fine — the plugin loads; only `override=True` tools are
refused. Re-grant later with `--allow-tool-override`.

Hub after install (measured): `total: 89 {'bundled': 86, 'git': 2, 'user': 1}`,
with `browser-health … source=git runtime_status=enabled`.

## 5. The dependency trap — write plugins against the SMALLEST runtime

| venv | `websocket-client` | `pytest` | pip |
|---|---|---|---|
| `<OPENAMER_HOME>/venv` (install) | 1.9.2 | 9.1.1 | yes |
| `openamer-agent/venv` (agent) | **absent** | **absent** | **absent** (uv-managed) |

A plugin that imports `websocket` works in one runtime and reports "unreadable"
in the other — a health plugin that lies because a package is missing is worse
than useless. Two consequences:

- **Runtime code: stdlib only.** The example ships a minimal RFC 6455 client
  (~90 lines: handshake, one masked text frame, read frames until the matching
  `id`) instead of `websocket-client`. Verified in the *agent* venv:
  `websocket-client importiert? False` while `cookies=444 via cdp` still worked.
- **Tests: run them where pytest exists.** The agent venv has no pip, so
  `python -m pytest` there is `No module named pytest` — that is an interpreter
  choice, not a broken suite. Run the repo's suite with the install venv's
  interpreter; for the strict environment use a plain `python -c` import check.

## 6. What the plugin must measure correctly (the browser-health case)

Counting cookies from the SQLite file is the trap: while Chrome runs, the WAL is
open and **both** `?mode=ro&immutable=1` and `?mode=ro` failed live (`-1`) on a
perfectly healthy profile that actually held 444 cookies. `Storage.getCookies`
over CDP returned 444 immediately. Order: CDP while the browser is alive, SQLite
only as the fallback for a dead browser, and `-1` (unreadable) must never be
flattened to `0`.

Minimal CDP call shape that worked (stdlib): build a `Host`/`Sec-WebSocket-Key`
handshake against the page's `webSocketDebuggerUrl`, send ONE masked text frame
with `{"id":1,"method":"Storage.getCookies","params":{}}`, then read frames until
`reply["id"] == 1` — skipping ping/pong (0x9/0xA) and stopping on close (0x8).

## 7. Canonical check in the repo

`tests/test_browser_health.py`, 9 tests, 6.7 s, all green:

- manifest identity (name/version/description/author)
- `register(ctx)` kwargs ⊆ real `PluginContext.register_tool` signature
- headless UA detection (headless / visible / empty / `None`)
- unreachable port → `down` with a reason, no exception
- empty profile dir → `-1`, never `0`
- live stack → not headless, `cookies >= 0`, `cookies_source == "cdp"`
  (**`pytest.skip` when no browser runs**, so "nothing to check" is not red)

```bash
cd <plugin repo>
"C:\Users\damir\AppData\Local\openamer-laptop\venv\Scripts\python.exe" -m pytest -v
# collected 9 items … 9 passed in 6.77s
```
