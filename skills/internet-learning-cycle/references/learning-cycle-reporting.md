# Internet Learning Cycle — Compact Execution Recipe

Use this reference for a single scheduled `internet_learner.py --once` run.

## Preflight

1. Probe `http://localhost:8081/health` with a short timeout.
2. If the response reports `alive`, do not restart the tool server.
3. If the probe fails, start the server using the user's exact restart command,
   wait the requested interval, and probe again before continuing.

## Run and verify

Run one invocation only:

```text
python <path>/scripts/training/internet_learner.py --once
```

Use the learner's own log as the source of truth. An accepted cycle is a
non-rejection result containing a verified `*-learn:` prefix (for example
`security-learn:`). Do not look for an `accepted` boolean; that field is not
part of the log schema.

When the logged insight is truncated, report only the verified prefix and the
visible substance. Never reconstruct missing wording or invent a source title.

## One-line delivery

For a scheduled job that asks for a one-line report, use:

```text
Internet-Learning-Zyklus <source-cycle>: <verified concise insight>.
```

Keep the output to one sentence and use the user's language. Mention a failed
health check or restart only when it changes the interpretation of the result.
