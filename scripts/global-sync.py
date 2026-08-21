#!/usr/bin/env python3
"""
Global State Sync — Multi-Machine State Synchronization für OpenAmer.

Sync-Mechanismus: HTTP POST /sync an Peers mit JSON-Delta
(nur geänderte Dateien seit last_sync).
Empfänger: HTTP-Server auf Port 8902, empfängt Deltas, merged lokal.
Konfliktlösung: timestamp-basiert (neueste Version gewinnt),
Konflikte in .global-sync/conflicts/.
Sicherheit: shared-token in jedem Request (SHA256).

CLI:
  --start        Server starten + Sync-Thread
  --sync-now     Sofort zu allen Peers syncen
  --peers        Peer-Liste anzeigen
  --add-peer     name host:port token  (Peer hinzufügen)
  --status       Letzter Sync, Konflikte
"""

import argparse
import hashlib
import hmac
import json
import mimetypes
import os
import shutil
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------

def get_home() -> Path:
    """Liefert OpenAmer Home."""
    env = os.environ.get("OPENAMER_HOME")
    if env:
        return Path(env).resolve()
    return Path.home() / "AppData" / "Local" / "openamer-laptop"

OPENAMER_HOME = get_home()
SYNC_DIR = Path.home() / ".global-sync"
CONFIG_FILE = SYNC_DIR / "config.json"
CONFLICTS_DIR = SYNC_DIR / "conflicts"
LAST_SYNC_FILE = SYNC_DIR / "last_sync.txt"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "peers": [],
    "sync_interval_minutes": 60,
    "sync_items": ["skills", "cron", "scripts", "config", "sessions"],
    "token": "CHANGE_ME_TO_A_SECURE_RANDOM_TOKEN",
    "server_port": 8902,
    "home_path": None,
}


def load_config() -> dict:
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    CONFLICTS_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # merge defaults for new keys
        merged = dict(DEFAULT_CONFIG)
        merged.update(cfg)
        return merged
    except (json.JSONDecodeError, OSError) as e:
        print(f"[global-sync] WARN: Config fehlerhaft ({e}), verwende Defaults.", file=sys.stderr)
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print(f"[global-sync] Config gespeichert: {CONFIG_FILE}")


# ---------------------------------------------------------------------------
# Token / Sicherheit
# ---------------------------------------------------------------------------

