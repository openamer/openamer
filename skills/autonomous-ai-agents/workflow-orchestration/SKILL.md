---
name: workflow-orchestration
description: Use when a task needs multi-agent CONTROL FLOW, not just parallel calls.
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [delegation, workflow, orchestration, multi-agent, subagents]
    related_skills: [goal-engine, agent-mesh, a2a-swarm]
---

# Workflow orchestration

`delegate_task` runs a **fixed list** of tasks in one batch. It cannot
express control flow — "run these three audits in parallel, then take
their findings and run a fourth pass over what they disagreed about".

The `workflow` tool closes that gap: the model writes a small Python
script that fans work out to subagents, and the script's return value
becomes the tool result.

Adapted from deepseek-ai/deepseek-harness `packages/workflow`.

## When to use which

| Situation | Tool |
|---|---|
| 1–2 independent subtasks | `delegate_task` — simpler, cheaper |
| A fixed list of N tasks, all independent | `delegate_task` with `tasks: [...]` |
| A second pass that depends on the first | **`workflow`** |
| Parallel work whose findings must be cross-checked | **`workflow`** |
| A migration with dependent steps | **`workflow`** |
| Multi-angle research where later rounds refine earlier answers | **`workflow`** |

If you cannot express the control flow in a `tasks` list, you need
`workflow`.

## The script contract

The script is a Python body (not a module). It runs with top-level
`await` and must end with `return <value>`.

```python
phase("collect")
findings = await parallel([
    agent("Audit src/auth.py for auth bypasses. Report file:line findings."),
    agent("Audit src/payments.py for auth bypasses. Report file:line findings."),
])

phase("cross-check")
disputes = [f for f in findings if "DISPUTED" in f]
if not disputes:
    return {"status": "clean", "checked": len(findings)}

verdicts = await parallel([
    agent(f"A previous auditor reported: {d}. Verify or refute it.") for d in disputes
])
return {"status": "reviewed", "disputes": len(disputes), "verdicts": verdicts}
```

### Hooks

| Hook | Purpose |
|---|---|
| `await agent(prompt, context=None)` | Run one subagent to completion; returns its final text. The subagent knows nothing of this conversation — `prompt` must be self-contained. |
| `await parallel([...])` | Run independent entries concurrently; order is preserved. Entries may be coroutines (`agent("...")`) or plain callables. |
| `await pipeline(items, step)` | Map `step` over `items`; `step(item, previous)` may see the previous item's result. Use when each step depends on the last. |
| `phase(name)` | Declare a phase boundary for progress narration. |
| `log(message)` | Emit a progress line. |
| `args` | The optional JSON object passed with the call. |

### Rules

- No `import`, `open`, `eval`, `exec` or `__import__`.
- A script that raises returns an **error**, never a partial success.
- The script may not use `import` to reach the filesystem — use `agent()`
  and let the subagent do the file work.
- The tool blocks until the whole workflow settles: you see one final
  outcome, never intermediate child messages.

## The call

```json
{
  "meta": {
    "name": "auth-audit",
    "description": "Audit two modules, then cross-check the disputed findings",
    "phases": ["collect", "cross-check"]
  },
  "script": "phase(\"collect\")\nfindings = await parallel([...])\nreturn {\"checked\": len(findings)}",
  "args": {"paths": ["src/auth.py", "src/payments.py"]}
}
```

`meta.name` and `meta.description` are required; `meta.phases` is
optional and only documents the expected phases.

## What it costs

Every `agent()` call is a real delegated child: it inherits the parent's
toolsets and obeys `delegation.max_concurrent_children`,
`delegation.max_spawn_depth` and the pause kill switch. A workflow with
ten `agent()` calls costs ten subagent runs — write the script so each
call does real work, and use `parallel` for independent calls.

Subagents cannot use `workflow` themselves (no recursive fan-out), and
`workflow` is refused while plan mode is active — same as
`delegate_task`.

## Pitfalls

1. **Do not use `workflow` for one or two delegations.** `delegate_task`
   is cheaper and easier to read.
2. **Make each `agent()` prompt self-contained.** A subagent has no
   access to this conversation, the script's variables, or the other
   subagents' results — unless you put them into the prompt text.
3. **`parallel` preserves order**, so index-aligned results line up with
   the input list. That is the reliable way to pair a finding with the
   file that produced it.
4. **Return a structured value, not prose.** The return value is what
   you (the caller) reason over. Put the conclusion in the dict.
5. **A script error is not a partial success.** If you need partial
   results, catch the condition inside the script and return them
   explicitly.
