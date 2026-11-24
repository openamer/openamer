#!/usr/bin/env bash
# Statically re-runnable verification for the gate_attribution_probe.
#
# Why this exists: the probe exits 0 whether or not its verdict line is honest,
# and (pre-21.09.26) it could exit 0 having printed NO verdict at all when a
# single extractor-only candidate suppressed the conclusion. So `echo $?` proves
# nothing -- assert on the output TEXT. Doing it here creates no temp .py, so
# nothing extra enters the changed-path census (see references §3 and §8).
#
# Usage:  bash scripts/verify_gate_probe.sh
# Exit:   0 = clean verdict, no alarm;  1 = assertion failed
set -u

HOME_DIR="${OPENAMER_HOME:-$HOME/AppData/Local/openamer-laptop}"
PROBE="$HOME_DIR/skills/internet-learning-cycle/scripts/gate_attribution_probe.py"
OUT="$(mktemp)"

cd "$HOME_DIR" || { echo "FAIL: cannot cd $HOME_DIR"; exit 1; }
if [ ! -f "$PROBE" ]; then echo "FAIL: probe not found: $PROBE"; exit 1; fi

echo "=== 1. py_compile ==="
if python -m py_compile "$PROBE"; then echo "PY_COMPILE_OK"; else
  echo "FAIL: py_compile"; rm -f "$OUT"; exit 1
fi

echo "=== 2. probe run (--section gate) ==="
timeout 300 python "$PROBE" --section gate > "$OUT" 2>&1
rc=$?
echo "probe_exit:$rc"

echo "=== 3. assert on output TEXT (never on the exit code) ==="
fails=""

# The verdict must be present and must be one of the two honest outcomes.
if grep -q "=> seed space exhausted" "$OUT"; then
  echo "ASSERT: clean verdict line present"
elif grep -qE "candidate\(s\) matched an UNKNOWN helper" "$OUT"; then
  echo "ASSERT: novel-chrome alarm present (real finding -- investigate, do not patch a gate)"
else
  fails="$fails verdict-absent"
  echo "ASSERT_FAIL: NO verdict line -- this is the 21.09.26 silent-verdict bug, not a clean bill of health"
fi

# No stale-registry alarm may remain in the histogram.
alarms=$(grep -c "INVESTIGATE\|UNKNOWN helper" "$OUT" || true)
echo "alarm_hits:$alarms"
if [ "$alarms" != "0" ]; then
  fails="$fails stale-registry-alarm"
  echo "ASSERT_FAIL: stale-registry alarm(s) above. For each helper run:"
  echo "  grep -rn \"def <helper>\" scripts/training/buffer_store.py scripts/training/internet_learner.py"
  echo "2 defs => registry staleness: batch-add to KNOWN_HELPERS (dated comment + line numbers),"
  echo "          then re-run. 0 defs => genuinely novel: probe the FULL 300-char string first."
fi

rm -f "$OUT"
if [ -n "$fails" ]; then echo "VERIFY: FAIL$fails"; exit 1; fi
echo "VERIFY: PASS"
