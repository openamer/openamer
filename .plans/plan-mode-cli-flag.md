# Plan: `openamer --plan` CLI flag

Status: **not implemented.** `website/docs/user-guide/plan-mode.md` documents plan
mode as config-only, and says so explicitly — do not add the flag to the docs
before it exists. (This file exists because that promise needs an address.)

## Why

Plan mode is shipped and enforced (`agent/plan_mode.py`, wired into both executor
paths), but the only switch is `agent.plan_mode: true` in `config.yaml`, read once
per session. Entering plan mode for one run means editing config and restarting.
Every competitor treats it as a per-session toggle.

`agent_init` already accepts `plan_mode: Optional[bool] = None` and falls back to
config when it is `None` — the plumbing at the agent level is **done**. What is
missing is the path from the argument parser to that parameter.

## Exact anchors (verified by grep, 2026-09-13)

`checkpoints` is the template — it is threaded exactly this way and works.

### 1. Argument parser

`--checkpoints` is not defined in `openamer_cli/main.py`; search
`openamer_cli/_parser.py` and the agent-run parser it builds. Add:

```python
parser.add_argument(
    "--plan",
    action="store_true",
    help="Plan mode: refuse state-changing tools; present a plan and ask for approval",
)
```

### 2. `openamer_cli/main.py`

| Line | What |
|---|---|
| 2255 | `checkpoints: bool = False,` — add `plan_mode: bool = False,` to the same signature |
| 2663 | `checkpoints=getattr(args, "checkpoints", False),` — add `plan_mode=getattr(args, "plan", False),` |
| 2684 | `"checkpoints": getattr(args, "checkpoints", False),` in the kwargs dict — add `"plan_mode": getattr(args, "plan", False),` |

### 3. `cli.py`

| Line | What |
|---|---|
| 4089 | `checkpoints: bool = False,` — add `plan_mode: bool = False,` |
| 4292-4296 | the `# Filesystem checkpoints: CLI flag > config` block — mirror it: `self.plan_mode = plan_mode or (CLI_CONFIG.get("agent") or {}).get("plan_mode", False)` |

Then find where `cli.py` constructs the agent and forward it the same way
`self.checkpoints_enabled` is forwarded into `checkpoints_enabled=`.

## Tests to write

Behaviour contracts, not snapshots:

- `--plan` present → the agent's gate is enabled even when config says false
- flag absent + config false → gate disabled (default must not change)
- flag absent + config true → gate enabled (config still works)
- Keep the existing structural guard in `tests/test_plan_mode.py` green: it asserts
  `PlanModeGate(enabled=` and `cfg_get("agent.plan_mode", False)` both exist in
  `agent_init.py`.

## Verification (must all pass before claiming done)

```bash
export PATH="$HOME/openamer-repo/.venv/Scripts:$PATH"
pytest tests/test_plan_mode.py -q
python scripts/verify_plan_mode.py          # end-to-end, with positive control
openamer --help | grep -- --plan            # the flag must actually be listed
```

Then remove the "config is the only switch" paragraph from
`website/docs/user-guide/plan-mode.md` and document `--plan` instead.

## Process notes from the session that wrote this

- **Never pipe a command through `tail` when its exit code is the result.**
  `npm run pack 2>&1 | tail -25` reported exit 0 while npm had exited 1 — the pipe
  returns `tail`'s status. Use `cmd; echo "EXIT=$?"` (bash) or
  `cmd; "EXIT=$LASTEXITCODE"` (PowerShell).
- **Check which copy you are building.** The running desktop app comes from
  `%LOCALAPPDATA%\openamer-laptop\openamer-agent\`, not from `openamer-repo`. A
  repo-only build produces an artifact nobody runs. Sync the source first.
- **Rebuilding the desktop app while it runs fails** with
  `EBUSY: resource busy or locked, unlink '...\release\win-unpacked\v8_context_snapshot.bin'`.
  The app must be closed first; do not kill it to work around this.
