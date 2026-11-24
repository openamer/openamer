# internet-learning-cycle -- moved sections

Split out of `SKILL.md` because the file exceeded the 100,000-character
SKILL.md limit; content is unchanged.

## Pitfalls

Moved to `references/pitfalls.md` (22.09.26) to keep SKILL.md under
the 100 K limit. Read it before editing the gates.

## References

- Tool server script: `C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/tool_server.py`
- Internet learner script: `C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/internet_learner.py`
- Classes 120+ (129 badge-ribbon weld + publish recipe):
  `references/junk-classes-120plus.md`
- **Class 149 (23.09.26) shipped** — a nav-menu WELD run into a card title drawn
  TWICE (`cycle_c_github`, 252 chars with digits → number-fed hole again). It did
  NOT yield to the 2x2 ladder: both halves fired on innocents. Two NEW measurement
  axes fixed it, and both belong in the toolbox now — **ADJACENCY** (`d <= L`: the
  repeat's second instance must START inside the first; repeat-alone = 88 episode
  FPs → adjacent = 6 → adjacent+run = 0) and a **windowed RUN of distinct marker
  tokens** (max distinct markers inside a 60-char slice; the leak = 7, a sentence
  LISTING the same labels = 6). Plus a **fifth veto corpus**: scan every
  `.md`/`.txt` in the repo (495 files / 11,959 chunks → 0 hits) — the packaged
  four-corpus `candidate_measure.py` has NO long-form prose corpus, which is
  exactly where a repeat/window rule misfires. Full sweep table, thresholds and
  the disjointness assert: `training-scripts-hygiene` →
  `references/conjunction-gate-ladders.md` §7.
- Junk corpus + gate design: `references/junk-classes-and-quality-gates.md`
- Classes 163–166 (publisher age notice STRIP + paper section-TOC chain REJECT +
  repo-listing badge-weld REJECT + a REFUTED quant-table threshold), with every
  candidate's per-corpus table, the hostile controls that killed the wider forms,
  the piped-`git push` exit-code trap, and the probe-hygiene lessons (a
  backtracking regex that hung >400 s; the MSYS `--training-dir` path trap):
  `references/news-age-notice-and-section-toc.md`
- Classes 26–27 (status banners, release-note chains):
  `references/status-and-release-chrome.md`
- Leading-chrome STRIP family: `references/leading-chrome-strip-family.md`
- Classes 17–18 verbatim strings, marker measurements, fixture/CRLF/pre-existing
  hygiene: `references/quality-gate-fixture-and-delta-hygiene.md`
- Re-runnable delta probe (measure a candidate / verify an applied pattern):
  `scripts/gate_delta_probe.py`
- **A count threshold is the weakest discriminator** — measured 23.09.26: a
  `>=5`-pairs count caught its leak with 0 hits on all six corpora and still hit
  3 real-prose controls. Sweep the threshold and print the prose-FP count at
  every step; a refuted candidate is a result to record, not to ship:
  `training-scripts-hygiene` → `references/count-thresholds-vs-structure.md`
- Monorepo "build + tests" (RE-MEASURED 14.10.26): `package.json` says
  `test = bash scripts/run_tests.sh`, and **`scripts/run_research_tests.sh` no
  longer exists** — the 23.09.26 "`research suite: 46 passed, 0 failed`" line is
  void, do not repeat it. A full `npm run test` **exceeds the 600 s foreground
  cap** (killed by the tool, not by the suite): run it as a background job. The
  bounded form, measured green, is `bash scripts/run_tests.sh <file> [<file>]`
  (one `python -m pytest <file>` per file) → **248 passed, 0 failed** on the two
  gate files. Read the target from `package.json` at call time; also attributing
  its reds, the repeated-prompt/deleted-scratch response, and which pytest pair is
  the real evidence: `references/monorepo-npm-verification.md`
- One guard into BOTH gates (`re` vs `_re` blast radii) + temp-probe and
  re-reported-path hygiene: `references/gate-insertion-and-probe-hygiene.md`
- **"WHICH predicate rejects this text?"** — `training-scripts-hygiene` →
  `scripts/diagnose_gate_rejection.py`. Print the FULL reason list in gate order
  with the measurement behind each numeric rule. Reach for it the moment a
  fixture or counter-case "fails": the blame-the-wrong-rule trap has cost four
  sessions now, and every time the guess was wrong. Also takes
  `--fixture-file <test.py> --var <NAME>` to evaluate a test fixture as the test
  sees it (and report the literal's type — adjacent string literals concatenate).
 - **The NEXT step after a learned row is the KTA cycle** —
 `knowledge_to_action.py` (see `autonomous-learning-architecture`) consumes
 `online_buffer.jsonl` and appends to `kta_log.jsonl`. Two facts that mislead on
 first read: the experiment is picked **round-robin** via `.kta_rotation`, so it
 rarely matches the insight's topic (report the `experiment` field, never infer
 it) — and the `online_buffer.jsonl` **300-row cap** reported as
 `buffer at cap 300/300 — trim enforced on every write` is the healthy steady
 state, not a fault to raise. Full matrix + pitfalls:
 `autonomous-learning-architecture` → `references/kta-cycle-verification.md`,
 re-runnable proof script `scripts/kta_cycle_verify.py`.
