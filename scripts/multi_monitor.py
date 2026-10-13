#!/usr/bin/env python3
"""
multi-monitor.py — Multi-Monitor Desktop Control für OpenAmer Agent.

Erkennt Windows-Monitore via Win32 API (ctypes) und PowerShell,
berechnet Koordinaten-Transformationen und stellt eine API bereit,
die sowohl als CLI als auch als importierbares Modul nutzbar ist.

Architektur:
  - MonitorManager: Singleton-artige Klasse, die Monitor-Topologie cached
  - Koordinaten-Transformation: Primär → Sekundär, Pixel-Clamping
  - Fallback-Kette: ctypes (EnumDisplayMonitors) → PowerShell → .NET via subprocess
  - JSON-Ausgabe für programmatische Nutzung durch andere Tools / Skills

Usage:
  python multi-monitor.py                     # Human-readable Report
  python multi-monitor.py --json              # Maschinenlesbar (JSON)
  python multi-monitor.py --transform 1920 0  # Koordinate transformieren
  python multi-monitor.py --monitor 2          # Monitor 2 als Ziel setzen
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────
# Datenmodelle
# ──────────────────────────────────────────────


@dataclass
class MonitorInfo:
    """Ein einzelner Monitor mit Position, Auflösung und Metadaten."""
    device_name: str = ""
    width: int = 0
    height: int = 0
    x: int = 0
    y: int = 0
    working_width: int = 0
    working_height: int = 0
    working_x: int = 0
    working_y: int = 0
    primary: bool = False
    bits_per_pixel: int = 32
    is_mirrored: bool = False
    adapter_name: str = ""

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_name": self.device_name,
            "width": self.width,
            "height": self.height,
            "x": self.x,
            "y": self.y,
            "working_width": self.working_width,
            "working_height": self.working_height,
            "working_x": self.working_x,
            "working_y": self.working_y,
            "primary": self.primary,
            "right": self.right,
            "bottom": self.bottom,
            "center_x": self.center_x,
            "center_y": self.center_y,
        }


@dataclass
class VirtualDesktop:
    """Der virtuelle Desktop — die Vereinigung aller Monitore."""
    min_x: int = 0
    min_y: int = 0
    max_x: int = 0
    max_y: int = 0

    @property
    def width(self) -> int:
        return self.max_x - self.min_x

    @property
    def height(self) -> int:
        return self.max_y - self.min_y

    def to_dict(self) -> Dict[str, int]:
        return {
            "min_x": self.min_x,
            "min_y": self.min_y,
            "max_x": self.max_x,
            "max_y": self.max_y,
            "width": self.width,
            "height": self.height,
        }


# ──────────────────────────────────────────────
# Erkennungs-Engine
# ──────────────────────────────────────────────


class MonitorDetector:
    """Erkennt Monitore via Win32-ctypes, mit PowerShell-Fallback."""

    @staticmethod
    def _try_ctypes() -> Optional[List[MonitorInfo]]:
        """Versuche native Erkennung via ctypes + EnumDisplayMonitors."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

            # Typdefinitionen
            MONITORINFOF_PRIMARY = 1

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            class MONITORINFOEXW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32),
                ]

            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL,
                wintypes.HANDLE,
                wintypes.HDC,
                ctypes.POINTER(RECT),
                wintypes.LPARAM,
            )

            monitors: List[MonitorInfo] = []
            callback_data = {"monitors": monitors}

            @MONITORENUMPROC
            def monitor_enum_proc(
                hMonitor: int,
                hdcMonitor: int,
                lprcMonitor: ctypes.POINTER(RECT),
                dwData: int,
            ) -> bool:
                info = MONITORINFOEXW()
                info.cbSize = ctypes.sizeof(MONITORINFOEXW)
                ok = user32.GetMonitorInfoW(
                    wintypes.HANDLE(hMonitor),
                    ctypes.byref(info),
                )
                if ok:
                    mi = MonitorInfo(
                        device_name=info.szDevice.strip("\0"),
                        width=info.rcMonitor.right - info.rcMonitor.left,
                        height=info.rcMonitor.bottom - info.rcMonitor.top,
                        x=info.rcMonitor.left,
                        y=info.rcMonitor.top,
                        working_width=info.rcWork.right - info.rcWork.left,
                        working_height=info.rcWork.bottom - info.rcWork.top,
                        working_x=info.rcWork.left,
                        working_y=info.rcWork.top,
                        primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
                    )
                    callback_data["monitors"].append(mi)
                return True

            # EnumDisplayMonitors: hdc=NULL, lprcClip=NULL => alle Monitore
            result = user32.EnumDisplayMonitors(
                None, None, monitor_enum_proc, 0
            )

            if not result and ctypes.get_last_error() != 0:
                return None

            if not callback_data["monitors"]:
                return None

            return callback_data["monitors"]

        except Exception:
            return None

    @staticmethod
    def _try_powershell() -> Optional[List[MonitorInfo]]:
        """Fallback: PowerShell-Call via subprocess."""
        try:
            ps_script = """
            Add-Type -AssemblyName System.Windows.Forms
            $screens = [System.Windows.Forms.Screen]::AllScreens
            $result = @{ monitors = @() }
            foreach ($s in $screens) {
                $result.monitors += @{
                    deviceName = $s.DeviceName
                    width = $s.Bounds.Width
                    height = $s.Bounds.Height
                    x = $s.Bounds.X
                    y = $s.Bounds.Y
                    workingWidth = $s.WorkingArea.Width
                    workingHeight = $s.WorkingArea.Height
                    workingX = $s.WorkingArea.X
                    workingY = $s.WorkingArea.Y
                    primary = $s.Primary
                    bitsPerPixel = $s.BitsPerPixel
                }
            }
            Write-Host ($result | ConvertTo-Json -Compress)
            """
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            if proc.returncode != 0:
                return None

            out = proc.stdout.strip()
            # Extract JSON (PowerShell may emit warnings before it)
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("{"):
                    data = json.loads(line)
                    break
            else:
                return None

            monitors = []
            for m in data.get("monitors", []):
                monitors.append(MonitorInfo(
                    device_name=m.get("deviceName", ""),
                    width=m.get("width", 0),
                    height=m.get("height", 0),
                    x=m.get("x", 0),
                    y=m.get("y", 0),
                    working_width=m.get("workingWidth", 0),
                    working_height=m.get("workingHeight", 0),
                    working_x=m.get("workingX", 0),
                    working_y=m.get("workingY", 0),
                    primary=m.get("primary", False),
                    bits_per_pixel=m.get("bitsPerPixel", 32),
                ))
            return monitors

        except Exception:
            return None

    @staticmethod
    def detect() -> List[MonitorInfo]:
        """Erkenne alle Monitore. ctypes primär, PowerShell-Fallback."""
        monitors = MonitorDetector._try_ctypes()
        if monitors and len(monitors) > 0:
            return monitors
        monitors = MonitorDetector._try_powershell()
        if monitors and len(monitors) > 0:
            return monitors
        # Letzter Fallback: 1 Monitor annehmen (Primary)
        return [MonitorInfo(
            device_name=r"\\.\DISPLAY1",
            width=1920,
            height=1080,
            x=0, y=0,
            primary=True,
            working_width=1920,
            working_height=1040,
        )]


