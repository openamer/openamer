# cua-driver Zombie Process Detection & Debugging

## Real Session (Aug 2026) — Exact Error Sequence

### Symptoms
```
computer_use(action="capture", mode="som")
→ error: "capture failed: Connection closed"

computer_use(action="capture", mode="vision")
→ 0x0, 0 elements, empty summary

computer_use(action="list_apps") → {"apps": [], "count": 0}
computer_use(action="list_windows") → {"windows": [], "count": 0}

BUT:

openamer computer-use doctor
→ ✅ cua-driver 0.21.0 on win32 — ok
→ ✅ session_active: MCP session is active.
→ ✅ ax_capability: UIAutomation is reachable
→ ✅ screen_capture_capability: D3D11 device reachable
```

### Process State
```
tasklist /FI "IMAGENAME eq cua-driver.exe"
→ cua-driver.exe  PID 11964  24,336K
→ cua-driver.exe  PID 5832   26,004K
```
Two cua-driver processes — one orphaned, one active. The orphan (11964) was
owned by a different OpenAmer.exe instance that had exited.

### Kill Attempts and Results
| Method | Result |
|--------|--------|
| `taskkill /F /IM cua-driver.exe` | "{1 process killed} {1 access denied}" |
| `taskkill /F /PID 11964` | "Zugriff verweigert" |
| `Stop-Process -Id 11964 -Force` | "Could not stop process: Access Denied" |
| `wmic` | not available in git-bash |
| Kill the OTHER (non-zombie, PID 5832) | Succeeds but zombie remains → still broken |

### Resolution
No tool-based fix possible. The zombie cua-driver (PID 11964) was spawned by
a different OpenAmer.exe with elevated privileges. Only a desktop app restart
(close ALL OpenAmer.exe processes, relaunch) resolves it.

Until then: all computer_use actions fail with Connection closed.
Switch to browser_navigate/browser_click tools for Chrome-based work.

## Detection Pattern
```python
# If ALL THREE are true, it's a zombie:
# 1. doctor says session_active ✅
# 2. capture returns 0x0 or Connection closed
# 3. 2+ cua-driver.exe processes or 1 with access-denied kills
```