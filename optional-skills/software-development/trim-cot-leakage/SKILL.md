---
name: trim-cot-leakage
description: Audit prose for leaked chain-of-thought reasoning residue.
version: 1.0.0
author: OpenAmer Agent (adapted from DeepSeek Harness, MIT)
license: MIT
platforms: [windows, linux, macos]
metadata:
  openamer:
    tags: [prose, review, quality, chain-of-thought, documentation]
    related_skills: [requesting-code-review, clean-code-edits]
---

# Trimming Chain-of-Thought Leakage

Chain-of-thought leakage is prose whose vantage is the authoring session
rather than the repository: it cites artifacts only that session could see,
narrates the change instead of the state, or argues with a reviewer who has
left. The fix is never deletion alone when a passage carries factual clauses —
restate each so it stands at HEAD, then delete the transcript around it; a
passage carrying none (an audit code, control-flow narration) is deleted
outright. It is guidance, not a script.

## The one test

For every suspect passage ask: **could a reader at HEAD, with no access to any
session transcript, PR thread, or uncommitted draft, resolve every reference
and verify every claim?** If no, restate the surviving facts from the
repository's vantage and delete the rest. If yes, it is not leakage, however
historical it sounds — but resolvability only clears this skill's bar: on
current-state surfaces (READMEs, docs, docstrings) a resolvable change story
is still change narration, and class 3 routes it to its sanctioned home.

## Taxonomy

1. **Dead design-session citations** — `(decision 7)`, `(audit C2)`, `design
   §4.7`, `plan §1.4`, phase labels (`T4`, `W3`, `P-I`), "the design ledger",
   "(B ruling)". If the decision has a committed owner, cite it by name and
   path; otherwise delete the citation and restate its factual clause to stand
   alone.
2. **Stack and PR vantage** — "a later PR in this stack", "this PR adds", "the
   previous commit". State the shipped mechanism or the extension point;
   deferred work moves to a `TODO` marker or an issue reference.
3. **Change narration and version stamps** — "used to", "no longer", "the old
   X", and indexical stamps ("v1", "this cut", "today", "now" contrasting with
   a past state). State the present behavior; a fixed regression becomes a
   present-tense counterfactual ("without X, Y happens"), never repo history
   ("used to Y").
4. **Review choreography** — "Rejected in review:", "the reviewer confirmed",
   draft ordinals ("v5 of this note"), round attributions. Keep the surviving
   decision and rationale as plain fact; delete who said it when.
5. **Reviewer-addressed justification** — "the cast is safe — it simply…",
   "this is correct because…". A comment arguing its own correctness addresses
   a reviewer, not a maintainer. State the invariant that makes the code safe,
   or delete the comment if the code shows it.
6. **Restatement and derivation transcripts** — control-flow narration ("first
   we X, then we Y"), test walkthroughs, proofs of obvious branches. Delete;
   keep only a non-obvious contract or invariant.
7. **Hedges and planning residue** — "probably fine for now", "should be
   enough", deferrals with no marker. Promote to `TODO`/`FIXME` or restate as
   the actual bound; delete the hedge.
8. **Authoring-language slips** — untranslated working-language fragments in
   prose whose language is otherwise English, or the reverse in a translated
   counterpart. Translate or delete.

## What is not leakage

Unaided citation passes fail in both directions by deleting durable references
and keeping dead ones. Apply these keep rules as written:

- **Issue references** — `#1470`, `TODO(name):`, "issue #N owns the follow-up"
  resolve at HEAD; keep them on any surface, including READMEs.
- **Merged-PR and issue citations inside design notes and postmortems** —
  sanctioned evidence.
- **Suppression justifications** — linter-disable comments with a reason,
  coverage-ignore reasons, empty-catch explanations are required prose; fix a
  false reason, never delete it.
- **Counterfactual-present regression pins** — "without X, Y happens", "a
  naive X would…".
- **Measured bounds** — "(measured: 512 nests ≈ 0.15s)" calibrating a
  constant; the provenance word "measured" is load-bearing.
- **Runtime old/new states** — "the old connection drains before the new one
  accepts" is runtime lifecycle, not change history.
- **Historical stage names inside a note's change-story sections** — "the
  first cut shipped X" is current-state-safe there; indexical stamps ("this
  cut") stay banned everywhere.
- **External references that resolve outside the repo by design** — standards
  sections (RFC 9110 §10.1.5), design-tool frame names; the §-ban covers
  uncommitted internal drafts, not external standards or committed docs that
  own their §-numbering.
- **Project voice and genre forms** — "we" as project voice; a note's
  Alternatives-considered section.

## Workflow

1. Require an explicit scope; never touch vendored dependencies, archived
   notes, or recorded fixtures and snapshots — recorded model output and
   sealed history keep their original voice.
2. Audit read-only first: run the [recall batteries](references/recall-batteries.md)
   (with `--hidden` so dot-directories are searched), then judge every hit
   semantically. The batteries are probes, not the definition — also read the
   densest prose in scope (module docstrings, READMEs, design notes) without a
   pattern in hand.
3. Fix owner-first per surface: generated catalogs → fix the source docstring
   or generator template, then regenerate; bilingual pairs → update the
   counterpart; model-visible strings → wording is behavior, so flag for a
   snapshot-backed change instead of silently rewording.
4. Before deleting anything, enumerate the passage's propositions and check
   the overcorrection traps: trims that flip an obligation into an
   endorsement, promote a hypothetical to a shipped feature, delete a true
   fact, or drop provenance.
5. Verify: re-run the batteries expecting only sanctioned keeps; confirm every
   remaining citation resolves at HEAD; run the relevant checks for touched
   surfaces.

## Related

Adapted from the DeepSeek Harness `dsh-trim-cot-leakage` skill (MIT). The
taxonomy and recall batteries are repository-agnostic; the original's
dsh-specific references (pnpm, oxlint, Cordis, `.agents/notes/`) were removed.
