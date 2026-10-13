#!/usr/bin/env python3
"""
Resource Monitor — Live-Terminal-Dashboard CPU/RAM/DISK/NET + Top-Prozesse + Alarm

Usage:
  python resource-monitor.py --once        Einmalig als JSON
  python resource-monitor.py --watch       Live-Modus (rich / echo+clear)
  python resource-monitor.py --alert       Exit-Code 1 wenn Schwellwert überschritten

Datenquellen: psutil (CPU, RAM, DISK, NET, Prozesse)
Keine externen Dependencies (ausser psutil, das bei OpenAmer installiert ist).
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
except ImportError:
    print("FEHLER: psutil nicht installiert. Bitte 'pip install psutil' ausführen.", file=sys.stderr)
    sys.exit(2)

# ─── Schwellwerte ────────────────────────────────────────────────────────────
THRESHOLDS = {
    "cpu": 90.0,        # CPU-Auslastung % (über 90%)
    "ram": 85.0,        # RAM-Auslastung % (über 85%)
    "disk": 90.0,       # Festplattenauslastung % (über 90%)
}

ALERTS_HISTORY = []  # (timestamp, msg)


def get_cpu_percent(interval=0.5):
    return psutil.cpu_percent(interval=interval)


def get_ram_info():
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024 ** 3), 1),
        "used_gb": round(mem.used / (1024 ** 3), 1),
        "percent": mem.percent,
    }


def get_disk_info():
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "total_gb": round(usage.total / (1024 ** 3), 1),
                "used_gb": round(usage.used / (1024 ** 3), 1),
                "free_gb": round(usage.free / (1024 ** 3), 1),
                "percent": usage.percent,
            })
        except PermissionError:
            continue
    return disks


def get_net_io():
    net = psutil.net_io_counters()
    return {
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
        "packets_sent": net.packets_sent,
        "packets_recv": net.packets_recv,
    }


def get_top_processes(sort_key="cpu", count=5):
    """Top-Prozesse nach CPU (%) oder RAM (MB)"""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info"]):
        try:
            info = p.info
            mem_mb = round(info["memory_info"].rss / (1024 * 1024), 1) if info.get("memory_info") else 0.0
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "?",
                "cpu_percent": info["cpu_percent"] or 0.0,
                "memory_mb": mem_mb,
                "memory_percent": round(info["memory_percent"] or 0.0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if sort_key == "cpu":
        procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
    else:
        procs.sort(key=lambda x: x["memory_mb"], reverse=True)
    return procs[:count]


def check_alerts(cpu, ram, disks):
    """Prüft Schwellwerte und sammelt Alarme."""
    now = datetime.now().strftime("%H:%M:%S")
    alerts = []
    if cpu > THRESHOLDS["cpu"]:
        msg = f"[{now}] ⚠ CPU {cpu:.0f}% > {THRESHOLDS['cpu']:.0f}%"
        alerts.append(msg)
    if ram["percent"] > THRESHOLDS["ram"]:
        msg = f"[{now}] ⚠ RAM {ram['percent']:.0f}% > {THRESHOLDS['ram']:.0f}%"
        alerts.append(msg)
    for d in disks:
        if d["percent"] > THRESHOLDS["disk"]:
            msg = f"[{now}] ⚠ DISK {d['device']} {d['percent']:.0f}% > {THRESHOLDS['disk']:.0f}%"
            alerts.append(msg)
    for a in alerts:
        if a not in ALERTS_HISTORY[-20:]:
            ALERTS_HISTORY.append(a)
    return alerts


def build_snapshot():
    """Ein vollständiger Snapshot aller Metriken."""
    cpu = get_cpu_percent(0)
    ram = get_ram_info()
    disks = get_disk_info()
    net = get_net_io()
    top_cpu = get_top_processes("cpu", 5)
    top_ram = get_top_processes("memory", 5)
    alerts = check_alerts(cpu, ram, disks)
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": cpu,
        "ram": ram,
        "disks": disks,
        "net": net,
        "top_cpu": top_cpu,
        "top_ram": top_ram,
        "alerts": alerts,
        "alerts_history": ALERTS_HISTORY[-10:],
    }


# ─── Rich / Fallback Live-Dashboard ──────────────────────────────────────────

def detect_terminal_width():
    try:
        import shutil
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


def live_dashboard_rich(snapshot, prev_net=None):
    """Render mit Rich (Live-Update)."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text

    console = Console()
    width = detect_terminal_width()

    # ── Zeile 1: CPU | RAM | DISK | NET ──
    cpu = snapshot["cpu_percent"]
    ram = snapshot["ram"]
    disks = snapshot["disks"]
    net = snapshot["net"]

    # Disk-Übersicht (nur letzte 2 relevante)
    disk_summary = " | ".join(
        f"{d['mountpoint']} {d['percent']:.0f}%"
        for d in disks[:3]
    )

    # Netzwerk-Delta
    net_down_mb = round(net["bytes_recv"] / (1024 * 1024), 1)
    net_up_mb = round(net["bytes_sent"] / (1024 * 1024), 1)

    header_text = (
        f"CPU {cpu:5.1f}% | "
        f"RAM {ram['used_gb']:.1f}/{ram['total_gb']:.1f} GB ({ram['percent']:.0f}%) | "
        f"DISK {disk_summary} | "
        f"NET ↓{net_down_mb}MB ↑{net_up_mb}MB"
    )

    # ── Top CPU ──
    cpu_table = Table(title="Top 5 CPU", box=None, show_header=True)
    cpu_table.add_column("PID", justify="right", style="dim")
    cpu_table.add_column("Name", style="cyan")
    cpu_table.add_column("CPU%", justify="right")
    for p in snapshot["top_cpu"]:
        cpu_table.add_row(str(p["pid"]), p["name"][:25], f"{p['cpu_percent']:.1f}")

    # ── Top RAM ──
    ram_table = Table(title="Top 5 RAM", box=None, show_header=True)
    ram_table.add_column("PID", justify="right", style="dim")
    ram_table.add_column("Name", style="green")
    ram_table.add_column("RAM MB", justify="right")
    ram_table.add_column("RAM%", justify="right")
    for p in snapshot["top_ram"]:
        ram_table.add_row(str(p["pid"]), p["name"][:25], f"{p['memory_mb']:.0f}", f"{p['memory_percent']:.1f}")

    # ── Alerts ──
    alert_lines = "\n".join(ALERTS_HISTORY[-5:]) if ALERTS_HISTORY else "–"
    alerts_panel = Panel(alert_lines, title="Letzte Alarme", border_style="yellow")

    # ── Layout ──
    layout = Layout()
    layout.split_column(
        Layout(Panel(header_text, title="Resource Monitor", border_style="blue"), size=3),
        Layout(name="middle"),
        Layout(alerts_panel, size=5),
    )
    layout["middle"].split_row(
        Layout(cpu_table),
        Layout(ram_table),
    )
    return layout


