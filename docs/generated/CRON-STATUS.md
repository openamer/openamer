# Cron-Status

> *Automatisch generiert am 2026-08-21 20:10 UTC*
> **17 Jobs** davon **17 aktiv**, **0 deaktiviert**
> Letzter Lauf: ✅ **6 OK** | ❌ **0 Fehler**

---

## Job-Übersicht

| Status | Name | Typ | Schedule | Letzter Lauf | Nächster Lauf | Ergebnis |
|--------|------|-----|----------|-------------|---------------|----------|
| ✅ | brain-collect | Agent (Prompt) | every 240m | 2026-08-21T21:42:53 | 2026-08-22T01:56:42 | ok |
| ✅ | self-reflection | Agent (Prompt) | every 240m | 2026-08-21T18:02:02 | 2026-08-22T01:56:44 | ok |
| ✅ | self-reflection-6h | Skill: `self-reflection-loop` | every 240m | 2026-08-21T16:20:25 | 2026-08-22T01:56:46 | ok |
| ✅ | auto-test-runner | Agent (Prompt) | every 240m | 2026-08-21T21:56:46 | 2026-08-22T01:56:49 | ok |
| ✅ | memory-healing | Agent (Prompt) | every 360m | 2026-08-21T21:48:59 | 2026-08-22T03:56:51 | ok |
| 🆕 | Auto-Import DeepSeek-Harness Skills | Skill: `auto-import-deepseek-harness` | 0 2 * * * | — | 2026-08-22T02:00:00 | 🆕 noch nie |
| 🆕 | Skills Hub Cache Warmer | Script: `skills/hub_cache_warmer.py` | every 360m | — | 2026-08-21T23:08:01 | 🆕 noch nie |
| 🆕 | Bugbot - Autonomous Bug Fixer | Script: `scripts/bugbot.py` | every 240m | — | 2026-08-21T22:53:40 | 🆕 noch nie |
| 🆕 | Security Agent - Vulnerability Scanner | Skill: `security-agent` | every 240m | — | 2026-08-22T01:56:53 | 🆕 noch nie |
| ✅ | Stealth Browser Server | Agent (Prompt) | every 15m | 2026-08-21T22:01:03 | 2026-08-21T22:16:03 | ok |
| 🆕 | PR Agent - Review & Approval Workflow | Skill: `github-pr-workflow` | every 240m | — | 2026-08-22T01:56:55 | 🆕 noch nie |
| 🆕 | KI-Performance-Optimizer | Skill: `perf-optimizer` | every 360m | — | 2026-08-22T03:56:57 | 🆕 noch nie |
| 🆕 | self-healer | Script: `scripts/self-healer.py` | every 60m | — | 2026-08-21T22:56:59 | 🆕 noch nie |
| 🆕 | skill-knowledge-graph | Script: `scripts/skill-knowledge-graph.py --build` | every 1440m | — | 2026-08-22T21:49:06 | 🆕 noch nie |
| 🆕 | Smart Cron Scheduler | Script: `scripts/smart-cron-scheduler.py` | every 360m | — | 2026-08-22T03:58:40 | 🆕 noch nie |
| 🆕 | Auto-Dokumentation | Script: `scripts/auto-docs.py --all` | every 1440m | — | 2026-08-22T20:07:49 | 🆕 noch nie |
| 🆕 | Dashboard Watchdog | Script: `scripts/dashboard-watchdog.py` | every 15m | — | 2026-08-21T20:24:11 | 🆕 noch nie |

## ⏱ Schedule-Übersicht

### Intervall-Jobs

- **Alle 15 min**: Stealth Browser Server, Dashboard Watchdog
- **Alle 60 min**: self-healer
- **Alle 240 min**: brain-collect, self-reflection, self-reflection-6h, auto-test-runner, Bugbot - Autonomous Bug Fixer, Security Agent - Vulnerability Scanner, PR Agent - Review & Approval Workflow
- **Alle 360 min**: memory-healing, Skills Hub Cache Warmer, KI-Performance-Optimizer, Smart Cron Scheduler
- **Alle 1440 min**: skill-knowledge-graph, Auto-Dokumentation

### Cron-Jobs

- `0 2 * * *` — Auto-Import DeepSeek-Harness Skills
