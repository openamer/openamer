#!/usr/bin/env bash
# Template: research verification gate.
#
# Copy to scripts/run_<topic>_tests.sh in the project, edit the two CONFIG
# blocks, and wire it into the project's canonical test command so it cannot be
# forgotten (e.g. package.json: "test": "bash scripts/run_<topic>_tests.sh --fast").
#
# WHY A TEMPLATE: the project may have NO test script at all. Reporting that is
# a blocker report; building the gate is the fix. See
# references/verification-gates.md for the failure classes this catches.
#
# Usage: bash scripts/run_<topic>_tests.sh [--fast]
#        --fast skips ONLY the slow end-to-end stage, never a correctness stage.

set -u
cd "$(dirname "$0")/.." || exit 1

# ============================ CONFIG 1: interpreter =========================
PY=./venv/Scripts/python.exe        # Windows/git-bash; "./venv/bin/python" on Linux
W=48                                # gate-name column width (see stage())
# ===========================================================================

FAST=0
[ "${1:-}" = "--fast" ] && FAST=1

pass=0
fail=0
declare -a FAILED

# One stage per PROCESS: a crash in one check must not mask the others.
stage() {
  local name="$1"; shift
  # pad to column W. A name LONGER than W must still be separated from
  # PASS/FAIL, or the output reads "…(6 groups)PASS" and the result is
  # unparseable. Never hardcode the pad twice -- keep it in W.
  printf "%-${W}s" "$name"
  [ ${#name} -lt "$W" ] || printf ' '
  if "$@" >/tmp/_gate.out 2>&1; then
    echo "PASS"
    pass=$((pass + 1))
  else
    echo "FAIL"
    fail=$((fail + 1))
    FAILED+=("$name")
    sed 's/^/    /' /tmp/_gate.out | tail -15   # output only on failure
  fi
}

# ======================== CONFIG 2: scripts + stages =========================
# Every script in the project. ADD NEW SCRIPTS HERE IN THE SAME CHANGE that
# creates them -- code sitting beside the gate is unverified code.
SCRIPTS=(
  # example_lab.py
  # example_model.py
  # example_analysis.py
)

# Behavioural checks, in order of EVIDENTIAL STRENGTH (cheap proofs first, so a
# failure is localized):
#   1. gradients   - finite differences vs analytic derivatives
#   2. proof       - model-vs-model equivalence / backward correctness
#   3. axioms      - mathematical ground truth (groups, invariants, conventions)
#   4. hygiene     - dead imports, determinism, no trivially exploitable baseline
# ===========================================================================

echo "==================================================================="
echo "Gate  (python: $PY)"
echo "==================================================================="

echo
echo "-- compile --"
for s in "${SCRIPTS[@]}"; do
  # No special case for a missing file: py_compile fails on it anyway and names
  # it in the output. A hand-written [ -f ] branch duplicates the counting logic
  # and drifts out of sync with stage().
  stage "compile $s" "$PY" -m py_compile "scripts/$s"
done

# Verify gradients BEFORE reading any result: a wrong derivative produces
# plausible-looking tables.
echo
echo "-- gradients --"
# stage "gradcheck: <models>" "$PY" scripts/example_lab.py --gradcheck

echo
echo "-- backward proof --"
# stage "model equivalence (fwd+bwd)" "$PY" scripts/proof_model_equiv.py

echo
echo "-- axioms / convention --"
# stage "group axioms + generator reach" "$PY" scripts/check_group.py

echo
echo "-- hygiene --"
# A gate that cannot fail is a rubber stamp -- keep a negative test for each.
# stage "no dead imports" "$PY" scripts/check_unused_imports.py
# Determinism: same seed MUST give identical weights. Catches the silent flake
# where an init helper used the global random module instead of the passed rng.
# stage "seeded init is reproducible" "$PY" scripts/check_seed_determinism.py --check
# Classification tasks: the task must not be solvable by predicting the majority
# class. Report the majority base + target entropy next to every accuracy figure.
# stage "no trivially exploitable prior" "$PY" scripts/check_prior.py --assert-prior

if [ "$FAST" = "0" ]; then
  echo
  echo "-- end-to-end result (slow) --"
  # stage "reproduces the headline claim" "$PY" scripts/example_e2e.py
else
  echo
  echo "-- end-to-end result SKIPPED (--fast) --"
fi

echo
echo "==================================================================="
echo "gate: $pass passed, $fail failed"
if [ "$fail" -gt 0 ]; then
  printf 'failed: %s\n' "${FAILED[*]}"
fi
echo "==================================================================="
[ "$fail" -eq 0 ]
