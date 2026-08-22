import os
from pathlib import Path
import tempfile

# Test with a temp dir as HOME
with tempfile.TemporaryDirectory() as td:
    os.environ['HOME'] = td
    print(f"HOME set to: {td!r}")
    print(f"expanduser('~/foo.png'): {os.path.expanduser('~/foo.png')!r}")
    
    # Create the file at that path
    img = Path(td) / 'foo.png'
    img.write_text('hello')
    print(f"File created at: {img!r}")
    print(f"File exists at expanduser path: {os.path.isfile(os.path.expanduser('~/foo.png'))}")
    
    # What form does expanduser give us?
    expanded = os.path.expanduser('~/foo.png')
    print(f"expanded == str(img)? {expanded == str(img)}")
    print(f"  expanded: {expanded!r}")
    print(f"  str(img): {str(img)!r}")
    
    # Try with as_posix
    print(f"  str(img) as isfile: {os.path.isfile(str(img))}")
    
    # What about normpath?
    import os.path
    norm = os.path.normpath(expanded)
    print(f"normpath(expanded): {norm!r}")
    print(f"isfile(normpath(expanded)): {os.path.isfile(norm)}")
    
    str_img = str(img)
    norm2 = os.path.normpath(str_img)
    print(f"normpath(str(img)): {norm2!r}")
    print(f"str(img) == normpath(str(img)): {str_img == norm2}")