import os
from pathlib import Path
import tempfile

# Test what os.path.normpath and os.path.abspath do with various path forms on Windows
with tempfile.TemporaryDirectory() as td:
    os.environ['HOME'] = td
    img = Path(td) / 'foo.png'
    img.write_text('hello')

    str_img = str(img)  # C:\Users\...\...\foo.png
    print(f"str(img) = {str_img!r}")
    print(f"  normpath: {os.path.normpath(str_img)!r}")
    print(f"  abspath:  {os.path.abspath(str_img)!r}")

    # Build /-prefixed path
    posix = img.as_posix()  # C:/Users/.../foo.png
    fwd = '/' + posix.split(':/', 1)[1]  # /Users/.../foo.png
    print(f"\nfwd = {fwd!r}")
    print(f"  normpath: {os.path.normpath(fwd)!r}")
    print(f"  abspath:  {os.path.abspath(fwd)!r}")
    print(f"  isfile:   {os.path.isfile(fwd)}")

    # Test normpath comparison
    print(f"\nnormpath(fwd) == normpath(str_img)?")
    print(f"  {os.path.normpath(fwd)!r} == {os.path.normpath(str_img)!r}")
    print(f"  result: {os.path.normpath(fwd) == os.path.normpath(str_img)}")

    print(f"\nabspath(fwd) == abspath(str_img)?")
    print(f"  {os.path.abspath(fwd)!r} == {os.path.abspath(str_img)!r}")
    print(f"  result: {os.path.abspath(fwd) == os.path.abspath(str_img)}")

    img2 = Path(td) / 'shouty.PNG'
    img2.write_text('hello')
    str_img2 = str(img2)
    posix2 = img2.as_posix()
    fwd2 = '/' + posix2.split(':/', 1)[1]

    print(f"\nstr(img2) = {str_img2!r}")
    print(f"fwd2      = {fwd2!r}")
    print(f"  normpath match: {os.path.normpath(fwd2) == os.path.normpath(str_img2)}")
    print(f"  abspath match:  {os.path.abspath(fwd2) == os.path.abspath(str_img2)}")

    # For test_finds_home_relative_path
    print(f"\nHOME = {td!r}")
    print(f"expanduser('~/foo.png') = {os.path.expanduser('~/foo.png')!r}")
    print(f"isfile(expanduser('~/foo.png')) = {os.path.isfile(os.path.expanduser('~/foo.png'))}")