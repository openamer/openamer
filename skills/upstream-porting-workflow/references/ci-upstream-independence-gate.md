# CI gate: enforcing the independence claim on every PR

**Session 2026-11-07.** The upstream-independence audit produces real numbers,
but a measurement that only runs locally is a claim, not a guarantee. The owner
asked for the claim to be *enforced* — and that means it has to run in CI, on
every PR, as a blocking required check.

## The reusable workflow

File: `.github/workflows/upstream-independence.yml`

```yaml
name: Upstream independence

on:
  workflow_call:
    inputs:
      event_name:
        description: The event name from the calling orchestrator (pull_request or push).
        type: string
        required: true

permissions:
  contents: read

concurrency:
  group: upstream-independence-${{ github.ref }}
  cancel-in-progress: true

jobs:
  independence:
    name: upstream independence (blocking)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Checkout code
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1

      - name: Set up Python
        uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0
        with:
          python-version: "3.11"

      - name: Check for runtime upstream coupling
        run: python scripts/audit_upstream_coupling.py --fail-on-findings

      - name: Check for unattributed upstream names
        run: python scripts/port_from_upstream.py --check-only

      - name: Check the provenance markers
        run: |
          python -m pytest tests/openamer_cli/test_upstream_provenance.py \
            tests/scripts/test_upstream_independence_audit.py -q
```

### Three gates, all CI-capable (no local upstream checkout needed)

| Step | Script | What it proves | Exit 1 when |
|---|---|---|---|
| 1 | `audit_upstream_coupling.py --fail-on-findings` | No runtime import of upstream module names; no network/git pull from upstream repo | Any import or network hit outside declared attribution sites |
| 2 | `port_from_upstream.py --check-only` | No upstream identifier survives in shipped tree outside a declared attribution site | Any unattributed upstream token found |
| 3 | `pytest` (provenance + audit tests) | Every shared file still carries its marker; NOTICE lists Python-side derived files | Any marker missing / malformed / not in NOTICE |

**These three scripts are the *entire* CI gate.** The line-level divergence audit
(`audit_upstream_independence.py` + desktop variant) needs the local upstream
checkout, so it is NOT part of this workflow. Run it locally before pushing.

## Wiring into the orchestrator

File: `.github/workflows/ci.yml` — added as a **non-lane-gated** job:

```yaml
upstream-independence:
  # Not lane-gated: the independence claim must hold on every change, not
  # only on the lanes that touch Python or the frontend. A new upstream
  # import can arrive through any file.
  name: Upstream independence
  needs: detect
  uses: ./.github/workflows/upstream-independence.yml
  with:
    event_name: ${{ needs.detect.outputs.event_name }}
```

And required in the gate:

```yaml
all-checks-pass:
  needs:
    - detect
    - tests
    - lint
    - js-tests
    - upstream-independence    # <-- added here
    - e2e-desktop
    ...
```

## The verdict script test pins the wiring

File: `tests/ci/test_upstream_independence_workflow.py` — 6 tests that verify:

1. The workflow exists and is valid YAML
2. The workflow runs the three checks (string match on step `run`)
3. All actions are pinned (`@sha` or `@vN`)
4. The lane is listed in `all-checks-pass` needs
5. The lane is **not path-gated** (no `if:` condition, only `needs: [detect]`)
6. The verdict script treats a failure in this lane as blocking

**Why path-gating is wrong here:** a new upstream import can arrive through
*any* file (a doc update, a skill, a config change). If the independence lane
only runs when the Python/frontend classifier says so, coupling slips in
unnoticed. The lane must run on every PR.

## The contract test for the verdict gate

File: `tests/ci/test_evaluate_needs.py` — two new tests:

```python
def test_the_independence_lane_is_a_required_lane():
    needs = _needs(detect="success", tests="success", upstream_independence="failure")
    blocking = _mod.verdict(needs)
    assert blocking == ["upstream_independence"]

def test_the_independence_lane_passes_when_green():
    needs = _needs(detect="success", tests="success", upstream_independence="success")
    blocking = _mod.verdict(needs)
    assert blocking == []
```

## What changed in the coupling scan to make it CI-clean

File: `scripts/audit_upstream_coupling.py` — new `--fail-on-findings` flag and
attribution-site awareness:

```python
# Reads ATTRIBUTION_FILES + TOOLING_FILES from port_from_upstream.py
# so legitimate references are not flagged as leaks
allowed = _known_attribution_sites()

for f in files:
    is_attribution_site = rel in allowed
    # Skip import scan on attribution sites
    # Route NET_RE hits on attribution sites to 'attributed' bucket
```

**Result:** the gate now reports

```
[1] runtime imports of upstream module names
  NONE - no OpenAmer module imports an upstream module

[2] network / git references to the upstream repo
  NONE

[2b] attributed upstream references (declared, not coupling): 9 files
  apps/desktop/src/lib/preview-act/act-in-page.ts  (lines [31])
  openamer_cli/_early_recovery.py  (lines [36])
  scripts/audit_upstream_coupling.py  (lines [32])
  scripts/audit_upstream_independence.py  (lines [32])
  scripts/audit_upstream_independence_desktop.py  (lines [21])
  scripts/port_from_upstream.py  (lines [1, 27])
  scripts/upstream_rebrand.py  (lines [35])
  tools/desktop_ui.py  (lines [18])
  tools/drive_preview_tool.py  (lines [11])

[3] residual 'hermes' token: 8 files
  openamer_cli/identity.py  x1  lines [448]
  packs/pro-pack/skills/windows-computer-use/references/session-recovery-fix.md  x3  lines [17, 19, 33]
  scripts/audit_upstream_coupling.py  x2  lines [25, 136]
  ...
```

The exit code is **0** — clean on every run.

## What changed in the port script

File: `scripts/port_from_upstream.py` — `act-in-page.ts` added to
`ATTRIBUTION_FILES` so its legitimate upstream reference is not a leak.

## The full test suite that must pass

```bash
python scripts/port_from_upstream.py --check-only              # gate 2
python scripts/audit_upstream_coupling.py --fail-on-findings   # gate 1
python -m pytest tests/openamer_cli/test_upstream_provenance.py \
  tests/scripts/test_upstream_independence_audit.py -q         # gate 3
```

All three run in ~4 seconds locally and ~45 seconds in CI.

## The artefacts (committed in the repo)

| Path | Role |
|---|---|
| `.github/workflows/upstream-independence.yml` | Reusable CI gate |
| `.github/workflows/ci.yml` (modified) | Orchestrator wiring |
| `scripts/audit_upstream_coupling.py` | Gate 1 — coupling scan with attribution awareness |
| `scripts/port_from_upstream.py` | Gate 2 — leak scan, single rebrand map |
| `tests/ci/test_upstream_independence_workflow.py` | Workflow contract test |
| `tests/ci/test_evaluate_needs.py` (modified) | Verdict gate contract test |
| `reports/upstream-coupling-scan.json` | Coupling scan output (regenerated) |

## What this enforces

The claim **"OpenAmer is its own implementation, not a rebranded Hermes fork"**
is now a **blocking required check on every PR and push**. A change that
introduces an upstream import, a network pull, or drops a provenance marker
**cannot merge**. The numbers from the local divergence audit (98.16% /
88.09% substantive) are now **continuously defended**, not just measured once.

## Related

- `references/upstream-independence-audit.md` — the local divergence audit method
- `fork-differentiation` skill — the branding layer (README/VISION/NOTICE)
- `upstream-porting-workflow` skill — the mechanical porting pipeline