"""Print the screen rect of the demo window, so ffmpeg records only that window.

Recording a region rather than the whole desktop guarantees the clip contains
nothing but our own controlled window — no personal folders, no open apps.

Two traps this script closes, both found by actually recording:

* **DPI.** gdigrab addresses PHYSICAL pixels; GetWindowRect/ClientToScreen
  return LOGICAL ones unless the process declares itself DPI-aware. At 125% the
  region lands ~40 px off and leaks neighbouring windows. We declare awareness.
* **Odd dimensions.** libx264 with yuv420p refuses odd width/height. A
  single-frame capture still works, so the trap only fires on the real
  recording ("Conversion failed", 0 frames). We snap to even.
"""
import ctypes
import ctypes.wintypes as w

TITLE = "OpenAmer demo target"


def even_region(x, y, width, height, inset=2):
    """Physical gdigrab args (x, y, w, h), inset from the border and made EVEN.

    The inset keeps a scale/border pixel out of the clip; the even snap keeps
    libx264/yuv420p from refusing the output.
    """
    return x + inset, y + inset, (width - 2 * inset) & ~1, (height - 2 * inset) & ~1


def find_window(title=TITLE):
    """Return (client_x, client_y, client_w, client_h) in physical pixels, or None."""
    u = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor v2
    except Exception:
        u.SetProcessDPIAware()

    found = []

    def cb(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        n = u.GetWindowTextLengthW(hwnd)
        if not n:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        if buf.value == title:
            r = w.RECT()
            u.GetClientRect(hwnd, ctypes.byref(r))
            origin = w.POINT(0, 0)
            u.ClientToScreen(hwnd, ctypes.byref(origin))
            found.append((origin.x, origin.y, r.right, r.bottom))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    u.EnumWindows(WNDENUMPROC(cb), 0)
    return found[0] if found else None


def main():
    rect = find_window()
    if rect is None:
        print("NOT_FOUND")
        return 1
    x, y, width, height = rect
    gx, gy, gw, gh = even_region(x, y, width, height)
    print(f"CLIENT x={x} y={y} w={width} h={height}")
    print(f"gdigrab=-offset_x {gx} -offset_y {gy} -video_size {gw}x{gh}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())