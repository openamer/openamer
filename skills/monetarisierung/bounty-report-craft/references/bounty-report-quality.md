# Bounty Report Quality — session detail (2026-10-02 run)

## Proven run sequence (01 cron run)

- Health check passed: HTTP 200 on `127.0.0.1:5000/debug`; no restart needed.
- No new report files that run (dir contained only template + handbuch) → no feedback grades needed; note this explicitly in the log entry.
- lessons.md did not exist → created it with 2 lessons.

## Lessons written (kept here for reuse/extension)

1. **60-Second Rule (triage checklist).** Triage engineer decides in first 60 seconds. Accepted H1 reports answer, in order: (1) bug type in title, (2) exact endpoint+parameter, (3) numbered repro with copy-pasteable HTTP, (4) visible impact proof, (5) real-world risk in one plain sentence, (6) severity justified (CVSS + why). #1 rejection reason on H1: "cannot reproduce / insufficient PoC".
2. **Impact chaining.** Chain several low-severity bugs into one critical attack path (enumeration → info-leak → ATO). Write the chain as an explicit step diagram; state attacker gain per step.

## Retrieval attempts log (what failed, exact errors)

- `web_extract https://hackerone.com/hacktivity` → backend is search-only, cannot extract.
- `curl https://hackerone.com/hacktivity` → 401 errors JSON.
- `curl /hacktivity/public_table` → 404 page.
- GraphQL POST `hacktivityItems` query → undefinedField (endpoint alive; suggests `activity`).
- GraphQL `activity(first:8)` → missing required arg `id`, rejects `first`, union needs inline selections — dead end blind.
- Fallback that worked: web search for current-year report-writing guides quoting triage stats → curl the article, strip tags, extract lesson material. Source used: hackersonlineclub.com "How to Write Bug Bounty Report That Gets Paid (2026)" (2026-09-02): acceptance rate ~25–35%, 300–800 words + 3–8 screenshots, PoC repro under 10 min, chaining as payout multiplier.

Note: `web_extract` backend was DuckDuckGo search-only that day; if extraction backends get configured (firecrawl/tavily), direct fetches may work again — retest before assuming.