def compute_signature(token: str, body: bytes) -> str:
    """SHA256-HMAC über den Body mit dem Token als Key."""
    return hmac.new(token.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(token: str, body: bytes, signature: str) -> bool:
    """Vergleicht erwartete Signatur mit übermittelter (timing-safe via hmac.compare_digest)."""
    expected = compute_signature(token, body)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Delta-Erstellung
# ---------------------------------------------------------------------------

def resolve_sync_items(cfg: dict) -> list[Path]:
    """Liefert Liste der zu syncenden Quell-Pfade."""
    home = OPENAMER_HOME
    sync_items = cfg.get("sync_items", DEFAULT_CONFIG["sync_items"])
    paths = []
    for item in sync_items:
        if item == "skills":
            p = home / "skills"
            if p.exists():
                paths.append(p)
        elif item == "cron":
            p = home / "cron"
            if p.exists():
                paths.append(p)
        elif item == "scripts":
            p = home / "scripts"
            if p.exists():
                paths.append(p)
        elif item == "config":
            p = home / "config.yaml"
            if p.exists():
                paths.append(p)
            p2 = Path.home() / ".openamer" / "config.yaml"
            if p2.exists():
                paths.append(p2)
        elif item == "sessions":
            p = home / "sessions"
            if p.exists():
                paths.append(p)
    return paths


def get_last_sync() -> float:
    """Liefert UNIX-Timestamp des letzten Syncs, oder 0."""
    try:
        if LAST_SYNC_FILE.exists():
            return float(LAST_SYNC_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        pass
    return 0.0


def set_last_sync(ts: float = None):
    if ts is None:
        ts = time.time()
    LAST_SYNC_FILE.write_text(f"{ts:.6f}\n", encoding="utf-8")


def compute_delta(cfg: dict, since: float) -> list[dict]:
    """
    Baut eine Liste von File-Deltas seit 'since'.
    Jeder Eintrag: {
        "path": relativer Pfad (z.B. "skills/foo/SKILL.md"),
        "content": Base64-kodierter Inhalt,
        "mtime": float,
        "size": int
    }
    Gelöschte Dateien werden als {"path": ..., "deleted": true} gemeldet.
    """
    import base64
    sync_paths = resolve_sync_items(cfg)
    deltas = []
    seen = set()

    for base in sync_paths:
        if not base.exists():
            continue
        if base.is_file():
            files_to_check = [base]
        else:
            files_to_check = list(base.rglob("*"))

        for fpath in files_to_check:
            if not fpath.is_file():
                continue
            # Ignoriere versteckte / Cache-Dateien
            rel = fpath.relative_to(base)
            rel_str = str(rel)
            if any(part.startswith(".") or part == "__pycache__" for part in fpath.parts):
                continue
            if fpath.suffix in (".pyc", ".pyo"):
                continue
            key = f"{base.name}/{rel_str}"
            if key in seen:
                continue
            seen.add(key)

            try:
                stat = fpath.stat()
                mtime = stat.st_mtime
                if mtime > since:
                    content = fpath.read_bytes()
                    deltas.append({
                        "path": key,
                        "content": base64.b64encode(content).decode("utf-8"),
                        "mtime": mtime,
                        "size": len(content),
                    })
            except OSError:
                continue

    return deltas


# ---------------------------------------------------------------------------
# Delta-Empfang und Merge
# ---------------------------------------------------------------------------

def apply_delta(delta: dict) -> list[dict]:
    """
    Wendet ein Delta lokal an.
    Gibt Liste von Konflikten zurück: [{"path", "local_mtime", "remote_mtime", "resolution"}]
    """
    import base64

    conflicts = []
    target = OPENAMER_HOME
    rel_path = delta["path"]

    if delta.get("deleted"):
        full = target / rel_path
        if full.exists():
            full.unlink()
            print(f"[global-sync] Gelöscht: {rel_path}")
        return conflicts

    full = target / rel_path
    content_b64 = delta.get("content", "")
    remote_mtime = delta.get("mtime", 0.0)

    try:
        content = base64.b64decode(content_b64)
    except Exception as e:
        print(f"[global-sync] FEHLER: Base64-Decode für {rel_path}: {e}", file=sys.stderr)
        return conflicts

    # Timestamp-Konfliktlösung
    if full.exists():
        local_mtime = full.stat().st_mtime
        if local_mtime > remote_mtime:
            # Lokal neuer → Konflikt, lokale Version behalten
            conflicts.append({
                "path": rel_path,
                "local_mtime": local_mtime,
                "remote_mtime": remote_mtime,
                "resolution": "local_wins",
            })
            # Remote-Version in conflicts/ ablegen
            conflict_dir = CONFLICTS_DIR / rel_path
            conflict_dir.parent.mkdir(parents=True, exist_ok=True)
            conflict_path = conflict_dir.with_suffix(f"{conflict_dir.suffix}.remote_{int(remote_mtime)}")
            conflict_path.write_bytes(content)
            print(f"[global-sync] KONFLIKT: {rel_path} (lokal neuer) → remote in {conflict_path}")
            return conflicts

    # Remote neuer oder gleich alt → überschreiben
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(content)

    # Setze mtime auf remote mtime
    try:
        os.utime(full, (remote_mtime, remote_mtime))
    except OSError:
        pass

    print(f"[global-sync] Empfangen: {rel_path} ({len(content)} bytes)")
    return conflicts


# ---------------------------------------------------------------------------
# HTTP-Client (Sync an Peer senden)
# ---------------------------------------------------------------------------

def sync_to_peer(peer: dict, cfg: dict) -> dict:
    """
    Sendet Delta an einen Peer.
    Gibt {"peer": name, "ok": bool, "error": str, "conflicts": list} zurück.
    """
    since = get_last_sync()
    deltas = compute_delta(cfg, since)

    if not deltas:
        return {"peer": peer["name"], "ok": True, "error": None, "conflicts": []}

    payload = json.dumps({
        "deltas": deltas,
        "since": since,
        "sender": peer.get("name", "unknown"),
    }).encode("utf-8")

    token = cfg.get("token", DEFAULT_CONFIG["token"])
    sig = compute_signature(token, payload)

    url = f"http://{peer['host']}:{peer['port']}/sync"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Sync-Signature": sig,
            "X-Sync-Token": hashlib.sha256(token.encode()).hexdigest()[:16],
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            result = json.loads(body.decode("utf-8"))
        print(f"[global-sync] Sync zu {peer['name']} ({url}): {len(deltas)} Dateien, OK")
        return {
            "peer": peer["name"],
            "ok": True,
            "error": None,
            "conflicts": result.get("conflicts", []),
        }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"[global-sync] FEHLER: Sync zu {peer['name']}: HTTP {e.code} - {error_body}", file=sys.stderr)
        return {"peer": peer["name"], "ok": False, "error": f"HTTP {e.code}: {error_body}", "conflicts": []}
    except urllib.error.URLError as e:
        print(f"[global-sync] FEHLER: Sync zu {peer['name']}: {e.reason}", file=sys.stderr)
        return {"peer": peer["name"], "ok": False, "error": str(e.reason), "conflicts": []}
    except Exception as e:
        print(f"[global-sync] FEHLER: Sync zu {peer['name']}: {e}", file=sys.stderr)
        return {"peer": peer["name"], "ok": False, "error": str(e), "conflicts": []}


def sync_to_all(cfg: dict) -> list[dict]:
    """Sync an alle konfigurierten Peers. Gibt Ergebnisliste zurück."""
    peers = cfg.get("peers", [])
    if not peers:
        print("[global-sync] Keine Peers konfiguriert.")
        return []

    results = []
    for peer in peers:
        result = sync_to_peer(peer, cfg)
        results.append(result)

    # last_sync nur aktualisieren, wenn mindestens ein Sync erfolgreich war
    if any(r["ok"] for r in results):
        set_last_sync()

    return results


# ---------------------------------------------------------------------------
# HTTP-Server (Empfänger)
# ---------------------------------------------------------------------------

class SyncHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler für /sync und /status."""

    cfg = load_config()  # wird beim Start geladen

    def do_POST(self):
        if self.path != "/sync":
            self.send_error(404, "Not Found")
            return

        # Token-Verifikation
        token = self.cfg.get("token", DEFAULT_CONFIG["token"])
        received_sig = self.headers.get("X-Sync-Signature", "")
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if not verify_signature(token, body, received_sig):
            self.send_error(403, "Invalid signature")
            return

        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            self.send_error(400, f"Invalid JSON: {e}")
            return

        deltas = data.get("deltas", [])
        sender = data.get("sender", "unknown")
        print(f"[global-sync] Empfange {len(deltas)} Deltas von {sender}")

        all_conflicts = []
        for delta in deltas:
            conflicts = apply_delta(delta)
            all_conflicts.extend(conflicts)

        response = json.dumps({
            "status": "ok",
            "received": len(deltas),
            "conflicts": all_conflicts,
        }).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self):
        if self.path == "/status":
            status = self._build_status()
            body = json.dumps(status, indent=2, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            # health
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            health = json.dumps({"status": "alive"}).encode("utf-8")
            self.send_header("Content-Length", str(len(health)))
            self.end_headers()
            self.wfile.write(health)

    def _build_status(self) -> dict:
        last_sync = get_last_sync()
        conflicts = list(CONFLICTS_DIR.rglob("*"))
        return {
            "server": "running",
            "port": self.cfg.get("server_port", 8902),
            "last_sync_ts": last_sync,
            "last_sync_human": datetime.fromtimestamp(last_sync, tz=timezone.utc).isoformat() if last_sync else "never",
            "conflict_count": len([c for c in conflicts if c.is_file()]),
            "peers": len(self.cfg.get("peers", [])),
            "sync_items": self.cfg.get("sync_items", []),
        }

    def log_message(self, format, *args):
        """Leiserer Server-Log."""
        print(f"[global-sync:server] {args[0]} {args[1]} {args[2]}")


# ---------------------------------------------------------------------------
# Sync-Thread (periodisch)
# ---------------------------------------------------------------------------

_sync_thread_running = False
_sync_thread_stop = threading.Event()


def _sync_loop(cfg: dict, interval_minutes: int):
    """Periodischer Sync-Thread."""
    global _sync_thread_running
    _sync_thread_running = True
    print(f"[global-sync] Sync-Thread gestartet (Intervall: {interval_minutes} min)")
    while not _sync_thread_stop.is_set():
        # Warte (in 10-Sekunden-Schritten für sauberen Stop)
        for _ in range(interval_minutes * 6):
            if _sync_thread_stop.is_set():
                break
            time.sleep(10)
        if _sync_thread_stop.is_set():
            break
        cfg_current = load_config()
        print("[global-sync] Periodischer Sync...")
        sync_to_all(cfg_current)
    _sync_thread_running = False
    print("[global-sync] Sync-Thread beendet.")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def print_status(cfg: dict):
    """Gibt aktuellen Status auf der Konsole aus."""
    last_sync = get_last_sync()
    conflicts = list(CONFLICTS_DIR.rglob("*"))
    conflict_files = [c for c in conflicts if c.is_file()]

    print(f"\n{'='*60}")
    print(f"  Global State Sync — Status")
    print(f"{'='*60}")
    print(f"  OpenAmer Home:     {OPENAMER_HOME}")
    print(f"  Sync-Verzeichnis:  {SYNC_DIR}")
    print(f"  Letzter Sync:      {datetime.fromtimestamp(last_sync, tz=timezone.utc).isoformat() if last_sync else 'nie'}")
    print(f"  Konflikte:         {len(conflict_files)}")
    print(f"  Peers:             {len(cfg.get('peers', []))}")
    print(f"  Sync-Intervall:    {cfg.get('sync_interval_minutes', 60)} min")
    print(f"  Sync-Items:        {', '.join(cfg.get('sync_items', []))}")
    print(f"  Server-Port:       {cfg.get('server_port', 8902)}")
    print(f"  Sync-Thread läuft: {'ja' if _sync_thread_running else 'nein'}")
    print()

    if conflict_files:
        print("  Konflikt-Dateien:")
        for c in sorted(conflict_files):
            print(f"    - {c.relative_to(CONFLICTS_DIR)}")
        print()

    peers = cfg.get("peers", [])
    if peers:
        print("  Peers:")
        for p in peers:
            print(f"    - {p['name']} @ {p['host']}:{p['port']}")
    else:
        print("  Keine Peers konfiguriert.")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_start(cfg: dict):
    """Server starten + Sync-Thread."""
    port = cfg.get("server_port", 8902)
    server = HTTPServer(("0.0.0.0", port), SyncHandler)

    # Sync-Thread starten
    global _sync_thread_stop
    _sync_thread_stop.clear()
    interval = cfg.get("sync_interval_minutes", 60)
    t = threading.Thread(target=_sync_loop, args=(cfg, interval), daemon=True)
    t.start()

    print(f"[global-sync] Server läuft auf Port {port} (http://0.0.0.0:{port})")
    print(f"[global-sync] Sync-Intervall: {interval} min")
    print(f"[global-sync] Drücke Ctrl+C zum Beenden.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[global-sync] Server wird beendet...")
    finally:
        _sync_thread_stop.set()
        server.shutdown()
        print("[global-sync] Server gestoppt.")


def cmd_sync_now(cfg: dict):
    """Sofort zu allen Peers syncen."""
    results = sync_to_all(cfg)
    ok_count = sum(1 for r in results if r["ok"])
    fail_count = sum(1 for r in results if not r["ok"])
    print(f"\n[global-sync] Sync abgeschlossen: {ok_count} OK, {fail_count} Fehler")
    for r in results:
        status = "✓" if r["ok"] else "✗"
        print(f"  {status} {r['peer']}: {'OK' if r['ok'] else r['error']}")
        if r.get("conflicts"):
            for c in r["conflicts"]:
                print(f"      Konflikt: {c['path']} (lokal: {c['resolution']})")
    print()


def cmd_peers(cfg: dict):
    """Peer-Liste anzeigen."""
    peers = cfg.get("peers", [])
    if not peers:
        print("[global-sync] Keine Peers konfiguriert.")
        return
    print(f"\n{'='*60}")
    print(f"  Konfigurierte Peers ({len(peers)}):")
    print(f"{'='*60}")
    for i, p in enumerate(peers, 1):
        print(f"  {i}. {p['name']} → http://{p['host']}:{p['port']}")
    print(f"{'='*60}\n")


def cmd_add_peer(cfg: dict, name: str, host_port: str):
    """Peer hinzufügen."""
    # Parse host:port
    if ":" in host_port:
        host, port_str = host_port.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            print(f"[global-sync] FEHLER: Ungültiger Port '{port_str}'", file=sys.stderr)
            sys.exit(1)
    else:
        host = host_port
        port = 8902

    # Prüfe auf Duplikate
    for p in cfg.get("peers", []):
        if p["name"] == name:
            print(f"[global-sync] FEHLER: Peer '{name}' existiert bereits.", file=sys.stderr)
            sys.exit(1)
        if p["host"] == host and p["port"] == port:
            print(f"[global-sync] FEHLER: Peer '{p['name']}' hat bereits {host}:{port}.", file=sys.stderr)
            sys.exit(1)

    if "peers" not in cfg:
        cfg["peers"] = []
    cfg["peers"].append({
        "name": name,
        "host": host,
        "port": port,
    })
    save_config(cfg)
    print(f"[global-sync] Peer '{name}' hinzugefügt: http://{host}:{port}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Global State Sync — Multi-Machine State Synchronization",
    )
    parser.add_argument("--start", action="store_true", help="Server starten + Sync-Thread")
    parser.add_argument("--sync-now", action="store_true", help="Sofort zu allen Peers syncen")
    parser.add_argument("--peers", action="store_true", help="Peer-Liste anzeigen")
    parser.add_argument("--add-peer", nargs=2, metavar=("NAME", "HOST:PORT"),
                        help="Peer hinzufügen: NAME HOST:PORT")
    parser.add_argument("--status", action="store_true", help="Status anzeigen")
    parser.add_argument("--token", type=str, help="Neues Shared-Token setzen")

    args = parser.parse_args()

    # Config laden
    cfg = load_config()

    # Token setzen
    if args.token:
        cfg["token"] = args.token
        save_config(cfg)
        print(f"[global-sync] Token aktualisiert.")
        return

    # Aktionen ausführen
    if args.start:
        cmd_start(cfg)
    elif args.sync_now:
        cmd_sync_now(cfg)
    elif args.peers:
        cmd_peers(cfg)
    elif args.add_peer:
        name, host_port = args.add_peer
        cmd_add_peer(cfg, name, host_port)
    elif args.status:
        print_status(cfg)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()