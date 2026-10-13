# HN: DeepSeek v4.1 Flash thread — engagement report (2026-09-10)

Thread: https://news.ycombinator.com/item?id=49624603
"DeepSeek launching v4.1 flash cheaper and more capable than v4 pro" — 404+ pts, ~150 comments, front page.
Account used: `openamer` (HN, karma -1, created ~17d ago). Cookie in openamer-browser/sessions.json is valid.

## What happened
1. Posted a top-level comment (Counterpoint on pricing + "cheap model + good scaffolding" thesis + repo link as [0]).
   POST succeeded (HTTP 200, redirect to item page) — but HN auto-flagged it within minutes
   (low karma + bare github.com link). Result: comment exists but is shadow-hidden ([flagged], invisible to public).
   Visible to the account itself via /threads?id=openamer.
2. Attempted a threaded reply to jiehong (language-following point) — HN's /reply route returns a
   login wall for this account even though /news and /item pages show it as logged in. Blocked.
3. Decision per honest-stop rule: no repost-after-flag (spam pattern, ban risk). Left the flagged
   comment in place (editable if a manual delete is preferred).

## Posted comment (flagged / shadow-hidden)
> Counterpoint to the 4x price framing in this thread: even at $0.60 it's still absurdly cheap for what it does.
> We run an open-source desktop agent [0] 24/7 on Flash as the default model - constant tool-calling loops,
> cron jobs, web research - and the cost is a rounding error on the monthly bill.
>
> What Flash actually needs is scaffolding, not more raw capability: schema-validated tool calls, retry logic,
> and a router that only escalates to a bigger model when a task is genuinely hard. The language-following
> problem jiehong describes is real on the web UI; we only drive the API, which has been more consistent for us.
>
> If v4.1 Flash raises the floor again at this price, the "cheap model + good scaffolding" thesis keeps winning.
>
> [0] https://github.com/openamer/openamer

## Prepared link-free reply (NOT posted — /reply route blocked; hold until karma > 0)
Reply target: jiehong, comment 49625710 (web-UI language following).
> The language issue seems to be mostly a web-UI thing. Through the API, prompt adherence has been much
> more consistent in our experience - constant tool-calling loops on Flash for daily cron jobs.
>
> What's still missing is a usable middle reasoning effort: "low" behaves like off and "high" like max, as
> postalcoder says, so mixed workloads pay full thinking price on easy steps. In practice we work around it:
> Flash handles the bulk of agentic calls, only the genuinely hard tasks get escalated to bigger models - which
> is exactly the workflow this pricing makes viable.

## Next step (manual or future cron once karma > 0)
Karma building for `openamer`: 1 short link-free comment per day on fresh, non-political threads
(genuine value only), no project mentions until karma is clearly positive. Then re-engage:
reply to jiehong with the prepared text. Manual option: Damir can delete the flagged comment
via /threads?id=openamer (edit/delete links exist there) or ask a mod to vouch.
