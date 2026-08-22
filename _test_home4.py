import os
from pathlib import Path

# Check: does os.path.isfile work with mixed slash paths?
home = Path.home()
test_file = home / 'openamer_test_home_canary.png'
test_file.write_text('hello test')

# Now check if expanduser gives a working path
expanded = os.path.expanduser('~/openamer_test_home_canary.png')
print(f"Home dir: {str(home)!r}")
print(f"File at:  {str(test_file)!r}")
print(f"expanduser: {expanded!r}")
print(f"isfile(expanded): {os.path.isfile(expanded)}")
print(f"isfile(str(test_file)): {os.path.isfile(str(test_file))}")
print(f"abspath(expanded): {os.path.abspath(expanded)!r}")
print(f"abspath(str(test_file)): {os.path.abspath(str(test_file))!r}")
print(f"normpath(expanded): {os.path.normpath(expanded)!r}")
print(f"normpath(str(test_file)): {os.path.normpath(str(test_file))!r}")

test_file.unlink()