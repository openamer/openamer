# Darwin Engine Report
_2026-11-10T06:58:07.969475+00:00 — evolutionary skill ecosystem_

**Population:** 1288 Skills | **Offspring:** 4 | **Competitions:** 33

## Top 10 (fittest skills)

| Skill | Fitness | Usage | Age (days) | Mutationen W/L |
|---|---|---|---|---|
| darwin-cron-guard | 3490.0 | 276 | 0 | 1624/48 |
| darwin-harvested-training-internet-learn-log-jsonl | 3470.0 | 271 | 0 | 1603/21 |
| autonomous-learning-architecture | 3235.0 | 355 | 0 | 1585/306 |
| learning-loop | 421.33 | 411 | 80 | 0/0 |
| asi-capability-summary | 286.47 | 275 | 46 | 0/0 |
| a2a-brain-meshlearn-verify | 286.03 | 274 | 29 | 0/0 |
| auto-env-checker | 208.47 | 255 | 46 | 15/88 |
| mini-openamer | 207.13 | 195 | 26 | 0/0 |
| cdp-social-posting | 90.1 | 75 | 27 | 0/0 |
| dream-cycle | 74.67 | 64 | 70 | 0/0 |

## Bottom 5 (selection candidates)

- **tao-train-optical-inspection** (Fitness 7.0, 30 days old)
- **web-artifacts-builder** (Fitness 7.0, 30 days old)
- **xlsx** (Fitness 7.0, 30 days old)
- **cron-autotest-run-cron-entry** (Fitness 6.33, 50 days old)
- **self-rewriter** (Fitness -2.37, 71 days old)

## New mutations

- darwin-cron-guard → `darwin-cron-guard__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- darwin-harvested-training-internet-learn-log-jsonl → `darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- autonomous-learning-architecture → `autonomous-learning-architecture__muttighten_trigger` (op=tighten_trigger, applied=True)
- asi-capability-summary → `asi-capability-summary__mutbroaden_trigger` (op=broaden_trigger, applied=True)

## Competitions

