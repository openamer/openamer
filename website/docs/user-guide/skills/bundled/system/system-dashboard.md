---
title: "Dashboard — Use for the Live-Web-Dashboard on port 8899"
sidebar_label: "Dashboard"
description: "Use for the Live-Web-Dashboard on port 8899"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Dashboard

Use for the Live-Web-Dashboard on port 8899.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/system\dashboard` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Dashboard (Port 8899)

## Übersicht
Live-Web-Dashboard auf `http://127.0.0.1:8899/` mit 4 Panels:
1. **Cron-Status** — Jobs, Status, nächster/letzter Lauf
2. **System-Health** — RAM, Disk, Temp, Top-Prozesse
3. **Security-Status** — CVEs, betroffene Pakete, Scans
4. **Skill-Graph** — Visualisierung des Skill-Netzwerks (Canvas)

## Starten
```bash
cd "$OPENAMER_HOME"
python3 scripts/dashboard-server.py
```

## Watchdog (alle 15 Minuten)
Ein Cron-Job "Dashboard Watchdog" prüft den Server alle 15min und startet ihn neu falls abgestürzt.

Manuelle Prüfung:
```bash
python3 scripts/dashboard-watchdog.py
```

## API-Endpunkte
- `GET /` — Dashboard HTML
- `GET /api/all` — Alle Daten als JSON (1 Aufruf)
- `GET /api/cron` — Cron-Status
- `GET /api/health` — System-Health (perf-optimizer)
- `GET /api/security` — CVE-Status
- `GET /api/graph` — Skill-Graph (max 200 Nodes)

## Datenquellen
- **Cron**: cron/jobs.json, cron/executions.db
- **Health**: scripts/perf-optimizer.py
- **Security**: .security-cve/state.json, .security-cve/last-report.json
- **Graph**: skill-graph.json (generiert von skill-knowledge-graph.py --json)

## Troubleshooting
- Port 8899 belegt: `netstat -ano | grep 8899` → PID finden → ggf. taskkill
- Keine RAM-Daten: perf-optimizer liefert auf Windows total_mb=0, Dashboard zeigt Fallback (Top-Prozess-Summe)
- Graph leer: `python3 scripts/skill-knowledge-graph.py --json` ausführen
