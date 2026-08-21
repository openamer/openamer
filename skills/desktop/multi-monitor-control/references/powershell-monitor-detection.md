# PowerShell Monitor Detection — Technische Referenz

## Win32 API: ctypes (primär)

Das Python-Skript `multi-monitor.py` verwendet `EnumDisplayMonitors` und
`GetMonitorInfoW` aus `user32.dll` via ctypes:

```c
BOOL EnumDisplayMonitors(
  HDC             hdc,          // NULL = alle Monitore
  LPCRECT         lprcClip,     // NULL = keine Einschränkung
  MONITORENUMPROC lpfnEnum,     // Callback pro Monitor
  LPARAM          dwData        // user data
);
```

Der Callback erhält pro Monitor:
- `hMonitor` — Handle für `GetMonitorInfoW`
- `lprcMonitor` — Bounding Rect des Monitors im virtuellen Desktop

```c
BOOL GetMonitorInfoW(
  HMONITOR         hMonitor,
  LPMONITORINFOEXW lpmi         // rcMonitor, rcWork, dwFlags, szDevice
);
```

Wichtige Felder in `MONITORINFOEXW`:
- `rcMonitor` — gesamter Monitor-Bereich (x, y, right, bottom)
- `rcWork` — Arbeitsbereich (exklusive Taskleiste)
- `dwFlags` — `MONITORINFOF_PRIMARY` (0x00000001) für Primary Monitor
- `szDevice` — Device-Name (z.B. `\\.\DISPLAY1`)

## .NET / PowerShell (Fallback)

```powershell
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Screen]::AllScreens
```

Jeder `Screen` hat:
- `Bounds` — Rectangle mit X, Y, Width, Height
- `WorkingArea` — Rectangle ohne Taskleiste
- `Primary` — bool
- `DeviceName` — z.B. `\\.\DISPLAY1`
- `BitsPerPixel` — Farbtiefe

**Wichtig bei Bash-Einbettung:** Da Git-Bash `$_.Property` als Bash-Variable
interpretiert, muss man entweder:
1. Ein `.ps1`-Skript ausführen (empfohlen)
2. Single-Quotes im PowerShell String verwenden: `'$_'`

```bash
# NICHT so (Bash ersetzt $_):
powershell.exe -Command "Get-CimInstance ... | ForEach-Object { $_.Name }"

# SONDERN so (.ps1 Datei):
powershell.exe -File "C:\...\detect-monitors.ps1"
```

## cua-driver und Multi-Monitor

Der cua-driver `computer_use` kann **kein Multi-Monitor-Capture** durchführen.
`app='screen'` erfasst nur den PRIMARY Monitor.

### Strategie A: Absolute Koordinaten (Pixel-Klick)

```python
mgr = MonitorManager()
sec = mgr.secondary_monitors[0]
# Absolute Koordinate im virtuellen Desktop
abs_x = sec.x + 500  # 500px vom linken Rand des Secondary
abs_y = sec.y + 300  # 300px vom oberen Rand des Secondary
computer_use(action="click", coordinate=[abs_x, abs_y])
```

### Strategie B: App auf Secondary starten (zuverlässiger)

```python
# Chrome auf Secondary starten (window-position = Secondary X-Offset)
terminal('"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --new-window --window-position=1920,0 "https://example.com"')
# Dann via App-Namen capturen — egal auf welchem Monitor
computer_use(action="capture", app="Chrome")
```

### Strategie C: Fenster verschieben

```powershell
# Fenster mit PowerShell auf Secondary verschieben
powershell.exe -Command "
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport(\"user32.dll\")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
    [DllImport(\"user32.dll\")] public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
}
'@
$hwnd = [Win32]::FindWindow(null, \"FensterTitel\")
# Move to Secondary (z.B. 1920,0 → 3840,1080 bei 1920er Monitoren)
[Win32]::SetWindowPos($hwnd, 0, 1920, 0, 1920, 1080, 0x0040)
"
```

## Koordinaten-Transformation — Mathematik

Der virtuelle Desktop ist die Vereinigung aller Monitore.
Monitore können beliebig angeordnet sein:

```
Monitor 1 (Primary)   Monitor 2 (Secondary)
(0,0)                 (1920, 0)
┌─────────┐           ┌─────────┐
│         │           │         │
│ 1920x1080│           │ 1920x1080│
│         │           │         │
└─────────┘           └─────────┘
(1920,1080)           (3840,1080)
```

**Formel:** Ein Punkt bei (x_rel, y_rel) relativ zum Primary-Monitor
wird zu absoluten Koordinaten transformiert:

```
abs_x = primary.x + x_rel
abs_y = primary.y + y_rel
```

**Für Secondary-Zugriff:** Die absolute Koordinate muss im Bounds
des Secondary liegen, also:

```
abs_x ∈ [sec.x, sec.right - 1]
abs_y ∈ [sec.y, sec.bottom - 1]
```

## WMI-Alternative (nicht .NET)

```powershell
# Basis-Info (oft leer/ungenau bei modernen GPUs)
Get-CimInstance Win32_DesktopMonitor | Select-Object *
# → ScreenWidth/ScreenHeight sind oft leer (UEFI/DP GOP Treiber)

# Genauer: Win32_VideoController
Get-CimInstance Win32_VideoController | Select-Object Name, VideoModeDescription, CurrentHorizontalResolution, CurrentVerticalResolution
```

`Win32_DesktopMonitor` liefert auf modernen Systemen oft keine Auflösung,
weil der Monitor nicht über VESA EDID vom Treiber gemeldet wird.
`System.Windows.Forms.Screen.AllScreens` oder die Win32 `EnumDisplayMonitors`
API sind zuverlässiger.

## Debugging

```bash
# 1. Python-Skript mit JSON
python /c/Users/damir/AppData/Local/openamer-laptop/scripts/multi-monitor.py --json

# 2. PowerShell direkt
powershell.exe -File "C:\Users\damir\AppData\Local\openamer-laptop\scripts\detect-monitors.ps1"

# 3. cua-driver Capture testen
computer_use(action="capture", app="screen")

# 4. cua-driver Health
openamer computer-use doctor
```