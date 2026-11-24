# Real bounty venues and aggregator pitfalls (verified 2026-10-13)

Companion to the "Bounty-Landschaft" sections in SKILL.md. Records the venues that
were confirmed to be REAL, money-paying, and reachable from this laptop, plus the
trap of mistaking an aggregator for the source.

## How these were found (the search that works)

```bash
gh search issues --label bounty --state open --sort created --limit 25 \
  --json repository,number,title,createdAt,commentsCount \
  --jq '.[] | "\(.createdAt[0:10]) \(.repository.nameWithOwner)#\(.number) c=\(.commentsCount) \(.title[0:60])"'
```

Notes on the query:
- `gh search issues` has NO `comments` field — it is `commentsCount`. Using `comments`
  errors with `Unknown JSON field`.
- **Always exclude the self-contaminated radar repo**: append
  `--repo`-scoped queries or filter out `relayhop/sn-monetization-runtime` mentally,
  or the result is only your own radar noise.
- This query DOES surface legitimate programs (proof below) — the earlier blanket rule
  "GitHub label:bounty search is only bot noise" was too strong. Both are true:
  the radar repo is noise; the label search still finds real programs if you filter
  and then vet each hit.

## sybil-solutions — recipe bounties, $50 each, paid via PayPal or GitHub Sponsors

The single most concrete real-money path found that needs **no crypto wallet**:

- Source of truth: `sybil-solutions/local-ai-registry` (249 stars), issues
  labelled `bounty`. Rules in `sybil-solutions/.github/BOUNTIES.md`.
- Org is real, not a farm: sibling repos carry real stars
  (`ai-data-extraction` 1344*, `local-studio` 1826*, `codex-shim` 1066*).
- 8 open bounties on 2026-10-13 (#216 Intel Arc B580 12GB, #217 RTX 2080 Ti 11GB,
  #218 GTX 1080 Ti 11GB, #219 RX 7900 XTX 24GB, #220 27B on 16GB AMD,
  #221 RTX 4060 Ti 16GB, #222 RTX 5060 Ti 16GB, #223 Ryzen AI 890M iGPU).
- **Pays $50 per accepted recipe, via PayPal OR GitHub Sponsors** (email
  `sherif@sybilsolutions.ai` with the PR link + payout preference after merge, paid
  within 7 days; never put payment details in a PR/issue).

Mechanics (from BOUNTIES.md):
1. Comment `/attempt` on the bounty issue; a maintainer adds the `claimed` label. You
   have 7 days; after that it reopens. One claimant at a time.
2. Clone `sybil-solutions/local-ai-recipe-kit`, run it on the named card with a coding
   agent + `PROMPT.md`.
3. In `local-ai-registry`, run
   `python3 lab/lab.py try <repo>@<commit> --model <id> --engine <profile> --card <card> --on endpoint --endpoint <your server>`.
   A recipe is written only if all six checks pass: loads, answers, thinks, calls a
   tool, recalls at a nearly full context window, **>= 15 tok/s**.
4. Open one PR to the registry with the recipe and `Closes #<bounty number>`, attach the
   kit submission file.

What does NOT pay: reported/estimated numbers, different card than named, a PR opened
while someone else holds the claim.

**Hardware gate (why this is blocked on this machine):** the bounties require the exact
named card. Our only GPU is an **AMD Radeon 860M iGPU** (laptop) — matches none of the
eight (890M != 860M). The remote GPU worker `192.168.178.23` was offline
(ping timeout, `:8082` refused). Verdict 2026-10-13: hardware-blocked, not a code task.

## MergeFi "Stellar Wave" — 30 unclaimed real frontend bugs

- `MergeFi/frontend`: Next.js client for a Stellar/Soroban escrow bounty platform
  (homepage `merge-fi-eight.vercel.app`). 30 open issues labelled `Stellar Wave`, all
  with `commentsCount=0` (unclaimed), created 2026-10-13 — real, specific bugs, e.g.
  #713 "Navbar 'Reputation' link 404s for every real signed-in user",
  #700 "Signing in from a bounty page never returns the user to it".
- Payout: Soroban smart-contract escrow on the **Stellar network** released on PR
  merge = **crypto**, so it needs Damir's Stellar wallet + a Drips/Wave account.
  The work is agent-doable; the payout rail is the blocker.

## Aggregator pitfall: bounty-plaza is not the source

`zhangjiayang6835-cyber/bounty-plaza` ("Real bug bounty aggregation and distribution
platform", 11 stars) lists issues that only mirror an upstream bounty, with an explicit
`### Source URL` field and a points→cash redemption model (1 point = $0.72, 100-point
minimum, 85-95% split). It is an **aggregator**, not the payer.

**Rule:** when a bounty issue contains a `Source URL` / "原始链接" field, follow it to
the upstream repo — that is where the real BOUNTIES.md, the real claim mechanism, and
the real payout live. Do not work the mirror.

## GitHub Sponsors — how to tell if the profile is actually LIVE

Logged in, `github.com/sponsors/<user>` shows a banner
`"You are previewing your GitHub Sponsors profile"` = profile exists but is a **draft,
not publicly serving**. Cross-check anonymously (no cookies):

```bash
curl -s -L -o /dev/null -w "final=%{url_effective} http=%{http_code}\n" \
  -A "Mozilla/5.0" "https://github.com/sponsors/<user>"
# a published profile serves the sponsor page; a draft 302s to the plain user profile
```

2026-10-13: `/sponsors/openamer` → 302 → `https://github.com/openamer` (draft/unpublished).
Treat "cookie present + page 200" as NOT proof of an active donation channel.
