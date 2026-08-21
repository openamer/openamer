#!/usr/bin/env python3
"""
Notification Engine v1.0 — Multi-Channel Alerting für OpenAmer
===============================================================
Empfängt Alarme von allen anderen Skripten via JSON-Datei und sendet
sie über konfigurierbare Kanäle (Desktop, Sound, Logfile, Webhook).

CLI:
  python notification-engine.py --send 'MESSAGE' --priority info --channel desktop
  python notification-engine.py --daemon              # Überwachung alle 30s
  python notification-engine.py --history              # Letzte 50 Benachrichtigungen
  python notification-engine.py --status               # Engine-Status anzeigen

Priority-Level: info, warning, critical
Cooldown: gleiche Nachricht max. alle 60 Minuten
"""

import argparse
import json
import os
import subprocess
import sys
import time
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── Pfade ────────────────────────────────────────────────────────────────────

HOME_DIR = Path.home()
ENGINE_DIR = HOME_DIR / ".notification-engine"
INCOMING_DIR = ENGINE_DIR / "incoming"
LOGS_DIR = ENGINE_DIR / "logs"
HISTORY_DIR = ENGINE_DIR / "history"
CONFIG_PATH = ENGINE_DIR / "config.json"
HISTORY_PATH = HISTORY_DIR / "history.json"
PID_FILE = ENGINE_DIR / "notification-engine.pid"
DEFAULT_LOG = LOGS_DIR / "engine.log"

# ─── Prioritäten ──────────────────────────────────────────────────────────────

PRIORITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
PRIORITY_LABELS = {
    "info": ("INFO", "[ℹ]", "information"),
    "warning": ("WARN", "[⚠]", "warning"),
    "critical": ("CRIT", "[🔴]", "error"),
}

# ─── Config ───────────────────────────────────────────────────────────────────

DEFAULT_CONFIG: Dict[str, Any] = {
    "channels": {
        "desktop": {"enabled": True, "min_priority": "info"},
        "sound": {"enabled": True, "min_priority": "critical"},
        "logfile": {"enabled": True, "min_priority": "info"},
        "webhook": {"enabled": False, "min_priority": "warning", "url": None},
    },
    "cooldown_minutes": 60,
    "history_max": 50,
    "webhook_default_url": None,
    "logfile_path": str(LOGS_DIR / "engine.log"),
    "history_path": str(HISTORY_PATH),
    "incoming_dir": str(INCOMING_DIR),
}


def load_config() -> Dict[str, Any]:
    """Lade Config, falle auf Defaults zurück."""
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            # Deep-Merge
            if "channels" in user_cfg:
                for ch in cfg["channels"]:
                    if ch in user_cfg["channels"]:
                        cfg["channels"][ch].update(user_cfg["channels"][ch])
            for key in ("cooldown_minutes", "history_max", "webhook_default_url",
                        "logfile_path", "history_path", "incoming_dir"):
                if key in user_cfg:
                    cfg[key] = user_cfg[key]
        except (json.JSONDecodeError, OSError) as e:
            log_message(f"Config-Fehler: {e}, verwende Defaults", "warning")
    cfg["logfile_path"] = str(Path(cfg["logfile_path"]).resolve())
    cfg["history_path"] = str(Path(cfg["history_path"]).resolve())
    cfg["incoming_dir"] = str(Path(cfg["incoming_dir"]).resolve())
    return cfg


def ensure_dirs():
    """Stelle sicher, dass alle benötigten Verzeichnisse existieren."""
    for d in (ENGINE_DIR, INCOMING_DIR, LOGS_DIR, HISTORY_DIR):
        d.mkdir(parents=True, exist_ok=True)


# ─── Logging ──────────────────────────────────────────────────────────────────

