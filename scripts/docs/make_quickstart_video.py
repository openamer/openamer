#!/usr/bin/env python3
"""Render the OpenAmer quickstart video from *real* command output.

The docs page shipped a third-party YouTube embed. This renders the project's
own clip: it runs the real CLI, draws the real output as frames, and encodes an
MP4. Re-run after a release so the numbers stay true.

    python scripts/docs/make_quickstart_video.py --out website/static/img/docs/quickstart
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 12
BG, FG, MUTED, ACCENT, GREEN = (13, 17, 23), (230, 237, 243), (139, 148, 158), (88, 166, 255), (63, 185, 80)
MONO = "C:/Windows/Fonts/consola.ttf"
SANS = "C:/Windows/Fonts/segoeuib.ttf"


def font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)


def run(cmd):
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=120)
    text = (out.stdout or "") + (out.stderr or "")
    return [ln.rstrip() for ln in text.replace(str(Path.home()), "C:\\Users\\you").splitlines()]


def chrome(d, title):
    d.rounded_rectangle((40, 40, W - 40, H - 40), radius=14, outline=(48, 54, 61), width=2)
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse((66 + i * 26, 64, 80 + i * 26, 78), fill=c)
    d.text((150, 62), title, font=font(MONO, 17), fill=MUTED)


def lines(d, rows, y=110):
    f = font(MONO, 19)
    for row in rows:
        d.text((72, y), row[:96], font=f, fill=GREEN if row.startswith("$") else FG)
        y += 28


def monogram(d, cx, cy, r):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ACCENT, width=max(4, r // 12))
    d.text((cx, cy), "A", font=font(SANS, int(r * 1.1)), fill=FG, anchor="mm")


def title(i, total):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    monogram(d, W // 2, 250, 78)
    d.text((W // 2, 400), "OpenAmer", font=font(SANS, 74), fill=FG, anchor="mm")
    d.text((W // 2, 462), "Quickstart - install, provider, chat", font=font(SANS, 28), fill=MUTED, anchor="mm")
    d.text((W // 2, 530), "self-improving agent, on your own hardware", font=font(MONO, 18), fill=ACCENT, anchor="mm")
    return img


def terminal(rows, cmd, heading, i, total):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    chrome(d, heading)
    typed_frames = int(total * 0.4)
    shown = ("$ " + cmd)[: max(1, int(len(cmd) * min(1.0, (i + 1) / max(1, typed_frames)))) + 2]
    if i < typed_frames:
        canvas = [shown]
    else:
        take = 1 + int(len(rows) * min(1.0, (i - typed_frames) / max(1, total - typed_frames)))
        canvas = ["$ " + cmd] + rows[:take]
    lines(d, canvas)
    if i < typed_frames or (i // 6) % 2 == 0:
        y = 110 + 28 * len(canvas)
        d.rectangle((72, y - 2, 82, y + 20), fill=FG)
    return img


def closer(i, total):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    monogram(d, W // 2, 240, 64)
    d.text((W // 2, 380), "openamer.com/docs", font=font(MONO, 34), fill=ACCENT, anchor="mm")
    d.text((W // 2, 440), "self-hosted - your data stays", font=font(SANS, 22), fill=MUTED, anchor="mm")
    d.text((W // 2, 510), "frames show real output of openamer --version / identity", font=font(MONO, 15), fill=MUTED, anchor="mm")
    return img


def render(out_dir: Path):
    version = run(["openamer", "--version"])[:6]
    ident = [ln for ln in run(["openamer", "identity"])
             if ln.startswith("#") or ln.startswith("I am") or ln.startswith("I belong")][:3]
    scenes = [(30, title, ()), (140, terminal, (version, "openamer --version", "terminal")),
              (140, terminal, (ident, "openamer identity", "terminal")), (40, closer, ())]
    tmp = Path(tempfile.mkdtemp(prefix="openamer-video-"))
    idx = 0
    for total, fn, extra in scenes:
        for i in range(total):
            img = fn(*extra, i, total) if extra else fn(i, total)
            img.save(tmp / f"f{idx:05d}.png")
            idx += 1
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4, poster = out_dir / "openamer-quickstart.mp4", out_dir / "openamer-quickstart-poster.png"
    shutil.copy(tmp / "f00045.png", poster)
    ffmpeg = shutil.which("ffmpeg") or sys.exit("ffmpeg not on PATH")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS),
                    "-i", str(tmp / "f%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "26", "-movflags", "+faststart", str(mp4)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{idx} frames @ {FPS}fps = {idx / FPS:.1f}s -> {mp4} ({mp4.stat().st_size} bytes)")
    print(f"poster -> {poster}")
    return mp4, poster


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="website/static/img/docs/quickstart")
    render(Path(ap.parse_args().out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
