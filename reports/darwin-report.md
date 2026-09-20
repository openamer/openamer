# Darwin Engine Report
_2026-09-20T23:55:06.468607+00:00 — evolutionary skill ecosystem_

**Population:** 122 Skills | **Offspring:** 5 | **Competitions:** 24

## Top 10 (fittest skills)

| Skill | Fitness | Usage | Age (days) | Mutationen W/L |
|---|---|---|---|---|
| auto-env-checker | 2130.0 | 2145 | 0 | 8/41 |
| autonomous-learning-architecture | 1908.9 | 1896 | 3 | 0/0 |
| cdp-social-posting | 952.9 | 940 | 3 | 0/0 |
| train-from-usage | 720.0 | 713 | 0 | 0/4 |
| plugin-api | 710.0 | 701 | 30 | 0/0 |
| asi-capability-summary | 429.0 | 419 | 0 | 0/0 |
| asi-identity | 316.0 | 306 | 0 | 0/0 |
| self-rewriter | 171.3 | 221 | 21 | 6/71 |
| a2a-brain-meshlearn-verify | 135.93 | 126 | 2 | 0/0 |
| darwin-harvested-package-lock-json | 106.83 | 58 | 5 | 27/15 |

## Bottom 5 (selection candidates)

- **darwin-harvested-reports-darwin-promoted** (Fitness 15.0, 0 days old)
- **darwin-harvested-was-created-by-the-uv-installer-seed** (Fitness 14.97, 1 days old)
- **darwin-harvested-tmp-cleanup-now-py** (Fitness 14.0, 0 days old)
- **darwin-harvested-tmp-verify-comment-5749873455-py** (Fitness 14.0, 0 days old)
- **darwin-harvested-temp-oa-wt-main** (Fitness 12.0, 0 days old)

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
- ⏳ `auto-env-checker__mutbroaden_trigger` (2130.0) vs `auto-env-checker` (2130.0)
- ⏳ `autonomous-learning-architecture__mutbroaden_trigger` (1908.9) vs `autonomous-learning-architecture` (1908.9)
- ⏳ `autonomous-learning-architecture__muttighten_trigger` (1908.9) vs `autonomous-learning-architecture` (1908.9)
- ⏳ `cdp-social-posting__muttighten_trigger` (952.9) vs `cdp-social-posting` (952.9)
- ⏳ `discord-server-management__mutadd_verification_step` (36.9) vs `discord-server-management` (36.9)
- ⏳ `discord-server-management__mutbroaden_trigger` (36.9) vs `discord-server-management` (36.9)
- ⏳ `discord-server-management__muttighten_trigger` (36.9) vs `discord-server-management` (36.9)
- ⏳ `github-readme-summary__mutbroaden_trigger` (28.0) vs `github-readme-summary` (28.0)
- ⏳ `github-readme-summary__muttighten_trigger` (28.0) vs `github-readme-summary` (28.0)
- ⏳ `openamer-plugin-development__muttighten_trigger` (27.3) vs `openamer-plugin-development` (27.3)
- ⏳ `plugin-api__mutbroaden_trigger` (710.0) vs `plugin-api` (710.0)
- ⏳ `plugin-api__muttighten_trigger` (710.0) vs `plugin-api` (710.0)
- ⏳ `self-rewriter__muttighten_trigger` (171.3) vs `self-rewriter` (171.3)
- ⏳ `train-from-usage__mutadd_pitfall` (720.0) vs `train-from-usage` (720.0)
- ⏳ `train-from-usage__mutadd_verification_step` (720.0) vs `train-from-usage` (720.0)
- ⏳ `train-from-usage__mutbroaden_trigger` (720.0) vs `train-from-usage` (720.0)
- ⏳ `train-from-usage__muttighten_trigger` (720.0) vs `train-from-usage` (720.0)
- ⏳ `undetectable-browsing__muttighten_trigger` (30.07) vs `undetectable-browsing` (30.07)
- ⏳ `vscode-extension-scaffold__mutbroaden_trigger` (31.0) vs `vscode-extension-scaffold` (31.0)

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