def log_message(message: str, priority: str = "info") -> None:
    """Schreibe eine Nachricht in die Logdatei."""
    cfg = load_config()
    log_path = Path(cfg["logfile_path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    label = PRIORITY_LABELS.get(priority, ("INFO", "[ℹ]", "information"))[1]
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{ts} {label} {message}\n")
    except OSError:
        pass


# ─── History ──────────────────────────────────────────────────────────────────

def load_history() -> List[Dict[str, Any]]:
    """Lade den Benachrichtigungsverlauf."""
    if HISTORY_PATH.exists():
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_history(history: List[Dict[str, Any]], max_entries: int = 50) -> None:
    """Speichere den Verlauf, begrenzt auf max_entries."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    trimmed = history[-max_entries:]
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, indent=2, ensure_ascii=False)
    except OSError as e:
        log_message(f"History-Schreibfehler: {e}", "warning")


def add_to_history(entry: Dict[str, Any]) -> None:
    """Füge einen Eintrag zur History hinzu und trimme."""
    history = load_history()
    history.append(entry)
    cfg = load_config()
    save_history(history, cfg.get("history_max", 50))


# ─── Cooldown ─────────────────────────────────────────────────────────────────

def is_on_cooldown(message: str, cooldown_minutes: int = 60) -> bool:
    """Prüfe, ob eine identische Nachricht im Cooldown ist."""
    if cooldown_minutes <= 0:
        return False
    history = load_history()
    now = datetime.now(timezone.utc)
    for entry in reversed(history):
        if entry.get("message", "").strip().lower() == message.strip().lower():
            try:
                sent_ts = datetime.fromisoformat(entry["sent_at"])
                if now - sent_ts < timedelta(minutes=cooldown_minutes):
                    return True
            except (ValueError, KeyError):
                continue
    return False


# ─── Kanal-Implementierungen ──────────────────────────────────────────────────

def send_desktop(message: str, priority: str = "info") -> bool:
    """Sende eine Desktop-Benachrichtigung via PowerShell Burst-Notification."""
    label = PRIORITY_LABELS.get(priority, ("INFO", "[ℹ]", "information"))
    title = f"OpenAmer {label[1]}"
    # PowerShell Burst-Notification: moderner Windows Toast
    ps_script = f"""
$title = '{title}'
$msg = @'
{message}
'@
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textNodes = $template.GetElementsByTagName('text')
$textNodes.Item(0).AppendChild($template.CreateTextNode($title)) > $null
$textNodes.Item(1).AppendChild($template.CreateTextNode($msg)) > $null
$toast = New-Object Windows.UI.Notifications.ToastNotification $template
try {{
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier().Show($toast)
}} catch {{}}
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        return result.returncode == 0
    except Exception as e:
        log_message(f"Desktop-Notification fehlgeschlagen: {e}", "warning")
        return False


def send_sound(priority: str = "info") -> bool:
    """Sende einen Sound-Alarm via PowerShell Beep."""
    if priority == "critical":
        freq, duration = 880, 500  # hoher Ton, länger
    elif priority == "warning":
        freq, duration = 660, 300
    else:
        freq, duration = 440, 200
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             f"[Console]::Beep({freq}, {duration})"],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        return True
    except Exception as e:
        log_message(f"Sound-Alarm fehlgeschlagen: {e}", "warning")
        return False


def send_logfile(message: str, priority: str = "info") -> bool:
    """Schreibe eine Nachricht in die Logdatei."""
    log_message(message, priority)
    return True


def send_webhook(message: str, priority: str = "info", url: Optional[str] = None) -> bool:
    """Sende einen HTTP-Webhook (Generic JSON POST)."""
    if not url:
        log_message("Keine Webhook-URL konfiguriert", "warning")
        return False
    import urllib.request
    import urllib.error
    payload = json.dumps({
        "source": "openamer-notification-engine",
        "priority": priority,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError) as e:
        log_message(f"Webhook-Fehler: {e}", "warning")
        return False


# ─── Senden einer Notification ────────────────────────────────────────────────

def send_notification(
    message: str,
    priority: str = "info",
    channels: Optional[List[str]] = None,
    force: bool = False
) -> Dict[str, bool]:
    """
    Sende eine Benachrichtigung über die angegebenen Kanäle.
    Gibt ein Dict zurück: {kanal: erfolg}
    """
    cfg = load_config()
    priority_val = PRIORITY_ORDER.get(priority, 0)

    if not channels:
        channels = list(cfg["channels"].keys())

    # Cooldown-Check (nur wenn nicht force)
    if not force:
        cd = cfg.get("cooldown_minutes", 60)
        if is_on_cooldown(message, cd):
            log_message(f"Cooldown aktiv für: {message[:60]}", "info")
            return {}

    results: Dict[str, bool] = {}
    channel_map = {
        "desktop": lambda: send_desktop(message, priority),
        "sound": lambda: send_sound(priority),
        "logfile": lambda: send_logfile(message, priority),
        "webhook": lambda: send_webhook(message, priority, cfg.get("webhook_default_url")),
    }

    for ch_name in channels:
        ch_name = ch_name.lower().strip()
        if ch_name not in cfg["channels"]:
            log_message(f"Unbekannter Kanal: {ch_name}", "warning")
            continue
        ch_cfg = cfg["channels"][ch_name]
        if not ch_cfg.get("enabled", True):
            continue
        # Min-Priority prüfen
        min_prio = PRIORITY_ORDER.get(ch_cfg.get("min_priority", "info"), 0)
        if priority_val < min_prio:
            continue

        sender = channel_map.get(ch_name)
        if sender:
            try:
                results[ch_name] = sender()
                if not results[ch_name]:
                    log_message(f"Kanal '{ch_name}' fehlgeschlagen", "warning")
            except Exception as e:
                log_message(f"Kanal '{ch_name}' Exception: {e}", "warning")
                results[ch_name] = False

    # History-Eintrag
    entry = {
        "message": message,
        "priority": priority,
        "channels": channels,
        "results": results,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    add_to_history(entry)

    return results


# ─── Incoming-Dateien verarbeiten ─────────────────────────────────────────────

def process_incoming() -> int:
    """Verarbeite alle JSON-Dateien im incoming/-Verzeichnis. Gibt Anzahl zurück."""
    if not INCOMING_DIR.exists():
        return 0
    count = 0
    for fpath in sorted(INCOMING_DIR.iterdir()):
        if not fpath.is_file() or fpath.suffix.lower() not in (".json",):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            msg = data.get("message", "")
            priority = data.get("priority", "info")
            channels = data.get("channels", None)
            force = data.get("force", False)
            if msg:
                send_notification(msg, priority, channels, force)
                count += 1
            fpath.unlink()  # Lösche verarbeitete Datei
        except (json.JSONDecodeError, OSError, ValueError) as e:
            log_message(f"Incoming-Fehler {fpath.name}: {e}", "warning")
            # Fehlerhafte Datei umbenennen statt löschen
            try:
                fpath.rename(fpath.with_suffix(".error"))
            except OSError:
                pass
    return count


def send_incoming(message: str, priority: str = "info",
                  channels: Optional[List[str]] = None, force: bool = False) -> str:
    """Lege eine JSON-Datei im incoming/-Verzeichnis ab (für andere Skripte)."""
    ensure_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    fname = f"alert_{ts}.json"
    fpath = INCOMING_DIR / fname
    data = {
        "message": message,
        "priority": priority,
        "channels": channels,
        "force": force,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    log_message(f"Incoming-Datei angelegt: {fname} ({priority}): {message[:60]}", "info")
    return str(fpath)


# ─── Daemon ───────────────────────────────────────────────────────────────────

class NotificationDaemon(threading.Thread):
    """Daemon-Thread, der alle 30s das incoming/-Verzeichnis überwacht."""

    def __init__(self, interval: int = 30):
        super().__init__(daemon=True, name="NotificationDaemon")
        self.interval = interval
        self.running = False

    def run(self):
        self.running = True
        log_message("Notification-Daemon gestartet (Intervall: {}s)".format(self.interval), "info")
        while self.running:
            try:
                count = process_incoming()
                if count > 0:
                    log_message(f"Daemon: {count} Alarm(e) verarbeitet", "info")
            except Exception as e:
                log_message(f"Daemon-Fehler: {e}", "warning")
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)

    def stop(self):
        self.running = False
        log_message("Notification-Daemon gestoppt", "info")


def run_daemon(interval: int = 30):
    """Starte den Daemon und warte auf SIGINT."""
    # PID schreiben
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass

    daemon = NotificationDaemon(interval)
    daemon.start()

    try:
        while daemon.is_alive():
            daemon.join(1)
    except KeyboardInterrupt:
        print("\nNotification-Daemon wird beendet...")
        daemon.stop()
        daemon.join(timeout=5)
    finally:
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except OSError:
                pass
        log_message("Notification-Daemon beendet", "info")


# ─── Status ───────────────────────────────────────────────────────────────────

def show_status():
    """Zeige den aktuellen Engine-Status an."""
    cfg = load_config()
    daemon_pid = None
    if PID_FILE.exists():
        try:
            daemon_pid = int(PID_FILE.read_text().strip())
        except (ValueError, OSError):
            pass

    print("╔══════════════════════════════════════════╗")
    print("║    Notification Engine — Status          ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║  Daemon PID:   {str(daemon_pid or '—').ljust(23)} ║")
    print(f"║  Incoming:     {str(INCOMING_DIR).ljust(23)} ║")
    print(f"║  Logfile:      {str(cfg['logfile_path']).ljust(23)} ║")
    print("╠══════════════════════════════════════════╣")
    print("║  Kanäle:                                 ║")
    for ch_name, ch_cfg in cfg["channels"].items():
        enabled = "✓" if ch_cfg["enabled"] else "✗"
        min_p = ch_cfg.get("min_priority", "info")
        url_str = ""
        if ch_name == "webhook" and ch_cfg.get("url"):
            url_str = f" → {ch_cfg['url']}"
        print(f"║    {enabled} {ch_name:10} min={min_p:8}{url_str:26} ║")
    print("╠══════════════════════════════════════════╣")
    # History-Stat
    history = load_history()
    print(f"║  Verlauf:      {len(history):4} Einträge                         ║")
    # Cooldown
    print(f"║  Cooldown:     alle {cfg.get('cooldown_minutes', 60):3} Min                        ║")
    print("╚══════════════════════════════════════════╝")


# ─── History ausgeben ─────────────────────────────────────────────────────────

def show_history(limit: int = 50):
    """Zeige die letzten Benachrichtigungen an."""
    history = load_history()
    if not history:
        print("Keine Benachrichtigungen im Verlauf.")
        return
    print(f"Letzte {min(limit, len(history))} Benachrichtigungen:")
    print("-" * 80)
    for entry in reversed(history[-limit:]):
        ts = entry.get("sent_at", "?")
        prio = entry.get("priority", "?")
        msg = entry.get("message", "?")
        chans = ", ".join(entry.get("channels", []))
        results = entry.get("results", {})
        ok = all(results.values()) if results else "?"
        status = "✓" if ok else "✗" if ok is False else "?"
        print(f"  {status} {ts[:19]} [{prio:8}] {msg[:60]}")
        if chans:
            print(f"    → {chans}")
    print("-" * 80)


# ─── CLI-Integration (für andere Skripte) ─────────────────────────────────────

def send_alert_from_script(message: str, priority: str = "info",
                           channels: Optional[List[str]] = None) -> Dict[str, bool]:
    """
    Einsendefunktion für andere Skripte.
    Legt eine Incoming-Datei an und sendet sofort.
    """
    send_incoming(message, priority, channels, force=True)
    return send_notification(message, priority, channels, force=True)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Notification Engine — Multi-Channel Alerting für OpenAmer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  notification-engine.py --send "Backup abgeschlossen" --priority info
  notification-engine.py --send "Kritischer Fehler" --priority critical --channel sound
  notification-engine.py --daemon
  notification-engine.py --history
  notification-engine.py --status
  notification-engine.py --send-incoming "Hallo"  # nur Datei anlegen
        """
    )
    parser.add_argument("--send", type=str, metavar="MESSAGE",
                        help="Sende eine Benachrichtigung sofort")
    parser.add_argument("--send-incoming", type=str, metavar="MESSAGE",
                        help="Lege nur eine Incoming-Datei an (für andere Skripte)")
    parser.add_argument("--priority", type=str, default="info",
                        choices=["info", "warning", "critical"],
                        help="Priorität (default: info)")
    parser.add_argument("--channel", type=str, nargs="+",
                        default=None, metavar="CHANNEL",
                        help="Kanal/mehrere Kanäle (default: alle aktiven)")
    parser.add_argument("--force", action="store_true",
                        help="Cooldown ignorieren")
    parser.add_argument("--daemon", action="store_true",
                        help="Daemon-Modus: überwacht incoming/ alle 30s")
    parser.add_argument("--interval", type=int, default=30,
                        help="Daemon-Intervall in Sekunden (default: 30)")
    parser.add_argument("--history", action="store_true",
                        help="Zeige die letzten Benachrichtigungen")
    parser.add_argument("--status", action="store_true",
                        help="Zeige Engine-Status")
    parser.add_argument("--process-incoming", action="store_true",
                        help="Verarbeite alle wartenden Incoming-Dateien")

    args = parser.parse_args()

    ensure_dirs()

    if args.daemon:
        run_daemon(args.interval)
    elif args.history:
        show_history()
    elif args.status:
        show_status()
    elif args.process_incoming:
        count = process_incoming()
        print(f"{count} Alarm(e) verarbeitet.")
    elif args.send_incoming:
        path = send_incoming(args.send_incoming, args.priority, args.channel, args.force)
        print(f"Incoming-Datei angelegt: {path}")
    elif args.send:
        results = send_notification(args.send, args.priority, args.channel, args.force)
        if results:
            ok = all(results.values())
            chans = ", ".join(f"{k}:{'✓' if v else '✗'}" for k, v in results.items())
            print(f"{'✓' if ok else '✗'} Gesendet ({chans})")
        else:
            print("— Keine Kanäle aktiv oder Cooldown aktiv.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()