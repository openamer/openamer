---
name: commander
description: Use for OpenAmer central CLI Commander with 28 subcommands.
---

# Commander — Zentrale CLI-Steuerung

Der **Commander** (`scripts/commander.py`) ist das zentrale CLI-Interface für alle OpenAmer-Skripte (28 Subcommands).

## Verwendung

```bash
python scripts/commander.py <subcommand> [args...]
python scripts/commander.py --status         # Alle Subsysteme prüfen
python scripts/commander.py --all            # Alle --check/--status nacheinander
python scripts/commander.py --help <cmd>     # Detail-Hilfe
python scripts/commander.py --list           # Alle Subcommands auflisten
python scripts/commander.py --version        # Version
```

## Alle 28 Subcommands

| Subcommand | Alias | Skript | Beschreibung |
|---|---|---|---|
| `security` | sec, cve | security-cve-scan.py | CVE-Scan + Auto-Patching |
| `perf` | performance, optimize | perf-optimizer.py | RAM/Disk/Cron-Optimierung |
| `monitor` | resources | resource-monitor.py | Live-CPU/RAM/DISK/NET |
| `test` | tests, testing | auto-test-runner.py | Auto-Test-Runner |
| `heal` | healing, selfheal | self-healer.py | Self-Healing-Daemon |
| `graph` | skillgraph, knowledge | skill-knowledge-graph.py | 630+ Skills Knowledge Graph |
| `cron` | scheduler, jobs | smart-cron-scheduler.py | Cron-Job-Analyse |
| `crew` | agents | crew-manager.py | Multi-Agent-Crew |
| `dashboard` | dash, web | dashboard-server.py | Live-Web-Dashboard :8899 |
| `docs` | documentation, doc | auto-docs.py | Automatische Dokumentation |
| `sync` | profiles, crossprofile | cross-profile-sync.py | Profil-Sync |
| `voice` | speech, audio | voice-assistant.py | STT + TTS Sprachassistent |
| `health` | predict, predhealth | predictive-health.py | ML-Prädiktive Health-Analyse |
| `mesh` | cluster | agent-mesh.py | Master/Worker Agent-Mesh |
| `review` | codereview, audit | auto-code-review.py | Auto-Code-Review |
| `backup` | backups | auto-backup.py | Auto-Backup aller Daten |
| `resource` | resources, system | resource-monitor.py | System-Ressourcen-Monitor |
| `cache` | cleancache | smart-cache.py | Cache-Analyse + Cleanup |
| `abtest` | ab, experiment | ab-test-engine.py | A/B-Experimente |
| `logs` | log, analyze | log-analyzer.py | Log-Analyse + Pattern |
| `env` | environment, check | auto-env-checker.py | Umgebungs-Validierung |
| `traffic` | apikey, ratelimit | traffic-cop.py | API-Key-Health + Rotation |
| `sessions` | session, archive | smart-session-saver.py | Session-Archivierung |
| `updater` | update, upgrade | auto-updater.py | Auto-Updater Git/pip/Skills |
| `plugin` | plugins | plugin-manager.py | Plugin-Verwaltung |
| `bugbot` | bugs, issues | bugbot.py | Bug-Tracking + Triage |
| `pr_approval` | pr, approval | pr_approval.py | PR-Approval-Workflow |
| `security_agent` | secagent, secbot | security_agent.py | CVE-Daemon Security-Agent |

## Features

- **Farbige Ausgabe**: 256-Farben-ANSI, kompatibel mit Windows 10+
- **Tabellen**: Automatische Spaltenbreiten, Header, Trennlinien
- **Progress-Bar**: Farbe, Prozent, ETA, Dauer — für --status und --all
- **Alias-Auflösung**: Alle Subcommands haben kurze Aliase
- **Kategorie-Gruppierung**: 11 Kategorien für Übersicht
- **Exit-Codes**: 0=OK, 1=Warnung, 2=Fehler, 3=Kritisch

## Abhängigkeiten

Nur **Python-Standardbibliothek** (argparse, subprocess, json, pathlib, shutil, sys).
Keine externen Packages.

## Pfade

- `scripts/commander.py` im OpenAmer-Repo (source)
- `OPENAMER_HOME/scripts/commander.py` (runtime)

## Exit-Codes

| Exit | Bedeutung |
|------|-----------|
| 0 | Alles OK |
| 1 | Warnungen vorhanden |
| 2 | Fehler in Subsystemen |
| 130 | Abbruch durch Benutzer (Ctrl+C) |

## Hinweise

- `--status` prüft nur Subcommands mit definiertem `status_flag` (--check, --status, --once etc.)
- `--all` führt alle Status-prüfenden Subcommands nacheinander aus
- Bei Timeout (124) wird das Skript übersprungen
- Output wird auf 80 Zeilen gekürzt bei langen Ausgaben

## Pflege

Neue Subcommands hinzufügen: Eintrag in `SUBCMDS`-Dict mit `script`, `desc`, `aliases`, `color`, `icon`, `category` und optional `status_flag`.