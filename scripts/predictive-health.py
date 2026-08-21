#!/usr/bin/env python3
"""
Predictive Health Monitor v1.0
==============================
ML-basierte Vorhersage von Systemproblemen:
- Sammlung: Systemmetriken (RAM, Disk, CPU, Cron-Exit-Codes) in CSV-Historie
- Trend-Analyse: Lineare Regression → Vorhersage für +24h
- Anomalie-Detektion: Abweichung > 2σ vom gleitenden Mittelwert
- Disk-Volllauf-Prognose: Wachstumsrate der letzten 7 Tage → predicted_full_date
- Daemon-Modus: --watch alle 5 Minuten

CLI:
  --collect      Sammelt aktuelle Metriken und hängt an history.csv an
  --predict      Führt Trend-Analyse, Anomalie-Detektion, Disk-Prognose aus
  --report       JSON-Report auf stdout ausgeben
  --watch        Daemon-Modus (alle 5min collect+predict+report)
  --daemon       Alias für --watch

Exit-Codes:
  0 = Alles gut (keine Trends, keine Anomalien, kein Disk-Risiko)
  1 = Trend steigend (RAM/Disk-Verbrauch steigt)
  2 = Anomalie erkannt (Wert > 2σ vom Mittel)
  3 = Kritische Vorhersage (Disk-Volllauf < 30 Tage)

Keine externen Dependencies — nur Python-Standardbibliothek.
"""

import csv
import json
import math
import os
import signal
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Pfade ──────────────────────────────────────────────────────────────────
HOME = Path.home()
OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    HOME / "AppData" / "Local" / "openamer-laptop",
))
DATA_DIR = OPENAMER_HOME / ".predictive-health"
HISTORY_CSV = DATA_DIR / "history.csv"
MAX_ROWS = 10000


# ── Metrik-Sammlung ─────────────────────────────────────────────────────────
def get_ram_usage() -> float:
    """Gibt RAM-Nutzung in Prozent zurück (0.0 – 100.0)."""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        total = 0
        available = 0
        for line in lines:
            if line.startswith("MemTotal:"):
                total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                available = int(line.split()[1])
            if total and available:
                break
        if total:
            return round((1 - available / total) * 100, 1)
    except (FileNotFoundError, ValueError, OSError):
        pass

    # Fallback: Windows via wmic
    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "OS", "get", "TotalVisibleMemorySize,FreePhysicalMemory", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            for line in lines:
                parts = line.split(",")
                if len(parts) >= 3:
                    try:
                        total_kb = int(parts[-2])
                        free_kb = int(parts[-1])
                        if total_kb:
                            return round((1 - free_kb / total_kb) * 100, 1)
                    except (ValueError, IndexError):
                        continue
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    # Letzter Fallback: psutil (nur wenn zufällig installiert)
    try:
        import psutil
        return psutil.virtual_memory().percent
    except ImportError:
        pass

    return 0.0


def get_disk_usage() -> float:
    """Gibt Festplatten-Nutzung in Prozent zurück (0.0 – 100.0)."""
    # Windows: Prüfe C: (Systemlaufwerk)
    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "LogicalDisk", "where", "Name='C:'",
             "get", "Size,FreeSpace", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            for line in lines:
                parts = line.split(",")
                if len(parts) >= 3:
                    try:
                        total_b = int(parts[-2])
                        free_b = int(parts[-1])
                        if total_b:
                            return round((1 - free_b / total_b) * 100, 1)
                    except (ValueError, IndexError):
                        continue
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    # Linux
    try:
        st = os.statvfs("/")
        total = st.f_frsize * st.f_blocks
        free = st.f_frsize * st.f_bfree
        if total:
            return round((1 - free / total) * 100, 1)
    except AttributeError:
        pass

    try:
        import psutil
        return psutil.disk_usage("/").percent
    except ImportError:
        pass

    return 0.0


