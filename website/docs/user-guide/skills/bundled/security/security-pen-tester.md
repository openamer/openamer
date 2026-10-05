---
title: "Pen Tester — Port-scan, deps, permissions, network, password hygiene"
sidebar_label: "Pen Tester"
description: "Port-scan, deps, permissions, network, password hygiene"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Pen Tester

Port-scan, deps, permissions, network, password hygiene.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/security\pen-tester` |
| Version | `1.0.0` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# pen-tester — Automatisierter Security-Audit

Führt vollständigen Security-Audit durch: Port-Scan, Dependency-Audit, File-Permissions, Network-Exposure, Password-Hygiene. Erzeugt HTML + JSON Reports mit CVSS-ähnlichem Scoring.

## CLI

```bash
# Quick-Modus (Port + Permissions) — ideal für Cron alle 4h
python scripts/pen-tester.py --quick

# Full-Modus (alle Checks)
python scripts/pen-tester.py --full

# Mit Report-Speicherung
python scripts/pen-tester.py --full --report reports/

# Nur Console (keine Dateien)
python scripts/pen-tester.py --quick --stdout
```

## Exit-Codes

| Code | Bedeutung |
|------|-----------|
| 0 | Sicher / keine Funde |
| 1 | Warnungen (low/medium) |
| 2 | Kritisch (high/critical) |

## Checks

1. **Port-Scan** — 30+ Common Ports (22,80,443,3306,5432,6379,27017,…) auf localhost + LAN-IP. Threaded parallel (50 Worker), ~4s.
2. **Dependency-Audit** — `pip-audit` (falls installiert) sonst `pip list --outdated`. Erkennt CVEs.
3. **File-Permissions** — `.env`, `config.yaml`, `.backup_key` auf korrekte Berechtigungen. Windows: Everyone/Users. Unix: group/other Bits.
4. **Network-Exposure** — `netstat -ano` auf 0.0.0.0/[::]-Bindungen. Warnt bei externer Erreichbarkeit.
5. **Password-Hygiene** — Scannt Configs auf Standard-Passwörter (admin, password, 123456, your-api-key) + API-Key-Zählung.

## Reports

- **HTML**: Dark-Theme mit Risk-Score-Ring, Summary-Cards, Findings-Tabelle.
- **JSON**: Maschinenlesbar mit CVSS-Scoring und Severity-Zählung.

## Pfad

Script: `$OPENAMER_HOME/scripts/pen-tester.py` (Default: `~/AppData/Local/openamer-laptop/scripts/`)
