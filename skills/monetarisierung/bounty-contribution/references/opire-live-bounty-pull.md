# Opire live bounty board — public read API + staleness trap

Opire (`app.opire.dev`) is JS-only behind a login wall for *claiming*, but its
**read API is open and unauthenticated**. This is the machine-readable live
source — use it instead of scrolling the JS board or trusting cached notes.

## Endpoint

```bash
curl -s "https://api.opire.dev/rewards" | python -m json.tool
```

Returns a JSON array. One reward:

```json
{
  "id": "01J42C08V4J78ZAWH8JH2RQS8G",
  "title": "research implementation for Windows",
  "url": "https://github.com/radumarias/rencfs/issues/3",
  "platform": "GitHub",
  "claimerUsers": [], "tryingUsers": [],
  "programmingLanguages": ["Rust"],
  "createdAt": 1722361586532,
  "pendingPrice": {"value": 4200, "unit": "USD_CENT"},
  "organization": {"name": "radumarias", "url": "https://github.com/radumarias"},
  "project": {"name": "rencfs", "url": "https://github.com/radumarias/rencfs",
              "isPublic": true, "isBotInstalled": false}
}
```

`pendingPrice.value` is in **USD cents** (divide by 100). Paths that 404:
`/bounties`, `/v1/bounties`, `app.opire.dev/api/bounties`. Only `/rewards` works.

## Trap 1 — the API listing is STALE (verified 2026-10-05)

The board advertises rewards that no longer exist. A live pull returned 5 open
rewards; cross-checking each against GitHub killed 2 of them immediately:

| Listed reward | Advertised | Reality |
|---|---|---|
| `rodrigompy/bugb#1` "c1work" | $100 | issue **CLOSED** |
| `buape/kiai-bounties#1` | $20 | repo **deleted** (GitHub GraphQL: "Could not resolve to a Repository") |

**Rule: never author against an Opire reward without an `gh` cross-check first.**
`gh issue view <n> --repo <o>/<r> --json state` and `gh repo view <o>/<r>`.
The API is a *lead list*, not a verified board.

## Trap 2 — claimer/tryer counts hide agent-farming; count PRs instead

`rencfs#3` ($42, Rust, "research implementation for Windows") reported
`claimerUsers: 0, tryingUsers: 0` — it looks untouched. It had **40+ open PRs**
from AI agents, all named variations of "docs: add Windows support implementation
research". The Opire counters were never updated because agent PRs don't comment
`/try`.

**Rule: for a doc/research/lesson-style bounty, count the PRs on the issue**
(`gh pr list --repo <o>/<r> --state all`), not the Opire counters. 40 competing
AI PRs on a 2024-era $42 doc bounty means the expected value is ~0 — skip it.

Stale-but-live distinction: the reward is genuinely *open* (the repo/issue exist)
but economically dead (saturated). Both traps matter; check for both.

## Cross-checks that matter (in order)

1. `gh issue view <n> --repo <o>/<r> --json state` → must be `OPEN`.
2. `gh repo view <o>/<r> --json name` → must resolve (not deleted/renamed).
3. `gh pr list --repo <o>/<r> --state all --limit 50` → count competing PRs;
   skip if it's a claim/PR storm.
4. Only then read the issue body for the real deliverable.

## Runnable probe

`scripts/opire_live_bounties.py` pulls the API and prints the table; add
`--verify` to cross-check every issue's live GitHub state via `gh`. Run it at the
start of any bounty session instead of trusting yesterday's listing.
