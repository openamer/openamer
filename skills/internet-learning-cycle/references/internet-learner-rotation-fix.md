# Internet Learning Cycle — Query Rotation Improvement

## User Preference (2026-11-22)

The user criticized the internet learning cycle as "amateurish — same approach every time, no new question generation". This skill has been updated to address this concern.

## Current Rotation Mechanism (as of 2026-11-22)

The learner rotates through 5 source types (A. Tech news [HN/Reddit/Dev.to], B. Papers [arxiv], C. GitHub trending, D. Docs [vLLM/transformers/PEFT], E. Competitors [Devin/OpenHands/AutoGPT]) and uses 8 thematic angles per source:

- ```` (plain seed)
- limitations and failure modes
- benchmark comparison
- production case study
- best practices 2026
- common pitfalls
- alternative approaches
- lessons learned postmortem

The angle selection uses a `.il_rotation` counter stored in `scripts/training/.il_rotation`. **Current behavior:** The counter advances **per day** (based on `datetime.date.today().timetuple().tm_yday`), so all invocations within the same day receive the same angle suffix.

## Identified Issue

When the counter does not advance per invocation, or when the `.il_rotation` file is static, all cycles within a given day query the same HN headlines or generate the same LLM prompts, leading to repeated "duplicate" rejections and the feeling that "nothing new is generated."

## Improvement — Per-Invocation Counter Advancement

**Fix:** Modify the `_rotate()` function in `scripts/training/internet_learner.py` to increment and persist the `.il_rotation` counter on **every invocation**, not just once per day. This ensures each cycle receives a unique angle combination.

### Suggested Code Change

In the `_rotate()` function, after computing `a = angles[(day + n) % len(angles)]`, add:

```python
# Persist advanced counter for next invocation
try:
    with open(ROT, "w", encoding="utf-8") as f:
        f.write(str(n + 1))
except Exception:
    pass
```

This writes `n + 1` back to the file after each invocation, so the next invocation uses `day + (n+1)`, advancing the angle cycle linearly regardless of calendar day.

## Verification

Run the learner multiple times within the same day:

```bash
python "$OPENAMER_HOME/scripts/training/internet_learner.py" --once
```

Each run should now produce a different angle suffix (e.g., first run plain seed, second run with "limitations and failure modes", etc.), and the insight stored should vary accordingly.

## Next Steps

- Monitor `internet_learn_log.jsonl` for reduced duplicate rejections.
- Consider expanding the angles list if 8 proves insufficient for long-term novelty.
- Evaluate whether the same fix applies to the HN `_fresh_headline` and LLM `_llm_novel_query` paths.