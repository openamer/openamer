# Windows Computer Use — Session Debug Log

## Environment
- OS: Windows 10 (build 26200.9168)
- cua-driver: 0.19.3
- Browser: Brave (Desktop Chromium), Microsoft Edge (UWP)
- OpenAmer model: deepseek/deepseek-v4-flash (OpenRouter — no vision)
- Host: HP OMEN laptop, AMD64

## Bugs encountered

### Bug 1: Desktop icons don't launch apps
**Symptom:** `computer_use(action="click", element=3)` on Brave desktop icon
reports `✅ Performed UIA SelectionItem.Select on [3]` but app never starts.
Screen capture after click unchanged.

**Root cause:** Desktop `ListItem` elements in the UIA tree only support
`SelectionItem.Select` (highlights the icon), not `Invoke` (launches the app).

### Bug 2: Edge (UWP) not detectable
**Attempt 1:** `start msedge` — shows no error, `tasklist` shows 8 msedge.exe
processes, but `list_windows()` doesn't find any Edge window.

**Attempt 2:** `cmd //c start microsoft-edge:https://...` — same result.

**Root cause:** Edge is a UWP app running inside `ApplicationFrameHost.exe`.
cua-driver's `list_windows()` only finds native Win32 windows, not UWP-
hosted windows.

### Bug 3: MCP session dies after foreground
After `scroll(delivery_mode="foreground")`, the next capture fails with:
```
capture failed: cua-driver list_windows failed: 
this session has ended; call start_session explicitly
```

**Fix (commit f36672486):** Auto-detected and recovered by `call_tool()` in
`_CuaDriverSession`. The `_is_ended_session_result()` method spots the
"session has ended" text in the tool output, `_revive_declared_session_once()`
re-registers the session and retries. No user-visible error. See
`references/session-recovery-fix.md` for full details.

**Legacy workaround (pre-fix):** Run `openamer computer-use doctor` to
re-establish the MCP session.

### Bug 4: ClickToDo popup intercepts desktop captures
`capture()` without app filter shows `ClickToDo.exe` window with 0 elements.
The "Klick-und-Los" Microsoft Office popup sits at z_index 6+ above the
desktop shell (explorer.exe at z_index 0).

## What worked

### Brave workflow (fully working)
```
# Launch
terminal('"C:\\Users\\<user>\\AppData\\Local\\BrAveSoftware\\BrAve-Browser\\Application\\brave.exe" ...')

# Capture
computer_use(action="capture", app="Brave", mode="som")
# → 1162 elements, full page tree

# Click navigation tabs
computer_use(action="click", element=42)  # "Pull requests 5"
# → navigated to PR page, document title changed

# Scroll (foreground only)
computer_use(action="scroll", direction="down", amount=3,
             delivery_mode="foreground")
```