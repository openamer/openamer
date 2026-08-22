import os
from pathlib import Path
import tempfile

# Test HOME env var on Windows expanduser
with tempfile.TemporaryDirectory() as td:
    # Check HOME before
    print(f"Before: HOME={os.environ.get('HOME', 'NOT SET')!r}")
    print(f"expanduser('~'): {os.path.expanduser('~')!r}")
    
    # Set HOME to td
    old_home = os.environ.get('HOME')
    os.environ['HOME'] = td
    print(f"\nAfter: HOME={os.environ.get('HOME', 'NOT SET')!r}")
    print(f"expanduser('~'): {os.path.expanduser('~')!r}")
    print(f"expanduser('~/foo.png'): {os.path.expanduser('~/foo.png')!r}")
    
    # Create file at expected location
    expected = Path(td) / 'foo.png'
    expected.write_text('hello')
    print(f"File at expected: {str(expected)!r}")
    print(f"isfile(expanduser('~/foo.png')): {os.path.isfile(os.path.expanduser('~/foo.png'))}")
    
    # Also check what path form works
    expanded = os.path.expanduser('~/foo.png')
    print(f"\nExpanded: {expanded!r}")
    print(f"isfile(expanded): {os.path.isfile(expanded)}")
    print(f"abspath(expanded): {os.path.abspath(expanded)!r}")
    print(f"abspath(str(expected)): {os.path.abspath(str(expected))!r}")
    print(f"abspath match: {os.path.abspath(expanded) == os.path.abspath(str(expected))}")
    print(f"normpath match: {os.path.normpath(expanded) == os.path.normpath(str(expected))}")