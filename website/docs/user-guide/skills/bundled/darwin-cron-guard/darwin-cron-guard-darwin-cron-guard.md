---
title: "Darwin Cron Guard — Use when creating or editing cron jobs - prevents timeouts, silent failures, and delivery gaps"
sidebar_label: "Darwin Cron Guard"
description: "Use when creating or editing cron jobs - prevents timeouts, silent failures, and delivery gaps"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Darwin Cron Guard

Use when creating or editing cron jobs - prevents timeouts, silent failures, and delivery gaps.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/darwin-cron-guard` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Darwin Cron Guard

## Trigger
Use whenever a scheduled job is created, edited, or diagnosed.

## Procedure
1. Terminal timeouts must be &lt;= 120s inside cron runs.
2. Background processes need notify_on_complete=true.
3. Exit code 2 may be a SUCCESS-with-changes convention -
   check the tool's documented exit semantics before alerting.
4. Verify last_status after the first scheduled run.

## Pitfall
A job that exits 0 with empty output may have done nothing.

## Verification
After following the procedure: confirm the outcome
with real evidence (exit code, file, or API response).
```bash
python -c "import sys; print('darwin-species-ok')"
```
