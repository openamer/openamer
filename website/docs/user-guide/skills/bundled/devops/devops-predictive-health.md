---
title: "Predictive Health — Use for health trend, anomaly, disk forecast"
sidebar_label: "Predictive Health"
description: "Use for health trend, anomaly, disk forecast"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Predictive Health

Use for health trend, anomaly, disk forecast

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/devops\predictive-health` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Predictive Health Monitor

ML-basierte System-Health-Überwachung mit Trend-Analyse, Anomalie-Detektion, Disk-Volllauf-Prognose und Daemon-Modus.

## Script

`scripts/predictive-health.py` — keine externen Dependencies (nur Python-Standardbibliothek).

## CLI-Modi

| Argument | Beschreibung |
|----------|-------------|
| `--collect` | Sammelt Systemmetriken (RAM, Disk, CPU, Cron-Exit-Codes) und hängt an history.csv an |
| `--predict` | Führt Trend-Analyse + Anomalie-Detektion + Disk-Prognose aus (menschenlesbar) |
| `--report` | JSON-Report auf stdout (maschinenlesbar) |
| `--watch [min]` | Daemon-Modus, alle N Minuten sammeln + analysieren (Default: 5) |
| `--daemon` | Alias für --watch |

## Exit-Codes

| Code | Bedeutung |
|------|-----------|
| 0 | Alles gut |
| 1 | Trend steigend |
| 2 | Anomalie erkannt (>2σ) |
| 3 | Disk-Volllauf &lt; 30 Tage |

## Daten

- Historie: `~/.openamer/.predictive-health/history.csv` (max 10.000 Zeilen)
- Report: `~/.openamer/.predictive-health/latest_report.json`
- PID: `~/.openamer/.predictive-health/predictive-health.pid`

## Cron-Jobs

| Job | Rhythmus | Beschreibung |
|-----|----------|-------------|
| `predictive-health-collect` | alle 30min | Metriken sammeln (--no-agent) |
| `predictive-health-predict` | alle 6h | Trend-Analyse + Report (--no-agent) |

## Verwendung

```bash
# Einmalig sammeln
python scripts/predictive-health.py --collect

# Trend-Report anzeigen
python scripts/predictive-health.py --predict

# JSON-Report
python scripts/predictive-health.py --report

# Als Daemon (alle 5 Minuten)
python scripts/predictive-health.py --watch
```

## Architektur

- `collect_metrics()`: RAM, Disk, CPU via WMIC (Win), /proc/stat (Linux), psutil (Fallback)
- `linear_regression()`: y = slope*x + intercept mit R²
- `detect_anomalies()`: Gleitender Mittelwert (Fenster=20) + Z-Score > 2σ
- `predict_disk_full()`: Multi-Fenster-Analyse (24h/3d/7d), wählt bestes R²
- `daemon_loop()`: Loop mit Signal-Handling und PID-Datei
