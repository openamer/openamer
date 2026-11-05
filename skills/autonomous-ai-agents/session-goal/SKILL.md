---
name: session-goal
description: Use when a task spans multiple turns and needs a durable objective.
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [goal, autonomy, continuation, planning]
    related_skills: [goal-engine, workflow-orchestration, todo]
---

# The session goal

OpenAmer can work toward a **durable goal** across many turns. The goal
survives turns, has a turn budget, and an auto-continuation loop picks
the work back up when a turn ends without finishing.

The `goal` tool is how *you* — the model — participate in that loop.

Adapted from deepseek-ai/deepseek-harness `packages/goal`, which
exposes the goal to the model through `get_goal` / `create_goal` /
`update_goal` tools.

## When to use a goal

| Situation | Tool |
|---|---|
| Steps for *this* turn | `todo` |
| One long objective spanning many turns | **`goal`** |
| Independent subtasks to fan out | `delegate_task` / `workflow` |
| A one-off question | neither |

A goal costs an auto-continuation loop: when a turn ends and the goal
is not done, the loop continues on its own. Use it for work that
genuinely spans turns ("migrate all 40 call sites to the new API"), not
for a question you can answer now.

## The actions

| Action | Effect |
|---|---|
| `read` | Show the goal, its contract, the turn budget and the last verdict |
| `set` | Define the goal (and optionally `max_turns`) |
| `amend` | Append a criterion to the existing goal |
| `report` `done` | Declare the goal complete |
| `report` `blocked` | Park the loop — **requires a `reason`** |
| `pause` / `resume` | Stop / restart the auto-continuation loop |

## How to use it well

1. **Read first.** `goal` with `action="read"` tells you what you are
   actually working toward, how many turns are left, and what the last
   verdict was. Do this before deciding what to do — otherwise you are
   guessing at an objective you did not see.
2. **Report honestly.** `report status="done"` when the objective is
   met — that stops the loop and saves the remaining budget.
   `report status="blocked"` with a reason when you cannot proceed;
   that parks the loop instead of burning the budget on busy-work.
3. **Amend, do not abandon.** If the objective turns out to be wrong or
   too broad, `amend` it. Do not silently work on something else.
4. **One goal at a time.** The loop is built around a single objective.

## What the goal does not do

- It does not replace `todo`. The todo list is the step plan *within* a
  turn; the goal is the objective *across* turns.
- It does not replace your judgement. A judge also evaluates each turn;
  your `report` and the judge can disagree, and the loop keeps working
  until both are satisfied.
- It does not grant extra permissions. The goal changes what you work
  toward, not what you are allowed to do.
