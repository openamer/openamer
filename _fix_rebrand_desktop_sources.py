"""Rebrand desktop TS/JS sources: Hermes -> OpenAmer."""
import os
from pathlib import Path

base = Path(r"D:\OpenAmer\apps\desktop")

for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "dist", "release"}]
    for fname in files:
        if not fname.endswith((".ts", ".tsx", ".js", ".mjs", ".html", ".css")):
            continue
        fpath = Path(root) / fname
        text = fpath.read_text(encoding="utf-8")
        original = text
        # Environment variables first (preserve HERMES_HOME etc? No — desktop uses HERMES_DESKTOP_*)
        text = text.replace("HERMES_DESKTOP_", "OPENAMER_DESKTOP_")
        # Protocol
        text = text.replace("\"hermes:\"", "\"openamer:\"").replace("'hermes:'", "'openamer:'")
        # Package references
        text = text.replace("@hermes/shared", "@openamer/shared")
        # Brand names (more specific first)
        text = text.replace("Hermes Agent", "OpenAmer Agent")
        text = text.replace("for Hermes", "for OpenAmer")
        # Generic Hermes -> OpenAmer, but avoid replacing `hermes` in technical contexts where already handled
        text = text.replace("Hermes", "OpenAmer")
        # hermes -> openamer for remaining occurrences (be careful with variable names)
        text = text.replace("hermes", "openamer")
        if text != original:
            fpath.write_text(text, encoding="utf-8")
            print(f"UPDATED {fpath.relative_to(base)}")

print("Desktop source rebrand done")
