# Darwin Engine Report
_2026-09-23T20:17:30.860847+00:00 — evolutionary skill ecosystem_

**Population:** 158 Skills | **Offspring:** 5 | **Competitions:** 23

## Top 10 (fittest skills)

| Skill | Fitness | Usage | Age (days) | Mutationen W/L |
|---|---|---|---|---|
| auto-env-checker | 2387.0 | 2429 | 0 | 15/82 |
| autonomous-learning-architecture | 2154.0 | 2141 | 0 | 0/0 |
| cdp-social-posting | 1198.0 | 1185 | 0 | 0/0 |
| train-from-usage | 954.93 | 948 | 2 | 0/4 |
| plugin-api | 943.93 | 935 | 32 | 0/0 |
| asi-capability-summary | 921.9 | 912 | 3 | 0/0 |
| a2a-brain-meshlearn-verify | 628.87 | 619 | 4 | 0/0 |
| asi-identity | 318.93 | 309 | 2 | 0/0 |
| self-rewriter | 278.2 | 327 | 24 | 7/72 |
| darwin-harvested-openamer-cli-main-py | 118.43 | 66 | 17 | 29/15 |

## Bottom 5 (selection candidates)

- **darwin-harvested-the-phantom** (Fitness 14.97, 1 days old)
- **darwin-harvested-scripts-test-self-learning-label-lea** (Fitness 14.0, 0 days old)
- **darwin-harvested-darwin-skill-hits-cache-json** (Fitness 13.97, 1 days old)
- **darwin-harvested-r-nname-com** (Fitness 13.97, 1 days old)
- **darwin-harvested-tmp-cycle-census-py** (Fitness 13.97, 1 days old)

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
- ⏳ `auto-env-checker__mutbroaden_trigger` (2387.0) vs `auto-env-checker` (2387.0)
- ⏳ `autonomous-learning-architecture__mutbroaden_trigger` (2154.0) vs `autonomous-learning-architecture` (2154.0)
- ⏳ `autonomous-learning-architecture__muttighten_trigger` (2154.0) vs `autonomous-learning-architecture` (2154.0)
- ⏳ `cdp-social-posting__muttighten_trigger` (1198.0) vs `cdp-social-posting` (1198.0)
- ⏳ `discord-server-management__mutadd_verification_step` (40.8) vs `discord-server-management` (40.8)
- ⏳ `discord-server-management__mutbroaden_trigger` (40.8) vs `discord-server-management` (40.8)
- ⏳ `discord-server-management__muttighten_trigger` (40.8) vs `discord-server-management` (40.8)
- ⏳ `github-readme-summary__mutbroaden_trigger` (31.93) vs `github-readme-summary` (31.93)
- ⏳ `github-readme-summary__muttighten_trigger` (31.93) vs `github-readme-summary` (31.93)
- ⏳ `openamer-plugin-development__muttighten_trigger` (30.2) vs `openamer-plugin-development` (30.2)
- ⏳ `plugin-api__mutbroaden_trigger` (943.93) vs `plugin-api` (943.93)
- ⏳ `plugin-api__muttighten_trigger` (943.93) vs `plugin-api` (943.93)
- ⏳ `train-from-usage__mutadd_pitfall` (954.93) vs `train-from-usage` (954.93)
- ⏳ `train-from-usage__mutadd_verification_step` (954.93) vs `train-from-usage` (954.93)
- ⏳ `train-from-usage__mutbroaden_trigger` (954.93) vs `train-from-usage` (954.93)
- ⏳ `train-from-usage__muttighten_trigger` (954.93) vs `train-from-usage` (954.93)
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
