---
name: independent-review
description: Autonomous independent review workflow for kanban tasks.
---

## Trigger
This skill activates when a task titled "Independent review" is assigned to the default profile.

## Usage
When invoked, the skill will:
1. Inspect the task body for PR reference and tests to run.
2. Execute the specified test files using `scripts/run_tests.sh` in a hermetic environment.
3. Collect test pass/fail counts and artifact paths.
4. Submit a kanban_complete with a concise summary and metadata of results.

## Note
The skill is intended for internal review only; it must not alter production crons or configs.
