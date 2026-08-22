import os
import re
from pathlib import Path

# Replicate exact regex from source
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic")
_IMAGE_EXT_PATTERN = "|".join(e.lstrip(".") for e in _IMAGE_EXTS)

_LOCAL_IMAGE_PATH_RE = re.compile(
    r"(?<![/:\w.])(?:~/|/)(?:[\w.\-]+/)*[\w.\-]+\.(?:" + _IMAGE_EXT_PATTERN + r")\b",
    re.IGNORECASE,
)

# Simulate test_finds_home_relative_path
body = "see ~/foo.png please"
print(f"Body: {body!r}")
print(f"Regex matches: {[(m.start(), m.group(0)) for m in _LOCAL_IMAGE_PATH_RE.finditer(body)]}")

# The issue might be os.path.expanduser or HOME env
print()
print(f"Current HOME: {os.environ.get('HOME', 'NOT SET')!r}")
print(f"expanduser('~/foo.png'): {os.path.expanduser('~/foo.png')!r}")
print(f"isfile(expanduser): {os.path.isfile(os.path.expanduser('~/foo.png'))}")

# Check: does ~/foo.png match the regex on Windows?
for m in _LOCAL_IMAGE_PATH_RE.finditer(body):
    raw = m.group(0)
    print(f"Regex matched: {raw!r}")
    expanded = os.path.expanduser(raw)
    print(f"  expanduser -> {expanded!r}")
    print(f"  isfile -> {os.path.isfile(expanded)}")