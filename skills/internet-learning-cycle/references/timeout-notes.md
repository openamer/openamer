# Timeout & rejection-streak observations (2026-09-21)

Observed in a cron run of `internet_learner.py --once`:

- **`cycle_b_papers` timeout**: the arxiv-backed papers cycle can hang for >120s
  (API latency, search result delay). When it times out, skip it and run
  `--once` again — the rotation advances to the next source.
- **Rejection streak recovery**: after 3+ consecutive `shallow + deep read both
  gated` rejections, do not stop. Run additional `--once` calls in sequence.
  `cycle_c_github` and `cycle_h_efficiency` are the most reliable fallback
  sources when quality gating is active.
- **Buffer at cap**: the `online_buffer.jsonl` at 300/300 lines does NOT prevent
  appends — `enforce_cap` rotates old entries out. Rejections at this point
  are genuine seed space exhaustion, not buffer full.