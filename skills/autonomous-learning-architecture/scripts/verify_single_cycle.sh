#!/usr/bin/env bash
# verify_single_cycle.sh — Verify that a training script's --once mode
# runs exactly ONE cycle and logs it, not all N cycles.
#
# Usage: bash /path/to/verify_single_cycle.sh <script_name_no_ext>
# Example: bash scripts/verify_single_cycle.sh internet_learner
#
# Checks:
#   1. Python syntax
#   2. "once" flag → 1 new log entry
#   3. "--once" flag → 1 new log entry (both forms)
#
# Works with any training script that:
#   - accepts both `once` and `--once` flags
#   - writes to a JSONL log (named <script_name_no_ext>_log.jsonl)

set -euo pipefail

SCRIPT_NAME="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_PY="${SCRIPT_DIR}/${SCRIPT_NAME}.py"
LOG_FILE="${SCRIPT_DIR}/${SCRIPT_NAME}_log.jsonl"

echo "=== Verify: ${SCRIPT_NAME} ==="

# 1. Syntax check
echo "  [1/3] Syntax check..."
python -c "
import ast
ast.parse(open('${SCRIPT_PY//\\/\\\\}').read())
print('    SYNTAX OK')
"

# 2. Count log entries before
BEFORE=0
[ -f "$LOG_FILE" ] && BEFORE=$(wc -l < "$LOG_FILE")

# 3. Run with 'once' flag
echo "  [2/3] Testing 'once' flag..."
python "$SCRIPT_PY" once 2>&1 | tail -1
AFTER_ONCE=$(wc -l < "$LOG_FILE")
if [ $((AFTER_ONCE - BEFORE)) -ne 1 ]; then
    echo "    FAIL: expected 1 new log entry, got $((AFTER_ONCE - BEFORE))"
    exit 1
fi
echo "    OK: 1 new log entry"

# 4. Run with '--once' flag
echo "  [3/3] Testing '--once' flag..."
python "$SCRIPT_PY" --once 2>&1 | tail -1
AFTER_BOTH=$(wc -l < "$LOG_FILE")
if [ $((AFTER_BOTH - AFTER_ONCE)) -ne 1 ]; then
    echo "    FAIL: expected 1 new log entry, got $((AFTER_BOTH - AFTER_ONCE))"
    exit 1
fi
echo "    OK: 1 new log entry"
echo ""
echo "=== All 3/3 checks passed ==="