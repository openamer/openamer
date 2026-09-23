# Darwin Engine Report
_2026-09-23T08:31:17.738271+00:00 — evolutionary skill ecosystem_

**Population:** 158 Skills | **Offspring:** 5 | **Competitions:** 23

## Top 10 (fittest skills)

| Skill | Fitness | Usage | Age (days) | Mutationen W/L |
|---|---|---|---|---|
| auto-env-checker | 2343.0 | 2385 | 0 | 13/78 |
| autonomous-learning-architecture | 2125.97 | 2113 | 1 | 0/0 |
| cdp-social-posting | 1171.0 | 1158 | 0 | 0/0 |
| train-from-usage | 927.93 | 921 | 2 | 0/4 |
| plugin-api | 916.93 | 908 | 32 | 0/0 |
| asi-capability-summary | 851.9 | 842 | 3 | 0/0 |
| a2a-brain-meshlearn-verify | 558.87 | 549 | 4 | 0/0 |
| asi-identity | 318.93 | 309 | 2 | 0/0 |
| self-rewriter | 275.23 | 324 | 23 | 7/72 |
| darwin-harvested-openamer-cli-main-py | 115.43 | 63 | 17 | 29/15 |

## Bottom 5 (selection candidates)

- **darwin-harvested-scripts-swarm-intelligence-py** (Fitness 14.0, 0 days old)
- **darwin-harvested-scripts-test-self-learning-label-lea** (Fitness 14.0, 0 days old)
- **darwin-harvested-darwin-skill-hits-cache-json** (Fitness 13.97, 1 days old)
- **darwin-harvested-tmp-cycle-census-py** (Fitness 13.97, 1 days old)
- **darwin-harvested-tmp-head-gate-py** (Fitness 13.97, 1 days old)

## New mutations

- auto-env-checker → `auto-env-checker__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- autonomous-learning-architecture → `autonomous-learning-architecture__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- cdp-social-posting → `cdp-social-posting__muttighten_trigger` (op=tighten_trigger, applied=True)
- train-from-usage → `train-from-usage__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- plugin-api → `plugin-api__muttighten_trigger` (op=tighten_trigger, applied=True)

## Competitions

- ⏳ `a2a-brain-meshlearn-verify+asi-capability-summary` (0) vs `None` (0)
- ⏳ `asi-capability-summary+asi-identity` (0) vs `None` (0)
- ⏳ `asi-identity+auto-env-checker` (0) vs `None` (0)
- ⏳ `auto-env-checker+autonomous-learning-architecture` (0) vs `None` (0)
- ⏳ `auto-env-checker+cdp-social-posting` (0) vs `None` (0)
- ⏳ `auto-env-checker__mutbroaden_trigger` (2343.0) vs `auto-env-checker` (2343.0)
- ⏳ `autonomous-learning-architecture__mutbroaden_trigger` (2125.97) vs `autonomous-learning-architecture` (2125.97)
- ⏳ `autonomous-learning-architecture__muttighten_trigger` (2125.97) vs `autonomous-learning-architecture` (2125.97)
- ⏳ `cdp-social-posting__muttighten_trigger` (1171.0) vs `cdp-social-posting` (1171.0)
- ⏳ `discord-server-management__mutadd_verification_step` (40.8) vs `discord-server-management` (40.8)
- ⏳ `discord-server-management__mutbroaden_trigger` (40.8) vs `discord-server-management` (40.8)
- ⏳ `discord-server-management__muttighten_trigger` (40.8) vs `discord-server-management` (40.8)
- ⏳ `github-readme-summary__mutbroaden_trigger` (31.93) vs `github-readme-summary` (31.93)
- ⏳ `github-readme-summary__muttighten_trigger` (31.93) vs `github-readme-summary` (31.93)
- ⏳ `openamer-plugin-development__muttighten_trigger` (30.2) vs `openamer-plugin-development` (30.2)
- ⏳ `plugin-api__mutbroaden_trigger` (916.93) vs `plugin-api` (916.93)
- ⏳ `plugin-api__muttighten_trigger` (916.93) vs `plugin-api` (916.93)
- ⏳ `train-from-usage__mutadd_pitfall` (927.93) vs `train-from-usage` (927.93)
- ⏳ `train-from-usage__mutadd_verification_step` (927.93) vs `train-from-usage` (927.93)
- ⏳ `train-from-usage__mutbroaden_trigger` (927.93) vs `train-from-usage` (927.93)
- ⏳ `train-from-usage__muttighten_trigger` (927.93) vs `train-from-usage` (927.93)
- ⏳ `undetectable-browsing__muttighten_trigger` (32.0) vs `undetectable-browsing` (32.0)
- ⏳ `vscode-extension-scaffold__mutbroaden_trigger` (32.93) vs `vscode-extension-scaffold` (32.93)

## Evolution Tree

```mermaid
graph TD
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] ==> a2a-brain-meshlearn-verify+asi-capability-summary["a2a-brain-meshlearn-verify+asi-capability-summary"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] ==> a2a-brain-meshlearn-verify+asi-capability-summary["a2a-brain-meshlearn-verify+asi-capability-summary"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] ==> a2a-brain-meshlearn-verify+asi-capability-summary["a2a-brain-meshlearn-verify+asi-capability-summary"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] ==> a2a-brain-meshlearn-verify+asi-capability-summary["a2a-brain-meshlearn-verify+asi-capability-summary"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] ==> a2a-brain-meshlearn-verify+asi-capability-summary["a2a-brain-meshlearn-verify+asi-capability-summary"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] ==> a2a-brain-meshlearn-verify+asi-capability-summary["a2a-brain-meshlearn-verify+asi-capability-summary"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] ==> a2a-brain-meshlearn-verify+asi-capability-summary["a2a-brain-meshlearn-verify+asi-capability-summary"]
```
