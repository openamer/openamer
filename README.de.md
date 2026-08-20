# OpenAmer Agent — der eine Agent, der alle beherrscht

**OpenAmer ist der Agent, der nicht kaputtgeht — und der sich nachweislich mit der Nutzung verbessert.**

Er läuft auf deiner eigenen Maschine, trifft dich in den Kanälen, die du bereits nutzt, und wird mit der Zeit besser. OpenAmer ist ein gehärteter, unabhängig entwickelter Fork der [Hermes Agent](https://github.com/NousResearch/hermes-agent)-Architektur (MIT, von Nous Research). Wir sagen das offen: OpenAmer versteckt seine Herkunft nicht. Was wir darauf aufbauen — Robustheit, Verifizierbarkeit und eine echte Lernschleife — ist unser Eigenes.

---

## 🔥 Was OpenAmer EINZIGARTIG macht

**15 Dinge, die kein anderer Agent kann** — ausgeliefert, getestet, verifiziert.

| # | Superkraft | Was es bedeutet | Wer hat es sonst? |
|---|---|---|---|
| 🖥️ | **Background Computer-Use** | Steuere deinen Desktop ohne Fokus-Klau. Aufnehmen und abspielen. | ❌ Niemand |
| 🌐 | **A2A Agentenschwarm** | Jede Installation ist ein Peer-to-Peer-Knoten. Frage das Netzwerk. | ❌ Niemand |
| 🧠 | **Brain Learning Loop** | Automatische Trainingsdatensammlung. Statistiken und Wachstumsgrafiken. | ❌ Niemand |
| 🪟 | **Windows-Nativ** | Volle native Windows-Unterstützung. Kein WSL nötig. | ❌ Niemand |
| 🛠️ | **99 Tools + 117 Skills** | Größte Bibliothek im Agenten-Bereich. | ❌ Niemand |
| 👥 | **Multi-Agenten-Crews** | Rollenbasierte Teams (Rechercheur, Schreiber, Analyst). | ❌ Nur CrewAI |
| 🏪 | **Agenten-Marktplatz** | Suche, installiere, veröffentliche Community-Agenten. | ❌ Niemand |
| 💾 | **Durable Execution** | Checkpoint/Resume überlebt Abstürze. | ❌ Nur LangGraph |
| 🤖 | **Visueller Agent-Builder** | `openamer agent create` aus NL-Beschreibung + Web UI. | ❌ Nur AutoGPT |
| 📊 | **Observability/Tracing** | Schritt-für-Schritt-Agenten-Ausführungsbrowser. | ❌ Niemand |
| 🧩 | **Selbstverbessernde Skills** | Skills, die sich bei Nutzung verbessern. | ❌ Niemand |
| 📋 | **Profilsystem** | Lernt deine Muster und Präferenzen. | ❌ Niemand |
| 🧠 | **Mesh Learning** | Netzwerkweiter Wissensaustausch. | ❌ Niemand |
| 🎯 | **Superintelligenz-Dashboard** | Systemweiter Gesundheits-Score (0-100). | ❌ Niemand |
| 🛡️ | **Human-in-the-Loop** | Riskante Aktionen genehmigen. Auto-Ablehnung bei Timeout. | ❌ Nur Enterprise |

---

## Was du bekommst, wenn du OpenAmer installierst

Ein Befehl von GitHub gibt dir einen **kompletten, eigenständigen, privaten AI-Agenten** — installiert und lauffähig auf deiner eigenen Maschine:

| Was du bekommst | Standard |
|---|---|
| **Desktop-App** | vom Installer gebaut (native Chat, Terminal, Einstellungen) |
| **117 gebündelte Skills** (apple, github, mlops, kreativ, Programmierung…) | automatisch gesät |
| **99 Tools** — Internet, Vision, Sprache, Terminal, Browser, Dateien, Code, Sub-Agenten | inklusive |
| **Computer-Use (Background)** — steuere Windows/macOS/Linux-Desktop | inklusive |
| **Computer-Use Record/Play** — nimm Desktop-Aktionen auf, spiele sie ab, cron-plane sie | inklusive |
| **A2A Schwarm** — jede Installation ist ein Agenten-Knoten (GitHub Relay) | inklusive |
| **A2A Peer Query** — stelle Fragen quer durch den Schwarm | inklusive |
| **Brain Learning Loop** — automatische Trainingsdatensammlung | **automatisch** |
| **Multi-Agenten-Crews** — rollenbasierte Teams (Rechercheur, Schreiber, Analyst…) | inklusive |
| **Agenten-Marktplatz** — suche, installiere, veröffentliche Community-Agenten | inklusive |
| **Durable Execution** — Checkpoint/Resume überlebt Abstürze | inklusive |
| **Visueller Agent-Builder** — `openamer agent create` aus Beschreibung | inklusive |
| **Agenten-Schwarm** — parallele, hierarchische, Debatten-Strategien | inklusive |
| **Superintelligenz-Dashboard** — System-Gesundheits-Score 0-100 | inklusive |
| **Selbstverbessernde Skills** — Skills verbessern sich bei Nutzung | inklusive |
| **A2A Mesh Learning** — netzwerkweiter Wissensaustausch | inklusive |
| **Observability/Tracing** — Agenten-Ausführungsbrowser | inklusive |
| **Profilsystem** — lernt deine Muster und Präferenzen | inklusive |
| **Human-in-the-Loop** — riskante Aktionen genehmigen | Konfigurationsoption |
| **Docker Sandbox** — sichere containerisierte Ausführung | Konfigurationsoption |
| **Autonomes Lernen** | der Agent destilliert Lektionen aus eigenen Durchläufen |
| **Privatsphäre by default** | Telefon/Passwort/E-Mail/Karte werden vor Speicherung redigiert |

### Probiere es gleich aus
```bash
openamer                      # Chat starten
openamer system               # Was läuft auf diesem Knoten?
openamer computer-use record mein-task   # Desktop-Aktionen aufnehmen
openamer computer-use play mein-task     # Aufnahme abspielen
openamer a2a status           # A2A-Identität & Mesh
openamer a2a query "Frage"    # Den A2A-Schwarm fragen
openamer brain stats          # Lernschleifen-Statistiken
openamer brain graph          # Hirnwachstum anzeigen
openamer agent create "Sende täglichen Bericht"  # NL-Agent-Builder
openamer agent ui             # Visueller Agent-Builder Web UI
openamer crew create mein-team --members researcher,writer  # Crew
openamer crew run mein-team "Erforsche KI-Trends"
openamer swarm run "Aufgabe" --agents 3 --strategy debate
openamer trace list           # Agenten-Ablaufverfolgung
openamer super status         # Superintelligenz-Status
```

---

## 🆚 OpenAmer vs. die Konkurrenz

| Feature | **OpenAmer** | Claude Code | Codex CLI | AutoGPT | CrewAI | LangGraph | OpenAI Agents |
|---|---|---|---|---|---|---|---|
| **Computer-Use (Background)** | ✅ **EINZIG** | ⚠️ Preview | ❌ | ❌ | ❌ | ❌ | ❌ |
| **A2A Agentenschwarm** | ✅ **EINZIG** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Brain Learning Loop** | ✅ **EINZIG** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Windows-Nativ** | ✅ **EINZIG** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **99+ Tools / 117 Skills** | ✅ **GRÖSSTE** | ⚠️ Begrenzt | ❌ | ⚠️ Plugin | ❌ | ❌ | ❌ |
| **Multi-Agenten-Crews** | ✅ **EINGEBAUT** | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| **Agenten-Marktplatz** | ✅ **EINGEBAUT** | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Durable Execution** | ✅ **EINGEBAUT** | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Visueller Agent-Builder** | ✅ **EINGEBAUT** | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Observability/Tracing** | ✅ **EINGEBAUT** | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Selbstverbessernde Skills** | ✅ **EINZIG** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Human-in-the-Loop** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Sandbox-Ausführung** | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ |
| **VS Code Erweiterung** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Agentenschwarm (Debatte)** | ✅ **EINZIG** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Superintelligenz-Dashboard** | ✅ **EINZIG** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Mesh Learning Netzwerk** | ✅ **EINZIG** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Computer-Use Record/Play** | ✅ **EINZIG** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Plattformübergreifendes Gateway** | ✅ 11+ Kanäle | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Anbieter-unabhängig** | ✅ 99+ Modelle | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Cron + Delegation** | ✅ Eingebaut | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Selbst-Modifikation mit Test-Gate** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## Schnellinstallation

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

### Windows (nativ, PowerShell)

```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Nach der Installation:

```bash
source ~/.bashrc
openamer  # Chat starten!
```

---

## Dokumentation & Community

- 📚 [Dokumentation](https://github.com/openamer/openamer/blob/main/website/docs/)
- 💬 [Discord](https://discord.gg/openamer)
- 🐛 [Issues](https://github.com/openamer/openamer/issues)

---

## Lizenz

Apache License 2.0 — siehe [LICENSE](LICENSE).

OpenAmer Agent.