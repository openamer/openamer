"""A controlled demo target — nothing private is ever on screen.

Purpose: give the background-computer-use demo a window whose contents we fully
control, so the recorded clip never shows the desktop, personal files or open
apps.

The window measures, with WinAPI GetCursorPos, whether the HUMAN's pointer moved
while the agent acted. That is the claim on trial: OpenAmer drives the desktop
through its own overlay cursor and never grabs the real one.

Run it and drive it via computer_use; the recorded clip is the proof asset for
the wedge: "drives your Windows desktop in the background — without taking your
mouse."
"""
import ctypes
import time
import tkinter as tk

GetCursorPos = ctypes.windll.user32.GetCursorPos


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def cursor():
    p = POINT()
    GetCursorPos(ctypes.byref(p))
    return p.x, p.y


root = tk.Tk()
root.title("OpenAmer demo target")
root.geometry("860x560+160+150")
root.attributes("-topmost", True)  # recording must not capture whatever covers it
root.configure(bg="#0f1115")

tk.Label(root, text="A window you did NOT click on.",
         font=("Segoe UI", 18, "bold"), fg="#e6e8eb", bg="#0f1115").pack(pady=(20, 2))
tk.Label(root, text="OpenAmer is working in here, in the background.",
         font=("Segoe UI", 11), fg="#8b93a1", bg="#0f1115").pack()

box = tk.Text(root, height=8, font=("Consolas", 14), bg="#171a21", fg="#4ade80",
              insertbackground="#4ade80", relief="flat", padx=12, pady=10)
box.pack(fill="both", expand=True, padx=22, pady=16)
box.focus_set()

status = tk.Label(root, text="", font=("Consolas", 12, "bold"),
                  fg="#facc15", bg="#0f1115")
status.pack(pady=(0, 18))

origin = {"x": None, "y": None}


def tick():
    x, y = cursor()
    if origin["x"] is None:
        origin["x"], origin["y"] = x, y
    drift = abs(x - origin["x"]) + abs(y - origin["y"])
    status.config(text=f"your real mouse pointer has moved: {drift} px")
    root.after(100, tick)


root.after(100, tick)
root.mainloop()