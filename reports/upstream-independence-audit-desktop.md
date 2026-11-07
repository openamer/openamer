# OpenAmer Upstream-Independence Audit — Desktop Surface

**Date:** 2026-11-07
**Upstream:** `C:\Users\damir\AppData\Local\hermes\hermes-agent` @ `b200f5bc60`
**OpenAmer:** `origin/main` @ `51fb53e10d4`

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
| `IDENTICAL` (rebrand only) | 163 | 12,259 | **3.56%** |
| `COSMETIC` | 4 | 83 | 0.02% |
| `MINOR` (<10% changed) | 146 | 28,633 | 8.32% |
| `SUBSTANTIVE` (real logic) | 621 | 303,126 | **88.09%** |

## What the 163 verbatim files are

They cluster in layers that carry no product logic:

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

The rest are leaf utilities with no OpenAmer-specific behavior to diverge
from: `lib/json-format.ts`, `lib/pool.ts`, `lib/sanitize.ts`,
`lib/session-ids.ts`, `lib/session-refs.ts`, `lib/utils.ts`,
`hooks/use-debounced.ts`, `hooks/use-delayed-true.ts`, `store/tool-dismiss.ts`,
`themes/install.ts`, and similar.

These are the React component library, the store slices, and the pure
helpers. They are the parts where a rewrite would cost lines without buying
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

The desktop surface is **88.09% substantively diverged**, with 3.56%
remaining verbatim in the React component library and pure helper modules.
Combined with the Python audit (98.16% substantive), the picture is
consistent across both surfaces: OpenAmer is not a rebranded Hermes.

The desktop verdict is lower than the Python verdict, and that is the honest
number — the UI layer is where a fork keeps the most shared code, because a
React component library has nothing product-specific to differentiate.

The 163 verbatim desktop files are the remaining open item: unlike the Python
side, they carry no provenance marker yet.

## Reproduce

```bash
python scripts/audit_upstream_independence_desktop.py --upstream <path>
```
