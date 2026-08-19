---
name: self-modify
description: Use when modifying OpenAmer's own core code safely. Gate every change behind the test suite with automatic rollback.
version: 1.0.0
author: OpenAmer Agent
license: MIT
metadata:
  openamer:
    tags: [self-improvement, safety, rollback, test-gate, core]
    related_skills: [openamer-agent, requesting-code-review, clean-code-edits]
---

# Self-Modify (Test-Gated Core Changes)

## Overview

OpenAmer can modify its own core code — but only through a verified gate that
makes self-destruction impossible. This is the "does not break" axis made
concrete: a change to a core file is kept **only if the test suite proves it
does not break anything**, and is rolled back automatically on any failure.

This is the same mechanism iklem has (`self_modify`), adapted to OpenAmer's
architecture. OpenAmer's design rule is "the core is a narrow waist; capability
lives at the edges" — so this is a **script + skill**, not a core tool. A
self-modify *tool* would ship on every API call; a script invoked via the
terminal tool costs nothing until it is actually used.

## When to Use

- The user asks you to change OpenAmer's own source code (a bug fix, a feature)
  and you want the change to be safe and verifiable.
- You are fixing a bug in OpenAmer itself and want proof the fix doesn't break
  anything else.
- You want to add a capability to OpenAmer's core and need the test gate.

Don't use for:
- Editing files outside the openamer-agent repo (the script refuses).
- Trivial edits where running the full suite is overkill — but prefer the gate
  for anything touching core behavior.

## The Mechanism

`scripts/self_modify.py` implements four guardrails:

1. **Scope guard** — the target must be inside the openamer-agent repo.
2. **Backup** — the original is always saved to `<file>.bak` before any change.
3. **Test gate** — the full suite (`scripts/run_tests.sh`) must pass.
4. **Rollback** — on any failure the original is restored atomically.

## Steps

1. **Write the new content** to a temp file (or a patch file), NOT directly to
   the target. Completion: the new content is in a separate file, the target is
   untouched.

2. **Run the gate:**
   ```bash
   python scripts/self_modify.py <path> <new_content_file>
   # or
   python scripts/self_modify.py <path> --content "new content"
   # or, for a diff:
   python scripts/self_modify.py <path> --patch <patch_file>
   ```
   Completion: the script prints either `✓ change applied and verified` or
   `✗ change rejected (tests failed, rolled back)`.

3. **On success**, verify the change is actually in place and the `.bak` is gone.
   Completion: `git diff` shows the change; no `.bak` file remains.

4. **On failure**, read the test output the script printed, fix the root cause,
   and re-run. Completion: the target is byte-identical to the original (the
   rollback worked) and you understand why the tests failed.

## Common Pitfalls

1. **Editing the target directly instead of going through the script.** This
   bypasses the test gate and the rollback — the exact failure mode the script
   exists to prevent.

2. **Running `pytest` directly instead of `scripts/run_tests.sh`.** The script
   uses the canonical runner so the gate matches CI behavior (per-file
   isolation, deterministic env). A green `pytest` locally may not match CI.

3. **Ignoring a rollback.** If the script says "rolled back", the change is
   gone — do not assume it is still applied. Re-read the file before proceeding.

4. **Modifying a file outside the repo.** The scope guard refuses; that is
   intentional. OpenAmer's self-modification is bounded to its own source.

5. **Treating the `.bak` as a feature.** It is a transient safety artifact, not
   a version-control substitute. Commit the change with git; the `.bak` is
   removed on success.

## Verification Checklist

- [ ] The change went through `scripts/self_modify.py`, not a direct edit
- [ ] The script printed `✓` (tests passed) — or you are iterating on a `✗`
- [ ] No `.bak` file remains after a successful change
- [ ] `git diff` shows exactly the intended change and nothing else
- [ ] The change is committed with a clear message
