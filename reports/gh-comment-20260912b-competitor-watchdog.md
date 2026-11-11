**Follow-up on the competitor pipeline: the watchdog was reporting success by exiting failure, and was structurally blind to the exact stories it exists to find (`f4f55cff1`).**

The last post here ended with "the next real fix is on the consumer side — the competitor insight extractor needs to reject non-answer snippets." Working that fix surfaced something upstream and worse: the *scan* feeding it was misreporting its own health.

**Bug 1 — a quiet window is not a crash.** `scan()` returned exit code 1 whenever both result sets came back empty. Empty is the watchdog's *normal* state, so on most runs the process exited non-zero and its real signal was buried in exit-code noise — a watchdog that cries every night trains you to ignore it. `scan()` now separates "requests answered with 0 hits" (healthy, silent, exit 0) from "every request actually errored" (broken, exit 1). `_fetch()` takes an `errors` list so failures are attributed per request instead of collapsing into one boolean.

**Bug 2 — a server-side floor was hiding the target stories.** The agent queries were fetched with the *log* threshold (points > 30), so a freshly submitted agent story — HN stories start at ~1 point — was filtered out by the API before the code ever saw it. The watchdog was structurally incapable of noticing the threads it was built to notice. New `AGENT_MIN_POINTS = 0` for the agent path; `LOG_THRESHOLD` 30 → 10 for the broad context feed.

**Measured, this run — the fix is not cosmetic.** I re-ran the real query set against live HN Algolia over the last 84 2-hour windows (7 days):

```
agent queries (4 phrases), points>30 :  10 stories in 7d |  7/84 windows =  8.3%
agent queries (4 phrases), points>10 :  23 stories in 7d | 14/84 windows = 16.7%
agent queries (4 phrases), points>0  : 280 stories in 7d | 76/84 windows = 90.5%
```

Same queries, same window, same API — the floor was discarding **90.5% → 8.3%** of the coverage. That 8.3% figure is the honest origin of the "7 of 84 windows" number in the commit message.

**Straight on that commit message:** the line "the top HN story is ~24 pts, so a points>=30 filter matches in only 7 of them" is imprecise and I want to flag it rather than let it stand. The 7/84 rate belongs to the **agent-scoped query set**; the **broad front feed** is a different population. Re-measured: every one of the 84 windows contains at least one story above 30 points, so a broad-feed-only threshold would *not* have looked broken. The conclusion the commit drew (raise coverage on the agent path) is right; the sentence supporting it conflates two populations. Corrected here.

**Live proof, not a fixture.** Against the real store (`reports/competitor-watch.jsonl`, not a temp dir), the agent path now logs rows the old code discarded — all of them below the old server-side floor, which is why none could ever appear before:

```json
{"kind": "agent", "points": 3, "title": "Aiope – An on-device AI agent for Android (terminal, browser, SSH, MCP)"}
{"kind": "agent", "points": 1, "title": "Build Agentic Memory That Keeps Your Loops Alive and Sharpens Them Every Run"}
{"kind": "agent", "points": 3, "title": "Why are AI agents lying, cheating and coordinating? – Yoshua Bengio"}
```

Right now, this same live query at `points>30` returns **0 hits** for `"AI agent"` and at `points>0` returns **3** — the three rows above. Direct before/after on the production endpoint.

**Regression guard, run just now:** `scripts/training/test_competitor_scan.py` → **11/11 passed** (network-free). Four of them exist only because of this fix: quiet-window exits 0, all-requests-errored still exits 1, the agent path carries no points floor, and `_fetch` collects per-request errors. Live run of the production script: **exit 0**, writes `kind=agent` rows.

**Store hygiene, measured:** `competitor-watch-seen.txt` is 47 lines / 47 distinct ids / **0 duplicates** (it was 145 lines holding 42 ids for 36 stories, 111 of them junk from a test writing into the production store — fixed in `77abeb0c0`).

**Honest limit:** `AGENT_MIN_POINTS = 0` buys coverage at the cost of precision — at 90.5% of windows matching, "a quiet window" is no longer a signal, so the alert path (still `points >= 50`, and still requiring an *unseen* id) is now the only thing separating noise from news. That threshold is now the weakest number in the file. Re-measuring it against a week of real alert history is the next honest step; not done yet.
