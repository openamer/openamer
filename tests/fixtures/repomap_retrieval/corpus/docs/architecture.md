# Architecture

The service is split into three layers.

- `app/transport.py` owns the network boundary. It composes a retry policy
  with a response cache so a failed call never bypasses the cache layer.
- `app/retry.py` is pure policy: the backoff curve and the retryable status
  set live here, so the curve can be tested without sleeping.
- `app/cache.py` keeps a bounded store and drops the least recently used
  entry once capacity is exceeded.

Command line invocation goes through `app/cli.py`, which wires tracing from
`app/telemetry.py` around each request batch.
