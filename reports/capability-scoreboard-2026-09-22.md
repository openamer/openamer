# Capability scoreboard - 2026-09-22T20:18:31+02:00

Live-measured. Every row names its source. Unmeasurable rows are marked.

## Distribution (measured via GitHub API)

| Product | Stars | Forks | Open issues | Created | Source |
|---|---:|---:|---:|---|---|
| **OpenAmer** | **6** | 3 | 25 | 2026-08-16 | GitHub API openamer/openamer |
| AutoGPT | 187492 | 46002 | 563 | 2023-03-16 | GitHub API Significant-Gravitas/AutoGPT |
| Claude Code | 147624 | 24128 | 12210 | 2025-02-22 | GitHub API anthropics/claude-code |
| OpenAI Codex CLI | 125948 | 19597 | 18271 | 2025-04-13 | GitHub API openai/codex |
| OpenHands | 88846 | 11686 | 882 | 2024-03-13 | GitHub API All-Hands-AI/OpenHands |
| CrewAI | 58914 | 8543 | 446 | 2023-10-27 | GitHub API crewAIInc/crewAI |
| Aider | 49117 | 4984 | 1883 | 2023-05-09 | GitHub API Aider-AI/aider |
| LangGraph | 42142 | 7123 | 810 | 2023-08-09 | GitHub API langchain-ai/langgraph |

## Capability (ours - grep-verified)

| Metric | Value | Source | Limit |
|---|---:|---|---|
| registered_tool_names | 62 | grep '"name": "' in tools/*.py + toolsets.py | grep count, not a runtime registry dump |
| tool_modules | 118 | ls tools/*.py | - |
| skills | 877 | find skills -name SKILL.md | - |
| cron_jobs | 101/104 active | cron/jobs.json | enabled flag, not last-run health |
| episodes | 3064 | memory/longterm_episodes.jsonl | line count, not unique facts |

## Learning system (measured, last 24h)

- Learner cycles: **240**, rejected: **145** -> yield **39.6%** (source: internet_learn_log.jsonl)
- Own micro-benchmark: best **0.704**, last run **0.0** (23 questions, 23 errored). NOT a standard benchmark.

## What this does NOT prove

- SWE-bench Verified score for OpenAmer: we are NOT on the leaderboard (checked 2026-09-22).
- Any head-to-head task comparison: no competitor harness is installed here (codex/claude/opencode/aider/openhands/autogpt all absent from PATH).
- Cost per task, latency, autonomy rate vs. competitors: no shared harness -> unmeasured.
- Our own benchmark uses 23 self-written questions, not a standard suite -> not comparable to any published number.
