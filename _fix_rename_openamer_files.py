"""Rename files and directories with 'hermes' in the name to 'openamer'."""
import os
import shutil
from pathlib import Path

base = Path(r"D:\OpenAmer")

renamed = []
for root, dirs, files in os.walk(base, topdown=False):
    # Skip git and dependencies
    if any(part in {".git", "node_modules", ".venv", "__pycache__"} for part in Path(root).parts):
        continue
    # Rename files
    for fname in files:
        if "hermes" in fname.lower():
            old = Path(root) / fname
            new_name = fname.lower().replace("hermes", "openamer")
            new = Path(root) / new_name
            # Avoid collision
            if new.exists() and new != old:
                print(f"SKIP collision {old} -> {new}")
                continue
            shutil.move(old, new)
            renamed.append((str(old.relative_to(base)), str(new.relative_to(base))))
    # Rename directories (bottom-up)
    for dname in dirs:
        if "hermes" in dname.lower():
            old = Path(root) / dname
            new_name = dname.lower().replace("hermes", "openamer")
            new = Path(root) / new_name
            if new.exists() and new != old:
                print(f"SKIP dir collision {old} -> {new}")
                continue
            shutil.move(old, new)
            renamed.append((str(old.relative_to(base)), str(new.relative_to(base))))

for old, new in renamed[:50]:
    print(f"RENAMED {old} -> {new}")
print(f"TOTAL RENAMED: {len(renamed)}")
