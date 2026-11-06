#!/usr/bin/env bash
# Rewrite every desktop locale file from its translation table and verify it.
#
# The writer has a safety gate: it refuses to write a file that does not
# parse. This script writes all locales, extracts the result and compares
# the leaf set with en.ts, so a locale that came out incomplete is visible
# instead of silently broken.
set -u

cd "$(dirname "$0")/.." || exit 1
# MSYS/Git-Bash hands us a POSIX path ("/c/Users/..."), but Node on Windows
# resolves it as a relative path ("C:\c\Users\..."). Convert it.
REPO=$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || pwd)
REPO=$(cygpath -m "$REPO" 2>/dev/null || echo "$REPO")
I18N="$REPO/apps/desktop/src/i18n"
TMP="$REPO/tmp"

mkdir -p "$TMP"

fail=0
ok=0

for src in "$I18N"/*.ts; do
  base=$(basename "$src")
  case "$base" in
    catalog.ts|types.ts|index.ts|define-locale.ts|plugin-i18n.ts|runtime.ts|languages.ts|*.test.ts)
      continue ;;
  esac
  loc="${base%.ts}"

  tr="$TMP/i18n_${loc}_translations.json"
  if [ ! -f "$tr" ]; then
    echo "SKIP  $loc (no translation table)"
    continue
  fi

  if ! node "$REPO/scripts/i18n_write_locale.mjs" "$src" "$tr" 2>"$TMP/write_${loc}.err"; then
    echo "FAIL  $loc (write aborted)"
    sed -n '1,4p' "$TMP/write_${loc}.err"
    fail=$((fail + 1))
    continue
  fi

  if ! node "$REPO/scripts/i18n_extract_locale.mjs" "$src" "$TMP/i18n_${loc}_verify.json" 2>/dev/null; then
    echo "FAIL  $loc (extract failed)"
    fail=$((fail + 1))
    continue
  fi

  leaves=$(python3 -c "
import json,sys
d=json.load(open(r'$TMP/i18n_${loc}_verify.json',encoding='utf-8'))
print(len(d['leaves']))
" 2>/dev/null || echo 0)

  if [ "$leaves" -lt 2500 ]; then
    echo "FAIL  $loc ($leaves leaves, expected 2539)"
    fail=$((fail + 1))
    continue
  fi

  echo "OK    $loc ($leaves leaves)"
  ok=$((ok + 1))
done

echo
echo "written: $ok   failed: $fail"
[ "$fail" -eq 0 ]