# ──────────────────────────────────────────────
# MonitorManager — zentrale API
# ──────────────────────────────────────────────


class MonitorManager:
    """Zentrale Klasse für Monitor-Topologie und Koordinaten-Transformation.

    Usage:
        mgr = MonitorManager()
        mgr.refresh()
        print(mgr.summary())
        coords = mgr.transform_to_monitor(2, x=1920, y=500)
        print(mgr.json_output())
    """

    def __init__(self, auto_refresh: bool = True):
        self.monitors: List[MonitorInfo] = []
        self.virtual_desktop: VirtualDesktop = VirtualDesktop()
        self._primary: Optional[MonitorInfo] = None
        if auto_refresh:
            self.refresh()

    def refresh(self) -> None:
        """Erkenne Monitore neu und aktualisiere VirtualDesktop + Primary."""
        self.monitors = MonitorDetector.detect()
        self._compute_virtual_desktop()
        self._primary = self._find_primary()

    @property
    def count(self) -> int:
        return len(self.monitors)

    @property
    def has_secondary(self) -> bool:
        """True wenn >= 2 aktive Monitore."""
        return self.count >= 2

    @property
    def primary(self) -> Optional[MonitorInfo]:
        return self._primary

    @property
    def secondary_monitors(self) -> List[MonitorInfo]:
        """Alle nicht-primären Monitore."""
        return [m for m in self.monitors if not m.primary]

    def _compute_virtual_desktop(self) -> None:
        if not self.monitors:
            self.virtual_desktop = VirtualDesktop()
            return
        xs = [m.x for m in self.monitors]
        ys = [m.y for m in self.monitors]
        rights = [m.right for m in self.monitors]
        bottoms = [m.bottom for m in self.monitors]
        self.virtual_desktop = VirtualDesktop(
            min_x=min(xs),
            min_y=min(ys),
            max_x=max(rights),
            max_y=max(bottoms),
        )

    def _find_primary(self) -> Optional[MonitorInfo]:
        for m in self.monitors:
            if m.primary:
                return m
        return self.monitors[0] if self.monitors else None

    def get_monitor(self, index: int) -> Optional[MonitorInfo]:
        """Monitor per 1-basiertem Index holen."""
        if 1 <= index <= len(self.monitors):
            return self.monitors[index - 1]
        return None

    def get_monitor_at(self, x: int, y: int) -> Optional[MonitorInfo]:
        """Finde Monitor, der den Punkt (x, y) enthält."""
        for m in self.monitors:
            if m.x <= x < m.right and m.y <= y < m.bottom:
                return m
        return None

    def transform_to_monitor(
        self, target_monitor: int,
        x: int = 0, y: int = 0,
        from_primary: bool = True,
    ) -> Tuple[int, int]:
        """Transformiere Koordinaten auf einen anderen Monitor.

        Args:
            target_monitor: 1-basierter Ziel-Monitor-Index
            x, y: Quell-Koordinaten
            from_primary: Wenn True, sind x,y relativ zum Primary-Monitor.
                          Wenn False, sind x,y virtuelle Desktop-Koordinaten.

        Returns:
            (absolute_x, absolute_y) — Koordinaten im virtuellen Desktop,
            begrenzt auf die Bounds des Ziel-Monitors.
        """
        target = self.get_monitor(target_monitor)
        if target is None:
            raise ValueError(f"Monitor {target_monitor} existiert nicht (max {self.count})")

        if from_primary and self._primary:
            # x,y sind relativ zum Primary → in absolute Koordinaten umwandeln
            abs_x = self._primary.x + x
            abs_y = self._primary.y + y
        else:
            abs_x = x
            abs_y = y

        # Auf Ziel-Monitor-Begrenzung clamps
        abs_x = max(target.x, min(abs_x, target.right - 1))
        abs_y = max(target.y, min(abs_y, target.bottom - 1))

        return (abs_x, abs_y)

    def transform_to_primary(
        self, x: int, y: int,
    ) -> Tuple[int, int]:
        """Wandle absolute Desktop-Koordinaten in Primary-relativ um."""
        if self._primary:
            return (x - self._primary.x, y - self._primary.y)
        return (x, y)

    def get_capture_region(self, monitor_index: int) -> Dict[str, int]:
        """Gebe die Bildschirm-Region für einen Monitor als Dict zurück.

        Diese Region kann verwendet werden um cua-driver auf diesen
        Monitor zu fokussieren (falls supported).
        """
        m = self.get_monitor(monitor_index)
        if m is None:
            raise ValueError(f"Monitor {monitor_index} nicht gefunden")
        return {
            "x": m.x,
            "y": m.y,
            "width": m.width,
            "height": m.height,
            "device_name": m.device_name,
        }

    def summary(self) -> str:
        """Menschlesbarer Report."""
        lines = []
        lines.append("=" * 60)
        lines.append("MULTI-MONITOR DETECTION REPORT")
        lines.append("=" * 60)
        lines.append(f"Total monitors: {self.count}")
        lines.append(f"Virtual Desktop: {self.virtual_desktop.width}x{self.virtual_desktop.height}")
        lines.append(f"  Bounds: ({self.virtual_desktop.min_x},{self.virtual_desktop.min_y}) to "
                     f"({self.virtual_desktop.max_x},{self.virtual_desktop.max_y})")
        lines.append("")

        for i, m in enumerate(self.monitors, 1):
            flags = " PRIMARY" if m.primary else ""
            lines.append(f"Monitor {i}{flags}:")
            lines.append(f"  Device : {m.device_name}")
            lines.append(f"  Bounds : {m.width}x{m.height} at ({m.x},{m.y})")
            lines.append(f"  Work   : {m.working_width}x{m.working_height} at ({m.working_x},{m.working_y})")
            lines.append(f"  Center : ({m.center_x},{m.center_y})")
            lines.append("")

        if self.secondary_monitors:
            lines.append("Coordinate Offsets (Primary → Secondary):")
            for m in self.secondary_monitors:
                if self._primary:
                    ox = m.x - self._primary.x
                    oy = m.y - self._primary.y
                else:
                    ox = m.x
                    oy = m.y
                lines.append(f"  {m.device_name}: offset=({ox:+d},{oy:+d}), "
                             f"region=({m.x},{m.y},{m.right},{m.bottom})")
            lines.append("")

        lines.append("HOW TO USE WITH CUA-DRIVER:")
        lines.append("  computer_use(action='capture', app='screen')  # Primary only")
        lines.append("  # Für Secondary: Koordinaten transformieren & click")
        lines.append("  # Siehe Skill multi-monitor-control für Details")
        lines.append("=" * 60)
        return "\n".join(lines)

    def json_output(self) -> str:
        """JSON-Darstellung für programmatische Nutzung."""
        data = {
            "count": self.count,
            "monitors": [m.to_dict() for m in self.monitors],
            "virtual_desktop": self.virtual_desktop.to_dict(),
            "has_secondary": self.has_secondary,
        }
        # Koordinaten-Offsets
        if self._primary:
            offsets = {}
            for i, m in enumerate(self.monitors, 1):
                if not m.primary:
                    offsets[f"monitor_{i}"] = {
                        "offset_x": m.x - self._primary.x,
                        "offset_y": m.y - self._primary.y,
                        "device_name": m.device_name,
                    }
            if offsets:
                data["coordinate_offsets"] = offsets
        return json.dumps(data, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────


def cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Multi-Monitor Desktop Control für OpenAmer Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python multi-monitor.py                         # Human-readable Report
  python multi-monitor.py --json                  # JSON-Ausgabe
  python multi-monitor.py --transform 1920 500    # Koordinate transformieren
  python multi-monitor.py --monitor 2              # Info über Monitor 2
  python multi-monitor.py --refresh               # Cache leeren und neu scannen
        """,
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Ausgabe als JSON (maschinenlesbar)"
    )
    parser.add_argument(
        "--transform", nargs=2, type=int, metavar=("X", "Y"),
        help="Primär-Anchored Koordinate auf Virtual Desktop transformieren"
    )
    parser.add_argument(
        "--monitor", type=int, metavar="INDEX",
        help="Details zu einem bestimmten Monitor anzeigen"
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Monitor-Cache leeren und neu scannen"
    )

    args = parser.parse_args()
    mgr = MonitorManager()

    if args.refresh:
        mgr.refresh()
        print("✅ Monitor-Cache refreshed.")

    if args.json:
        print(mgr.json_output())
        return

    if args.monitor:
        m = mgr.get_monitor(args.monitor)
        if m:
            print(json.dumps(m.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"❌ Monitor {args.monitor} nicht gefunden (es gibt {mgr.count})")
            sys.exit(1)
        return

    if args.transform:
        x, y = args.transform
        try:
            if mgr.count >= 2:
                # Versuche auf Secondary zu transformieren
                tx, ty = mgr.transform_to_monitor(2, x=x, y=y)
                print(f"  Quell-Koordinate (Primary-relativ): ({x}, {y})")
                print(f"  Ziel-Koordinate (Virtual Desktop):  ({tx}, {ty})")
                print(f"  Auf Monitor 2: {mgr.get_monitor(2).device_name}")
                print(f"  Capture-Offset für diese Koordinate: x={tx - x:+d}, y={ty - y:+d}")
            else:
                print("⚠️  Nur ein Monitor aktiv — keine Transformation nötig.")
                print(f"  Koordinate ({x}, {y}) bleibt unverändert.")
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
        return

    print(mgr.summary())


# ──────────────────────────────────────────────
# Modul-API (für Import)
# ──────────────────────────────────────────────

def get_manager() -> MonitorManager:
    """Erzeuge und gib einen frischen MonitorManager zurück."""
    return MonitorManager()


def detect_monitors() -> List[MonitorInfo]:
    """Kurzform: Nur Monitor-Liste holen."""
    return MonitorDetector.detect()


def coordinate_transform(
    from_x: int,
    from_y: int,
    target_monitor: int = 2,
) -> Tuple[int, int]:
    """Kurzform: Koordinate auf Ziel-Monitor transformieren.

    Gibt (abs_x, abs_y) im virtuellen Desktop zurück.
    """
    mgr = MonitorManager()
    return mgr.transform_to_monitor(target_monitor, x=from_x, y=from_y)


def get_secondary_region() -> Optional[Dict[str, int]]:
    """Kurzform: Region des zweiten Monitors holen, falls vorhanden."""
    mgr = MonitorManager()
    if mgr.count >= 2:
        return mgr.get_capture_region(2)
    return None


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

if __name__ == "__main__":
    cli()