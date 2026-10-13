---
sidebar_position: 12
title: "Plan mode"
description: "Enforced read-only mode: state-changing tools are refused before they run, so the agent plans first instead of asking to."
---

# Plan mode

Plan mode makes the agent **read-only**. While it is active, tools that change
anything — files, the shell, the desktop, skills, memory, cron, delegation — are
refused *before* they execute, and the refusal tells the agent to present a plan
and ask for approval.

This is enforcement, not a request. The `/plan` skill writes a markdown plan but
leaves every write tool available, so "plan first" stays something the model can
ignore. Plan mode removes the tools instead.

## Turn it on

For one run, without touching config:

```bash
openamer chat --plan
```

Or for every session:

```yaml
# ~/.openamer/config.yaml
agent:
  plan_mode: true
```

The flag wins over the config. The config value is read once per session and
cached, like the terminal backend's other settings — change it, then restart
the session.

## What is refused

`write_file`, `patch`, `terminal`, `process`, `execute_code`, `computer_use`,
`skill_manage`, `memory`, `cronjob`, `delegate_task` (a subagent could write on
the agent's behalf), the browser tools that can submit or type, `project_create`,
`project_switch`, `homeassistant`, `kanban`, `discord`, `discord_admin`,
`spotify`, `yuanbao`, `image_generate`, `video_generate`.

**Unknown tools are refused too.** A tool added after this list was written
defaults to blocked, so a new capability cannot silently open a write path in
plan mode.

## What keeps working

`read_file`, `search_files`, `skills_list`, `skill_view`, `session_search`,
`web_search`, `web_extract`, `browser_snapshot`, `browser_get_images`,
`browser_console`, `browser_vision`, `browser_scroll`, `browser_back`,
`read_terminal`, `vision_analyze`, `todo`, `clarify`.

## Leaving plan mode

The refusal message asks the agent to present the plan and request approval.
Approval is the human's to give: once you confirm, drop `--plan` (or set
`plan_mode: false`) and restart the session.

## Verifying it on your machine

```bash
python scripts/verify_plan_mode.py
```

That drives the real tool executor with a live `write_file` call, once with plan
mode on and once off, and reports both halves — a refusal *and* a positive
control, so a harness that simply fails to execute cannot be mistaken for a
working gate.

## Design note

Plan mode is a plain gate consulted next to the existing tool guardrails. It
adds no model tool and does not modify the system prompt, so it cannot disturb
prompt caching. See `agent/plan_mode.py`.
