# Junk classes 120+ — verbatim leaks, the measured counter-cases, the gate wiring

Companion to `junk-classes-and-quality-gates.md` (classes up to ~119) and
`leading-chrome-strip-family.md` (the STRIP classes). Every row below was
learned by a real `internet_learner.py --once` cycle and cleared BOTH gates
before being fixed. Same two-layer rule as always: a REJECT class lands in
`_is_junk` (learner) **and** in `buffer_store._is_nav_chrome` (writer), each
gated by its own FP measurement.

## Class 129 — a blog BADGE RIBBON welded to the headline stack (live 21.09.26)

`cycle_d_docs` stored a site card ribbon, not knowledge:

```
Arab World #3 Featured Blog 85% 3 Machine Learning RAG Systems in Production:
Architecture, Tradeoffs, and Failure Modes Retrieval-augmented generation (RAG)
is the dominant application pattern for l
```

239 chars WITH digits → the >=90 length trust AND the technical-signal gate both
fired. Class 106's rule (`_is_blog_nav_feature_run_chrome`) needs a >=8-token nav
vocabulary run and this ribbon has none.

Guard: **THREE conjuncts IN ORDER**, never the bare label —

```python
_BADGE_RIBBON_RE = re.compile(
    r"^[\s\S]{0,40}?#\s*\d{1,3}\b[\s\S]{0,60}?\bFeatured\s+Blog\b"
    r"[\s\S]{0,60}?\d{1,3}\s*%", re.IGNORECASE)
```

A **bare `Featured Blog` marker was measured and REJECTED as too broad** — it
fired on all 3 natural-prose counter-cases:

| Counter-case | Why it must stay learnable |
|---|---|
| `"The site's Featured Blog section covers RAG in production systems, and the 2026 article explains chunking and reranking tradeoffs."` | prose ABOUT the section |
| `"Our Featured Blog post on quantization recovers 97% of fp16 accuracy at INT4."` | a real technical claim |
| `"The Featured Blog archive lists 3 posts about agent evaluation harnesses."` | a listing sentence |

Only the leading-anchored 3-conjunct form discriminates. Keep all three as the
test controls.

REJECT, not strip (same call as class 128, the AI-agent index landing page): the
prose behind the ribbon is a generic RAG lede with no capability token. Wired as
`_is_badge_ribbon_chrome` in `internet_learner._is_junk` and mirrored as
`buffer_store._is_badge_ribbon_chrome` so both gates agree by construction.

### Measured (the numbers that justify the pattern)

| Corpus | Hits |
|---|---|
| `online_buffer.jsonl` (210 rows) | **1** — and it IS the leak |
| `buffer_junk.jsonl` (7,984 rows) | 0 |
| `memory/longterm_episodes.jsonl` (3,059 rows) | 0 |
| 3 hand-written prose controls | 0 |

Old-vs-new delta over the 209-row live buffer (committed module vs working copy,
same process, unique module names): `newly_rejected=0, regressions=0` — the leak
had already been dropped with `_drop_offtopic_row.py` before the edit.

Suites: **139 passed** (`tests/scripts/test_internet_learner_gate.py`),
**24 passed** (`scripts/training/test_internet_learner.py`),
**295 passed** (`tests/scripts/` full folder — required because the writer gate
was touched). One live `--once` after the HOME sync reported an on-topic
`efficiency-learn:` row.

## Two live traps from the same round

1. **The leak was an ACCEPTED row** — worse than a miss, because it becomes LoRA
   training data. It is only visible by reading the LAST line of
   `online_buffer.jsonl` after a `learned:` line. Never trust the cycle name or
   the `[<source>-learn]` prefix as proof of relevance.
2. **`tests/scripts/test_internet_learner_gate.py` carries 120 PRE-EXISTING bare
   LFs and 2 CRCRLF in its committed blob.** An append helper that asserts
   `bare_LF == 0` fails on the *baseline*, not on your block. Capture
   `before = d.count(b"\n") - d.count(b"\r\n")` and assert the count is
   **unchanged**; same for CRCRLF. Do NOT normalise the file — that rewrites all
   5,254 lines and buries the real change (the classic flip). The same applies to
   any file whose blob you did not write.

## Publishing a single commit when the local branch is 33/41 off `origin/main`

The tree sat on a stray `fix/28-…` branch, 33 ahead / 41 behind, and
`origin/main` did **not** contain classes 125–128 — so a `cherry-pick` of the
commit would have failed on a missing anchor (it inserts next to the class-128
call site). The working recipe for this shape:

1. `git worktree add -f "C:/Users/<u>/oa-pub129" origin/main` (Windows drive
   form, then `cd` in a SEPARATE step).
2. Build the content from the **blobs** (`git show origin/main:<path>`), never
   from worktree files, and re-target the insert to an anchor that
   `origin/main` actually HAS (here the class-106 call site).
3. `git -c core.autocrlf=false add` → assert
   `diff --cached --numstat` **equals** `diff --cached -w --numstat`, and that
   deletions are 0 (insert-only). `30/0`, `30/0`, `59/0` here.
4. Run the gate suite INSIDE the worktree before committing (129 passed) — the
   worktree is a different base, so the repo run does not transfer.
5. Commit, push with `git -c credential.helper= -c credential.helper=store push
   origin HEAD:main`, then prove it landed with
   `git ls-remote origin main` == `git rev-parse HEAD` (`9a155bfa2` both sides).
6. `git worktree remove --force "C:/Users/<u>/oa-pub129"` + `git worktree prune`.
