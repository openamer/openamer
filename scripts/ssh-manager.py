#!/usr/bin/env python3
"""
SSH Remote Manager — Multi-Host-Verwaltung + parallel exec + scp + Ping-Health-Check

Usage:
  ssh-manager.py --add <name> <user@host:port>
  ssh-manager.py --list
  ssh-manager.py --exec <host> '<command>'
  ssh-manager.py --exec-all '<command>'
  ssh-manager.py --fetch <host> <remote_path> <local_path>
  ssh-manager.py --push <host> <local_path> <remote_path>
  ssh-manager.py --check

Exit codes:
  0 = alle OK
  1 = teilweise Fehler
  2 = alle tot
"""

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Konfiguration ──────────────────────────────────────────────────────────

CONFIG_DIR = Path.home() / ".ssh-manager"
HOSTS_FILE = CONFIG_DIR / "hosts.json"

# ── Hilfsfunktionen ────────────────────────────────────────────────────────

def _ensure_config() -> None:
    """Stelle sicher, dass Config-Verzeichnis und hosts.json existieren."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not HOSTS_FILE.exists():
        HOSTS_FILE.write_text("[]", encoding="utf-8")


def _load_hosts() -> list[dict[str, Any]]:
    _ensure_config()
    try:
        data = json.loads(HOSTS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _save_hosts(hosts: list[dict[str, Any]]) -> None:
    _ensure_config()
    HOSTS_FILE.write_text(
        json.dumps(hosts, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _find_host(hosts: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for h in hosts:
        if h["name"] == name:
            return h
    return None


def _parse_user_host_port(raw: str) -> tuple[str, str, int]:
    """
    Parst 'user@host:port' → (user, host, port)
    Erlaubt: user@host, user@host:22, host (Default user = aktueller User)
    """
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "root"
    host: str = raw
    port: int = 22

    if "@" in raw:
        user, host = raw.split("@", 1)

    if ":" in host:
        host, port_str = host.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            print(f"⚠ Ungültiger Port '{port_str}', verwende 22", file=sys.stderr)

    return user, host, port


def _ping(host: str, timeout: int = 5) -> bool:
    """Ping einen Host (betriebssystem-unabhängig)."""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        result = subprocess.run(
            ["ping", param, "1", "-W", str(timeout), host],
            capture_output=True,
            timeout=timeout + 2,
            text=True,
            errors="replace",
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _ssh_exec(host_entry: dict[str, Any], command: str) -> subprocess.CompletedProcess | None:
    """Führe einen Befehl per SSH auf dem Host aus."""
    ssh_cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        "-p", str(host_entry["port"]),
    ]
    if host_entry.get("key_path"):
        ssh_cmd += ["-i", host_entry["key_path"]]

    ssh_cmd.append(f"{host_entry['user']}@{host_entry['host']}")
    ssh_cmd.append(command)

    try:
        result = subprocess.run(
            ssh_cmd, capture_output=True, text=True, timeout=120
        )
        return result
    except subprocess.TimeoutExpired:
        return None
    except OSError as e:
        print(f"  ✗ SSH-Fehler: {e}", file=sys.stderr)
        return None


def _scp_exec(
    host_entry: dict[str, Any], src: str, dst: str, direction: str
) -> subprocess.CompletedProcess | None:
    """Führe scp aus (direction='to' oder 'from')."""
    scp_cmd = [
        "scp",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        "-P", str(host_entry["port"]),
    ]
    if host_entry.get("key_path"):
        scp_cmd += ["-i", host_entry["key_path"]]

    remote = f"{host_entry['user']}@{host_entry['host']}"

    if direction == "to":
        scp_cmd.append(src)
        scp_cmd.append(f"{remote}:{dst}")
    else:  # from
        scp_cmd.append(f"{remote}:{src}")
        scp_cmd.append(dst)

    try:
        result = subprocess.run(
            scp_cmd, capture_output=True, text=True, timeout=120
        )
        return result
    except subprocess.TimeoutExpired:
        return None
    except OSError as e:
        print(f"  ✗ SCP-Fehler: {e}", file=sys.stderr)
        return None


def _check_host(host_entry: dict[str, Any]) -> dict[str, Any]:
    """Prüfe einen Host (Ping) und gib Status-Dict zurück."""
    host = host_entry["host"]
    alive = _ping(host)
    return {
        "name": host_entry["name"],
        "host": host,
        "port": host_entry["port"],
        "alive": alive,
        "checked_at": datetime.now().isoformat(),
    }


# ── CLI-Kommandos ──────────────────────────────────────────────────────────

def cmd_add(args: argparse.Namespace) -> int:
    hosts = _load_hosts()
    name = args.add
    raw = args.hostspec

    if _find_host(hosts, name):
        print(f"✗ Host '{name}' existiert bereits.", file=sys.stderr)
        return 1

    user, host, port = _parse_user_host_port(raw)
    key_path = args.key

    entry: dict[str, Any] = {
        "name": name,
        "host": host,
        "port": port,
        "user": user,
        "key_path": key_path,
    }

    hosts.append(entry)
    _save_hosts(hosts)
    print(f"✓ Host '{name}' hinzugefügt: {user}@{host}:{port}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    hosts = _load_hosts()
    if not hosts:
        print("(keine Hosts konfiguriert)")
        return 0

    print(f"{'NAME':<20} {'HOST':<30} {'PORT':<6} {'USER':<16} {'KEY':<30} {'STATUS'}")
    print("-" * 130)
    errors = 0
    for h in hosts:
        alive = _ping(h["host"])
        status = "✓ ONLINE" if alive else "✗ OFFLINE"
        if not alive:
            errors += 1
        key = h.get("key_path") or "(Key-Agent)"
        print(
            f"{h['name']:<20} {h['host']:<30} {h['port']:<6} "
            f"{h['user']:<16} {key:<30} {status}"
        )

    if errors == len(hosts):
        return 2
    if errors > 0:
        return 1
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    hosts = _load_hosts()
    entry = _find_host(hosts, args.exec_host)
    if not entry:
        print(f"✗ Host '{args.exec_host}' nicht gefunden.", file=sys.stderr)
        return 1

    command = args.exec_command
    print(f"▶ {args.exec_host}: Ausführen: {command}")
    result = _ssh_exec(entry, command)

    if result is None:
        print(f"  ✗ {args.exec_host}: Timeout oder Fehler")
        return 1

    if result.returncode == 0:
        print(f"  ✓ Exit {result.returncode}")
    else:
        print(f"  ✗ Exit {result.returncode}")

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode


def _parallel_exec(hosts: list[dict], command: str, results: list, lock: threading.Lock) -> None:
    """Worker für --exec-all."""
    for entry in hosts:
        name = entry["name"]
        print(f"  ▶ {name} ... ", end="", flush=True)
        result = _ssh_exec(entry, command)
        with lock:
            if result is None:
                print(f"✗ TIMEOUT")
                results.append((name, 1, "", "Timeout"))
            else:
                status = "✓" if result.returncode == 0 else "✗"
                print(f"{status} Exit {result.returncode}")
                results.append((name, result.returncode, result.stdout, result.stderr))


def cmd_exec_all(args: argparse.Namespace) -> int:
    hosts = _load_hosts()
    if not hosts:
        print("(keine Hosts konfiguriert)")
        return 0

    command = args.exec_all_command
    print(f"▶ EXEC-ALL on {len(hosts)} host(s): {command}")
    print()

    # Parallele Ausführung via Threads
    results: list[tuple[str, int, str, str]] = []
    lock = threading.Lock()
    threads = []

    chunk_size = max(1, len(hosts) // 4)  # Max 4 parallele Threads
    for i in range(0, len(hosts), chunk_size):
        chunk = hosts[i : i + chunk_size]
        t = threading.Thread(
            target=_parallel_exec, args=(chunk, command, results, lock)
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Report
    print()
    print("═" * 50)
    print("ZUSAMMENFASSUNG")
    print("═" * 50)
    successes = sum(1 for _, rc, _, _ in results if rc == 0)
    failures = sum(1 for _, rc, _, _ in results if rc != 0)

    for name, rc, stdout, stderr in results:
        icon = "✓" if rc == 0 else "✗"
        print(f"  {icon} {name}: Exit {rc}")
        if stdout.strip() and args.verbose:
            print(f"     {stdout.strip()}")
        if stderr.strip() and args.verbose:
            print(f"     ERR: {stderr.strip()}", file=sys.stderr)

    print(f"\n{successes} OK, {failures} Fehler")
    if failures == len(hosts):
        return 2
    if failures > 0:
        return 1
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    hosts = _load_hosts()
    entry = _find_host(hosts, args.fetch_host)
    if not entry:
        print(f"✗ Host '{args.fetch_host}' nicht gefunden.", file=sys.stderr)
        return 1

    remote_path = args.remote_path
    local_path = args.local_path

    print(f"▶ FETCH von {args.fetch_host}:{remote_path} → {local_path}")
    result = _scp_exec(entry, remote_path, local_path, direction="from")

    if result is None:
        print("  ✗ Timeout oder Fehler", file=sys.stderr)
        return 1

    if result.returncode == 0:
        print(f"  ✓ Datei geholt: {local_path}")
    else:
        print(f"  ✗ SCP-Fehler (Exit {result.returncode})", file=sys.stderr)
        if result.stderr:
            print(f"     {result.stderr.strip()}", file=sys.stderr)
    return result.returncode


def cmd_push(args: argparse.Namespace) -> int:
    hosts = _load_hosts()
    entry = _find_host(hosts, args.push_host)
    if not entry:
        print(f"✗ Host '{args.push_host}' nicht gefunden.", file=sys.stderr)
        return 1

    local_path = args.local_path
    remote_path = args.remote_path

    print(f"▶ PUSH von {local_path} → {args.push_host}:{remote_path}")
    result = _scp_exec(entry, local_path, remote_path, direction="to")

    if result is None:
        print("  ✗ Timeout oder Fehler", file=sys.stderr)
        return 1

    if result.returncode == 0:
        print(f"  ✓ Datei gesendet: {remote_path}")
    else:
        print(f"  ✗ SCP-Fehler (Exit {result.returncode})", file=sys.stderr)
        if result.stderr:
            print(f"     {result.stderr.strip()}", file=sys.stderr)
    return result.returncode


def cmd_check(args: argparse.Namespace) -> int:
    hosts = _load_hosts()
    if not hosts:
        print("(keine Hosts konfiguriert)")
        return 0

    report: list[dict[str, Any]] = []
    errors = 0

    print(f"▶ Health-Check: {len(hosts)} Host(s)")
    print()

    for h in hosts:
        status = _check_host(h)
        report.append(status)
        icon = "✓" if status["alive"] else "✗"
        print(f"  {icon} {status['name']:<20} {status['host']:<30} "
              f"{'ONLINE' if status['alive'] else 'OFFLINE'}")
        if not status["alive"]:
            errors += 1

    # JSON-Report speichern
    report_path = CONFIG_DIR / f"health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Aktuellsten Report als symlink/ Kopie
    latest_path = CONFIG_DIR / "health_latest.json"
    latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(f"  Report: {report_path}")
    print(f"  Latest: {latest_path}")
    print()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    total = len(hosts)
    alive = total - errors
    print(f"  {alive}/{total} online")

    if errors == total:
        return 2
    if errors > 0:
        return 1
    return 0


# ── Argument-Parser ────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SSH Remote Manager — Multi-Host-Verwaltung",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit-Codes:
  0  Alle Hosts OK
  1  Teilweise Fehler
  2  Alle Hosts offline/tot

Beispiele:
  %(prog)s --add myserver root@192.168.1.100:22
  %(prog)s --add myserver root@192.168.1.100:22 --key ~/.ssh/id_rsa
  %(prog)s --list
  %(prog)s --exec myserver 'uptime'
  %(prog)s --exec-all 'df -h'
  %(prog)s --fetch myserver /var/log/syslog ./syslog.log
  %(prog)s --push myserver ./config.yaml /etc/myapp/config.yaml
  %(prog)s --check
  %(prog)s --check --json
        """,
    )

    parser.add_argument("--add", metavar="NAME", help="Host hinzufügen")
    parser.add_argument("--key", metavar="PATH", help="SSH-Key-Pfad (optional)")
    parser.add_argument(
        "hostspec",
        nargs="?",
        metavar="user@host:port",
        help="Host-Spezifikation für --add (user@host:port)",
    )

    parser.add_argument("--list", action="store_true", help="Alle Hosts auflisten")

    parser.add_argument(
        "--exec", nargs=2, metavar=("HOST", "COMMAND"),
        dest="exec_pair", help="Befehl auf einem Host ausführen"
    )

    parser.add_argument(
        "--exec-all", metavar="COMMAND",
        help="Befehl auf ALLEN Hosts parallel ausführen"
    )

    parser.add_argument(
        "--fetch", nargs=3, metavar=("HOST", "REMOTE", "LOCAL"),
        dest="fetch_triple", help="Datei von Host holen (scp)"
    )

    parser.add_argument(
        "--push", nargs=3, metavar=("HOST", "LOCAL", "REMOTE"),
        dest="push_triple", help="Datei zu Host senden (scp)"
    )

    parser.add_argument("--check", action="store_true", help="Health-Check (Ping)")
    parser.add_argument("--json", action="store_true", help="JSON-Ausgabe für --check")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Ausführliche Ausgabe (z.B. stdout bei --exec-all)"
    )
    parser.add_argument(
        "--version", action="version", version="ssh-manager 1.0.0"
    )

    return parser


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # --add <name> <hostspec>
    if args.add:
        if not args.hostspec:
            parser.error("--add benötigt NAME und user@host:port")
        return cmd_add(args)

    # --list
    if args.list:
        return cmd_list(args)

    # --exec HOST COMMAND
    if args.exec_pair:
        args.exec_host, args.exec_command = args.exec_pair
        return cmd_exec(args)

    # --exec-all
    if args.exec_all:
        args.exec_all_command = args.exec_all
        return cmd_exec_all(args)

    # --fetch HOST REMOTE LOCAL
    if args.fetch_triple:
        args.fetch_host, args.remote_path, args.local_path = args.fetch_triple
        return cmd_fetch(args)

    # --push HOST LOCAL REMOTE
    if args.push_triple:
        args.push_host, args.local_path, args.remote_path = args.push_triple
        return cmd_push(args)

    # --check
    if args.check:
        return cmd_check(args)

    # Kein Kommando
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())