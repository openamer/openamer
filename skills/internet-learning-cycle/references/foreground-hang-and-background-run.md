# Foreground hang vs background run — 17.10.26

Cron run 17.10.26 04:47–04:51. `tool_server :8081` was alive
(`{"status": "alive", "tools": 10, "swaps": 50}`), so no restart was needed.

## The failure

| invocation | how run | result |
|---|---|---|
| 1 | `terminal(timeout=300)` | exit 124, no log entry |
| 2 | `terminal(timeout=600)` | exit 124, no log entry |
| 3 | `terminal(background=true)` + `process(wait, timeout=300)` | exit 0, `cycle_g_security` logged, 65.3 s |

Same command, same server, same state — only the execution mode differed.
Foreground kills the process before the cycle writes its log line; background
lets it finish.

## Why it matters for reporting

A foreground timeout produces a clean `exit 124` and an unchanged
`internet_learn_log.jsonl`, which reads exactly like "the learner is broken".
The lesson is not "the learner is broken" — it is "run it in the background".

## Measured cycle durations (this session, for sizing)

| cycle | elapsed_s |
|---|---|
| `cycle_d_docs` | 245.1 |
| `cycle_g_security` | 65.3 |
| `cycle_b_papers` | 96.4 |
| `cycle_c_github` | 75.6 |

So a single `--once` is 1–4 minutes of wall time. A foreground `terminal` call
must therefore be sized ≥ 600 s, and even then it hung — background is the
reliable shape.