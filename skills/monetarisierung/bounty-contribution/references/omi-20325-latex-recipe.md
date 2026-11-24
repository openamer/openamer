# Session detail: BasedHardware/omi #20325 — conversations→LaTeX recipe (PR #20351)

Class lesson source: large-repo "bounty proposal" issue with a full spec inside
the body. The spec IS the contract — read the whole body before coding (it
defined file paths, CLI flags, test-class breakdown, and validation commands).

## Vetting data points
- omi: 13,624★, pushed same day → real. Payout is PayPal-after-merge; the
  proposal body itself carried a `<<PAYPAL_EMAIL>>` placeholder and an
  "AI assistant disclosure" — proceed anyway; credit + merge is the asset.
- Candidates rejected this scan: ThinkRL #208 (7★ < 20 threshold, no bounty
  label), tt-metal $1000 cumsum NaN (needs GPU hardware, out of CPU budget),
  relayhop/sn-monetization-runtime `[radar]` bot issues (auto-post spam), and
  the analyzer script that produced them (only emits radar items — for real
  candidates use `gh api search/issues?q=...+is:issue+is:open` instead).
- Claim protocol: comment "Claiming this one" on the issue FIRST, then build.

## Workflow that landed the PR
1. `gh api "search/issues?q=repo:<owner>/<repo>+<keyword>+is:issue+is:open"` to
   resolve the issue number when `gh search issues` JSON parsing is flaky.
2. Clone: `git clone --depth 1 --filter=blob:none --sparse` + `git
   sparse-checkout set sdks/python-cli/examples` (fast on huge repos).
3. Mirror the sibling recipe (`conversations_to_markdown.py`) for conventions:
   is_completed loose-type coercion, format_timestamp, slugify,
   extract_conversations envelope unwrapping.
4. Tests colocated in `sdks/python-cli/tests/test_<name>.py`, runnable via
   `python -m unittest test_conversations_to_latex` from the tests dir.
5. Format with repo settings: `black --line-length 120` + `isort --profile black`.
6. Push via Contents API (see SKILL.md pitfall — direct push timed out twice).
   Commit SHAs: 0268a7f, 60c11a6, 1b8621c, 4498667 on
   `openamer/omi:fix/conversations-to-latex`.
7. PR via `gh pr create --repo BasedHardware/omi --head openamer:fix/conversations-to-latex`
   → BasedHardware/omi#20351, body `Closes #20325`.

## Test-invariant pattern worth copying (from the spec)
- Every raw `& % $ # _` occurrence is part of its own escape.
- Raw `~`/`^` fully absent from generated `.tex`.
- Braces balance after stripping `\{`/`\}`.
- `\begin{env}`/`\end{env}` pairs balanced.
- Deterministic bytes (same input → same output).

## Fixture-helper lesson
`conv(**over)` style helpers: overrides of NESTED spec fields (title inside
structured) must write the nested path, and must be idempotent for falsy
values, or later per-test overrides inherit stale fixtures.