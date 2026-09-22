# Darwin Engine Report
_2026-09-22T04:45:59.210237+00:00 — evolutionary skill ecosystem_

**Population:** 142 Skills | **Offspring:** 5 | **Competitions:** 24

## Top 10 (fittest skills)

| Skill | Fitness | Usage | Age (days) | Mutationen W/L |
|---|---|---|---|---|
| auto-env-checker | 2246.0 | 2272 | 0 | 10/56 |
| autonomous-learning-architecture | 2029.0 | 2016 | 0 | 0/0 |
| cdp-social-posting | 1074.0 | 1061 | 0 | 0/0 |
| train-from-usage | 835.97 | 829 | 1 | 0/4 |
| plugin-api | 824.97 | 816 | 31 | 0/0 |
| asi-capability-summary | 656.97 | 647 | 1 | 0/0 |
| a2a-brain-meshlearn-verify | 363.9 | 354 | 3 | 0/0 |
| asi-identity | 319.0 | 309 | 0 | 0/0 |
| self-rewriter | 237.27 | 285 | 22 | 7/71 |
| darwin-harvested-package-lock-json | 106.8 | 59 | 6 | 27/16 |

## Bottom 5 (selection candidates)

- **darwin-harvested-tmp-hook-update-md** (Fitness 14.0, 0 days old)
- **darwin-harvested-logs-skill-validator-latest-json** (Fitness 13.0, 0 days old)
- **darwin-harvested-the-phantom** (Fitness 11.0, 0 days old)
- **darwin-harvested-training-buffer-junk-jsonl** (Fitness 11.0, 0 days old)
- **darwin-harvested-cpython-3-11-windows-x86-64-none-pyt** (Fitness 10.0, 0 days old)

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
- ⏳ `auto-env-checker__mutbroaden_trigger` (2246.0) vs `auto-env-checker` (2246.0)
- ⏳ `autonomous-learning-architecture__mutbroaden_trigger` (2029.0) vs `autonomous-learning-architecture` (2029.0)
- ⏳ `autonomous-learning-architecture__muttighten_trigger` (2029.0) vs `autonomous-learning-architecture` (2029.0)
- ⏳ `cdp-social-posting__muttighten_trigger` (1074.0) vs `cdp-social-posting` (1074.0)
- ⏳ `discord-server-management__mutadd_verification_step` (40.83) vs `discord-server-management` (40.83)
- ⏳ `discord-server-management__mutbroaden_trigger` (40.83) vs `discord-server-management` (40.83)
- ⏳ `discord-server-management__muttighten_trigger` (40.83) vs `discord-server-management` (40.83)
- ⏳ `github-readme-summary__mutbroaden_trigger` (31.97) vs `github-readme-summary` (31.97)
- ⏳ `github-readme-summary__muttighten_trigger` (31.97) vs `github-readme-summary` (31.97)
- ⏳ `openamer-plugin-development__muttighten_trigger` (30.23) vs `openamer-plugin-development` (30.23)
- ⏳ `plugin-api__mutbroaden_trigger` (824.97) vs `plugin-api` (824.97)
- ⏳ `plugin-api__muttighten_trigger` (824.97) vs `plugin-api` (824.97)
- ⏳ `self-rewriter__muttighten_trigger` (237.27) vs `self-rewriter` (237.27)
- ⏳ `train-from-usage__mutadd_pitfall` (835.97) vs `train-from-usage` (835.97)
- ⏳ `train-from-usage__mutadd_verification_step` (835.97) vs `train-from-usage` (835.97)
- ⏳ `train-from-usage__mutbroaden_trigger` (835.97) vs `train-from-usage` (835.97)
- ⏳ `train-from-usage__muttighten_trigger` (835.97) vs `train-from-usage` (835.97)
- ⏳ `undetectable-browsing__muttighten_trigger` (32.03) vs `undetectable-browsing` (32.03)
- ⏳ `vscode-extension-scaffold__mutbroaden_trigger` (31.97) vs `vscode-extension-scaffold` (31.97)

## Evolution Tree

```mermaid
graph TD
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
    auto-env-checker["auto-env-checker"] --> darwin-harvested-training-buffer-junk-jsonl["darwin-harvested-training-buffer-junk-jsonl"]
    auto-env-checker["auto-env-checker"] --> darwin-harvested-the-phantom["darwin-harvested-the-phantom"]
    auto-env-checker["auto-env-checker"] --> auto-env-checker__mutbroaden_trigger["auto-env-checker__mutbroaden_trigger"]
    autonomous-learning-architecture["autonomous-learning-architecture"] --> autonomous-learning-architecture__mutbroaden_trigger["autonomous-learning-architecture__mutbroaden_trigger"]
    cdp-social-posting["cdp-social-posting"] --> cdp-social-posting__muttighten_trigger["cdp-social-posting__muttighten_trigger"]
    train-from-usage["train-from-usage"] --> train-from-usage__mutbroaden_trigger["train-from-usage__mutbroaden_trigger"]
    plugin-api["plugin-api"] --> plugin-api__muttighten_trigger["plugin-api__muttighten_trigger"]
    a2a-brain-meshlearn-verify["a2a-brain-meshlearn-verify"] ==> a2a-brain-meshlearn-verify+asi-capability-summary["a2a-brain-meshlearn-verify+asi-capability-summary"]
    darwin-harvested-training-online-buffer-jsonl["darwin-harvested-training-online-buffer-jsonl"] --> darwin-harvested-training-buffer-junk-jsonl["darwin-harvested-training-buffer-junk-jsonl"]
```
