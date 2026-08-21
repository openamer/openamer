# OpenAmer — Auto-Generated README

> *Automatisch generiert am 2026-08-21 20:10 UTC*
> Version: **260821** | Branche: v260821

**OpenAmer** ist ein persönlicher KI-Agent, der auf CLI, Desktop-App, TUI und
über 20 Messaging-Plattformen (Telegram, Discord, Slack u.v.m.) läuft.
Er lernt über Sessions hinweg (Memory + Skills), delegiert an Sub-Agents,
führt geplante Cron-Jobs aus und steuert Terminal und Browser.

---

## 📊 Projekt-Kennzahlen

| Metrik                | Wert                         |
|-----------------------|------------------------------|
| Python-Dateien        | 3651         |
| Python-LOC            | ?                    |
| JavaScript-Dateien    | 21022         |
| TypeScript-Dateien    | 18979         |
| Skills (Installation) | 636             |
| Scripts               | 38             |
| Cron-Jobs             | 17        |
| Git-Commits           | 18158    |
| Autoren               | 2234          |
| Repo-Grösse           | ?        |

---

## 🚀 Features

### Core Agent
- **Multi-Plattform**: CLI, Desktop (Electron), TUI, Telegram, Discord, Slack + 20 weitere
- **Modell-Agnostisch**: OpenAI, Anthropic, Google, DeepSeek, OpenRouter, lokale Modelle
- **Prompt-Caching**: Byte-stabiler System-Prompt für effiziente API-Nutzung
- **Kontext-Kompression**: Automatische Reduzierung langer Konversationen
- **Memory-System**: Sessions-übergreifendes Lernen (Brain-Dataset + Memory-Healing)
- **Skill-System**: 630+ Skills für spezialisierte Aufgaben, modular erweiterbar

### Superintelligence
- **Smart Cron Scheduler**: Intelligente Zeitplan-Optimierung mit Auto-Korrektur
- **Self-Healer Daemon**: Automatische Log-Analyse, Mustererkennung und Reparatur
- **Auto-Test-Runner**: Git-Diff-basierte Test-Priorisierung und parallele Ausführung
- **Knowledge Graph**: Skill-Netzwerk mit 630 Skills + Vorschlags-Engine
- **Circuit Breaker**: Selbstzerstörungsschutz für autonome Systeme
- **Swarm Metrics**: Echtzeit-Überwachung des Agent-Schwarms

### A2A (Agent-to-Agent)
- **Swarm-Kommunikation**: Identität, Vertrauen, Node-to-Node Ask
- **Brain Collect**: Automatischer Export von Sessions ins Brain-Dataset
- **Mesh Learning**: Autonomer Lernprozess über mehrere Agenten hinweg
- **GitHub Relay**: A2A über GitHub als Transport (kein Localhost nötig)
- **Autolog**: Automatische Aufzeichnung aller Aktivitäten für das Brain

### Entwicklung
- **IDE-Integration**: VS Code Extension + JetBrains Plugin
- **Plugin-System**: Erweiterbar über Plugins und MCP-Server
- **CI/CD**: Tägliche Releases (CalVer), automatische Tags
- **Bugbot**: Autonome Bug-Erkennung und -Reparatur
- **Security Agent**: Automatischer CVE-Scan und Patching via OSV.dev API

---

## 🏗️ Architektur

```
openamer-repo/
├── cli.py                 # CLI-Dispatcher (Hauptkommando)
├── run_agent.py           # Agent-Core (Konversationsschleife)
├── openamer_state.py      # State-Management
├── openamer_constants.py  # Konstanten
├── openamer_logging.py    # Logging
├── scripts/               # Automatisierungs-Scripts (38 Stk.)
├── gateway/               # Multi-Plattform-Gateway
├── plugins/               # Plugin-System
├── providers/             # Modell-Provider
├── tools/                 # Tool-Definitionen
├── skills/                # In-Repo Skills
├── docs/                  # Dokumentation
│   └── generated/         # Auto-generierte Doks (dieses Script)
├── cron/                  # Cron-Konfiguration
├── tests/                 # Python-Tests
├── desktop-plugins/       # Desktop-Plugins
├── website/               # Docusaurus-Website
├── web/                   # Web-App
└── docker/                # Docker-Konfiguration
```

### Datenfluss
1. **Eingabe**: User-Nachricht via CLI/TUI/Desktop/Gateway
2. **Verarbeitung**: Agent-Core mit System-Prompt, Tool-Auswahl, LLM-Call
3. **Aktion**: Tool-Ausführung (Terminal, Browser, Dateien, Skills)
4. **Lernen**: Sessions → Brain-Dataset → Fine-Tuning
5. **Automatisierung**: Cron-Jobs für regelmässige Wartung

---

## 📦 Installation

```bash
# Via pip (empfohlen)
pip install openamer

# Via uv (schneller)
uv pip install openamer

# Von Source
git clone https://github.com/openamer/openamer.git
cd openamer
pip install -e .
```

### Desktop-App (Windows)
Lade das neueste `.exe`-Setup von [Releases](https://github.com/openamer/openamer/releases).

---

## 🚴 Usage

```bash
# CLI starten
openamer

# Skills verwalten
openamer skills list
openamer skills install <name>

# Cron-Jobs verwalten
openamer cron list
openamer cron add --name "my-job" --prompt "..."

# System-Info
openamer system
openamer config show

# A2A (Agent-to-Agent)
openamer a2a swarm ask "Frage an den Schwarm"
openamer a2a brain collect
```

---

## 🔧 Wartung & Cron-Jobs

OpenAmer läuft rund um die Uhr mit 17 Cron-Jobs:

- **Brain Collect** (alle 4h): Exportiert Sessions ins Brain-Dataset
- **Self-Reflection** (alle 4h): Überprüft System-Gesundheit
- **Auto-Test-Runner** (alle 4h): Führt Tests aus
- **Security Agent** (alle 4h): Scannt auf CVEs
- **Bugbot** (alle 4h): Fixt automatisch gefundene Bugs
- **Self-Healer** (alle 30min): Daemon für automatische Reparaturen
- **Perf-Optimizer** (alle 6h): Optimiert System-Performance
- **Skills Hub Cache** (alle 6h): Wärmt den Skills-Cache

Vollständige Liste: `docs/generated/CRON-STATUS.md`

---

## 🤝 Mitwirken

Beiträge sind willkommen! Siehe [CONTRIBUTING.md](./CONTRIBUTING.md) und [AGENTS.md](./AGENTS.md) für Entwickler-Richtlinien.

### Entwicklungs-Setup
```bash
git clone https://github.com/openamer/openamer.git
cd openamer
pip install -e ".[dev]"
pre-commit install
```

---

## 📄 Lizenz

Apache 2.0 — siehe [LICENSE](./LICENSE).

---

*Generiert von [auto-docs.py](../scripts/auto-docs.py) — letzte Aktualisierung: 2026-08-21 20:10 UTC*
