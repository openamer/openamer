# HN Dream Cycle post check — 09.09.2026 (outreach cron)

## Context
Cron task: post `reports/post-dream-cycle-hn-reddit.md` (Dream Cycle story) to HN or Reddit, ONCE, no duplicates.

## Session state findings
- `session_manager.py` is at `AppData/Local/openamer-laptop/openamer-browser/session_manager.py` — NOT `scripts/`. Running `list`/`status` only prints cookie-injection confirmation (84 cookies / 11 platforms); it does NOT list sessions. To see which platforms are stored, grep `sessions.json` for platform names (e.g. `news.ycombinator`, `reddit`).
- CDP on :9222 was alive (Chrome/152). Login verified as user `openamer` via in-page fetch of `/news` + `a[href^="user?id="]` parse.

## Duplicate check (the core of this run)
Script `hn_dream_cycle_post.py` already existed with built-in checks: login → duplicate → fnid → fetch-POST `/r`. Running it returned:
```
LOGIN: {'logged': True, 'user': 'openamer'}
DUP_CHECK_title_seen: True
RESULT: DUPLICATE_EXISTS   (exit 3)
```
Correct behavior — the Dream Cycle post had ALREADY been submitted in an earlier session. No double post.

## Inventory from `/submitted?id=openamer`
Titleline scrape (15 latest):
- ` [flagged] Show HN: I gave my AI agent a sleep cycle – it dreams and fixes its errors`
- `I gave my AI agent a sleep cycle – it dreams about its errors and fixes them (github.com/openamer)` ← alive link post
- 2x OpenAmer profile posts

Flagged Show HN + alive plain submission = the documented showlim fallback pattern (drop "Show HN" prefix) already applied, but the Show HN attempt still got flagged separately.

## Lesson
For cron outreach, the duplicate check is not optional — cron has zero memory of prior sessions. Encode it as step 1 of any submission script. The script pattern (login check → dup check → fresh fnid → fetch POST) in `openamer-browser/hn_dream_cycle_post.py` is the reusable template for text submissions.
