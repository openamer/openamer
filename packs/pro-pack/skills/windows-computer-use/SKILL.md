---
name: windows-computer-use
description: Use on Windows. UIA quirks, Edge failures, MCP recovery.
version: 1.1.0
platforms: [windows]
metadata:
  openamer:
    tags: [windows, computer-use, cua-driver, desktop-automation, uia]
    category: desktop
    related_skills: [computer-use]
---

# Windows Computer Use (cua-driver patterns & pitfalls)

Load this skill alongside `computer-use` when driving a Windows desktop.
The canonical cross-platform workflow is documented there; this skill
captures Windows-specific behaviours that differ from macOS/Linux.

## Key limitations on Windows

### 1. Desktop icons do NOT launch apps

Desktop shortcuts appear as `ListItem` elements in the UIA tree. cua-driver
performs `SelectionItem.Select` on them, which **only highlights the icon**
— it never starts the application. The action reports `ok: true` but nothing
happens.

**Canonical fix — always launch via terminal:**

```python
# Good: terminal with full path
terminal('"C:\\Path\\To\\brAve.exe" "https://target.url"')

# Bad: clicking desktop icon (does nothing)
computer_use(action="click", element=3)  # ❌ only selects the icon
```

### 2. Microsoft Edge — UWP vs Chromium (critical difference)

**⚠️ UWP Edge (`ApplicationFrameHost.exe`)**: Cannot be captured — `capture(app="Microsoft Edge")`
fails with "no on-screen window matched." This is the old Edge that ships with some Windows 10 builds.

**✅ Chromium-based Edge (`msedge.exe`, Chrome_WidgetWin_1)**: Works perfectly — full UIA tree,
all actions work. This is the modern Edge installed by Windows Update. Tested on Win10 22H2+.

**How to check which one is running:**
- Look for `msedge.exe` processes in Task Manager
- If the window title appears in the UIA tree as `msedge.exe`, it's Chromium-based
- If captures show `ApplicationFrameHost.exe`, it's UWP — switch to Brave/Chrome

**✅ Chromium-based Edge** works identically to Brave — full UIA tree, click, type, scroll (FG),
key combos (FG). Use with `app="msedge"` or no app parameter for the active window.

**Preferred browsers (tested, working):**
- **Brave** (Desktop Chromium) — perfect UIA tree, all actions work
- **Chrome** (Desktop Chromium, `Chrome_WidgetWin_1`) — full UIA tree
- **Edge** (Chromium-based, `msedge.exe`) — full UIA tree
- **agent-browser headless** (via `browser_navigate` tool) — works without any
  visible window, no UIA tree needed. This is the **primary fallback** when
  no Chromium desktop app is running. Install via:
  ```
  npm install -g agent-browser && agent-browser install
  ```
  Then use `browser_navigate` / `browser_click` / `browser_snapshot` normally.
  Note: works without residential proxies, though bot detection may be more
  aggressive on GitHub login pages.
- **Browserbase headless** (via `browser_navigate` tool) — works but requires
  paid API key

### 3. Chromium input requires foreground for type, key, scroll

On Windows, **all input actions** (`scroll`, `text_input`/`type`, `key`/key_combo) on a
Chromium window (`Chrome_WidgetWin_1` class — Chrome, Brave, Edge, **OpenAmer.exe
desktop**) return:
```
code: "background_unavailable"
escalation.recommended: "foreground"
```
Note: a frameless Electron app (like OpenAmer Desktop) can silently SWALLOW a
foreground `ctrl+r` (effect stays `unverifiable`, no reload happens) — after such
a reload attempt, confirm the app state with a fresh capture and, if you must
reload renderer assets, prefer closing/reopening the app via its lifecycle rather
than trusting ctrl+r.

**Exception:** `click` (button, link, element) works in background mode on Chromium.

**Fix — always follow the escalation ladder:**

```python
# Clicks work in background
computer_use(action="click", element=42, capture_after=True)

# Type, key, scroll must use foreground
computer_use(action="type", text="Hello World",
             delivery_mode="foreground", capture_after=True)

computer_use(action="key", keys="ctrl+a",
             delivery_mode="foreground")

computer_use(action="scroll", direction="down", amount=3,
             delivery_mode="foreground", capture_after=True)
```

