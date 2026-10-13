---
name: bug-bounty
description: "Use for autonomous bug-hunt: scan, reproduce, fix, bounty."
---

# 🐛 Bug Bounty — Autonomous Bug Hunter

Self-finding + self-fixing bug bounty system. Scans multiple sources, reproduces bugs, generates fixes, awards bounty points, and maintains a leaderboard.

## Script

`scripts/bug-bounty.py`

## CLI Commands

```bash
# Scan all sources for new bugs (no fixing)
python scripts/bug-bounty.py --scan

# Hunt one bug: find → reproduce → fix → award bounty
python scripts/bug-bounty.py --hunt

# Show leaderboard
python scripts/bug-bounty.py --leaderboard

# Show statistics (found/fixed/trend)
python scripts/bug-bounty.py --stats
```

## Exit Codes
| Code | Meaning |
|------|---------|
| 0    | No bugs found |
| 1    | Bugs found (not fixed) |
| 2    | Bugs fixed + bounty awarded |

## Data Sources Scanned

| Source | Description |
|--------|-------------|
| GitHub Issues | Open issues with `bug` label (via `gh` CLI) |
| Cron Logs | Error patterns in cron output files (+ `last_error` fields in jobs.json) |
| Self-Healer Memory | Recurring issues (3+ occurrences) from self-healer's memory.json |
| Code Quality | Static analysis: bare `except:` clauses, TODO/FIXME markers |

## Bounty Point System

| Severity | Base Points |
|----------|-------------|
| Critical | 10 |
| High     | 7  |
| Medium   | 5  |
| Low      | 3  |
| Info     | 1  |

Bonuses: +2 for reproducible, +1-3 for source difficulty, +/-1 variance.

## Storage

| File | Purpose |
|------|---------|
| `~/.bug-bounty/state.json` | Seen/fixed bugs, stats, scan history |
| `~/.bug-bounty/leaderboard.json` | Bounty entries (fixer, points, bug) |
| `~/.bug-bounty/hunts.json` | Detailed hunt log |
| `~/.bug-bounty/fix_*.md` | Fix reports |
| `~/.bug-bounty/repro_*.txt` | Reproduction output |

## Cron Setup

```bash
# Scan every 4 hours
openamer cronjob create \
  --schedule 'every 240m' \
  --script scripts/bug-bounty.py -- --scan \
  --name 'Bug Bounty Scanner'
```

## Related
- `bugbot.py` — GitHub Issues to PR pipeline (complementary: bugbot creates PRs, bug-bounty awards points)
- `self-healer.py` — daemon-level error recovery