import os
import re
from pathlib import Path

# Replicate the exact regex and test matching
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic")
_IMAGE_EXT_PATTERN = "|".join(e.lstrip(".") for e in _IMAGE_EXTS)

_LOCAL_IMAGE_PATH_RE = re.compile(
    r"(?<![/:\w.])(?:~/|/)(?:[\w.\-]+/)*[\w.\-]+\.(?:" + _IMAGE_EXT_PATTERN + r")\b",
    re.IGNORECASE,
)

print(f"Pattern: {_LOCAL_IMAGE_PATH_RE.pattern!r}")
print()

# Test 1: The /-prefixed path
test_path = Path('C:/Users/damir/AppData/Local/Temp/pytest-of-damir/pytest-365/test_finds/screenshot.png')
posix = test_path.as_posix()
# Strip drive letter
if ':' in posix:
    slash_posix = '/' + posix.split(':', 1)[1].lstrip('/')
else:
    slash_posix = posix

body = f"Look at {slash_posix} and tell me what's wrong."
print(f"Body: {body!r}")
print(f"Matches: {[(m.start(), m.end(), m.group(0)) for m in _LOCAL_IMAGE_PATH_RE.finditer(body)]}")
print()

# Let's try debugging: test if we can match individual path components
print("Debugging regex matching:")
for m in re.finditer(r'(?:~/|/)', body):
    print(f"  Found prefix candidate at {m.start()}: {m.group(0)!r}")
    # Try matching from this position with the full pattern
    test_pat = re.compile(r"(?<![/:\w.])(?:~/|/)(?:[\w.\-]+/)*[\w.\-]+\.(?:png|jpg|jpeg|gif|webp|bmp|tiff|tif|heic)\b", re.IGNORECASE)
    for m2 in test_pat.finditer(body[m.start():]):
        print(f"  FULL MATCH from {m.start()}: {m2.group(0)!r}")
        break

print()
# The problem might be the lookbehind. Let's test without lookbehind
_LOCAL_NO_LB = re.compile(
    r"(?:~/|/)(?:[\w.\-]+/)*[\w.\-]+\.(?:" + _IMAGE_EXT_PATTERN + r")\b",
    re.IGNORECASE,
)
body2 = f"Look at {slash_posix} and tell me what's wrong."
print(f"Without lookbehind: {[(m.start(), m.group(0)) for m in _LOCAL_NO_LB.finditer(body2)]}")

# What about a simpler path - just /tmp/test.png
body3 = "Look at /tmp/test.png please"
print(f"Simple /tmp/test.png: {[(m.start(), m.group(0)) for m in _LOCAL_NO_LB.finditer(body3)]}")
print(f"With LB: {[(m.start(), m.group(0)) for m in _LOCAL_IMAGE_PATH_RE.finditer(body3)]}")

# Test /a/b/c/d.png 
body4 = "Look at /a/b/c/d.png please"
print(f"/a/b/c/d.png without LB: {[(m.start(), m.group(0)) for m in _LOCAL_NO_LB.finditer(body4)]}")
print(f"/a/b/c/d.png with LB: {[(m.start(), m.group(0)) for m in _LOCAL_IMAGE_PATH_RE.finditer(body4)]}")