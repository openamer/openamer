---
name: multi-monitor-control
description: Use when driving two monitors on Windows with cua-driver.
version: 1.0.0
platforms: [windows]
metadata:
  openamer:
    tags: [windows, multi-monitor, dual-monitor, computer-use, cua-driver, desktop-automation]
    category: desktop
    related_skills: [windows-computer-use, computer-use]
---

# Multi-Monitor Desktop Control

Erkenne alle aktiven Monitore auf Windows, transformiere Koordinaten
zwischen Primary und Secondary Monitoren, und steuere beide Monitore
via cua-driver (`computer_use`).

## Architektur

```
Python (multi-monitor.py)
  ├── ctypes (EnumDisplayMonitors + GetMonitorInfoW)  ← primär
  └── PowerShell Fallback (System.Windows.Forms.Screen) ← sekundär

MonitorManager
  ├── monitors[]           → Liste aller Monitore mit Position & Größe
  ├── virtual_desktop      → Vereinigung aller Monitore
  ├── transform_to_monitor → Koordinaten-Transformation
  └── get_capture_region   → Region für cua-driver capture
```

## Quick Start

### 1. Monitor-Erkennung

```bash
# Menschlesbarer Report
python /c/Users/damir/AppData/Local/openamer-laptop/scripts/multi_monitor.py

# Maschinenlesbares JSON
python /c/Users/damir/AppData/Local/openamer-laptop/scripts/multi_monitor.py --json

# Info über Monitor 2
python /c/Users/damir/AppData/Local/openamer-laptop/scripts/multi_monitor.py --monitor 2
```

### 2. Koordinaten-Transformation

Wenn Monitor 1 (primary) 1920x1080 bei (0,0) ist
und Monitor 2 (secondary) 1920x1080 rechts daneben bei (1920,0):

```bash
# Transformiere Primary-Koordinate (100, 50) auf Virtual Desktop
python multi_monitor.py --transform 100 50
# → Quell: (100, 50) → Ziel: (2020, 50) auf Monitor 2
```

### 3. cua-driver mit Dual-Monitor

**Aktuelle Limitation:** `computer_use(action='capture', app='screen')` erfasst
nur den PRIMARY Monitor. Der Secondary Monitor ist im Capture unsichtbar.

**Workaround — Koordinaten-Klick auf Secondary:**

```python
# 1. Monitor-Topologie abfragen
from scripts.multi_monitor import get_secondary_region, coordinate_transform

region = get_secondary_region()
# → {'x': 1920, 'y': 0, 'width': 1920, 'height': 1080, 'device_name': r'\\.\DISPLAY2'}

# 2. Koordinate auf Secondary transformieren
abs_x, abs_y = coordinate_transform(from_x=100, from_y=50, target_monitor=2)
# → (2020, 50)

# 3. Klick auf Secondary via absolute Koordinaten
computer_use(action="click", coordinate=[abs_x, abs_y])
```

## Vollständiger Dual-Monitor-Workflow

```python
# Schritt 1: Monitore erkennen
import sys
sys.path.insert(0, r"C:\Users\damir\AppData\Local\openamer-laptop\scripts")
from multi_monitor import MonitorManager

mgr = MonitorManager()
print(f"Monitore: {mgr.count}")
print(f"Secondary: {mgr.has_secondary}")

if not mgr.has_secondary:
    print("⚠️  Nur ein Monitor aktiv.")
    # Normalen cua-driver flow verwenden
    computer_use(action="capture", app="screen")
else:
    # Schritt 2: Koordinate auf Secondary vorbereiten
    sec = mgr.secondary_monitors[0]
    target_x = sec.x + 500   # 500px vom linken Rand des Secondary
    target_y = sec.y + 300   # 300px vom oberen Rand des Secondary

    # Schritt 3: Aktion auf Secondary
    computer_use(action="capture", app="screen")
    # → Zeigt nur Primary

    # Schritt 4: Klick auf Secondary mit absoluten Koordinaten
    computer_use(action="click", coordinate=[target_x, target_y], capture_after=True)
```

## PowerShell Direktzugriff (für Terminal / Scripting)

```powershell
# Alle Monitore mit Bounds
powershell.exe -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens | ForEach-Object { Write-Host ($_.DeviceName + ': ' + $_.Bounds.Width + 'x' + $_.Bounds.Height + ' at (' + $_.Bounds.X + ',' + $_.Bounds.Y + ') Primary=' + $_.Primary) }"

# JSON-Ausgabe
powershell.exe -File "C:\Users\damir\AppData\Local\openamer-laptop\scripts\detect-monitors.ps1"
```

## cua-driver: App-spezifisch auf Secondary

Wenn eine App auf dem Secondary Monitor läuft, kann man sie direkt ansprechen:

```python
# App auf Secondary starten
terminal('"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --new-window --window-position=1920,0 "https://example.com"')

# Dann via app= Namen capturen
computer_use(action="capture", app="Chrome")
# → Erfasst das Chrome-Fenster, egal auf welchem Monitor
```

Dies ist der **zuverlässigste** Weg für Dual-Monitor — starte die App
mit `--window-position=MONITOR2_X,0` auf dem Secondary und capture
dann via `app=` Name, nicht via `app='screen'`.

## API-Referenz (Python-Modul)

### `MonitorManager`

| Methode | Beschreibung |
|---------|-------------|
| `refresh()` | Monitor-Topologie neu erkennen |
| `has_secondary` | True wenn ≥2 Monitore |
| `count` | Anzahl Monitore |
| `get_monitor(index)` | Monitor per 1-basiertem Index |
| `get_monitor_at(x, y)` | Monitor der Punkt enthält |
| `transform_to_monitor(target, x, y, from_primary=True)` | Koordinate transformieren |
| `get_capture_region(index)` | Bounds eines Monitors |
| `summary()` | Menschlesbarer Report |
| `json_output()` | JSON-Darstellung |

### Freie Funktionen

| Funktion | Beschreibung |
|----------|-------------|
| `detect_monitors()` | Nur Monitor-Liste |
| `coordinate_transform(x, y, target_monitor=2)` | Kurzform |
| `get_secondary_region()` | Region des 2. Monitors |

## Fehlerbehandlung

- **Kein Secondary:** `has_secondary` ist `False`, `transform_to_monitor(2)` wirft `ValueError`
- **ctypes-Fallback:** Falls WinAPI versagt, wird PowerShell verwendet
- **Letzter Fallback:** 1 Pseudomonitor (1920x1080) als Notlösung

## Bekannte Limitationen

1. `computer_use(action='capture', app='screen')` zeigt nur den PRIMARY Monitor
2. Koordinaten-Klicks auf Secondary sind absolute Pixel-Koordinaten, nicht SOM-Elemente
3. Nach Navigation auf Secondary muss die Koordinate neu berechnet werden (re-capture)
4. Chromium-Scroll auf Windows benötigt `delivery_mode='foreground'` (siehe windows-computer-use Skill)
5. Der cua-driver unterstützt kein Multi-Monitor-Capture — man muss pro Monitor arbeiten

## Siehe auch

- `windows-computer-use` Skill — Chromium Scroll, UIA Quirks, Edge Problematik
- `computer-use` Skill — Canonical Cross-Plattform cua-driver Workflow
- `C:\Users\damir\AppData\Local\openamer-laptop\scripts\multi_monitor.py` — Das Skript
- `C:\Users\damir\AppData\Local\openamer-laptop\scripts\detect-montors.ps1` — PowerShell Helper