def live_dashboard_echo(snapshot):
    """Fallback: echo + clear (wenn rich nicht verfügbar)."""
    os.system("cls" if os.name == "nt" else "clear")
    cpu = snapshot["cpu_percent"]
    ram = snapshot["ram"]
    disks = snapshot["disks"]
    net = snapshot["net"]

    disk_summary = " | ".join(f"{d['mountpoint']} {d['percent']:.0f}%" for d in disks[:2])
    net_down_mb = round(net["bytes_recv"] / (1024 * 1024), 1)
    net_up_mb = round(net["bytes_sent"] / (1024 * 1024), 1)

    print("=" * 70)
    print(f"  RESOURCE MONITOR — {snapshot['timestamp']}")
    print("=" * 70)
    print(f"  CPU   {cpu:5.1f}%")
    print(f"  RAM   {ram['used_gb']:.1f} / {ram['total_gb']:.1f} GB  ({ram['percent']:.0f}%)")
    print(f"  DISK  {disk_summary}")
    print(f"  NET   ↓ {net_down_mb} MB  ↑ {net_up_mb} MB")
    print("-" * 70)
    print("  Top 5 CPU:")
    for i, p in enumerate(snapshot["top_cpu"], 1):
        print(f"    {i}. {p['name'][:30]:30s}  CPU {p['cpu_percent']:5.1f}%  PID {p['pid']}")
    print("  Top 5 RAM:")
    for i, p in enumerate(snapshot["top_ram"], 1):
        print(f"    {i}. {p['name'][:30]:30s}  RAM {p['memory_mb']:6.0f} MB  PID {p['pid']}")
    print("-" * 70)
    print("  Letzte Alarme:")
    if ALERTS_HISTORY:
        for a in ALERTS_HISTORY[-5:]:
            print(f"    {a}")
    else:
        print("    – keine –")
    print("=" * 70)
    print("  [Strg+C zum Beenden]  (Aktualisiert alle 2s)")
    print("=" * 70)


# ─── Hauptlogik ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Resource Monitor — Live-Terminal-Dashboard CPU/RAM/DISK/NET"
    )
    parser.add_argument("--once", action="store_true", help="Einmalige JSON-Ausgabe")
    parser.add_argument("--watch", action="store_true", help="Live-Modus (alle 2s)")
    parser.add_argument("--alert", action="store_true", help="Exit-Code 1 bei Schwellwertüberschreitung")
    args = parser.parse_args()

    # ── Einmaliger Modus ──
    if args.once:
        snapshot = build_snapshot()
        print(json.dumps(snapshot, indent=2, default=str, ensure_ascii=False))
        if snapshot["alerts"]:
            sys.exit(1)
        sys.exit(0)

    # ── Alert-Modus ──
    if args.alert:
        snapshot = build_snapshot()
        if snapshot["alerts"]:
            print("[RESOURCE-MONITOR ALERT]", "; ".join(snapshot["alerts"]))
            sys.exit(1)
        print(f"[RESOURCE-MONITOR OK] CPU {snapshot['cpu_percent']:.0f}% | RAM {snapshot['ram']['percent']:.0f}%")
        sys.exit(0)

    # ── Watch-Modus ──
    if args.watch:
        use_rich = False
        try:
            from rich.console import Console
            use_rich = True
        except ImportError:
            pass

        if use_rich:
            try:
                from rich.live import Live
                first = True
                prev_net = None
                while True:
                    snap = build_snapshot()
                    layout = live_dashboard_rich(snap, prev_net)
                    if first:
                        console = Console()
                        console.clear()
                        first = False
                    # Live display mit print + clear (da Live nicht reset-basiert)
                    os.system("cls" if os.name == "nt" else "clear")
                    from rich.console import Console as C2
                    C2().print(layout)
                    time.sleep(2)
            except KeyboardInterrupt:
                print("\nBeendet.")
                sys.exit(0)
        else:
            try:
                while True:
                    snap = build_snapshot()
                    live_dashboard_echo(snap)
                    time.sleep(2)
            except KeyboardInterrupt:
                print("\nBeendet.")
                sys.exit(0)

    # ── Kein Argument → Watch ──
    if not any([args.once, args.watch, args.alert]):
        args.watch = True
        # Recurse with --watch
        sys.argv.append("--watch")
        main()


if __name__ == "__main__":
    main()