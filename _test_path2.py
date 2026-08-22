import os
from pathlib import Path

# Check what extract_image_refs returns for various path forms
# Simulating exactly what happens in the test

# First, test_path_to_posix conversion
test_path = Path('C:/Users/damir/AppData/Local/Temp/pytest-of-damir/pytest-365/test_finds/screenshot.png')

# as_posix gives C:/Users/... 
posix = test_path.as_posix()
print(f'as_posix: {posix!r}')

# Strip drive letter for /-prefix
if ':' in posix:
    slash_posix = '/' + posix.split(':', 1)[1].lstrip('/')
else:
    slash_posix = posix
print(f'slash_posix: {slash_posix!r}')

# Now what does expanduser do with this?
expanded = os.path.expanduser(slash_posix)
print(f'expanduser: {expanded!r}')

# And does the file exist at this path?
# We need to create the file first
Path(slash_posix).parent.mkdir(parents=True, exist_ok=True)
Path(slash_posix).write_text('hello')
print(f'isfile: {os.path.isfile(slash_posix)}')
os.remove(str(test_path))

# Now test the reverse: what does expanduser return for 
# paths with backslashes? And does normpath match?
fmt = test_path.as_posix()
print()
print(f'Forward-slash form {fmt!r}')
print(f'os.path.normpath: {os.path.normpath(test_path)!r}')
print(f'os.path.normpath(forward): {os.path.normpath(fmt)!r}')

# What does the actual function return for our body path?
# Let's see the regex match and expanduser behavior
import re
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic")
_IMAGE_EXT_PATTERN = "|".join(e.lstrip(".") for e in _IMAGE_EXTS)
_LOCAL_IMAGE_PATH_RE = re.compile(
    r"(?<![/:\\w.])(?:~/|/)(?:[\\w.\\-]+/)*[\\w.\\-]+\\.(?:" + _IMAGE_EXT_PATTERN + r")\\b",
    re.IGNORECASE,
)

body = f"Look at {slash_posix} and tell me what's wrong."
print()
print(f'body: {body!r}')
matches = list(_LOCAL_IMAGE_PATH_RE.finditer(body))
print(f'regex matches: {[m.group(0) for m in matches]}')
if matches:
    raw = matches[0].group(0)
    print(f'raw match: {raw!r}')
    exp = os.path.expanduser(raw)
    print(f'expanded: {exp!r}')
    isfile = os.path.isfile(exp)
    print(f'isfile: {isfile}')