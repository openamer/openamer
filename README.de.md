# OpenAmer Agent

**OpenAmer ist der Agent, der nicht kaputtgeht — und der sich nachweislich mit der Nutzung verbessert.**

Er läuft auf deiner eigenen Maschine, trifft dich in den Kanälen, die du bereits nutzt, und wird mit der Zeit besser. Zwei Dinge heben ihn ab:

1. **Er geht nicht kaputt.** Das Selbst-Update ist gegen die Fehlerquellen gehärtet, die andere Agenten halb installiert zurücklassen — Datei-Sperren, unterbrochene Installationen, veraltete Recovery-Marker. Der Agent verifiziert, bevor er etwas behauptet, und meldet echte Fehler statt Ergebnisse zu erfinden.
2. **Er verbessert sich nachweislich mit der Nutzung.** Erinnerungen bleiben über Sitzungen hinweg erhalten, Fähigkeiten werden aus schwierigen Aufgaben destilliert und bei Wiederverwendung verfeinert, und der A2A-Schwarm teilt kuratiertes, signiertes, leckfreies Wissen zwischen Knoten. Lernen, das du beobachten kannst — kein Marketing-Versprechen.

Nutze jedes beliebige Modell — OpenRouter, OpenAI, deinen eigenen Endpunkt und [viele weitere](https://github.com/openamer/openamer/blob/main/website/docs/integrations/providers). Wechsle mit `openamer model` — ohne Codeänderungen, ohne Bindung.

## Funktionen

| Funktion | Beschreibung |
|---|---|
| **Geht nicht kaputt** | Gehärtetes Selbst-Update, das Datei-Sperren, unterbrochene Installationen und veraltete Recovery-Marker übersteht. Der Agent verifiziert, bevor er etwas behauptet, und meldet echte Fehler statt Ergebnisse zu erfinden. |
| **Verbessert sich nachweislich** | Erinnerungen bleiben über Sitzungen erhalten, Fähigkeiten werden aus schwierigen Aufgaben destilliert und bei Wiederverwendung verfeinert, und der A2A-Schwarm teilt kuratiertes, signiertes, leckfreies Wissen zwischen Knoten. |
| **Echte Terminal-Oberfläche** | Vollständiges TUI mit mehrzeiligem Bearbeiten, Slash-Command-Autovervollständigung, Gesprächsverlauf, Unterbrechen-und-Umleiten und Live-Streaming der Tool-Ausgabe. |
| **Lebt, wo du bist** | Telegram, Discord, Slack, WhatsApp, Signal und CLI — ein Gateway, ein Gespräch, das dir über jeden Kanal folgt. Sprachnachrichten werden automatisch transkribiert. |
| **Geplante Automatisierungen** | Eingebauter Cron-Scheduler mit Zustellung an jede Plattform. Beschreibe einen Tagesbericht, ein nächtliches Backup oder ein wöchentliches Audit in einfacher Sprache — es läuft unbeaufsichtigt. |
| **Delegiert und parallelisiert** | Starte isolierte Subagenten für parallele Arbeitsströme oder schreibe Python-Skripte, die Tools über RPC aufrufen, um mehrstufige Pipelines in einen einzigen Turn zu verdichten. |
| **Läuft überall, nicht nur auf deinem Laptop** | Sechs Terminal-Backends — lokal, Docker, SSH, Singularity, Modal und Daytona. Daytona und Modal bieten Serverless-Persistenz, sodass die Umgebung deines Agenten im Leerlauf ruht und bei Bedarf aufwacht — fast ohne Kosten zwischen den Sitzungen. |
| **Privat per Standard** | Telefonnummern, Passwörter, E-Mails und Kartennummern werden vor dem Speichern redigiert. Betriebssystem, Hardware und Modell deines Knotens bleiben in deinem eigenen System-Prompt. |
| **Forschungsbereit** | Batch-Trajektoriengenerierung und Trajektorienkompression für das Training der nächsten Generation von Tool-aufrufenden Modellen. |

## Schnellinstallation

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

### Windows (nativ, PowerShell)

```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Der Installer erledigt alles: uv, Python 3.11, Node.js, ripgrep, ffmpeg und ein portables Git Bash.

## Einstieg

```bash
openamer              # Interaktive CLI — ein Gespräch starten
openamer model        # LLM-Anbieter und Modell wählen
openamer tools        # Konfigurieren, welche Tools aktiviert sind
openamer gateway      # Messaging-Gateway starten (Telegram, Discord, …)
openamer setup        # Vollständigen Setup-Assistenten ausführen
openamer update       # Auf die neueste Version aktualisieren
openamer doctor       # Probleme diagnostizieren
```

## Aktualisierung

OpenAmer hält sich automatisch aktuell. Beim Start prüft es im Hintergrund, ob eine neuere Version verfügbar ist — falls ja, zeigt das Willkommensbanner `⚠ N Commits zurück — 'openamer update' ausführen` direkt im Chat an.

```bash
openamer update
```

## Dokumentation

Die vollständige Dokumentation findest du unter **[OpenAmer Docs](https://github.com/openamer/openamer/blob/main/website/docs/)**.

## Community

- 💬 [Discord](https://discord.gg/openamer)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/openamer/openamer/issues)

## Lizenz

Apache License 2.0 — siehe [LICENSE](LICENSE).