### 4. Foreground mode can kill the MCP session

After a `delivery_mode="foreground"` action, subsequent captures may fail:
```
"this session has ended; call start_session explicitly"
```

**This is now FIXED in OpenAmer's code (commits f36672486, 6b041ed37, 628304321).** The `call_tool()`
method auto-detects "this session has ended" in the tool result via
`_is_ended_session_result()`, revives the session via `_revive_declared_session_once()`,
and retries the original call — all transparently.

The fix was ported from Hermes which had already solved this. Pattern: when
cua-driver returns a logical "session ended" error (not an MCP protocol error),
`call_tool` in `_CuaDriverSession` now:
1. Detects `isError: true` + "this session has ended" in the data
2. Calls `start_session` with the stored `_declared_session_id`
3. Replays the original tool call once

**Legacy fallback (pre-fix builds / older cua-driver):**

```python
terminal("openamer computer-use doctor")
# Re-establishes the session, then capture works again
```

### 5. Web apps with active sessions — the "already logged in" pattern

When the user has an active browser session (cookies, logged-in state), you can
drive the web app end-to-end via Background Computer-Use without ever asking
for credentials. Successful patterns:

**Pattern: Find, activate, and drive an already-open tab**

```python
# 1. Capture to find the running browser
computer_use(action="capture", mode="som")  # or app="msedge" / app="Brave"

# 2. Look for a relevant tab (usually in TabItem elements)
# E.g. TabItem 'Launch Day dashboard' or 'Edit Launch'

# 3. Click the tab to switch to it
computer_use(action="click", element=<tab-index>, capture_after=True)

# 4. Interact with the page
# Clicks work in background mode
computer_use(action="click", element=<button-or-link>, capture_after=True)

# Input fields require foreground delivery_mode
computer_use(action="type", text="new text",
             delivery_mode="foreground")

# Key combos also require foreground
computer_use(action="key", keys="ctrl+a",
             delivery_mode="foreground")
```

**When this works:**
- User already logged in to the service (saved cookies or session)
- Browser is already open with at least one tab
- The page loads without OAuth redirect or 2FA

**When this fails:**
- Page requires Cloudflare/JS challenge (Product Hunt login, Google login)
- Service demands OAuth re-auth every session
- Page uses service workers that intercept automation

**Real example (Product Hunt launch):**
The user had logged into Product Hunt 2 days prior. The browser tab was
still open in Edge. I clicked the tab, navigated the Edit form, changed
name + tagline + description (all via foreground type/key), and clicked
Save — all autonomously. Result: "All changes saved successfully."

#### Web form editing: the verify-after-every-field pattern

When typing into `Edit` fields on web pages (especially Chromium Edge),
`type` can **append** to existing text instead of replacing it, even after
`ctrl+a`. This happens because foreground key combos don't always register
in the UIA control before the type action runs. Example: typing "OpenAmer"
after "GitHub" produced "GitHubOpenAmer" instead of just "OpenAmer".

**Protocol to follow for EVERY form field edit:**
```python
# 1. Click the field
computer_use(action="click", element=<edit-field>, delivery_mode="foreground")

# 2. Select all
computer_use(action="key", keys="ctrl+a", delivery_mode="foreground")

# 3. Type the new value
computer_use(action="type", text="New Value", delivery_mode="foreground")

# 4. VERIFY by re-capturing and reading the field's label
computer_use(action="capture", app="msedge", mode="som")
# Look for the Edit element's label — it shows character count:
#   "Name of the launch 8/40" → text is "OpenAmer" (8 chars) ✅
#   "Name of the launch 22/40" → concatenation bug ❌
```

**How to read field state from the AX tree:** The `Edit` element's
`label` attribute includes both the field name and character count:
- `"Name of the launch 8/40"` → 8 chars → "OpenAmer" ✅
- `"Name of the launch 22/40"` → 22 chars → concatenation ❌
- `"Tagline 60/60"` → 60 chars → correct ✅

