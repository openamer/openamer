#!/usr/bin/env python3
"""
Darwin Video Generator - records the 3D world via playwright.
Output: reports/video/darwin-video.mp4
"""
import asyncio
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FFMPEG = str(REPO.parent.parent / "Microsoft" / "WinGet" / "Packages" /
             "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" /
             "ffmpeg-8.1.2-full_build" / "bin" / "ffmpeg.exe")
if not Path(FFMPEG).exists():
    # fallback to system ffmpeg
    FFMPEG = "ffmpeg"

MP4_OUT = REPO / "reports" / "video" / "darwin-video.mp4"


async def record():
    from playwright.async_api import async_playwright
    MP4_OUT.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=[
            "--use-gl=angle", "--use-angle=default", "--enable-webgl"])
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(MP4_OUT.parent),
            record_video_size={"width": 1920, "height": 1080})
        page = await context.new_page()
        await page.goto("http://127.0.0.1:8910")
        await page.wait_for_timeout(3000)   # 3D init
        await page.wait_for_timeout(20000)  # 20s of 3D animation
        await context.close()
        await browser.close()
        time.sleep(2)
        videos = list(MP4_OUT.parent.glob("*.webm"))
        if videos:
            return max(videos, key=lambda v: v.stat().st_mtime)
    return None


def main():
    print("Recording 3D world (20s)...")
    webm = asyncio.run(record())
    if not webm:
        print("no video captured")
        sys.exit(1)
    size_mb = webm.stat().st_size / (1024 * 1024)
    print(f"webm: {webm.name} ({size_mb:.1f} MB)")
    cmd = [FFMPEG, "-y", "-i", str(webm), "-c:v", "libx264",
           "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
           str(MP4_OUT)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode == 0:
        size = MP4_OUT.stat().st_size / (1024 * 1024)
        print(f"OK: {MP4_OUT} ({size:.1f} MB)")
    else:
        print(f"ffmpeg error: {r.stderr[-200:]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
