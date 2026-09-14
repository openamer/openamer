"""Print the screen rect of the demo window, so ffmpeg records only that window.

Recording a region rather than the whole desktop guarantees the clip contains
nothing but our own controlled window — no personal folders, no open apps.
"""
import ctypes
import ctypes.wintypes as w

u = ctypes.windll.user32
TITLE = "OpenAmer demo target"

# The display runs at 125%. ffmpeg's gdigrab addresses PHYSICAL pixels, while
# GetWindowRect/ClientToScreen return LOGICAL ones unless the process declares
# itself DPI-aware — the mismatch showed up as a region shifted up/left by
# ~40 px (border slivers in the clip). Declare awareness first so both agree.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor v2
except Exception:
    u.SetProcessDPIAware()

found = []


def cb(hwnd, _):
    if not u.IsWindowVisible(hwnd):
        return True
    n = u.GetWindowTextLengthW(hwnd)
    if n:
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        if buf.value == TITLE:
            r = w.RECT()
            u.GetClientRect(hwnd, ctypes.byref(r))
            origin = w.POINT(0, 0)
            u.ClientToScreen(hwnd, ctypes.byref(origin))
            found.append((origin.x, origin.y, r.right, r.bottom))
    return True


WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
u.EnumWindows(WNDENUMPROC(cb), 0)

if not found:
    print("NOT_FOUND")
else:
    x, y, ww, hh = found[0]
    # Inset by 1px so no window border pixel can leak onto the clip.
    print(f"CLIENT x={x} y={y} w={ww} h={hh}")
    print(f"gdigrab=-offset_x {x + 2} -offset_y {y + 2} -video_size {ww - 4}x{hh - 4}")
