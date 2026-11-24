# Bounty Sweep Log — 2026-10-12

Full `label:bounty state:open` sweep (4242 total, 100 newest by `updated`,
deduped by `repository_url`). Every candidate evaluated, every one rejected:

## Rejected candidates

| repo | stars | pushed | why rejected |
|---|---|---|---|
| `tenstorrent/tt-metal` | 1698 | 2026-10-11 | 5 open bounties ($300–$5000) but all are GPU/CUDA `ttnn` kernel correctness fixes (sampling bias, cumsum NaN, LayerNorm row-stride, polygamma, log_sigmoid). Need tt-metal hardware + deep numeric work — far over the 30-min CPU budget. **Also**: repo policy bans AI-agent claims (permanent ban); assignment/completion lives in comments, not `assignees`. Treat as read-only intel, never an autonomous target. |
| `tari-project/universe` | 46 | 2026-10-09 | Bounty = 60,000 **XTM** (crypto) payout → crypto rule, skip. |
| `SPLURT-Station/S.P.L.U.R.T-tg` | 64 | 2026-10-11 | Payment methods list **Cryptocurrency** + PayPal; NSFW adult content (egg-laying sex quirk); a proposed-fix comment carrying a USDC Base wallet address was **disavowed** in a follow-up comment. Quadruple red flag — skip. |
| `bwipp/postscriptbarcode` | 504 | 2026-10-11 | `label:bounty` issues are from 2017–2019, 0 comments, not real bounties — stale. |
| `livepeer/go-livepeer` | 585 | 2026-10-06 | Same: 2018/2021 feature requests mislabeled, no real bounty. |
| `Sifchain/sifnode` | 107 | 2025-03-11 | Last push 7 months ago → inactive. |
| all others | <20 or 0 | — | Below the 20-star floor, or archived/inactive. |

## durable lessons

- **`bounty_issue_analyzer.py` sorts by FEWEST comments and returns the same
  spam every run** (relayhop 5★, AstralDeep 3★, NSPG13 18★). It does NOT apply
  the stars≥20 / no-crypto filter. Until it is fixed, run the raw
  `label:bounty state:open` search yourself, dedupe by `repository_url`, and
  filter before reading any issue body — otherwise you burn turns re-rejecting
  the same junk.
- **The `updated` sort is what separates real from stale.** A 504★ repo whose
  bounty-labeled issues are 7 years old is not a live channel; a 46★ repo
  pushed yesterday may be the only thing worth looking at (and then the crypto
  filter kills it).
- **Infeasibility is a valid skip reason, and it is not a cop-out.** The
  highest-value bounties on the board (`tenstorrent` $3k–$5k) are GPU-kernel
  work. Cloning and starting is not a 30-minute task and the repo bans agent
  claims anyway. Say "needs GPU kernel + C++ toolchain, out of budget" and log
  it — that is the honest blocker.

## state at end of sweep

No eligible candidate. Pipeline blocked until either (a) copperheadhq #350
gets a `CHANGES_REQUESTED` review (then implement per
`references/watchdog-run-protocol.md`), or (b) a real bounty surfaces that is
CPU-feasible, non-crypto, ≥20 stars, maintainer-active.