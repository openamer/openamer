# CRLF Normalization on Windows with `core.autocrlf=true`

## The Problem

When moving files between the live OpenAmer tree (C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent) and the canonical repo (C:\Users\damir\openamer-repo) on Windows with `core.autocrlf=true`:

- **Repo index stores LF** (Git's internal format)
- **Working tree has CRLF** (Windows default)
- `git diff HEAD -- path` shows **massive line churn** (every line appears changed)
- But `git diff --cached` (staged) shows **clean additive diffs**

Live example (2026-10-11): `tools/asi/heartbeat.py` showed 1,675 lines of CRLF noise in unstaged diff, but staged diff was empty (clean).

## The Fix

**Normalize using the repo's own standard** — don't fight Git's line-ending handling:

```bash
# In the canonical repo (where .git/config has core.autocrlf=true)
git add <files>
# Git converts CRLF→LF in the blob automatically
# The staged diff is the real diff
```

**Verify with blob comparison**, not worktree:

```bash
# What the remote will receive (LF)
git show HEAD:tools/asi/heartbeat.py | wc -c
git show HEAD:tools/asi/heartbeat.py | tr -d '\r' | wc -c   # should match

# What's on disk (CRLF)
wc -c tools/asi/heartbeat.py
tr -d '\r' < tools/asi/heartbeat.py | wc -c
```

## Pattern for Cross-Tree Sync (Live Tree → Canonical Repo)

The live tree is **not a git repo**. To sync changes:

1. **Copy files directly** (not git) from live tree to repo working tree
2. **Stage in repo** — `git add` normalizes CRLF→LF
3. **Verify staged diff** (`git diff --cached`) is purely additive (+lines only)
4. **Commit** — the blob is correct LF

```bash
# Live tree source
L=/c/Users/damir/AppData/Local/openamer-laptop/openamer-agent
R=/c/Users/damir/openamer-repo

# Copy modified files
cp "$L/tools/asi/cognition.py" "$R/tools/asi/cognition.py"
cp "$L/tools/asi/heartbeat.py" "$R/tools/asi/heartbeat.py"
# ... etc

# In repo: stage and verify
cd "$R"
git add tools/asi/cognition.py tools/asi/heartbeat.py ...
git diff --cached --stat   # should show only your real changes
```

## Pitfall: `git add -A` in ship.py sweeps cron artifacts

The ship gate (`scripts/ship.py`) runs `git add -A`. **Before running ship**, restore any cron-generated files to HEAD so they don't pollute the commit:

```bash
# Cron files that get auto-modified (restore to HEAD)
git restore reports/darwin-fitness.json reports/darwin-history.jsonl reports/darwin-report.md ...
# Then ship.py only stages your 6 intended files
```