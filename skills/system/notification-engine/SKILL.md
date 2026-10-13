---
name: notification-engine
description: "'Use for alerting: desktop, sound, log, webhook, daemon.'"
version: 1.0.0
author: OpenAmer
tags: [notification, alert, alarm, desktop, sound, webhook, daemon, cron]
---

# Notification Engine — Multi-Channel Alerting

Use this skill when you need to send alerts, configure the notification engine,
start/stop the daemon, or check alert history.

## Files

- **Script:** `scripts/notification-engine.py` im OpenAmer-Repo
- **Config:** `~/.notification-engine/config.json`
- **Incoming:** `~/.notification-engine/incoming/` (JSON-Alarm-Dateien)
- **Log:** `~/.notification-engine/logs/engine.log`
- **History:** `~/.notification-engine/history/history.json`

## CLI Usage

```bash
# Sofort eine Benachrichtigung senden
python scripts/notification-engine.py --send "Backup abgeschlossen"
python scripts/notification-engine.py --send "Kritischer Fehler" --priority critical --channel sound
python scripts/notification-engine.py --send "Warnung" --priority warning --channel desktop --channel logfile

# Daemon starten (überwacht incoming/ alle 30s)
python scripts/notification-engine.py --daemon

# Daemon mit eigenem Intervall
python scripts/notification-engine.py --daemon --interval 10

# History anzeigen
python scripts/notification-engine.py --history

# Status anzeigen
python scripts/notification-engine.py --status

# Incoming-Datei anlegen (für andere Skripte)
python scripts/notification-engine.py --send-incoming "Nachricht"

# Alle wartenden Incoming-Dateien verarbeiten
python scripts/notification-engine.py --process-incoming

# Cooldown ignorieren
python scripts/notification-engine.py --send "Dringend!" --force
```

## Priority-Level

| Level    | Desktop | Sound | Logfile | Webhook |
|----------|---------|-------|---------|---------|
| info     | ✓       | —     | ✓       | —       |
| warning  | ✓       | —     | ✓       | ✓       |
| critical | ✓       | ✓     | ✓       | ✓       |

(Sound nur bei critical, es sei denn die Config wird angepasst)

## Channels

- **desktop:** Windows Toast-Notification via PowerShell Burst
- **sound:** PowerShell Console.Beep (Frequenz abhängig von Priority)
- **logfile:** Text-Log in `~/.notification-engine/logs/engine.log`
- **webhook:** HTTP-POST (Generic JSON) — muss in Config aktiviert werden

## Config (`~/.notification-engine/config.json`)

```json
{
  "channels": {
    "desktop": { "enabled": true, "min_priority": "info" },
    "sound":   { "enabled": true, "min_priority": "critical" },
    "logfile": { "enabled": true, "min_priority": "info" },
    "webhook": { "enabled": false, "min_priority": "warning", "url": null }
  },
  "cooldown_minutes": 60,
  "history_max": 50,
  "webhook_default_url": null
}
```

## Cooldown

Identische Nachrichten werden nicht öfter als alle `cooldown_minutes` (Default 60)
gesendet. Mit `--force` kann der Cooldown umgangen werden.

## Incoming-Datei-Format (für andere Skripte)

Andere Skripte legen einfach eine JSON-Datei in `~/.notification-engine/incoming/` ab:

```json
{
  "message": "Deine Nachricht",
  "priority": "critical",
  "channels": ["desktop", "sound"],
  "force": false
}
```

Der Daemon oder `--process-incoming` verarbeitet sie dann automatisch.

## Cron-Job

Der Notification-Daemon läuft als Cron-Job (`notification-engine-daemon`)
alle 1 Minute. Er startet den Daemon, falls er nicht läuft, oder lässt ihn
laufen.

## Integration in andere Skripte

```python
# Direkt in einem anderen Skript:
import subprocess
subprocess.run(["python", "scripts/notification-engine.py",
    "--send", "Backup fehlgeschlagen!", "--priority", "critical"])
```

Oder:

```python
# Incoming-Datei anlegen:
from pathlib import Path
import json
(Path.home() / ".notification-engine/incoming/alert.json").write_text(
    json.dumps({"message": "Test", "priority": "info"}), encoding="utf-8")
```