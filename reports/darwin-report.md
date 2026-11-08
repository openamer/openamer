# Darwin Engine Report
_2026-11-08T14:10:27.473862+00:00 — evolutionary skill ecosystem_

**Population:** 1278 Skills | **Offspring:** 4 | **Competitions:** 33

## Top 10 (fittest skills)

| Skill | Fitness | Usage | Age (days) | Mutationen W/L |
|---|---|---|---|---|
| darwin-cron-guard | 3342.0 | 276 | 0 | 1548/44 |
| darwin-harvested-training-internet-learn-log-jsonl | 3324.0 | 271 | 0 | 1530/21 |
| autonomous-learning-architecture | 3089.0 | 355 | 0 | 1512/306 |
| learning-loop | 421.4 | 411 | 78 | 0/0 |
| asi-capability-summary | 286.53 | 275 | 44 | 0/0 |
| a2a-brain-meshlearn-verify | 283.1 | 271 | 27 | 0/0 |
| mini-openamer | 223.2 | 211 | 24 | 0/0 |
| auto-env-checker | 208.53 | 255 | 44 | 15/88 |
| cdp-social-posting | 90.13 | 75 | 26 | 0/0 |
| dream-cycle | 74.73 | 64 | 68 | 0/0 |

## Bottom 5 (selection candidates)

- **tao-train-optical-inspection** (Fitness 7.03, 29 days old)
- **web-artifacts-builder** (Fitness 7.03, 29 days old)
- **xlsx** (Fitness 7.03, 29 days old)
- **cron-autotest-run-cron-entry** (Fitness 6.37, 49 days old)
- **self-rewriter** (Fitness -2.3, 69 days old)

## New mutations

- darwin-cron-guard → `darwin-cron-guard__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- darwin-harvested-training-internet-learn-log-jsonl → `darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- autonomous-learning-architecture → `autonomous-learning-architecture__muttighten_trigger` (op=tighten_trigger, applied=True)
- asi-capability-summary → `asi-capability-summary__mutbroaden_trigger` (op=broaden_trigger, applied=True)

## Competitions

- ⏳ `a2a-brain-meshlearn-verify+asi-capability-summary` (0) vs `None` (0)
- ⏳ `a2a-brain-meshlearn-verify__mutbroaden_trigger` (283.1) vs `a2a-brain-meshlearn-verify` (283.1)
- ⏳ `a2a-brain-meshlearn-verify__muttighten_trigger` (283.1) vs `a2a-brain-meshlearn-verify` (283.1)
- ⏳ `asi-capability-summary+asi-identity` (0) vs `None` (0)
- ⏳ `asi-capability-summary__mutbroaden_trigger` (286.53) vs `asi-capability-summary` (286.53)
- ⏳ `asi-capability-summary__muttighten_trigger` (286.53) vs `asi-capability-summary` (286.53)
- ⏳ `asi-identity+auto-env-checker` (0) vs `None` (0)
- ⏳ `auto-env-checker+autonomous-learning-architecture` (0) vs `None` (0)
- ⏳ `auto-env-checker+cdp-social-posting` (0) vs `None` (0)
- ⏳ `auto-env-checker__mutbroaden_trigger` (208.53) vs `auto-env-checker` (208.53)
- ⏳ `auto-env-checker__muttighten_trigger` (208.53) vs `auto-env-checker` (208.53)
- ⏳ `autonomous-learning-architecture__mutbroaden_trigger` (3089.0) vs `autonomous-learning-architecture` (3089.0)
- ⏳ `autonomous-learning-architecture__muttighten_trigger` (3089.0) vs `autonomous-learning-architecture` (3089.0)
- ⏳ `cdp-social-posting__mutbroaden_trigger` (90.13) vs `cdp-social-posting` (90.13)
- ⏳ `cdp-social-posting__muttighten_trigger` (90.13) vs `cdp-social-posting` (90.13)
- ⏳ `darwin-cron-guard__mutbroaden_trigger` (3342.0) vs `darwin-cron-guard` (3342.0)
- ⏳ `darwin-cron-guard__muttighten_trigger` (3342.0) vs `darwin-cron-guard` (3342.0)
- ⏳ `darwin-harvested-training-internet-learn-log-jsonl__mutbroaden_trigger` (3324.0) vs `darwin-harvested-training-internet-learn-log-jsonl` (3324.0)
- ⏳ `darwin-harvested-training-internet-learn-log-jsonl__muttighten_trigger` (3324.0) vs `darwin-harvested-training-internet-learn-log-jsonl` (3324.0)
- ⏳ `discord-server-management__mutadd_verification_step` (15.27) vs `discord-server-management` (15.27)
- ⏳ `discord-server-management__mutbroaden_trigger` (15.27) vs `discord-server-management` (15.27)
- ⏳ `discord-server-management__muttighten_trigger` (15.27) vs `discord-server-management` (15.27)
- ⏳ `github-readme-summary__mutbroaden_trigger` (19.07) vs `github-readme-summary` (19.07)
- ⏳ `github-readme-summary__muttighten_trigger` (19.07) vs `github-readme-summary` (19.07)
- ⏳ `openamer-plugin-development__muttighten_trigger` (20.8) vs `openamer-plugin-development` (20.8)
- ⏳ `plugin-api__mutbroaden_trigger` (21.4) vs `plugin-api` (21.4)
- ⏳ `plugin-api__muttighten_trigger` (21.4) vs `plugin-api` (21.4)
- ⏳ `train-from-usage__mutadd_pitfall` (28.4) vs `train-from-usage` (28.4)
- ⏳ `train-from-usage__mutadd_verification_step` (28.4) vs `train-from-usage` (28.4)
- ⏳ `train-from-usage__mutbroaden_trigger` (28.4) vs `train-from-usage` (28.4)
- ⏳ `train-from-usage__muttighten_trigger` (28.4) vs `train-from-usage` (28.4)
- ⏳ `undetectable-browsing__muttighten_trigger` (18.47) vs `undetectable-browsing` (18.47)
- ⏳ `vscode-extension-scaffold__mutbroaden_trigger` (16.4) vs `vscode-extension-scaffold` (16.4)

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
```
