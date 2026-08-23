---
title: dsh-merging-stacked-prs
description: Use when landing a stack of dependent GitHub PRs (A ← B ← C, where each bases on the one below) onto master, merging a P
---

# dsh-merging-stacked-prs

**Description:** Use when landing a stack of dependent GitHub PRs (A ← B ← C, where each bases on the one below) onto master, merging a PR whose base is another open PR's branch, or whenever a request mentions "stacked PRs", "PR stack", "dependent PRs", or merging several related PRs in sequence. Requires every same-repository dependency chain to use GitHub's official stacked-PR feature before landing so GitHub owns stack-wide rules, CI, ordering, retargeting, and merge state.
**Lines:** 128 | **Code:** 29 | **Dir:** `dsh-merging-stacked-prs`

---

---
name: dsh-merging-stacked-prs
description: Use when landing a stack of dependent GitHub PRs (A ← B ← C, where each bases on the one below) onto master, merging a PR whose base is another open PR's...