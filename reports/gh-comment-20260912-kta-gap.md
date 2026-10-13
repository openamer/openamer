**Honest fix on main: a self-learning "experiment" that inspected nothing — and what it now says about our competitor pipeline (`ba9f5b728`).**

Continuing this thread's pattern of posting the failure first: our Knowledge-to-Action loop has an `experiment_competitor_gap()` step. It reported success on every run. It was reciting a canned line.

**Measured evidence (not an impression).** `scripts/training/kta_log.jsonl` holds 567 entries right now, 155 of them competitor-gap runs. Counting the distinct `identified_gap` values across those runs:

```
 96x  OpenHands has a modular SDK design — our tool_server.py is monolithic
 11x  buffer near cap — meta_learn will trim      (unrelated meta experiments)
 ...
```

96 runs, one string — while the buffer signal underneath changed every time. The function also always returned `measurable: False`, i.e. the loop was structurally incapable of ever showing a result. A log that grows while the content is frozen is worse than no log: it looks like analysis.

**What changed.** The experiment now (1) quotes the real latest competitor signal verbatim so every entry is traceable, (2) maps it against a small capability lexicon, (3) actually **measures our own tool surface**, and (4) says so plainly when a signal isn't mappable — because that is itself the finding.

**Live run, minutes ago, on the real buffer (not a temp fixture):**

```json
{
  "signal_source_question": "What new agent architectures are trending on GitHub?",
  "signal_candidates": 15,
  "measured_tool_surface": {"lines": 436, "tool_funcs": 9, "has_tools_pkg": false},
  "identified_gap": "no mappable capability in latest signal (our tool surface:
                     9 tool funcs in 436 lines, tools/ package: no) —
                     upstream competitor answers are not informative",
  "proposed_fix": "repair competitor insight extraction (answers are non-answer snippets)",
  "measurable": true
}
```

That is the useful part. `measurable` flipped from a hardwired `False` to `true`, and the first honest reading it produced is that **the upstream competitor pipeline is feeding it ad copy** — the "latest signal" is a vendor blurb (*"Kiro helps developers and teams do their best work…"*), not a competitor capability. Previously that junk was silently laundered into a fixed, plausible-sounding gap about OpenHands. Now a broken upstream shows up as a broken upstream instead of as a fake insight.

Also worth reading straight: `tools/ package: no` is a real measurement of us, not a claim about a competitor. Our tool surface is 9 tool functions in 436 lines with no per-tool module boundary — that number is now recorded on every run instead of being asserted from vibes.

**Regression guard, run just now:** `scripts/training/test_competitor_gap.py` — 6 tests, all pass, temp-dir only (the real buffer is never read or written). They pin: gap derived not constant (two different signals → two different gaps), a real measurement is present, the unmappable path is honest, the no-signal path is explicit, and junk lines in the buffer don't crash the scan.

```
PASS test_entry_carries_a_real_measurement
PASS test_gap_is_derived_not_hardcoded
PASS test_latest_signal_wins_and_junk_lines_tolerated
PASS test_missing_tool_server_does_not_crash
PASS test_no_competitor_data_is_explicit
PASS test_unmappable_signal_reported_honestly
OK: 0 failure(s)
```

**Honest limit:** the new function cannot tell you whether we *lack* a capability or whether the input is simply garbage — it can only tell you which one it is looking at, per run. That is the point: it stops inventing a gap when there is no signal. The next real fix is on the *consumer* side — the competitor insight extractor needs to reject non-answer snippets ("X helps teams do their best work") before they reach this step at all. Not done yet; logged here as the follow-up.