If the count is wrong, repeat click+ctrl+a+type — the second attempt
usually works because the field is already focused.

**Verify saves explicitly — never assume:**
```python
computer_use(action="click", element=<save-button>, delivery_mode="foreground")
computer_use(action="capture", app="msedge", mode="som")
# Look for "All changes saved successfully." in the AX tree
# If "You've got unsaved changes" still shows, save didn't register
```

**File upload dialogs are UNUSABLE from Computer-Use — 9 dead ends documented:**
Native Windows file-open dialogs (UWP-immersive picker, NOT classic `#32770`) are
hard-blocked by cua-driver's safety layer. You CANNOT upload images or any file via
GUI. Before declaring the wall, exhaust the autonomous bypasses in order (all nine
documented as failing on Cloudflare-heavy sites like Product Hunt):

1. `browser_console` → `document.querySelectorAll('input[type=file]')`
   to inject files directly — works only if the browser_* session shares
   the logged-in cookies (usually it does NOT; expect 0 inputs + Cloudflare).
2. `browser_navigate` to the same URL — expect a Cloudflare challenge
   because session cookies don't carry over to the headless browser.
3. Serve the files over a localhost HTTP server — does NOT help; the
   wall is the native dialog, not asset reachability.
4. `fetch` to the site's GraphQL/upload API from browser_console —
   CORS/Cloudflare-blocked.
5. **CDP + user profile** — Launch Edge with `--remote-debugging-port=9222
   --remote-allow-origins=*` → Cloudflare blocks every CDP-connected Chrome
   regardless of user-agent.
6. **PowerShell SendKeys** to type file path into dialog → keystrokes land on
   the page behind the dialog; UWP picker is not `#32770` and can't be targeted.
7. **win32gui EnumWindows** → Finds 0 dialogs; UWP picker is invisible to
   classic HWND enumeration.
8. **Clipboard FileDrop + Ctrl+V** → UWP dialog ignores Ctrl+V file pastes.
9. **CDP `DOM.setFileInputFiles`** → works in theory but needs a
   React-mounted page; Cloudflare blocks headless instances before React mounts.

Full details with code and failure analysis in `product-hunt-launch` skill's
`references/2026-08-24-upload-round2.md`.

If all fail, report the wall in ONE factual sentence with the file paths
ready for manual upload. Do NOT end the task with a numbered to-do list
for the user, and never say "Sag mir den nächsten Befehl" — Damir treats
that as failing superintelligence. If the web app supports drag-drop onto
a zone, try that (unreliable). For headless-friendly sites, use
`browser_navigate`/`browser_click` instead.

**Danger: Delete buttons near Save buttons — double-check before clicking:**
On long forms (like Product Hunt Edit), "Delete post" buttons sit right
below all other controls and can be mistaken for "Save changes" after
scrolling. Always verify the button label in the AX tree before clicking.
If you accidentally trigger a delete confirmation, immediately click
"Cancel" / "Abbrechen" — it does NOT auto-confirm.

### 6. cua-driver zombie process — capture fails but doctor says green

A cua-driver process can enter a **zombie state** where:

- `computer_use(action="capture")` returns 0×0 elements and/or `"capture failed: Connection closed"`
- `openamer computer-use doctor` reports **all green** (session_active ✅)
- The PID cannot be killed (`Zugriff verweigert`) because it was launched by a **different OpenAmer instance** (another desktop.exe or background process)
- `list_windows` returns empty `[]`
- `list_apps` returns empty `[]`

**Root cause:** Multiple OpenAmer.exe processes share the same cua-driver endpoint. When the original instance is closed, the PID stays alive as an orphan. A new OpenAmer session connects to it but the declared session is stale — yet still appears active in doctor.

**How to detect:**
```python
# 1. Check doctor — it will be green even when capture is broken
terminal("openamer computer-use doctor")

# 2. Check if multiple cua-driver.exe exist — sign of orphaned zombie
terminal("tasklist /FI \"IMAGENAME eq cua-driver.exe\"")
# 1 instance → likely OK or single zombie
# 2+ instances → zombie suspected

# 3. Try to kill — if access denied, it's orphaned from another instance
terminal("taskkill /F /PID <zombie-pid>")
# "Zugriff verweigert" = can't be killed from current session
```

