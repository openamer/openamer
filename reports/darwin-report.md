# Darwin Engine Report
_2026-09-15T16:00:54.205794+00:00 — evolutionary skill ecosystem_

**Population:** 87 Skills | **Offspring:** 5 | **Competitions:** 25

## Top 10 (fittest skills)

| Skill | Fitness | Usage | Age (days) | Mutationen W/L |
|---|---|---|---|---|
| auto-env-checker | 1911.7 | 1912 | 9 | 2/14 |
| autonomous-learning-architecture | 1700.0 | 1687 | 0 | 0/0 |
| cdp-social-posting | 721.0 | 710 | 0 | 0/0 |
| train-from-usage | 513.6 | 507 | 12 | 0/4 |
| plugin-api | 506.2 | 497 | 24 | 0/0 |
| darwin-harvested-openamer-cli-main-py | 93.7 | 43 | 9 | 27/13 |
| mini-openamer | 93.6 | 84 | 12 | 0/0 |
| darwin-harvested-package-lock-json | 93.0 | 45 | 0 | 26/14 |
| darwin-harvested-skills-autonomou | 84.5 | 38 | 15 | 25/13 |
| darwin-cron-guard | 83.5 | 51 | 15 | 21/19 |

## Bottom 5 (selection candidates)

- **darwin-harvested-a2a-brainlog-disabled-no-such-file-o** (Fitness 12.97, 1 days old)
- **darwin-harvested-home-where-scripts-training-does-not** (Fitness 12.0, 0 days old)
- **darwin-harvested-scripts-autonomous-loop-py** (Fitness 12.0, 0 days old)
- **darwin-harvested-training-internet-learner-py** (Fitness 12.0, 0 days old)
- **darwin-harvested-usersdamiropenamer-reposcriptsgithub** (Fitness 12.0, 0 days old)

## New mutations

- auto-env-checker → `auto-env-checker__mutadd_verification_step` (op=add_verification_step, applied=True)
- autonomous-learning-architecture → `autonomous-learning-architecture__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- cdp-social-posting → `cdp-social-posting__muttighten_trigger` (op=tighten_trigger, applied=True)
- train-from-usage → `train-from-usage__mutbroaden_trigger` (op=broaden_trigger, applied=True)
- plugin-api → `plugin-api__muttighten_trigger` (op=tighten_trigger, applied=True)

## Competitions

- ⏳ `asi-identity+auto-env-checker` (0) vs `None` (0)
- ⏳ `auto-env-checker+autonomous-learning-architecture` (0) vs `None` (0)
- ⏳ `auto-env-checker+cdp-social-posting` (0) vs `None` (0)
- ⏳ `auto-env-checker__mutadd_pitfall` (1911.7) vs `auto-env-checker` (1911.7)
- ⏳ `auto-env-checker__mutadd_verification_step` (1911.7) vs `auto-env-checker` (1911.7)
- ⏳ `auto-env-checker__muttighten_trigger` (1911.7) vs `auto-env-checker` (1911.7)
- ⏳ `autonomous-learning-architecture__mutbroaden_trigger` (1700.0) vs `autonomous-learning-architecture` (1700.0)
- ⏳ `autonomous-learning-architecture__muttighten_trigger` (1700.0) vs `autonomous-learning-architecture` (1700.0)
- ⏳ `cdp-social-posting__muttighten_trigger` (721.0) vs `cdp-social-posting` (721.0)
- ⏳ `discord-server-management__mutadd_verification_step` (28.9) vs `discord-server-management` (28.9)
- ⏳ `discord-server-management__mutbroaden_trigger` (28.9) vs `discord-server-management` (28.9)
- ⏳ `discord-server-management__muttighten_trigger` (28.9) vs `discord-server-management` (28.9)
- ⏳ `github-readme-summary__mutbroaden_trigger` (28.2) vs `github-readme-summary` (28.2)
- ⏳ `github-readme-summary__muttighten_trigger` (28.2) vs `github-readme-summary` (28.2)
- ⏳ `openamer-plugin-development__muttighten_trigger` (27.47) vs `openamer-plugin-development` (27.47)
- ⏳ `plugin-api__mutbroaden_trigger` (506.2) vs `plugin-api` (506.2)
- ⏳ `plugin-api__muttighten_trigger` (506.2) vs `plugin-api` (506.2)
- ⏳ `self-rewriter__mutadd_verification_step` (24.2) vs `self-rewriter` (24.2)
- ⏳ `self-rewriter__muttighten_trigger` (24.2) vs `self-rewriter` (24.2)
- ⏳ `train-from-usage__mutadd_pitfall` (513.6) vs `train-from-usage` (513.6)
- ⏳ `train-from-usage__mutadd_verification_step` (513.6) vs `train-from-usage` (513.6)
- ⏳ `train-from-usage__mutbroaden_trigger` (513.6) vs `train-from-usage` (513.6)
- ⏳ `train-from-usage__muttighten_trigger` (513.6) vs `train-from-usage` (513.6)
- ⏳ `undetectable-browsing__muttighten_trigger` (30.27) vs `undetectable-browsing` (30.27)
- ⏳ `vscode-extension-scaffold__mutbroaden_trigger` (31.2) vs `vscode-extension-scaffold` (31.2)

## Evolution Tree

```mermaid
graph TD
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    asi-identity["asi-identity"] ==> asi-identity+auto-env-checker["asi-identity+auto-env-checker"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutadd_verification_step["auto-env-checker__mutadd_verification_step"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    asi-identity["asi-identity"] ==> asi-identity+auto-env-checker["asi-identity+auto-env-checker"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutadd_verification_step["auto-env-checker__mutadd_verification_step"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    asi-identity["asi-identity"] ==> asi-identity+auto-env-checker["asi-identity+auto-env-checker"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutadd_verification_step["auto-env-checker__mutadd_verification_step"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    asi-identity["asi-identity"] ==> asi-identity+auto-env-checker["asi-identity+auto-env-checker"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutadd_verification_step["auto-env-checker__mutadd_verification_step"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    asi-identity["asi-identity"] ==> asi-identity+auto-env-checker["asi-identity+auto-env-checker"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutadd_verification_step["auto-env-checker__mutadd_verification_step"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    asi-identity["asi-identity"] ==> asi-identity+auto-env-checker["asi-identity+auto-env-checker"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutadd_verification_step["auto-env-checker__mutadd_verification_step"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    asi-identity["asi-identity"] ==> asi-identity+auto-env-checker["asi-identity+auto-env-checker"]
```
