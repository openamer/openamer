# Darwin Engine Report
_2026-09-20T05:45:08.461225+00:00 — evolutionary skill ecosystem_

**Population:** 113 Skills | **Offspring:** 5 | **Competitions:** 24

## Top 10 (fittest skills)

| Skill | Fitness | Usage | Age (days) | Mutationen W/L |
|---|---|---|---|---|
| auto-env-checker | 2087.97 | 2096 | 1 | 7/32 |
| autonomous-learning-architecture | 1863.93 | 1851 | 2 | 0/0 |
| cdp-social-posting | 906.93 | 894 | 2 | 0/0 |
| train-from-usage | 678.43 | 672 | 17 | 0/4 |
| plugin-api | 669.03 | 660 | 29 | 0/0 |
| asi-capability-summary | 342.87 | 333 | 4 | 0/0 |
| asi-identity | 311.87 | 302 | 4 | 0/0 |
| self-rewriter | 144.33 | 198 | 20 | 4/71 |
| darwin-harvested-package-lock-json | 105.87 | 57 | 4 | 27/15 |
| darwin-harvested-openamer-cli-main-py | 99.57 | 48 | 13 | 28/14 |

## Bottom 5 (selection candidates)

- **darwin-harvested-darwin-gate-queue-json** (Fitness 16.97, 1 days old)
- **darwin-harvested-darwin-promoted** (Fitness 15.97, 1 days old)
- **darwin-harvested-tmp-oa-home** (Fitness 15.97, 1 days old)
- **darwin-harvested-gridverify-desktop-json** (Fitness 11.97, 1 days old)
- **darwin-harvested-was-created-by-the-uv-installer-seed** (Fitness 11.97, 1 days old)

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
- ⏳ `auto-env-checker__mutbroaden_trigger` (2087.97) vs `auto-env-checker` (2087.97)
- ⏳ `autonomous-learning-architecture__mutbroaden_trigger` (1863.93) vs `autonomous-learning-architecture` (1863.93)
- ⏳ `autonomous-learning-architecture__muttighten_trigger` (1863.93) vs `autonomous-learning-architecture` (1863.93)
- ⏳ `cdp-social-posting__muttighten_trigger` (906.93) vs `cdp-social-posting` (906.93)
- ⏳ `discord-server-management__mutadd_verification_step` (34.9) vs `discord-server-management` (34.9)
- ⏳ `discord-server-management__mutbroaden_trigger` (34.9) vs `discord-server-management` (34.9)
- ⏳ `discord-server-management__muttighten_trigger` (34.9) vs `discord-server-management` (34.9)
- ⏳ `github-readme-summary__mutbroaden_trigger` (28.03) vs `github-readme-summary` (28.03)
- ⏳ `github-readme-summary__muttighten_trigger` (28.03) vs `github-readme-summary` (28.03)
- ⏳ `openamer-plugin-development__muttighten_trigger` (27.3) vs `openamer-plugin-development` (27.3)
- ⏳ `plugin-api__mutbroaden_trigger` (669.03) vs `plugin-api` (669.03)
- ⏳ `plugin-api__muttighten_trigger` (669.03) vs `plugin-api` (669.03)
- ⏳ `self-rewriter__muttighten_trigger` (146.33) vs `self-rewriter` (146.33)
- ⏳ `train-from-usage__mutadd_pitfall` (678.43) vs `train-from-usage` (678.43)
- ⏳ `train-from-usage__mutadd_verification_step` (678.43) vs `train-from-usage` (678.43)
- ⏳ `train-from-usage__mutbroaden_trigger` (678.43) vs `train-from-usage` (678.43)
- ⏳ `train-from-usage__muttighten_trigger` (678.43) vs `train-from-usage` (678.43)
- ⏳ `undetectable-browsing__muttighten_trigger` (30.1) vs `undetectable-browsing` (30.1)
- ⏳ `vscode-extension-scaffold__mutbroaden_trigger` (31.03) vs `vscode-extension-scaffold` (31.03)

## Evolution Tree

```mermaid
graph TD
    alpha["alpha"] ==> alpha+dead-skill["alpha+dead-skill"]
    alpha["alpha"] --> darwin-evidence-hygiene["darwin-evidence-hygiene"]
    alpha["alpha"] --> darwin-session-recall["darwin-session-recall"]
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
    auto-env-checker["auto-env-checker"] -.-> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
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
