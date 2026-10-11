# Darwin Engine Report
_2026-10-11T12:30:52.105942+00:00 — evolutionary skill ecosystem_

**Population:** 1109 Skills | **Offspring:** 4 | **Competitions:** 28

## Top 10 (fittest skills)

| Skill | Fitness | Usage | Age (days) | Mutationen W/L |
|---|---|---|---|---|
| autonomous-learning-architecture | 3337.0 | 2740 | 0 | 292/3 |
| auto-env-checker | 2888.47 | 2934 | 16 | 15/88 |
| asi-capability-summary | 1995.47 | 1983 | 16 | 0/0 |
| learning-loop | 1879.33 | 1868 | 50 | 0/0 |
| a2a-brain-meshlearn-verify | 1699.0 | 1686 | 0 | 0/0 |
| cdp-social-posting | 1577.0 | 1561 | 0 | 0/0 |
| train-from-usage | 1097.33 | 1088 | 20 | 0/4 |
| plugin-api | 966.33 | 955 | 50 | 0/0 |
| darwin-cron-guard | 921.0 | 302 | 0 | 315/24 |
| darwin-harvested-training-internet-learn-log-jsonl | 893.0 | 277 | 0 | 312/21 |

## Bottom 5 (selection candidates)

- **tao-train-optical-inspection** (Fitness 7.97, 1 days old)
- **web-artifacts-builder** (Fitness 7.97, 1 days old)
- **xlsx** (Fitness 7.97, 1 days old)
- **cron-autotest-run-cron-entry** (Fitness 7.33, 20 days old)
- **systematic-debugging** (Fitness 6.33, 50 days old)

## New mutations

- autonomous-learning-architecture → `autonomous-learning-architecture__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- auto-env-checker → `auto-env-checker__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- asi-capability-summary → `asi-capability-summary__muttighten_trigger` (op=tighten_trigger, applied=True)
- a2a-brain-meshlearn-verify → `a2a-brain-meshlearn-verify__mutbroaden_trigger` (op=broaden_trigger, applied=True)

## Competitions

- ⏳ `a2a-brain-meshlearn-verify+asi-capability-summary` (0) vs `None` (0)
- ⏳ `a2a-brain-meshlearn-verify__mutbroaden_trigger` (1699.0) vs `a2a-brain-meshlearn-verify` (1699.0)
- ⏳ `a2a-brain-meshlearn-verify__muttighten_trigger` (1699.0) vs `a2a-brain-meshlearn-verify` (1699.0)
- ⏳ `asi-capability-summary+asi-identity` (0) vs `None` (0)
- ⏳ `asi-capability-summary__mutbroaden_trigger` (1995.47) vs `asi-capability-summary` (1995.47)
- ⏳ `asi-capability-summary__muttighten_trigger` (1995.47) vs `asi-capability-summary` (1995.47)
- ⏳ `asi-identity+auto-env-checker` (0) vs `None` (0)
- ⏳ `auto-env-checker+autonomous-learning-architecture` (0) vs `None` (0)
- ⏳ `auto-env-checker+cdp-social-posting` (0) vs `None` (0)
- ⏳ `auto-env-checker__mutbroaden_trigger` (2888.47) vs `auto-env-checker` (2888.47)
- ⏳ `autonomous-learning-architecture__mutbroaden_trigger` (3337.0) vs `autonomous-learning-architecture` (3337.0)
- ⏳ `autonomous-learning-architecture__muttighten_trigger` (3337.0) vs `autonomous-learning-architecture` (3337.0)
- ⏳ `cdp-social-posting__mutbroaden_trigger` (1577.0) vs `cdp-social-posting` (1577.0)
- ⏳ `cdp-social-posting__muttighten_trigger` (1577.0) vs `cdp-social-posting` (1577.0)
- ⏳ `discord-server-management__mutadd_verification_step` (62.2) vs `discord-server-management` (62.2)
- ⏳ `discord-server-management__mutbroaden_trigger` (62.2) vs `discord-server-management` (62.2)
- ⏳ `discord-server-management__muttighten_trigger` (62.2) vs `discord-server-management` (62.2)
- ⏳ `github-readme-summary__mutbroaden_trigger` (41.0) vs `github-readme-summary` (41.0)
- ⏳ `github-readme-summary__muttighten_trigger` (41.0) vs `github-readme-summary` (41.0)
- ⏳ `openamer-plugin-development__muttighten_trigger` (34.6) vs `openamer-plugin-development` (34.6)
- ⏳ `plugin-api__mutbroaden_trigger` (966.33) vs `plugin-api` (966.33)
- ⏳ `plugin-api__muttighten_trigger` (966.33) vs `plugin-api` (966.33)
- ⏳ `train-from-usage__mutadd_pitfall` (1097.33) vs `train-from-usage` (1097.33)
- ⏳ `train-from-usage__mutadd_verification_step` (1097.33) vs `train-from-usage` (1097.33)
- ⏳ `train-from-usage__mutbroaden_trigger` (1097.33) vs `train-from-usage` (1097.33)
- ⏳ `train-from-usage__muttighten_trigger` (1097.33) vs `train-from-usage` (1097.33)
- ⏳ `undetectable-browsing__muttighten_trigger` (42.4) vs `undetectable-browsing` (42.4)
- ⏳ `vscode-extension-scaffold__mutbroaden_trigger` (42.33) vs `vscode-extension-scaffold` (42.33)

## Evolution Tree

```mermaid
graph TD
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__muttighten_trigger["asi-capability-summary__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] --> a2a-brain-meshlearn-verify__mutbroaden_trigger["a2a-brain-meshlearn-verify__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__muttighten_trigger["asi-capability-summary__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] --> a2a-brain-meshlearn-verify__mutbroaden_trigger["a2a-brain-meshlearn-verify__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__muttighten_trigger["asi-capability-summary__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] --> a2a-brain-meshlearn-verify__mutbroaden_trigger["a2a-brain-meshlearn-verify__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__muttighten_trigger["asi-capability-summary__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] --> a2a-brain-meshlearn-verify__mutbroaden_trigger["a2a-brain-meshlearn-verify__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__muttighten_trigger["asi-capability-summary__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] --> a2a-brain-meshlearn-verify__mutbroaden_trigger["a2a-brain-meshlearn-verify__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    asi-capability-summary["asi-capability-summary"] --> asi-capability-summary__muttighten_trigger["asi-capability-summary__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] --> a2a-brain-meshlearn-verify__mutbroaden_trigger["a2a-brain-meshlearn-verify__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-loops["autonomous-learning-loops"]
    darwin-cron-guard["darwin-cron-guard"] --> guard["guard"]
    darwin-harvested-training-internet-learn-log-jsonl["darwin-harvested-training-internet-learn-log-jsonl"] --> learn["learn"]
```
