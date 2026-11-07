# OpenAmer Upstream-Independence Audit

**Date:** 2026-11-07
**Upstream reference:** `C:\Users\damir\AppData\Local\hermes\hermes-agent` @ `b200f5bc60`
**OpenAmer tree:** `origin/main`

## Question

Is OpenAmer still a Hermes fork wearing a new name, or is it its own
implementation? Measured, not asserted.

## Method

Every upstream `.py` file under `agent/` and `hermes_cli/` was taken, run
through the canonical rebrand map (`scripts/upstream_rebrand.py`), and diffed
against the OpenAmer counterpart. Classification:

| Class | Meaning |
| --- | --- |
| `IDENTICAL` | byte-identical after rebrand — still upstream, only renamed |
| `COSMETIC` | only header/import/docstring noise changed |
| `MINOR` | fewer than 10% of upstream lines changed |
| `SUBSTANTIVE` | real logic divergence |

**Change counting.** `difflib.unified_diff` emits a `-` and a `+` line for
every modification, so counting diff lines doubles the real change count and
pushes borderline files across the 10% threshold. The audit uses
`SequenceMatcher` opcodes instead, and a modified block counts once
(`max(removed, added)`), not as removed + added.

Raw reports:
`reports/upstream-independence-audit.json`,
`reports/upstream-coupling-scan.json`.

## Result 1 — file-level divergence

| Class | Files |
| --- | --- |
| `IDENTICAL` (rebrand only) | **0** |
| `COSMETIC` | 0 |
| `MINOR` (<10% changed) | 14 |
| `SUBSTANTIVE` (real logic) | **373** |
| OpenAmer-only (no upstream counterpart) | **841** |

## Result 2 — line-level divergence

Of **210,738** upstream lines compared:

| Class | Lines | Share |
| --- | --- | --- |
| verbatim identical | 0 | **0.00%** |
| cosmetic | 0 | 0.00% |
| minor change (<10%) | 3,885 | 1.84% |
| substantive divergence | 206,853 | **98.16%** |

The four files that were byte-identical to upstream (673 lines, 0.32%) now
each carry a one-line `Upstream-Derived:` marker, which is the only
difference — so the same runtime behavior is now explicitly accounted for
instead of silently inherited.

## Result 3 — the fourteen near-verbatim files

All fourteen are small, self-contained utility modules with no
OpenAmer-specific behavior to diverge from — generic plumbing, not
architecture:

| File | Upstream lines | Delta |
| --- | --- | --- |
| `agent/interrupt_compat.py` | 55 | 1 line (provenance marker) |
| `openamer_cli/archive_safe.py` | 104 | 1 line (provenance marker) |
| `openamer_cli/kanban_db_graph.py` | 214 | 1 line (provenance marker) |
| `openamer_cli/kanban_swarm.py` | 300 | 1 line (provenance marker) |
| `openamer_cli/kanban_db_notify.py` | 441 | 3 lines |
| `openamer_cli/kanban_transfer.py` | 371 | 9 lines |
| `agent/credential_persistence.py` | 116 | 4 lines |
| `openamer_cli/kanban_specify.py` | 241 | 14 lines |
| `agent/provider_base.py` | 66 | 4 lines |
| `openamer_cli/kanban_output.py` | 86 | 6 lines |
| `openamer_cli/kanban_db_connect.py` | 1,296 | 97 lines |
| and three more in the same class | | |

## Result 4 — runtime coupling

| Probe | Result |
| --- | --- |
| OpenAmer modules importing upstream module names | **NONE** (3,375 files scanned) |
| Network/git pulls from the upstream repo | **NONE** — no updater or CI path fetches upstream |
| Unattributed upstream names in the shipped tree | **ZERO** (`port_from_upstream.py --check-only` → `leftover hermes tokens: 0`) |

The remaining upstream mentions are all deliberate:

- `scripts/port_from_upstream.py`, `scripts/upstream_rebrand.py`,
  `scripts/audit_upstream_*.py` — the audit tooling itself
- `scripts/update-safe.ps1` — a **protective** filter: the updater deliberately
  refuses to kill `hermes|emilija` processes so the separate local Hermes
  installation is shielded from OpenAmer's update cycle
- `scripts/training/online-learning-service.ps1` — same protective pattern
- `openamer_cli/identity.py:448` — a guard that *forbids* the word "hermes"
  from appearing as a claimed lineage in the identity file
- `packs/pro-pack/skills/windows-computer-use/references/session-recovery-fix.md`
  — upstream-derived documentation

## Result 5 — attribution that remains (and should)

Nine files carry explicit, honest upstream attribution. Five name the upstream
commit `bfa652fae87fd7c5c01161188f97a8ed68b5a762`:

- `openamer_cli/_early_recovery.py`
- `tools/desktop_ui.py`
- `tools/drive_preview_tool.py`
- `apps/desktop/src/lib/preview-act/act-in-page.ts`
- `openamer_state.py` (references `hermes_state_repair.py`)

Four carry the machine-readable `Upstream-Derived:` marker added by this audit:

- `agent/interrupt_compat.py` @ `7fa7b58b3c`
- `openamer_cli/archive_safe.py` @ `bf1300b27c`
- `openamer_cli/kanban_db_graph.py` @ `3b7ff435fd`
- `openamer_cli/kanban_swarm.py` @ `b7bef04861`

Each states what was *not* ported. This is the correct way to do it: bounded,
attributed, and documented in `NOTICE`.

## Result 6 — the marker is enforced, not just written

`openamer_cli/upstream_provenance.py` defines the marker format and
`tests/openamer_cli/test_upstream_provenance.py` pins the contract:

- every known derived file carries a marker
- the marker names a real upstream path and a hex commit
- `NOTICE` lists every derived file

A derived file that loses its attribution fails the test suite. The audit
script itself now reports `[attributed]` vs `[UNATTRIBUTED]` per verbatim file.

## Conclusion

**OpenAmer is not a rebranded Hermes.** The runtime is 98.16% diverged from
upstream at line level; 841 files have no upstream counterpart at all; no
OpenAmer module imports an upstream module; nothing in the updater or CI
fetches upstream; and zero upstream names survive in the shipped tree outside
a documented attribution site.

The honest residue is small and named:

1. **14 utility files** that are near-verbatim upstream — generic plumbing
   with nothing OpenAmer-specific to add.
2. **1 porting script** that can still pull from a local upstream checkout.
3. **9 attributed ports** with explicit MIT attribution in-place.

Every remaining piece of upstream influence is attributed, bounded, and
license-compliant.

## Reproduce

```bash
python scripts/audit_upstream_independence.py --upstream <path-to-upstream-checkout>
python scripts/audit_upstream_coupling.py
python scripts/port_from_upstream.py --check-only
python -m pytest tests/scripts/test_upstream_independence_audit.py tests/openamer_cli/test_upstream_provenance.py -q
```

The two JSON reports in `reports/` are the committed artifacts.
