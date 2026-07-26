"""Rebrand markdown files from Hermes to OpenAmer."""
import os
from pathlib import Path

base = Path(r"D:\OpenAmer")

for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".venv", "__pycache__"}]
    for fname in files:
        if not fname.endswith(".md"):
            continue
        fpath = Path(root) / fname
        text = fpath.read_text(encoding="utf-8")
        new_text = text.replace("Hermes", "OpenAmer").replace("hermes", "openamer")
        if new_text != text:
            fpath.write_text(new_text, encoding="utf-8")
            print(f"UPDATED {fpath.relative_to(base)}")

print("Markdown content rebrand done")