def get_cpu_usage() -> float:
    """Gibt CPU-Auslastung in Prozent zurück."""
    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "path", "Win32_PerfFormattedData_PerfOS_Processor",
             "get", "PercentProcessorTime", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            for line in lines:
                parts = line.split(",")
                for p in parts:
                    try:
                        val = float(p)
                        if 0 <= val <= 100:
                            return round(val, 1)
                    except ValueError:
                        continue
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "cpu", "get", "loadpercentage", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and l.strip().isdigit()]
            if lines:
                return round(float(lines[0]), 1)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    import subprocess
    import os
    # Linux: /proc/stat
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()
        if len(parts) >= 5:
            total = sum(int(p) for p in parts[1:])
            idle = int(parts[4])
            # Kurze Messung über 1s
            time.sleep(0.5)
            with open("/proc/stat") as f:
                line = f.readline()
            parts2 = line.split()
            total2 = sum(int(p) for p in parts2[1:])
            idle2 = int(parts2[4])
            delta_total = total2 - total
            delta_idle = idle2 - idle
            if delta_total:
                return round((1 - delta_idle / delta_total) * 100, 1)
    except (FileNotFoundError, ValueError, OSError):
        pass

    try:
        import psutil
        return psutil.cpu_percent(interval=0.5)
    except ImportError:
        pass

    return 0.0


def get_cron_exit_codes() -> list[dict]:
    """Sammelt letzte Cron-Exit-Codes aus dem Cron-Output-Verzeichnis."""
    exits = []
    cron_out = OPENAMER_HOME / "cron" / "output"
    if not cron_out.exists():
        return exits
    try:
        files = sorted(cron_out.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:50]
    except OSError:
        return exits
    for f in files:
        if f.suffix == ".txt" and f.stem.startswith("cron-"):
            # Dateiname enthält Timestamp
            parts = f.stem.replace("cron-", "", 1).split("-", 1)
            timestamp = parts[0] if parts else ""
            job_name = parts[1] if len(parts) > 1 else f.stem
            # Letzten Exit-Code aus Datei lesen
            try:
                content = f.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            lines = content.splitlines()
            exit_code = None
            for line in reversed(lines):
                m = re.search(r"exit[=_ ]?code[=: ]?(\d+)", line, re.IGNORECASE)
                if m:
                    exit_code = int(m.group(1))
                    break
            exits.append({
                "job": job_name,
                "timestamp": timestamp,
                "exit_code": exit_code,
            })
    return exits


