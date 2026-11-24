# SWE-bench Verified eval for OpenAmer — research + working runner (2026-10-01)

## Submission routes (verified via curl of official sources)

- **Official cloud route (no local Docker needed — the realistic one for Windows/CPU-only):**
  1. `pip install sb-cli` → `sb-cli gen-api-key <email>` → verify code by email →
     `export SWEBENCH_API_KEY=...`
  2. Predictions JSONL: `{"instance_id", "model_name_or_path", "model_patch"}` (unified diff)
  3. `sb-cli submit swe-bench_verified <dev|test> --predictions_path preds.jsonl --run_id X`
  4. `sb-cli get-report swe-bench_verified <split> <run_id> -o ./reports`
  5. Leaderboard PR: fork `swe-bench/experiments` → `experiments/verified/<NAME>/` with
     README.md + metadata.yaml → PR with sb-cli email + run_id
  - **Quota**: test split is quota-limited (`sb-cli get-quotas`, 30-day reset); use
    `dev` split first. Exact Verified quota UNVERIFIED.
- **Local harness**: `pip install swebench` (5.x, installs fine on Win py3.11) — but local
  `swebench eval` REQUIRES Docker (containerized since 2024-06). CPU is fine, speed is not.
- **Citable number without official submission**: run a 50-task random subset (seed fixed)
  through the official harness (cloud or local), publish logs + results.json via
  `swebench submit hf <run_id> -b <user>/<repo>` → README line: "X% resolved on N-task
  subset of SWE-bench Verified, official harness, logs: <URL>".

## Working runner (committed in openamer repo `runner/eval.py`, 142 lines)

- `--subset N --seed 42` → loads random subset from HF `princeton-nlp/SWE-bench_Verified`
  (needs `pip install datasets`; ~5s for 500 tasks)
- `gold_patch_fallback` currently submits the GOLD patch — validates the pipeline
  end-to-end (known-good baseline ≈ 100% if harness runs) before burning quota on
  real agent patches. Replace with real `openamer -p` agent calls next.
- `--dry-run` builds + validates format only; `--submit` posts via sb-cli (dev split default).
- Verified live: dry-run n=3 and n=50 both format-OK; preds written to `reports/`.

## Adapter shortcut

mini-SWE-agent (100 LOC, ~65% Verified): swap its model backend for OpenAmer CLI calls —
fastest path from "runner works" to "our number is honest".

## Windows notes

- `sb-cli` and `swebench` both pip-install clean under the OpenAmer venv.
- No GPU anywhere in the pipeline; only cost is time on local-Docker route.
- Docker Desktop/WSL2 needed ONLY for local harness runs; cloud sb-cli route avoids it.