# Retrieving the FULL insight behind a truncated `result` line

## The trap

`scripts/training/internet_learn_log.jsonl` rows are `{ts, source, result, elapsed_s}`.
The `result` string is **truncated by design to ~80 chars** — each cycle ends with
something like `return f"efficiency-learn: {insight[:80]}"` (see
`internet_learner.py` ~line 6987 for `cycle_h_efficiency`). So a log line such as

    efficiency-learn: GB (shared) Single-request latency (GPU-A100) 180 ms 90 ms 55 ms Throughput (req

is only a *headline*, not the learned content. Reporting that headline as "what was
learned" loses the actual payload.

## Where the full insight actually lives

The untruncated insight is stored as a **`{"u","a"}` pair in the training buffer**:

- `scripts/training/online_buffer.jsonl` — `{"u": "<query / trigger>", "a": "<full insight>"}`  ← primary source
- `scripts/training/kta_log.jsonl` — knowledge-to-action copy

Do NOT expect it in `memory/*.jsonl` (`research_log`, `world_model`,
`longterm_episodes` carry embeddings/facts, not the raw cycle insight), and
`skills/auto-generated/auto-*-learning-*/SKILL.md` only updates on some stores —
it can lag days behind the cycle. The buffer is the reliable read-back.

## Retrieval recipe (one command)

Use a distinctive substring of the truncated headline to grep the buffer:

```bash
cd C:/Users/damir/AppData/Local/openamer-laptop
grep -h "Single.request latency" scripts/training/online_buffer.jsonl | tail -1 \
  | python -c "import sys,json; d=json.loads(sys.stdin.read()); print(d['a'])"
```

Notes:
- `.` in the grep pattern matches the non-ASCII middle-dot (`‑`) the buffer uses, so
  a mostly-ASCII anchor still hits. If unsure, grep on the ASCII head of the headline.
- `tail -1` takes the newest matching row (the buffer appends).
- Read `d['a']` for the insight, `d['u']` for the query that produced it.

## Verifying the tool server (context)

`curl -s -m 8 http://localhost:8081/health` returns
`{"status":"alive","tools":N,"swaps":N}`. The `tools` key is what distinguishes the
real `tool_server.py` from a bare TCP listener / deprecated `serve_mini.py`
(`serve_mini.py` / `serve_live.py` squat :8081 without a `/health` payload). A
non-empty JSON with a `tools` key means the correct server is already up — no
restart needed.
