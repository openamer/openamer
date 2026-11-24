# Port-dropped methods: restore-vs-revert, and the probes that decide

Session 2026-10-10. Seven failing PLUGIN/TOOL suites on `origin/main` of the
bundled-plugin port. Same disease as PR #132 (feishu) and the `8e6a3629c`
methods drop: a "Port … from upstream" commit **rebuilt** files and quietly
dropped names the unchanged tests still call.

Symptoms seen, one per flavour:

```
AttributeError: module 'tools.homeassistant_tool' has no attribute '_HASS_TOKEN'
AttributeError: 'ManagedToolGatewayConfig' object has no attribute 'nous_user_token'
AttributeError: 'module' object at tools.spotify.client has no attribute ...
assert 'NOT capable of image-to-image' in "<description string>"
```

## 1. The decisive probe: did the TEST move with the port?

Run this **before** deciding whether to fix the code or amend the test:

```bash
git diff <port_commit>^:tests/tools/test_x.py HEAD:tests/tools/test_x.py
```

- **Empty output** → the test predates the port. It is the ground truth; the
  *implementation* regressed. Restore behaviour; touch no assertion.
- **Non-empty** → the test travelled with the port, so the assertion itself may
  be the drift (see upstream-porting-workflow trap 2).

This was empty for all four failing groups here, which settled every one of them
in a single command. It is cheaper than reading both versions and is immune to
"the docstring already describes the new behaviour" hand-waving.

## 2. Git archaeology when the path history was rewritten

The repo's real history is a giant squashed dump (`9cb4dc471 a2a worker:
replies` adds ~10k files), so **path-scoped history lies**:

```bash
git log --oneline --follow -- plugins/spotify/client.py     # -> one ancient commit. Useless.
git log --oneline -S "library_contains" --all               # -> finds the port + follow-ups
git log --oneline --all -S "def get_devices" -- <path>      # -> names the exact commits
```

And do not use ancestry as a proxy for content:

```bash
git merge-base --is-ancestor <port_commit> HEAD && echo "IS ancestor" || echo "NOT ancestor"
# NOT ancestor — yet:  git diff <port_commit>:plugins/spotify/tools.py HEAD:plugins/spotify/tools.py
#                      -> EMPTY (byte-identical)
git diff --stat <port_commit>:<path> HEAD:<path>
```

The port commit can be off-branch while its file content is identical to HEAD.
Compare trees with `git diff <c>:<path> HEAD:<path>`, never with ancestry.

`git log <c>:<path> | grep -nE "def "` gives you the pre-port method list in one
shot — that is the inventory of what was dropped.

## 3. Size the repair: surgical restore vs. `git checkout <pre-port> --`

Both work. Measure the diff before choosing:

| Approach | Diff | Loses |
|---|---|---|
| `git checkout <port>^ -- <files>` | 889 + / 512 − (≈1400 lines on 2 spotify files) | the intentional decomposition (`_dispatcher`, `_schema`, PLUGIN-COMPAT blocks) |
| Surgical: re-add the lost API + rewire callers | ~50 lines | nothing |

Decision rule: **the port's new STRUCTURE is not the bug; the dropped NAMES are.**
When the port also introduced a refactor worth keeping (a dispatcher table, a
compat shim, a `compat_manifest.json` entry), restore the behaviour *into* the
new structure. Revert wholesale only when the ported file is an incoherent mess
whose refactor has no consumer.

The one thing a wholesale revert is right for: when the ported file has no new
structure at all — then `git checkout <port>^ -- <path>` is the faithful, one-line
fix and produces an exactly-correct result (it did for spotify: 15/15 green).

## 4. `compat_manifest.json` is a contract the tests do NOT enforce

The repo carries `compat_manifest.json` (12.5k lines) listing every name the
"Sep 2026 decomposition" kept importable from an OLD module path, implemented by
`# ---- BEGIN PLUGIN-COMPAT ----` blocks with a PEP 562 `__getattr__`.

```bash
grep -n "spotify" compat_manifest.json       # facade / name / kind / target
```

- **No test validates it** — `scripts/check_compat_pointers.py` only checks that
  in-tree code does not *import through* a facade (and it times out walking this
  machine's tree; skip it locally).
- So a rename/removal will not turn a suite red for missing a manifest entry —
  check the manifest by hand before renaming a public symbol, and keep the
  `PLUGIN-COMPAT` block intact when you revert a file.

## 5. Incomplete rebrand: the `nous_*` → `openamer_*` leftover

A rebrand that renamed a dataclass field but missed one consumer looks exactly
like a dropped symbol. Majority rules — rename the *consumer*, not the field:

```bash
grep -rn "nous_user_token"  --include=*.py .   # -> 2 hits, both in image_generation_tool.py
grep -rn "openamer_user_token" --include=*.py . # -> 7+ modules already use the new name
```

**Trap:** tests that set the stale attribute on a `MagicMock` / `SimpleNamespace`
still pass, because the read path is never reached on that branch (the test
monkeypatches the function that would read it). A green test does NOT prove the
attribute name is right. Only the failing test that takes the *real* path
(`resolve_managed_tool_gateway()` → real frozen dataclass) exposes it.

## 6. Restoring an override seam a config migration removed

The port replaced env access with a secret store and dropped the module globals:

```python
# pre-port:  _HASS_URL: str = ""   _HASS_TOKEN: str = ""   # "kept for backward
#                                                          #  compat (e.g. test monkeypatching)"
# port:      get_secret("HASS_TOKEN", "")
```

The fix is NOT to revert the `get_secret` migration. Restore the module-level
override as a **precedence layer** above the store, so both the migration and the
seam survive:

```python
_HASS_URL: str = ""
_HASS_TOKEN: str = ""

def _get_config():
    return (
        (_HASS_URL or get_secret("HASS_URL", "http://homeassistant.local:8123") or "").rstrip("/"),
        _HASS_TOKEN or get_secret("HASS_TOKEN", "") or "")
```

Apply it to the availability gate too (`bool(_HASS_TOKEN or get_secret("HASS_TOKEN"))`),
or the tool stays hidden while the header reader works.

## 7. Attribute a non-listed failure without stashing

When a suite you did not touch fails, prove it pre-existing in a **second,
untouched checkout** rather than stashing staged work:

```bash
cd <pristine-repo> && pytest tests/...::test_x -q --tb=line    # same failure on main
```

Here `test_get_platform_tools_expands_composite_when_mixed_with_configurable`
failed identically in `openamer-repo` (clean) → pre-existing, reported as such,
not "fixed".

## 8. Scratch worktree when told not to touch main

```bash
git worktree add --detach /c/Users/<u>/wt-plugins origin/main
# ... work ... commit nothing, push nothing; remove with `git worktree remove <dir>`
```

Detached HEAD keeps `main` pristine and gives you a whole separate tree to run
suites in.
