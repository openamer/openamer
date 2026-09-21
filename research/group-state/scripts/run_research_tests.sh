#!/usr/bin/env bash
# Research test suite for the neural-architecture work.
#
# WHY THIS EXISTS: this repo has no `test` script (its package.json only has
# check/fix/audit), and `npm run check` lints TypeScript workspaces that this
# work never touches. The research code is Python, so its gate is Python:
# compile every script, verify every gradient against finite differences, prove
# the backward pass, verify each group's axioms and matrix convention, and
# check for dead code.
#
# Exit 0 only if every stage passes. Each stage runs in its own python process
# so one crash cannot mask the others.
#
# Usage: bash scripts/run_research_tests.sh [--fast]
#        --fast   skip the (slow) end-to-end comparison run

set -u
cd "$(dirname "$0")/.." || exit 1

# Interpreter: prefer the repo's own venv, then any local venv, then python3.
# The original script hard-coded ./venv/Scripts/python.exe, which made the gate
# unusable anywhere but the machine it was written on.
if [ -n "${PY:-}" ] && [ -x "${PY:-}" ]; then
  :                                   # caller supplied one
elif [ -x ./venv/Scripts/python.exe ]; then
  PY=./venv/Scripts/python.exe        # Windows venv (git-bash)
elif [ -x ./venv/bin/python ]; then
  PY=./venv/bin/python                # POSIX venv
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "no python interpreter found (set PY=/path/to/python)" >&2
  exit 1
fi

W=48                      # gate-name column width, used by stage()
FAST=0
[ "${1:-}" = "--fast" ] && FAST=1

pass=0
fail=0
declare -a FAILED

stage() {
  local name="$1"; shift
  # pad to column W; a name that outgrows it gets a separator so the name can
  # never run into PASS/FAIL
  printf "%-${W}s" "$name"
  [ ${#name} -lt "$W" ] || printf ' '
  if "$@" >/tmp/_rt.out 2>&1; then
    echo "PASS"
    pass=$((pass + 1))
  else
    echo "FAIL"
    fail=$((fail + 1))
    FAILED+=("$name")
    sed 's/^/    /' /tmp/_rt.out | tail -14
  fi
}

SCRIPTS=(
  state_tracking_lab.py
  diagnose_rotor_drift.py
  cyclic_state_lab.py
  rotor_snap_lab.py
  rotor_snap_warmup.py
  validate_rotor_snap.py
  final_comparison.py
  gradcheck_cyclic_state.py
  gradcheck_eps_sweep.py
  check_unused_imports.py
  research_arxiv_probe.py
  s5_group.py
  perm_state_lab.py
  diagnose_s5.py
  s5_anneal_lab.py
  s5_prior_check.py
  seed_init_fix.py
  gradcheck_flaky_probe.py
  diagnose_gradient_flow.py
  s5_init_lab.py
  group_scaling_lab.py
  free_group_lab.py
  group_state_engine.py
  test_group_state_engine.py
  test_tool_server_wiring.py
  s5_curriculum_lab.py
  s5_structural_readout.py
  s5_tau_sweep.py
)

echo "==================================================================="
echo "Research suite  (python: $PY)"
echo "==================================================================="

# ---- 1. syntax ------------------------------------------------------------
echo
echo "-- compile --"
for s in "${SCRIPTS[@]}"; do
  # no special case for a missing file: py_compile fails on it anyway, and the
  # failure output names the file
  stage "compile $s" "$PY" -m py_compile "scripts/$s"
done

# ---- 2. gradient correctness ---------------------------------------------
echo
echo "-- gradients (must be verified before any result is read) --"
stage "gradcheck: window/rnn/lstm/rotor" \
      "$PY" scripts/state_tracking_lab.py --gradcheck
stage "gradcheck: cyclic-state convolution" \
      "$PY" scripts/gradcheck_cyclic_state.py

# ---- 3. backward proof + estimator behaviour ------------------------------
echo
echo "-- backward proof --"
stage "snap=False == continuous rotor (fwd+bwd)" \
      "$PY" scripts/validate_rotor_snap.py
stage "eps sweep: noise, not a bug" \
      "$PY" scripts/gradcheck_eps_sweep.py

# ---- 3b. non-abelian group (S_5) -----------------------------------------
echo
echo "-- non-abelian: group axioms + matrix convention + gradients --"
stage "S_5 axioms, generators reach 120/120" \
      "$PY" scripts/s5_group.py
stage "S_5 matrix convention vs composition" \
      "$PY" scripts/perm_state_lab.py --selftest
stage "gradcheck: non-commutative matrix path" \
      "$PY" scripts/perm_state_lab.py --gradcheck
stage "gradcheck: MLP-head path" \
      "$PY" scripts/perm_state_lab.py --gradcheck-mlp
stage "S_5 choice-matrix init is input-dependent" \
      "$PY" scripts/s5_init_lab.py --assert-init
stage "gradcheck: structural readout dL/dS" \
      "$PY" scripts/s5_structural_readout.py --gradcheck
stage "group scaling: axioms+convention+grads" \
      "$PY" scripts/group_scaling_lab.py --selftest
# NOTE: only --selftest is gated. The --quick measurement gives the letter
# choices to the model (exact_choice_logits), so it tests the hand-written
# matrix product, not the architecture -- a circular check that must not be
# presented as evidence. The selftest proves real properties of the embedding
# (freeness, injectivity on reduced words, w.w^-1 == I) and is fast (0.2 s).
stage "free group F_2: embedding is faithful" \
      "$PY" scripts/free_group_lab.py --selftest
stage "group-state ENGINE: save/load/answer/tool" \
      "$PY" scripts/test_group_state_engine.py

# ---- 3c. the tool-server integration --------------------------------------
# These checks need training/tool_server.py, which lives in the HOST project.
# A standalone research checkout does not carry it, so the section is SKIPPED
# there rather than failing on a file that was never meant to be here.
if [ -f scripts/training/tool_server.py ]; then
  echo
  echo "-- integration: tool_server wiring (compile only: starts :8081) --"
  stage "compile tool_server.py (integration)" \
        "$PY" -m py_compile scripts/training/tool_server.py
  stage "group_state registered in TOOLS+EXAMPLES" \
        "$PY" scripts/test_tool_server_wiring.py
else
  echo
  echo "-- integration: SKIPPED (scripts/training/tool_server.py absent) --"
fi

# ---- 4. hygiene -----------------------------------------------------------
echo
echo "-- hygiene --"
stage "no dead imports" "$PY" scripts/check_unused_imports.py
stage "seeded init is reproducible" \
      "$PY" scripts/seed_init_fix.py --check
stage "S_5 task has no trivially exploitable prior" \
      "$PY" scripts/s5_prior_check.py --assert-prior

# ---- 5. the headline result ----------------------------------------------
if [ "$FAST" = "0" ]; then
  echo
  echo "-- end-to-end result (slow: ~15 min in pure python) --"
  stage "final comparison reproduces the claim" \
        "$PY" scripts/final_comparison.py --epochs 400 --warmup 250 --seeds 2
else
  echo
  echo "-- end-to-end result SKIPPED (--fast) --"
fi

echo
echo "==================================================================="
echo "research suite: $pass passed, $fail failed"
if [ "$fail" -gt 0 ]; then
  printf 'failed: %s\n' "${FAILED[*]}"
fi
echo "==================================================================="
[ "$fail" -eq 0 ]
