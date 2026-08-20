"""
Swarm Metrics Dashboard — live Messung der A2A Swarm Performance.

Erfasst Latenz, Durchsatz, Confidence und Fehlerraten des Swarms.
Kann als CLI oder Web-Endpunkt dienen.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _home() -> Path:
    return Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))


def _metrics_dir() -> Path:
    mdir = _home() / "swarm_metrics"
    mdir.mkdir(parents=True, exist_ok=True)
    return mdir


def _logs_dir() -> Path:
    ldir = _home() / "logs"
    ldir.mkdir(parents=True, exist_ok=True)
    return ldir


# ----- In-Memory Metrics -----

_metrics: dict[str, list[dict[str, Any]]] = defaultdict(list)
"""category → [entry, ...]"""


def record_metric(category: str, name: str, value: float, tags: dict[str, str] | None = None) -> None:
    """Zeichnet einen Metrik-Wert auf."""
    entry = {
        "name": name,
        "value": value,
        "tags": tags or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "unix_ts": time.time(),
    }
    _metrics[category].append(entry)
    # Persist
    cat_file = _metrics_dir() / f"{category}.jsonl"
    with open(cat_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_metrics(category: str | None = None, last_n: int = 100) -> dict[str, Any]:
    """Liefert gesammelte Metriken (In-Memory + Disk)."""
    # Lade von Disk
    disk_data: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in _metrics_dir().glob("*.jsonl"):
        cat = f.stem
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    disk_data[cat].append(json.loads(line))

    # Merge mit In-Memory
    merged: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cat, entries in disk_data.items():
        merged[cat].extend(entries)
    for cat, entries in _metrics.items():
        merged[cat].extend(entries)

    # Filter
    if category:
        merged = {k: v for k, v in merged.items() if k == category}

    # Aggregate
    result: dict[str, Any] = {}
    for cat, entries in merged.items():
        # Nur die letzten N
        recent = entries[-last_n:]
        if not recent:
            continue
        values = [e["value"] for e in recent]
        names = [e["name"] for e in recent]
        avg_val = sum(values) / len(values)
        max_val = max(values)
        min_val = min(values)
        last_val = values[-1] if values else 0
        result[cat] = {
            "count": len(recent),
            "avg": round(avg_val, 3),
            "min": round(min_val, 3),
            "max": round(max_val, 3),
            "last": round(last_val, 3),
            "last_name": names[-1] if names else "",
            "recent": recent[-10:],  # letzte 10 Rohdaten
        }

    return {
        "metrics": result,
        "total_records": sum(len(v) for v in merged.values()),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def get_swarm_summary() -> dict[str, Any]:
    """Spezifische Metrik-Zusammenfassung für den A2A Swarm."""
    metrics = get_metrics("swarm")
    swarm_data = metrics.get("metrics", {}).get("swarm", {})
    return {
        "avg_latency_ms": swarm_data.get("avg", 0),
        "max_latency_ms": swarm_data.get("max", 0),
        "total_operations": swarm_data.get("count", 0),
        "last_operation": swarm_data.get("last_name", ""),
        "health": "pass" if swarm_data.get("avg", 1) < 5000 else "warn",
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def record_swarm_operation(name: str, latency_ms: float, success: bool) -> None:
    """Shortcut für Swarm-Operation-Metriken."""
    record_metric(
        "swarm",
        name,
        latency_ms,
        tags={"success": "1" if success else "0"},
    )


def generate_report() -> str:
    """Menschlesbarer Report für CLI."""
    metrics = get_metrics()
    lines = [
        "╔══════════════════════════════════════════════╗",
        "║       SWARM METRICS DASHBOARD               ║",
        "╚══════════════════════════════════════════════╝",
        "",
        f"  Total Records: {metrics['total_records']}",
        f"  Collected at:  {metrics['collected_at']}",
        "",
    ]

    for cat, data in metrics.get("metrics", {}).items():
        lines.append(f"── {cat.upper()} ──")
        lines.append(f"  Avg:    {data['avg']}")
        lines.append(f"  Min:    {data['min']}")
        lines.append(f"  Max:    {data['max']}")
        lines.append(f"  Last:   {data['last']} ({data['last_name']})")
        lines.append(f"  Count:  {data['count']}")
        lines.append("")

    # Spezifisch Swarm
    swarm = get_swarm_summary()
    badge = "✅" if swarm["health"] == "pass" else "⚠️"
    lines.append(f"── SWARM HEALTH ──")
    lines.append(f"  {badge} Avg Latency: {swarm['avg_latency_ms']}ms")
    lines.append(f"  {badge} Max Latency: {swarm['max_latency_ms']}ms")
    lines.append(f"  {badge} Operations:  {swarm['total_operations']}")

    return "\n".join(lines)


def run_cron_entry() -> str:
    """Cron-kompatibler Einstieg."""
    report = generate_report()
    logfile = _logs_dir() / f"swarm-metrics-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(logfile, "w", encoding="utf-8") as f:
        f.write(report)
    return str(logfile)