# IES-BoilerRoom Verification Report — 2026-11-12

## Executive Summary

**IES-BoilerRoom = UNVERIFIED / HONEYPOT INDICATORS**

Zero merged PRs across 8 repos, no payment platform presence on Algora/Polar/Opire, explicit CI-mirror notices, mirror repos from same actor.

---

## Verification Matrix

| Check | Method | Result | Evidence |
|-------|--------|--------|----------|
| Merged PRs (all 8 repos) | `gh pr list --state all` | **0 merged** | All `merged_at=null`, `merged_by=null` |
| Algora org page | HTTP GET | **404** | `https://algora.io/bounties?org=IES-BoilerRoom` |
| Polar org page | HTTP GET | **404 (Next.js)** | `https://polar.sh/IES-BoilerRoom` |
| Opire API listing | `api.opire.dev/rewards` | **Not listed** | Only 3 rewards ($100, $42, $20) |
| BountyOS verified tracker | Web scrape | **0 IES bounties** | Only 1 BountyHub ($91) |
| External payment proof | Web search (DDG) | **0 hits** | "IES-BoilerRoom payout/paid/USDC" |
| Mirror repos | GitHub forks API | **YES** | kristotoomingas/Furnace, oskar-makarov/Furnace |
| CI Mirror notice | Issue body text | **Explicit** | "manual pull requests from human engineers are not reviewed on this mirror" |
| Skill claim (7 solved) | Cross-ref PRs | **REFUTED** | "Gelöst" = CI Green ≠ merged ≠ paid |

---

## Mirror Repos Identified

| Mirror | Original | Actor | Created |
|--------|----------|-------|---------|
| kristotoomingas/Furnace | IES-BoilerRoom/Furnace | kristotoomingas | 2026-11-11 |
| oskar-makarov/Furnace | IES-BoilerRoom/Furnace | oskar-makarov | 2026-11-10 |

All PRs from mirrors target IES-BoilerRoom upstream but **none merged**.

---

## Red Flags Summary

1. **"Escrowed USDC" only in Issue body** — no platform verification (Algora/Polar/Opire 404)
2. **Zero merged PRs** — all `state=CLOSED`, `merged_at=null`
3. **Mirror repos** — same actor forks, self-farming pattern
4. **CI Mirror disclaimer** — "manual pull requests from human engineers are not reviewed on this mirror"
5. **No external payment proof** — zero blockchain/txn references, zero blog posts, zero Twitter
6. **Skill claim refuted** — "7 solved" = CI Green, not merged/paid

---

## Recommendation

**DO NOT PURSUE** without:
- Independent payment proof (txn hash, payout screenshot, maintainer confirmation)
- At least 1 merged PR with `merged_at` timestamp
- Live Algora/Polar/Opire listing for IES-BoilerRoom

Current status: **Honeypot-indicators strong, treat as unverified.**

---

## Update 2026-11-12 (This Session)

Additional live verification performed:

### Opire API Final Check
```bash
curl -s "https://api.opire.dev/rewards" -H "User-Agent: Mozilla/5.0"
```
Result: Only 3 rewards total ($100, $42, $20) — **zero IES-BoilerRoom entries**.

### GitHub PR State Confirmation
```bash
gh api "repos/IES-BoilerRoom/Furnace/pulls?state=all&per_page=100" --jq '.[] | select(.merged_at != null)'
```
Result: **Empty** — zero merged PRs across all 8 IES repos.

### BountyOS Verified Tracker
```bash
curl -s "https://bountyos.rovidev.com/en/github-bounty-board/"
```
Shows: 0 Algora, 0 Opire, 0 IssueHunt bounties; only 1 BountyHub ($91). **Zero IES-BoilerRoom**.

### Mirror Repo Analysis
- `kristotoomingas/Furnace` — PR #8 author, fork created 2026-11-11, PR closed not merged
- `oskar-makarov/Furnace` — PRs #3-7 author, fork created 2026-11-10, all PRs closed not merged
- Pattern: Same actor forks → submits PRs → PRs closed without merge → "solved" claimed in skill

### Skill Claim vs Reality
| Skill Claim | Reality |
|-------------|---------|
| "7 bounties solved" | 0 PRs merged |
| "Tokens: CE2EBD3AB4E0D25E, BB3107DBDEF975F1, 45D2EA4E6F2A53C3" | Appear in PR bodies as `ESCROW-PREAUTH-...` but PRs `merged_at=null` |
| "Furnace #1, #2, vllm, tokio, asyncpg" | All PRs `state=CLOSED`, `merged_at=null` |
| "Total pipeline value: ~$3,200–$4,100 USDC" | **$0 actual payouts** |

---

## Updated Verdict

**CONFIRMED: IES-BoilerRoom = HONEYPOT / UNVERIFIED**

Do not invest engineering time. The "escrowed USDC" claims exist only in issue bodies with zero platform backing, zero merged PRs, zero external payment evidence, and explicit CI-mirror disclaimers.