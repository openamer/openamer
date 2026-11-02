# Native local service supervisor

`openamer supervisor` supervises an explicit, user-owned registry in the
**active profile's canonical home** (`get_openamer_home()`), independently of
chat sessions, cron, and the gateway. It does not install a system service,
Scheduled Task, Startup entry, or another watchdog. Nothing is registered or
started automatically.

```sh
openamer supervisor status   # read-only: not running / no state on a new profile
openamer supervisor init     # creates supervisor/registry.json, EMPTY; never overwrites
openamer supervisor once     # one bounded pass, including readiness checks
openamer supervisor run      # foreground, long-lived native loop; Ctrl+C to exit
```

`once` exits 1 when any service is not UP, or on configuration/lock errors;
an empty registry succeeds without starting anything. `status` succeeds when
stopped and prints `running: false`. Its snapshot is explicitly **historical**,
not a new health check. A kernel-held lock (not a stale PID flag) determines
whether an instance is running. An overlapping `run` or `once` fails closed.

## Register one service deliberately

Edit `<profile-home>/supervisor/registry.json`. This file is executable authority:
keep it private to its owner. Do not copy another machine's registry or secrets.
The initial contents are exactly `{"version": 1, "services": []}`.

Example to adapt to an existing local HTTP service (not an installed default):

```json
{
  "version": 1,
  "services": [
    {
      "name": "my-local-service",
      "observe_only": true,
      "probe": {
        "kind": "http_json",
        "url": "http://127.0.0.1:8765/health",
        "expect": {"status": "ready"},
        "timeout_s": 1
      },
      "start": {
        "argv": ["/absolute/path/to/python", "{home}/services/my_service.py"],
        "cwd": "{home}"
      },
      "ready_timeout_s": 15,
      "restart_budget_per_hour": 6,
      "backoff_s": 5
    }
  ]
}
```

Start with `observe_only: true` (also the default when omitted). Verify `once`
against an independent health check. Only set it to **false** once the argv,
probe and ownership are correct and any previous watchdog for that service has
been disabled by you. There is no built-in service list or machine-specific
maintenance logic. Registry changes take effect on the next invocation; restart
the supervisor to reload them.

- Probes: `http_json` checks a JSON object and each `expect` key/value;
  `http_status` checks status (default 200); `tcp` requires `host` (default
  `127.0.0.1`) and `port`. Only loopback destinations are accepted. HTTP probes
  ignore proxy environment settings and reject redirects. TCP proves a listener,
  **not** application identity; prefer an identity-specific JSON health response.
- Probe first: an already healthy service is adopted, never duplicated. An
  adopted external process is not owned and is never signalled. A spawn alone
  is STARTING, never UP. UP requires the declared health probe to pass.
- Commands are argv arrays passed with `shell=False`; no command strings,
  implicit shell expansion, `.bat` or `.cmd` launchers. `{home}` expands only
  in argv and cwd. Use an absolute executable path for predictable behavior.
  A Windows interpreter path works too; no POSIX executable is bundled.
- A failed/expired readiness gate is START_FAILED. Only the child started by
  this supervisor (PID plus creation time) and its descendants are terminated
  with bounded waits. Ready services survive supervisor exit for later adoption.
  A known child still alive but unhealthy becomes DEGRADED rather than spawning
  a duplicate or killing a possibly useful service. It needs operator attention.
- Restart attempts (including failed executable launches), exponential backoff
  and an hourly budget persist across supervisor restarts. Backoff is capped at
  one hour; the hourly budget defaults to 6. `restart_budget_per_hour: 0`
  prohibits starts. Each pass is serial and bounded per-service, so a slow
  readiness gate delays other entries. `run --interval 2` controls the pause
  between passes, not the readiness budget.
- Standard input/output/error of children go to the null device. Arrange
  service-specific logging in the service itself. No credentials should be put
  in argv, health URLs, or registry entries.

## State and operational boundaries

`<profile-home>/supervisor/state.json` stores last health observations, failure
reasons, child identity, retry deadlines, attempt timestamps and the **last 200
state transitions**. Snapshot and bounded journal are written together through
one fsynced temporary file and atomic replacement; it is not an unlimited audit
archive. A service being down is not the same as the supervisor being stopped.
Removed registry entries are no longer supervised; removal never kills services.

The OS lock file remains on disk intentionally: locks release automatically on
process exit/crash, and deleting a live lock file can break mutual exclusion.
Do not delete it while supervision may be running. Do not run different profiles
against the same service: the lock is per profile, not a machine-wide port lock.

This is not a sandbox or a privileged init replacement. It cannot prove that an
unrelated process answering the configured endpoint is the intended service;
health responses must be chosen appropriately. Like other user-space launchers,
a hard crash between OS process creation and recording its identity leaves a
small unowned-child window; probe-first adoption reduces duplicates when that
child reaches readiness. Do not layer this over existing service managers.
