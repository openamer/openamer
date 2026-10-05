---
title: "Darwin Session Recall — Use when the user references past work or you suspect cross-session context exists"
sidebar_label: "Darwin Session Recall"
description: "Use when the user references past work or you suspect cross-session context exists"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Darwin Session Recall

Use when the user references past work or you suspect cross-session context exists.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/darwin-session-recall` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Darwin Session Recall

## Trigger
Use before asking the user to repeat prior decisions or paths.

## Procedure
1. Search session history for the referenced topic first.
2. Prefer direct sources (files, repos, DBs) over memory.
3. Link the found session inline rather than restating it.
4. If nothing found, say so plainly - do not guess.

## Pitfall
Session history is context, not proof of current state.

## Verification
After following the procedure: confirm the outcome
with real evidence (exit code, file, or API response).
```bash
python -c "import sys; print('darwin-species-ok')"
```
