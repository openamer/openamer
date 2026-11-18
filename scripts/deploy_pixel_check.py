#!/usr/bin/env python3
"""Pixel-proof that the app the user sees is the app we deployed.

Why this exists (2026-11-18): the agent could prove a green test suite and could
not prove that the window on screen showed anything. Tests answer "does the code
behave"; they do not answer "did the user's window render it". The owner reads the
status line in the running window himself and reports "noch alt" — so the deploy
gate has to look at the same pixels.

    python scripts/deploy_pixel_check.py                 # capture + mechanical checks
    python scripts/deploy_pixel_check.py --expect-title OpenAmer --min-bytes 8000
    python scripts/deploy_pixel_check.py --json

What it checks mechanically (no model needed):
  * the process has a real window with a non-empty title,
  * the capture is a plausible UI: bytes >= --min-bytes (a blank window compresses
    to a few KB; a real one is >50 KB), and the PNG decodes to >= 100x100 px,
  * the evidence file records sha256, pid, title, size and the verdict.

Exit 0 = verified, 1 = captured but implausible (blank/tiny), 2 = could not verify
(no window / capture failed). "Could not verify" is never reported as success.

The second half is a human or vision-model reading of the PNG: the script writes
the path so `vision_analyze` can answer "does the status line show the new build?"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
OUTDIR = HOME / "reports" / "ui-captures"
EVIDENCE = HOME / "reports" / "ui-pixel-check.json"

PS = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinCap {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
$proc = Get-Process -Name $env:PIXEL_PROC -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) { Write-Output "NOWINDOW"; exit 3 }
$h = $proc.MainWindowHandle
$r = New-Object WinCap+RECT
[void][WinCap]::GetWindowRect($h, [ref]$r)
$w = $r.Right - $r.Left; $hh = $r.Bottom - $r.Top
if ($w -lt 100 -or $hh -lt 100) { Write-Output "TINYWINDOW $w $hh"; exit 4 }
$bmp = New-Object System.Drawing.Bitmap $w, $hh
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
$ok = [WinCap]::PrintWindow($h, $hdc, 2)   # 2 = PW_RENDERFULLCONTENT
$g.ReleaseHdc($hdc)
if (-not $ok) {
  $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
}
$bmp.Save($env:PIXEL_OUT, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output ("OK {0} {1} {2} {3}" -f $proc.Id, $w, $hh, ($proc.MainWindowTitle -replace '\s+', ' '))
"""


def png_size(path: Path) -> tuple[int, int]:
    """Read the PNG header — width/height without an image library."""
    with path.open("rb") as fh:
        head = fh.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Capture the running app window and check it is real.")
    ap.add_argument("--process", default="OpenAmer")
    ap.add_argument("--expect-title", default="OpenAmer")
    ap.add_argument("--min-bytes", type=int, default=8000)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    shot = OUTDIR / f"ui-{stamp}.png"

    env = dict(os.environ, PIXEL_PROC=args.process, PIXEL_OUT=str(shot))
    script_path = OUTDIR / f"_cap-{stamp}.ps1"
    script_path.write_text(PS, encoding="utf-8")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(script_path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=90, env=env)
    script_path.unlink(missing_ok=True)
    out = (r.stdout or "").strip()
    line = next((l for l in out.splitlines() if l.startswith(("OK", "NOWINDOW", "TINYWINDOW"))), "")

    result: dict = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "process": args.process,
                    "capture": str(shot), "verdict": "UNVERIFIED", "reasons": []}

    if not line.startswith("OK"):
        result["reasons"].append(line or f"capture failed: {(r.stderr or '')[-200:]}")
        verdict, code = "UNVERIFIED", 2
    else:
        _, pid, w, h, title = (line.split(" ", 4) + ["", "", "", "", ""])[:5]
        result.update({"pid": int(pid), "width": int(w), "height": int(h), "title": title})
        size = shot.stat().st_size if shot.exists() else 0
        pw, ph = png_size(shot) if shot.exists() else (0, 0)
        digest = hashlib.sha256(shot.read_bytes()).hexdigest()[:16] if shot.exists() else ""
        result.update({"bytes": size, "png": f"{pw}x{ph}", "sha256_16": digest})

        if args.expect_title and args.expect_title.lower() not in title.lower():
            result["reasons"].append(f"title '{title}' does not contain '{args.expect_title}'")
        if size < args.min_bytes:
            result["reasons"].append(f"{size} bytes < {args.min_bytes} (window looks blank)")
        if pw < 100 or ph < 100:
            result["reasons"].append(f"png {pw}x{ph} is too small to be a UI")

        verdict = "VERIFIED" if not result["reasons"] else "IMPLAUSIBLE"
        code = 0 if verdict == "VERIFIED" else 1

    result["verdict"] = verdict
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(f"pixel check: {verdict}")
        if result.get("pid"):
            print(f"  window  pid {result['pid']} '{result.get('title')}' "
                  f"{result.get('width')}x{result.get('height')}  png {result.get('png')}")
            print(f"  capture {result['capture']}  {result.get('bytes')} bytes  "
                  f"sha256 {result.get('sha256_16')}")
        for reason in result["reasons"]:
            print(f"  ! {reason}")
        print(f"  evidence {EVIDENCE}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