- ⏳ `a2a-brain-meshlearn-verify+asi-capability-summary` (0) vs `None` (0)
- ⏳ `a2a-brain-meshlearn-verify__mutbroaden_trigger` (286.03) vs `a2a-brain-meshlearn-verify` (286.03)
- ⏳ `a2a-brain-meshlearn-verify__muttighten_trigger` (286.03) vs `a2a-brain-meshlearn-verify` (286.03)
- ⏳ `asi-capability-summary+asi-identity` (0) vs `None` (0)
- ⏳ `asi-capability-summary__mutbroaden_trigger` (286.47) vs `asi-capability-summary` (286.47)
- ⏳ `asi-capability-summary__muttighten_trigger` (286.47) vs `asi-capability-summary` (286.47)
- ⏳ `asi-identity+auto-env-checker` (0) vs `None` (0)
- ⏳ `auto-env-checker+autonomous-learning-architecture` (0) vs `None` (0)
- ⏳ `auto-env-checker+cdp-social-posting` (0) vs `None` (0)
- ⏳ `auto-env-checker__mutbroaden_trigger` (208.47) vs `auto-env-checker` (208.47)
- ⏳ `auto-env-checker__muttighten_trigger` (208.47) vs `auto-env-checker` (208.47)
- ⏳ `autonomous-learning-architecture__mutbroaden_trigger` (3235.0) vs `autonomous-learning-architecture` (3235.0)
- ⏳ `autonomous-learning-architecture__muttighten_trigger` (3235.0) vs `autonomous-learning-architecture` (3235.0)
- ⏳ `cdp-social-posting__mutbroaden_trigger` (90.1) vs `cdp-social-posting` (90.1)
- ⏳ `cdp-social-posting__muttighten_trigger` (90.1) vs `cdp-social-posting` (90.1)
- ⏳ `darwin-cron-guard__mutbroaden_trigger` (3490.0) vs `darwin-cron-guard` (3490.0)
- ⏳ `darwin-cron-guard__muttighten_trigger` (3490.0) vs `darwin-cron-guard` (3490.0)
- ⏳ `darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger` (3470.0) vs `darwin-harvested-training-internet-learn-log-jsonl` (3470.0)
- ⏳ `darwin-harvested-training-internet-learn-log-jsonl__muttighten_trigger` (3470.0) vs `darwin-harvested-training-internet-learn-log-jsonl` (3470.0)
- ⏳ `discord-server-management__mutadd_verification_step` (15.2) vs `discord-server-management` (15.2)
- ⏳ `discord-server-management__mutbroaden_trigger` (15.2) vs `discord-server-management` (15.2)
- ⏳ `discord-server-management__muttighten_trigger` (15.2) vs `discord-server-management` (15.2)
- ⏳ `github-readme-summary__mutbroaden_trigger` (19.0) vs `github-readme-summary` (19.0)
- ⏳ `github-readme-summary__muttighten_trigger` (19.0) vs `github-readme-summary` (19.0)
- ⏳ `openamer-plugin-development__muttighten_trigger` (20.73) vs `openamer-plugin-development` (20.73)
- ⏳ `plugin-api__mutbroaden_trigger` (21.33) vs `plugin-api` (21.33)
- ⏳ `plugin-api__muttighten_trigger` (21.33) vs `plugin-api` (21.33)
- ⏳ `train-from-usage__mutadd_pitfall` (28.33) vs `train-from-usage` (28.33)
- ⏳ `train-from-usage__mutadd_verification_step` (28.33) vs `train-from-usage` (28.33)
- ⏳ `train-from-usage__mutbroaden_trigger` (28.33) vs `train-from-usage` (28.33)
- ⏳ `train-from-usage__muttighten_trigger` (28.33) vs `train-from-usage` (28.33)
- ⏳ `undetectable-browsing__muttighten_trigger` (18.4) vs `undetectable-browsing` (18.4)
- ⏳ `vscode-extension-scaffold__mutbroaden_trigger` (16.33) vs `vscode-extension-scaffold` (16.33)

## Evolution Tree

```mermaid
graph TD
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> darwin-cron-guard__mutbroaden_trigger["darwin-cron-guard__mutbroaden_trigger"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger["darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__muttighten_trigger["autonomous-learning-architecture__muttighten_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__mutbroaden_trigger["asi-capability-summary__mutbroaden_trigger"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> darwin-cron-guard__mutbroaden_trigger["darwin-cron-guard__mutbroaden_trigger"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger["darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__muttighten_trigger["autonomous-learning-architecture__muttighten_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__mutbroaden_trigger["asi-capability-summary__mutbroaden_trigger"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> darwin-cron-guard__mutbroaden_trigger["darwin-cron-guard__mutbroaden_trigger"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger["darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__muttighten_trigger["autonomous-learning-architecture__muttighten_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__mutbroaden_trigger["asi-capability-summary__mutbroaden_trigger"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> darwin-cron-guard__mutbroaden_trigger["darwin-cron-guard__mutbroaden_trigger"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger["darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__muttighten_trigger["autonomous-learning-architecture__muttighten_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__mutbroaden_trigger["asi-capability-summary__mutbroaden_trigger"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> darwin-cron-guard__mutbroaden_trigger["darwin-cron-guard__mutbroaden_trigger"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger["darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__muttighten_trigger["autonomous-learning-architecture__muttighten_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__mutbroaden_trigger["asi-capability-summary__mutbroaden_trigger"]
    darwin-cron-guard["darwin-cron-guard"] --> darwin-cron-guard__mutbroaden_trigger["darwin-cron-guard__mutbroaden_trigger"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger["darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__muttighten_trigger["autonomous-learning-architecture__muttighten_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__mutbroaden_trigger["asi-capability-summary__mutbroaden_trigger"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
```