**Fix (the only one that works):**
1. Restart the OpenAmer desktop app entirely (close all OpenAmer.exe processes)
2. OR use PowerShell from terminal to kill all cua-driver processes:
   ```powershell
   powershell "Get-Process -Name 'cua-driver' | Stop-Process -Force"
   ```
   This fails with "access denied" if another elevated OpenAmer instance owns the PID.

**Pitfall — Do NOT fixate on killing the zombie:**
- `taskkill /F /PID` → Access Denied (you are not the owner)
- `wmic process where "name='cua-driver.exe'" call terminate` → WMIC not in git-bash
- `Stop-Process -Force` → Access Denied (same reason)
- The only reliable fix is: **close all OpenAmer.exe, restart the desktop app**

**User fallback:** If the user says "desktop app ost nicht oeffen, ich bin in chrome browser" (can't open desktop app, I'm in Chrome), switch entirely to `browser_navigate`/`browser_click` tools for Chrome-based operations. Computer-Use sessions cannot be recovered without a restart.

### 7. Office Click-to-Run popup (ClickToDo.exe) blocks the desktop

The "Klick-und-Los" popup from Microsoft Office sits above the desktop with
`z_index: 6+` and captures as an empty `ClickToDo.exe` window with 0 elements.

**Fix:** either close the popup manually, or run a screen-level capture
(`app="screen"`) instead of an app-level capture to see the desktop icons.

### 8. Settings/About panels close on app reload — re-navigate, not re-capture

In the OpenAmer Desktop (and other frameless Electron apps), a reload (or
background asset swap) closes an open Settings/About panel back to the main
chat view. A subsequent `click` at remembered screen coordinates lands on the
chat (no-op) instead. After any reload: fresh SOM capture, find the settings
gear button by element index, click it, capture again, THEN walk the sidebar
(„Über" etc.) — element indices shift between the two views and coordinates
from before the reload are invalid.

## The canonical Windows workflow

```python
# 1. Launch app via terminal (never desktop icon)
terminal('"C:\\Path\\To\\brave.exe" "https://github.com/..."')

# 2. Capture the app
computer_use(action="capture", app="Brave", mode="som")

# 3. Click elements (background works for Chromium buttons/links)
computer_use(action="click", element=42, capture_after=True)

# 4. Scroll (must use foreground on Chromium)
computer_use(action="scroll", direction="down", amount=3,
             delivery_mode="foreground")

# 5. After foreground, verify capture still works
computer_use(action="capture", app="Brave", mode="som")
# If fails → run doctor

# 6. Type into address bar (background works)
computer_use(action="key", keys="ctrl+l")  # focus address bar
computer_use(action="type", text="https://new-url.com")
computer_use(action="key", keys="return")
```

## Element reference stability

UIA element indices on Windows Chromium (`Chrome_WidgetWin_1` class) are
stable within a single page load. After navigation or scroll, re-capture.

The SOM index includes elements from all visible toolbars, infobars,
and the page itself. Expect 100+ elements on a GitHub page — plan for
`max_elements=200` when capturing complex pages.

## Known good combinations (tested)

| App | Type | UIA Tree | Click | Scroll | Type |
|-----|------|----------|-------|--------|------|
| Brave | Desktop Chromium | ✅ Full | ✅ BG | ✅ FG | ✅ |
| Chrome | Desktop Chromium | ✅ Full | ✅ BG | ✅ FG | ✅ |
| Edge (Chromium) | Desktop Chromium (msedge.exe) | ✅ Full | ✅ BG | ✅ FG | ✅ |
| Edge (UWP) | UWP in ApplicationFrameHost | ❌ Not found | N/A | N/A | N/A |
| GitHub (in Brave) | Web page | ✅ Full | ✅ BG | ✅ FG | ✅ |
| Desktop icons | Shell ListItem | ✅ Listed | ❌ Select only | N/A | N/A |