# Diagnosing live but unproductive task workers

## Trigger and scope

Use when a task is `running`, the worker exists, and neither tools nor artifacts show progress. Diagnose before restarting. Honor a user request for read-only investigation and targeted tests; repeated full suites do not explain an inference stall.

## Evidence ladder

1. **Identity:** correlate task ID, active run, recorded worker PID and process creation time. List descendants and exact command arguments. Windows venv launchers and the real interpreter can form one multi-process worker; count independent task roots rather than matching process names.
2. **Session:** query the correct profile's session store read-only. Record message roles, completed tool results, API accounting and last timestamps. Zero completed API accounting may mean an in-flight request, not that no request was sent. A session with just its initial user message and no tools has not begun tool-driven development.
3. **Routing:** inspect the effective worker-profile endpoint, provider overrides and fallback sequence. Compare with default-profile configuration and selected nonsecret environment variables. Never dump all environment variables or provider credentials. Attribute each connection error, rate-limit response and fallback to the task's session; neighboring workers can share the log.
4. **Inference:** distinguish discovery/health from completion. Read request start, time-to-first-byte/chunk, prefill throughput, context estimate, timeout, retry and socket-abort records. A CPU model consuming a large prompt can advance prefill for minutes without emitting a response. Successful `/health` or `/api/ps` calls do not establish completion capacity.
5. **Wait location:** sample the actual interpreter with a bounded nonblocking stack dump. For example, where installation is authorized and `uvx` is available:

   ```text
   uvx --from py-spy py-spy dump --pid <interpreter-pid> --nonblocking
   ```

   This may download the diagnostic tool; disclose/authorize that mutation when the investigation is strictly read-only. Prefer an already installed debugger during the read-only phase. Do not request locals, which may reveal credentials or prompt contents.

   - `httpcore ... SyncStream.read` followed by `_receive_response_headers`: waiting on the provider's HTTP response, not an executing tool.
   - Agent `Thread.join(timeout=...)` and CLI `Queue.get`: expected surrounding waits; neither alone proves deadlock.
   - Import-loader frames during startup: initialization still progressing; do not call them inference failure.
   - A sampled stack cannot exclude every possible lock or permission issue. State only the wait actually observed.
6. **Recovery control:** read how the current dispatcher handles fresh heartbeats, expired claims, worker identity and respawn. A parent-generated heartbeat can keep a request-starved worker nominally healthy indefinitely. Verify whether a block/reclaim API actually terminates the worker; never assume it does.

## Cancellation is an observation, not a success message

A stale detector logging "killing connection" proves it fired, not that the HTTP request ended. Check the socket-shutdown count, subsequent thread state, completion/timeout log and retry timestamp. A zero shutdown count followed by a much later SDK timeout supports ineffective prompt cancellation; it does **not** establish a permanent deadlock. Keep configuration recovery separate from any unimplemented transport hardening.

## Controlled recovery without duplicates

Only after the fault is demonstrated and mutation is authorized:

1. Save consistent SQLite backups using `Connection.backup`; check each with `PRAGMA quick_check`. Save the task/run/events, session, configuration, logs, workspace and process identities. Keep private backups local; publish only a sanitized report.
2. Hold dispatch on the existing task using the board tools. Do not create a replacement task or start a manual parallel worker.
3. Revalidate the root PID's creation time and exact task argument immediately before stopping its tree. Retire that task only, then wait for every identified process to exit. Do not kill a shared model service or another worker merely because both use the same fallback.
4. Repair the proven configuration defect through the supported configuration interface. Compare parsed configuration with the snapshot, allowing only the intended key change. Preserve unrelated configuration and hashes of protected memory/directive/language files.
5. Verify no surviving worker for the task before releasing it. Use exact argv-element membership, e.g. `task_query in cmdline`, not `task_query in ' '.join(cmdline)`: an inline diagnostic can otherwise match its own Python/shell command. Classify ancestry before counting roots; recheck creation time before any further termination.
6. Unblock/resume the same task through the existing dispatcher. Observe with a bounded poll that returns on actual task-related completed tool results or useful artifact changes. Do not report success from a fresh PID or heartbeat alone.
7. Compare the new session's provider URL, completed requests, latency and tool results. Record task/run/session handles and measurement time. Return control to the development worker once productive activity is demonstrated; do not compete with its repair.

Do not restore an entire live board/session database as routine rollback: unrelated tasks may have advanced since the backup. Roll back narrowly and preserve later events.

## Historical case: ACE development-worker recovery

Observed 2026-11-12; these are historical examples, not current system facts:

- The worker profile overrode Kilo Gateway with `https://127.0.0.1:9/dead`, while the default profile had a working endpoint. Logs showed connection failures, an unavailable configured fallback and exhausted OpenRouter daily limits before local CPU fallback.
- The task's local model request carried about 37,325 estimated input tokens. Server logs recorded 2,048 prefill tokens in 80.46 seconds and 32,768 in 1,636.86 seconds.
- At 900 seconds a stale-request abort logged `tcp_force_closed=0`. A later `APITimeoutError` and retry showed the request outlived the attempted abort. A nonblocking stack sample located the active wait in HTTP response-header reception.
- The original session held one user message and no tool calls; the workspace was empty. This explained absent development artifacts without blaming tests or file permissions.
- After backup, task hold, verified old-tree retirement and a single endpoint correction, the same task resumed through its existing dispatcher. A semantic configuration comparison allowed only the endpoint change.
- Recovery was proven by completed task/source-inspection tools and completed model requests on the corrected endpoint, including recorded request latencies of 3.7 and 4.9 seconds. No full regression suite or application fix was implied by that result.

## Reporting checklist

- Separate: alive process, active request, completed model response, completed tools, changed files, passing regressions, installed code and merge readiness.
- Name measured cause and unresolved sub-causes; avoid "deadlock" when the request later times out.
- State what was backed up, changed and left untouched.
- Preserve narrow test scope in the task comment so the resumed worker does not start an unwanted full sweep.
- Treat a successful recovery monitor exit as evidence about the monitor's explicit predicate only.
