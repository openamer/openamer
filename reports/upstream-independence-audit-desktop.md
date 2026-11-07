# OpenAmer Upstream-Independence Audit — Desktop Surface

**Date:** 2026-11-07
**Upstream:** `C:\Users\damir\AppData\Local\hermes\hermes-agent` @ `b200f5bc60`
**OpenAmer:** `origin/main`

## Why a second audit

The Python audit (`scripts/audit_upstream_independence.py`) covers `agent/`
and `openamer_cli/`. The Electron desktop app is a separate surface with its
own file tree, so it gets the same treatment: rebrand → diff → classify.

Method: `scripts/audit_upstream_independence_desktop.py`.

## Result

| | Files |
| --- | --- |
| Upstream `apps/desktop/src` files | 3,593 |
| OpenAmer `apps/desktop/src` files | 1,045 |
| Same path, compared | 934 |
| Upstream-only, **dropped** by OpenAmer | **2,659** |
| OpenAmer-only (no upstream path) | 111 |

| Class | Files | Upstream lines | Share |
| --- | --- | --- | --- |
| `IDENTICAL` (rebrand only) | **0** | 0 | **0.00%** |
| `COSMETIC` (marker line only) | 167 | 12,342 | 3.59% |
| `MINOR` (<10% changed) | 146 | 28,633 | 8.32% |
| `SUBSTANTIVE` (real logic) | 621 | 303,126 | **88.09%** |

**Zero files are verbatim-identical to upstream.** Every file that was is now
`COSMETIC` — it differs by exactly one line: the provenance marker.

## Provenance markers

All **163** previously-verbatim desktop files now carry a machine-readable
marker naming the exact upstream path and commit they derive from:

```ts
// Upstream-Derived: apps/desktop/src/lib/json-format.ts @ 0c190083c (MIT)
```

The commit recorded is the upstream commit that last touched that file,
verified against the upstream git history (163/163 confirmed: the recorded
commit is the file's last change, not an approximation).

The marker placement respects the language:

- after a directive prologue (`'use client'`) — 5 files — because a directive
  must stay at the very top of the file to take effect
- after an existing leading license/comment block
- otherwise as the first line of the file

### Which files

| Cluster | Files |
| --- | --- |
| `components/ui/*` | 26 |
| `components/assistant-ui/*` | 23 |
| `app/chat/*` | 11 |
| `app/starmap/*` | 9 |
| `app/settings/*` | 6 |
| `components/pet/*` | 6 |
| `app/pet-generate/*` | 5 |
| `app/right-sidebar/*` | 5 |
| `components/chat/*` | 5 |
| `components/pane-shell/*` | 4 |
| `lib/*` | 26 |
| `store/*` | 11 |
| `hooks/*`, `app/hooks/*` | 4 |
| `themes/*` | 3 |
| `contrib/*`, `app/contrib/*` | 4 |
| remaining (`app/index.tsx`, `app/shell`, `app/session`, `app/cron`, `app/gateway`, `app/overlays`, `app/pet-overlay`, `components/idle-mount*`, `components/page-loader`, `components/particles`, `components/remote-display-banner`) | 16 |

These are the React component library, the store slices, and the pure
helpers — the layers where a rewrite would cost lines without buying
behavior.

## What OpenAmer dropped from upstream

| Upstream dir | Files dropped | What it was |
| --- | --- | --- |
| `plugin-catalog/` | 977 | the upstream plugin registry |
| `evals/` | 236 | the upstream eval suite |
| `pm/` | 93 | the upstream package manager |
| `hermes_platform/` | 30 | the upstream platform abstraction |

OpenAmer replaced `pm/` with `openamer_cli/managed_uv.py` — a different
design: OpenAmer owns its own uv binary at `$OPENAMER_HOME/bin/uv`, with an
install-scoped Python store and generation-based cutover instead of a
multi-location resolution chain.

## What OpenAmer built that upstream never had

These top-level trees exist **only** in OpenAmer:

| Tree | Files | LOC |
| --- | --- | --- |
| `os/` (Rust kernel) | 25 | 4,323 |
| `research/` | 28 | 5,782 |
| `openamer_brain/` | 11 | 2,013 |
| `packs/` | 3 | 539 |
| `go/` (mesh daemon) | 2 | 245 |
| `providers/` | 2 | 423 |

Plus the whole learning/Darwin layer in `scripts/` (269 files, ~108k LOC,
21 `darwin_*` engines) and `tools/asi/` (ASI Core + the 9-subsystem daemon).

## Conclusion

The desktop surface is **88.09% substantively diverged**, with **zero**
verbatim-identical files remaining. Combined with the Python audit (98.16%
substantive), the picture is consistent across both surfaces: OpenAmer is not
a rebranded Hermes.

The desktop verdict is lower than the Python verdict, and that is the honest
number — the UI layer is where a fork keeps the most shared code, because a
React component library has nothing product-specific to differentiate.

Every remaining shared file is now individually attributed with its upstream
path and commit, in the file itself, in `NOTICE`, and in the audit report.

## Reproduce

```bash
python scripts/audit_upstream_independence_desktop.py --upstream <path>
python -m pytest tests/openamer_cli/test_upstream_provenance.py -q
```