def collect_metrics() -> dict:
    """Sammelt alle Systemmetriken und gibt sie als Dict zurück."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ram_pct": get_ram_usage(),
        "disk_pct": get_disk_usage(),
        "cpu_pct": get_cpu_usage(),
        "cron_exits": get_cron_exit_codes(),
    }


# ── CSV-Historie ────────────────────────────────────────────────────────────
def append_to_history(metrics: dict) -> None:
    """Hängt Metriken an history.csv an (append, max 10.000 Zeilen)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    file_exists = HISTORY_CSV.exists()
    ts = metrics["timestamp"]
    cron_exits = metrics.get("cron_exits", [])
    cron_exit_summary = ";".join(
        f"{e['job']}={e['exit_code']}" for e in cron_exits if e["exit_code"] is not None
    )

    row = {
        "timestamp": ts,
        "ram_pct": metrics["ram_pct"],
        "disk_pct": metrics["disk_pct"],
        "cpu_pct": metrics["cpu_pct"],
        "cron_exits": cron_exit_summary,
    }

    with open(HISTORY_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    # Zeilenbegrenzung durchsetzen
    trim_history()


def trim_history(max_rows: int = MAX_ROWS) -> None:
    """Behält nur die letzten max_rows Zeilen in history.csv."""
    if not HISTORY_CSV.exists():
        return
    try:
        with open(HISTORY_CSV, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if len(rows) <= max_rows:
            return
        rows = rows[-max_rows:]
        with open(HISTORY_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    except (csv.Error, OSError):
        pass


def load_history(column: str = "ram_pct", max_rows: int = 1000) -> tuple[list[float], list[str]]:
    """Lädt Historien-Werte + Timestamps für eine Spalte."""
    if not HISTORY_CSV.exists():
        return [], []

    try:
        with open(HISTORY_CSV, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            all_rows = list(reader)
    except (csv.Error, OSError):
        return [], []

    if not all_rows:
        return [], []

    rows = all_rows[-max_rows:]
    values = []
    timestamps = []
    for r in rows:
        try:
            val = float(r.get(column, ""))
            values.append(val)
            timestamps.append(r.get("timestamp", ""))
        except (ValueError, TypeError):
            continue

    return values, timestamps


# ── Lineare Regression ──────────────────────────────────────────────────────
def linear_regression(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """Berechnet lineare Regression y = slope * x + intercept.
    Gibt (slope, intercept, r_squared) zurück."""
    n = len(x)
    if n < 2:
        return 0.0, (y[0] if y else 0.0), 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denom = sum((x[i] - mean_x) ** 2 for i in range(n))

    if denom == 0:
        return 0.0, mean_y, 0.0

    slope = num / denom
    intercept = mean_y - slope * mean_x

    # R² berechnen
    ss_tot = sum((y[i] - mean_y) ** 2 for i in range(n))
    ss_res = sum((y[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return slope, intercept, r_squared


def predict_future(values: list[float], hours_ahead: int = 24, interval_minutes: int = 30) -> tuple[float, float, float, float]:
    """Prognostiziert Wert in hours_ahead Stunden.
    values: Liste von Messwerten im Abstand von interval_minutes.
    Gibt (predicted_value, slope, intercept, r_squared) zurück."""
    if len(values) < 2:
        return values[-1] if values else 0.0, 0.0, 0.0, 0.0

    # x = Index (0, 1, 2, ...) normiert auf Stunden
    x = [(i * interval_minutes) / 60.0 for i in range(len(values))]
    y = values

    slope, intercept, r_squared = linear_regression(x, y)

    # Vorhersage für +hours_ahead Stunden
    future_x = (len(values) * interval_minutes / 60.0) + hours_ahead
    predicted = slope * future_x + intercept

    return predicted, slope, intercept, r_squared


# ── Anomalie-Detektion ──────────────────────────────────────────────────────
def detect_anomalies(values: list[float], threshold_sigma: float = 2.0) -> list[dict]:
    """Erkennt Anomalien: Werte > threshold_sigma vom gleitenden Mittelwert.
    Gibt Liste von Dicts mit {'index', 'value', 'mean', 'std', 'z_score'}."""
    if len(values) < 5:
        return []

    anomalies = []
    # Gleitender Mittelwert (Fenster = min(20, len/2))
    window = min(20, max(5, len(values) // 4))

    for i in range(len(values)):
        if i < window:
            continue
        segment = values[i - window:i]
        mean = statistics.mean(segment)
        std = statistics.stdev(segment) if len(segment) > 1 else 1.0
        if std == 0:
            continue
        z = (values[i] - mean) / std
        if abs(z) > threshold_sigma:
            anomalies.append({
                "index": i,
                "value": round(values[i], 1),
                "mean": round(mean, 1),
                "std": round(std, 1),
                "z_score": round(z, 2),
                "direction": "up" if z > 0 else "down",
            })

    return anomalies


# ── Disk-Volllauf-Prognose ──────────────────────────────────────────────────
def predict_disk_full(disk_values: list[float], timestamps: list[str], max_disk_pct: float = 95.0) -> dict:
    """Prognostiziert Datum des Disk-Volllaufs anhand der letzten 7 Tage Wachstumsrate.
    Gibt Dict mit {'predicted_full_date', 'days_until_full', 'growth_per_day', 'disk_pct', 'at_risk'}."""
    if len(disk_values) < 3 or len(timestamps) < 3:
        return {"predicted_full_date": None, "days_until_full": None,
                "growth_per_day": None, "disk_pct": disk_values[-1] if disk_values else 0,
                "at_risk": False}

    current_disk = disk_values[-1]

    # Nur letzte 7 Tage an Daten (ca. 336 Einträge bei 30min-Intervall)
    # Beschränkung auf ~336 Datenpunkte
    recent = disk_values[-336:]
    recent_ts = timestamps[-336:]

    # Prüfe ob überhaupt genug Range da ist
    if len(recent) < 3:
        return {"predicted_full_date": None, "days_until_full": None,
                "growth_per_day": None, "disk_pct": current_disk, "at_risk": False}

    # Analyse über mehrere Zeitfenster
    # 1. Letzte 24h (48 Einträge)
    # 2. Letzte 3 Tage (144 Einträge)
    # 3. Letzte 7 Tage (336 Einträge)

    windows = {
        "24h": min(48, len(recent)),
        "3d": min(144, len(recent)),
        "7d": min(336, len(recent)),
    }

    best_growth = None
    max_conf_keys = []

    for name, size in windows.items():
        if size < 3:
            continue
        segment = recent[-size:]
        y = segment
        x = [i for i in range(len(segment))]
        slope, intercept, r2 = linear_regression(x, y)
        if slope > 0 and r2 > 0.3:
            if best_growth is None or r2 > best_growth["r2"]:
                best_growth = {
                    "window": name,
                    "slope": slope,
                    "r2": r2,
                    "growth_per_day": slope * 48,  # 48 Einträge = 24h
                }
            if r2 > 0.5:
                max_conf_keys.append(name)

    if best_growth is None:
        return {"predicted_full_date": None, "days_until_full": None,
                "growth_per_day": None, "disk_pct": current_disk, "at_risk": False}

    growth_per_day = best_growth["growth_per_day"]

    # Wachstum pro Tag > 0?
    if growth_per_day <= 0:
        return {"predicted_full_date": None, "days_until_full": None,
                "growth_per_day": None, "disk_pct": current_disk, "at_risk": False}

    remaining_pct = max_disk_pct - current_disk
    if remaining_pct <= 0:
        # Disk ist schon voll
        days_until_full = 0
    else:
        days_until_full = max(0, int(remaining_pct / growth_per_day))

    # Berechne predicted_full_date
    now = datetime.now(timezone.utc)
    last_ts_str = timestamps[-1]
    try:
        last_ts = datetime.fromisoformat(timestamps[-1])
    except (ValueError, TypeError):
        last_ts = now

    if days_until_full is not None:
        predicted_date = (now + timedelta(days=days_until_full)).isoformat()[:10]
    else:
        predicted_date = None

    at_risk = days_until_full is not None and days_until_full <= 30

    return {
        "predicted_full_date": predicted_date,
        "days_until_full": days_until_full,
        "growth_per_day": round(growth_per_day, 3),
        "disk_pct": current_disk,
        "max_disk_pct": max_disk_pct,
        "at_risk": at_risk,
        "confidence_window": best_growth["window"],
        "r2": round(best_growth["r2"], 3),
    }


# ── Trend-Analyse ───────────────────────────────────────────────────────────
def analyze_trend(column: str, label: str, hours_ahead: int = 24) -> dict:
    """Führt Trend-Analyse für eine Metrik durch.
    Gibt Dict mit {'label', 'current', 'predicted', 'slope', 'r_squared', 'direction', 'trend'}."""
    values, timestamps = load_history(column)
    if len(values) < 2:
        return {
            "label": label,
            "current": values[-1] if values else 0,
            "predicted": None,
            "slope": 0,
            "r_squared": 0,
            "direction": "stable",
            "trend": "insufficient_data",
        }

    predicted, slope, intercept, r_squared = predict_future(values, hours_ahead)

    # Trend-Richtung
    direction = "stable"
    threshold = 0.01  # 0.01% pro Stunde als Mindest-Steigung
    if slope > threshold:
        direction = "rising"
    elif slope < -threshold:
        direction = "falling"

    # Steigend/fallend qualifizieren
    if direction == "rising" and r_squared > 0.5:
        trend = "rising_significant"
    elif direction == "rising":
        trend = "rising_weak"
    elif direction == "falling" and r_squared > 0.5:
        trend = "falling_significant"
    elif direction == "falling":
        trend = "falling_weak"
    else:
        trend = "stable"

    return {
        "label": label,
        "current": round(values[-1], 1),
        "predicted": round(predicted, 1) if predicted else None,
        "slope": round(slope, 4),
        "r_squared": round(r_squared, 3),
        "direction": direction,
        "trend": trend,
        "data_points": len(values),
    }


# ── Report ──────────────────────────────────────────────────────────────────
def generate_report() -> dict:
    """Generiert vollständigen JSON-Report."""
    # Aktuelle Metriken sammeln
    metrics = collect_metrics()

    # Trends analysieren
    ram_trend = analyze_trend("ram_pct", "RAM")
    disk_trend = analyze_trend("disk_pct", "Disk")
    cpu_trend = analyze_trend("cpu_pct", "CPU")

    # Anomalien erkennen
    ram_values, _ = load_history("ram_pct")
    disk_values, _ = load_history("disk_pct")
    cpu_values, _ = load_history("cpu_pct")

    ram_anomalies = detect_anomalies(ram_values)
    disk_anomalies = detect_anomalies(disk_values)
    cpu_anomalies = detect_anomalies(cpu_values)

    # Disk-Volllauf-Prognose
    disk_values_for_pred, disk_timestamps = load_history("disk_pct")
    disk_full = predict_disk_full(disk_values_for_pred, disk_timestamps)

    # Exit-Code bestimmen
    exit_code = compute_exit_code(ram_trend, disk_trend, cpu_trend, disk_full)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
        "metrics": {
            "ram_pct": metrics["ram_pct"],
            "disk_pct": metrics["disk_pct"],
            "cpu_pct": metrics["cpu_pct"],
        },
        "trends": {
            "ram": ram_trend,
            "disk": disk_trend,
            "cpu": cpu_trend,
        },
        "anomalies": {
            "ram": ram_anomalies,
            "disk": disk_anomalies,
            "cpu": cpu_anomalies,
        },
        "disk_full_prediction": disk_full,
        "cron_health": {
            "recent_exits": metrics.get("cron_exits", []),
        },
    }

    return report


def compute_exit_code(ram_trend: dict, disk_trend: dict, cpu_trend: dict,
                       disk_full: dict) -> int:
    """Berechnet Exit-Code basierend auf Analyseergebnissen:
    0 = Alles gut
    1 = Trend steigend
    2 = Anomalie erkannt
    3 = Kritische Vorhersage (Disk-Volllauf < 30 Tage)
    """
    # Prüfung 3: Kritische Disk-Prognose
    if disk_full.get("at_risk") or (disk_full.get("days_until_full") is not None
                                     and disk_full["days_until_full"] <= 30):
        return 3

    # Prüfung 2: Anomalien
    for trend in [ram_trend, disk_trend, cpu_trend]:
        if trend.get("trend") in ("rising_significant",):
            return 2

    # Prüfung 1: Trend steigend
    for trend in [ram_trend, disk_trend, cpu_trend]:
        if trend.get("direction") == "rising":
            return 1

    return 0


# ── Daemon-Modus ────────────────────────────────────────────────────────────
def daemon_loop(interval_minutes: int = 5) -> None:
    """Daemon-Modus: Sammelt Metriken alle interval_minutes und erstellt Reports."""
    pid_file = DATA_DIR / "predictive-health.pid"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # PID speichern für sauberes Beenden
    pid_file.write_text(str(os.getpid()))
    print(f"[PredictiveHealth] Daemon gestartet (PID={os.getpid()}), "
          f"Intervall={interval_minutes}min, Daten={DATA_DIR}")

    # Signal-Handler für sauberes Beenden
    shutdown_flag = False

    def handle_signal(signum, frame):
        nonlocal shutdown_flag
        shutdown_flag = True
        print(f"\n[PredictiveHealth] Signal {signum} empfangen, fahre herunter...")

    signal.signal(signal.SIGTERM, handle_signal)
    try:
        signal.signal(signal.SIGINT, handle_signal)
    except (AttributeError, ValueError):
        pass

    try:
        while not shutdown_flag:
            try:
                # Sammeln
                metrics = collect_metrics()
                append_to_history(metrics)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] "
                      f"RAM={metrics['ram_pct']}% "
                      f"Disk={metrics['disk_pct']}% "
                      f"CPU={metrics['cpu_pct']}%")

                # Analyse
                report = generate_report()
                if report["exit_code"] != 0:
                    print(f"⚠  Exit-Code={report['exit_code']}: "
                          f"{exit_code_message(report['exit_code'])}")

                    # Bei Anomalie Details ausgeben
                    for key in ("ram", "disk", "cpu"):
                        anoms = report["anomalies"].get(key, [])
                        if anoms:
                            for a in anoms[-3:]:
                                print(f"   Anomalie {key}: Wert={a['value']}% "
                                      f"(Mittel={a['mean']}%, Z={a['z_score']})")

                    # Bei Disk-Risiko warnen
                    dp = report.get("disk_full_prediction", {})
                    if dp.get("at_risk"):
                        print(f"   ⛔ DISK-VOLLLAUF-RISIKO: Noch ~{dp['days_until_full']} Tage "
                              f"(Wachstum {dp['growth_per_day']}%/Tag)")

                # Report als JSON speichern
                report_file = DATA_DIR / "latest_report.json"
                report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"[PredictiveHealth] Fehler im Sammelzyklus: {e}")

            time.sleep(interval_minutes * 60)
    finally:
        if pid_file.exists():
            pid_file.unlink()
        print("[PredictiveHealth] Daemon beendet.")


def exit_code_message(code: int) -> str:
    messages = {
        0: "Alles gut — keine Auffälligkeiten",
        1: "Trend steigend — Verbrauch nimmt zu",
        2: "Anomalie erkannt — ungewöhnliche Metrik-Abweichung",
        3: "Kritische Vorhersage — Disk-Volllauf < 30 Tage",
    }
    return messages.get(code, f"Unbekannter Exit-Code {code}")


# ── CLI ─────────────────────────────────────────────────────────────────────
def print_report(report: dict) -> None:
    """Gibt einen menschenlesbaren Report auf stdout aus."""
    ts = report["timestamp"][:19].replace("T", " ")
    print(f"\n{'='*60}")
    print(f"  Predictive Health Report — {ts}")
    print(f"{'='*60}")

    # Metriken
    m = report["metrics"]
    print(f"\n  Aktuelle Metriken:")
    print(f"    RAM:  {m['ram_pct']:>5.1f}%")
    print(f"    Disk: {m['disk_pct']:>5.1f}%")
    print(f"    CPU:  {m['cpu_pct']:>5.1f}%")

    # Trends
    print(f"\n  Trend-Analyse (+24h):")
    for key, t in report["trends"].items():
        arrow = {"rising": "↑", "falling": "↓", "stable": "→"}.get(t["direction"], "?")
        if t["predicted"] is not None:
            print(f"    {t['label']:5s}: {t['current']:>5.1f}% {arrow} {t['predicted']:>5.1f}%  "
                  f"(R²={t['r_squared']:.3f}, {t['trend']})")
        else:
            print(f"    {t['label']:5s}: {t['current']:>5.1f}%  — unzureichende Daten")

    # Anomalien
    has_anomaly = False
    for key, anoms in report["anomalies"].items():
        if anoms:
            has_anomaly = True
            break
    if has_anomaly:
        print(f"\n  Anomalien (>{2:.0f}σ):")
        for key, anoms in report["anomalies"].items():
            if not anoms:
                continue
            names = {"ram": "RAM", "disk": "Disk", "cpu": "CPU"}
            print(f"    {names.get(key, key)}:")
            for a in anoms[-5:]:
                print(f"      • Wert={a['value']}% (Mittel={a['mean']}%, "
                      f"Std={a['std']}%, Z={a['z_score']:.2f}, {a['direction']})")

    # Disk-Prognose
    dp = report.get("disk_full_prediction", {})
    if dp.get("predicted_full_date"):
        icon = "⛔" if dp.get("at_risk") else "ℹ"
        print(f"\n  Disk-Volllauf-Prognose:")
        print(f"    {icon} Aktuell: {dp['disk_pct']:.1f}%")
        print(f"    {icon} Wachstum: {dp['growth_per_day']:.3f}%/Tag")
        print(f"    {icon} Max: {dp['max_disk_pct']:.0f}%")
        print(f"    {icon} Voraussichtlich voll am: {dp['predicted_full_date']}")
        print(f"    {icon} Noch ~{dp['days_until_full']} Tage")
        print(f"    {icon} Konfidenz: Fenster={dp['confidence_window']}, R²={dp['r2']}")
        if dp.get("at_risk"):
            print(f"    ⚠ KRITISCH: Disk-Volllauf in < 30 Tagen!")
    else:
        print(f"\n  Disk-Volllauf-Prognose:")
        print(f"    — Keine ausreichenden Daten oder kein Wachstumstrend")

    # Exit-Code
    ec = report["exit_code"]
    print(f"\n  Exit-Code: {ec} — {exit_code_message(ec)}")
    print(f"{'='*60}\n")


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nVerwendung: predictive-health.py [--collect|--predict|--report|--watch|--daemon]")
        sys.exit(0)

    arg = sys.argv[1].lstrip("-").lower()

    if arg == "collect":
        metrics = collect_metrics()
        append_to_history(metrics)
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        print(f"\n→ Gespeichert in {HISTORY_CSV}")
        sys.exit(0)

    elif arg == "predict":
        report = generate_report()
        print_report(report)
        sys.exit(report["exit_code"])

    elif arg == "report":
        report = generate_report()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(report["exit_code"])

    elif arg in ("watch", "daemon"):
        interval = 5
        if len(sys.argv) > 2:
            try:
                interval = int(sys.argv[2])
            except ValueError:
                pass
        daemon_loop(interval)
        sys.exit(0)

    elif arg == "help" or arg == "--help":
        print(__doc__)
        sys.exit(0)

    else:
        print(f"Unbekanntes Argument: {sys.argv[1]}")
        print("Verwendung: --collect | --predict | --report | --watch [interval_min] | --daemon")
        sys.exit(1)


if __name__ == "__main__":
    main()