import os
from pathlib import Path

p = Path('C:/Users/damir/AppData/Local/Temp')
f = p / 'test_regex_match.png'
Path(f).write_text('hello')

print('Testing os.path.isfile with various path forms:')
native = str(f)
print(f'  str(f): {native!r} -> {os.path.isfile(native)}')

posix = f.as_posix()
print(f'  as_posix: {posix!r} -> {os.path.isfile(posix)}')

drive, rest = os.path.splitdrive(native)
rest_stripped = rest.lstrip("\\")
slash_path = '/' + rest_stripped.replace('\\', '/')
print(f'  /-prefixed: {slash_path!r} -> {os.path.isfile(slash_path)}')

msys_path = '/' + drive.rstrip(':') + rest.replace('\\', '/')
print(f'  MSYS-style: {msys_path!r} -> {os.path.isfile(msys_path)}')

# Also test what os.path.expanduser does
print()
print('os.path.expanduser behavior:')
print(f'  expanduser(~/{rest_stripped.replace(chr(92), chr(47))}):')
expanded = os.path.expanduser('~/' + rest_stripped.replace('\\', '/'))
print(f'    -> {expanded!r}')

os.remove(str(f))