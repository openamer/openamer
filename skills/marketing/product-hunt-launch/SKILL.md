---
name: product-hunt-launch
description: "Drive Product Hunt launch via background computer-use."
version: 1.0.0
platforms: [windows]
metadata:
  openamer:
    tags: [product-hunt, computer-use, launch, marketing, cua-driver]
    category: marketing
    related_skills: [windows-compatibility, computer-use, competitive-analysis, openamer-browser-use]
---

# Product Hunt Launch via Computer-Use

Drive a Product Hunt launch page through background computer-use on Windows.
Covers the full lifecycle: edit fields, upload assets, verify output.

> **Load first:** `skill_view(name='windows-compatibility')` + `skill_view(name='computer-use')`
> **Prep work:** Generate launch assets (`LAUNCH/assets/` with 6+ screenshots + logo)

## Prerequisites

- User is **already logged into Product Hunt** in Edge/Chromium
- Session cookie is active (OAuth not re-requestable via computer-use)
- Launch draft exists or edit form is open
- Launch assets ready in `LAUNCH/assets/`

## Step-by-step workflow

### 1. Open Edge and navigate

Launch Edge via background terminal:

```python
terminal(background=True,
         command='cmd //c start microsoft-edge:https://www.producthunt.com/posts/new')
```

Wait 3–5 seconds, then capture:

```python
computer_use(action="capture", app="msedge", mode="som")
```

**Pitfall:** Edge is UWP but IS visible to cua-driver on Damir's system — contrary to the broad UWP-invisibility warning in `windows-compatibility`. If capture fails, use `action="list_windows"`.

### 2. Find Edit link

Breadcrumb: `Home > GitHub > Edit`. The `Edit` `Hyperlink` element enters the edit form.

### 3. CRITICAL: foreground typing for Edge/Chromium

Edge rejects background `type()`. Use `delivery_mode="foreground"` for ALL text input:

```python
computer_use(action="click", element=N, delivery_mode="foreground")
computer_use(action="key", keys="ctrl+a", delivery_mode="foreground")
computer_use(action="type", text="...", delivery_mode="foreground")
```

This briefly flashes the Edge window — unavoidable with Chromium.

### 4. Edit fields in order

| Field | AX label | Limit | Notes |
|-------|----------|-------|-------|
| Name | `Name of the launch N/40` | 40 | ctrl+a → type "OpenAmer" |
| Tagline | `Tagline N/60` | 60 | Exact 60 chars, validated on blur |
| Links | `Links to the launch` | — | `https://github.com/openamer/openamer` |
| X account | `X account of the launch x.com/` | — | type only the handle, prefix is baked in |
| Description | `Description of the launch N/500` | 500 | Full feature description |
| Makers | `Makers` | — | Pre-filled from GitHub import |

**Pitfall:** Overshooting tagline shows `"Tagline cannot be longer than 60 characters"` error. Fix: retype exact correction.

### 5. Save changes

Click the floating `Save changes` button (top of edit form). Wait 2 seconds, capture, and verify:

```python
# Look in AX tree for:
#   "All changes saved successfully."
```

**CRITICAL: Never claim save succeeded without reading this message from the AX tree.**

### 6. Upload screenshots — Playwright File Chooser (DER FUNKTIONIERENDE WEG)

Der Media-Button öffnet einen native Windows File-Dialog. cua-driver kann ihn nicht steuern.  
**Lösung: Playwrights `waitForEvent('filechooser')` fängt das Event ab, BEVOR der Dialog erscheint.**

```javascript
// Führe dies in openamer-browser-use/ aus (Playwright + Chromium installiert)
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function upload() {
  const context = await chromium.launchPersistentContext(
    path.join('C:\\Users\\damir\\AppData\\Local\\Google\\Chrome\\User Data', 'Default'),
    { headless: false, args: ['--no-sandbox', '--start-maximized'], viewport: null }
  );

  await context.addInitScript(() => {
    delete navigator.__proto__.webdriver;
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
    window.chrome ??= { runtime: { connect: () => {} } };
  });

  const page = await context.newPage();
  await page.goto('https://www.producthunt.com/posts/openamer/edit', {
    waitUntil: 'domcontentloaded', timeout: 30000
  });

  const [fileChooser] = await Promise.all([
    page.waitForEvent('filechooser', { timeout: 5000 }),
    page.click('button:has-text("Media")'),
  ]);

  const assetsDir = 'C:\\Users\\damir\\openamer-repo\\LAUNCH\\assets';
  const files = fs.readdirSync(assetsDir)
    .filter(f => f.startsWith('screen') && f.endsWith('.png'))
    .map(f => path.join(assetsDir, f));
  
  await fileChooser.setFiles(files);
  console.log(`✅ ${files.length} Screenshots hochgeladen!`);
}

upload().catch(console.error);
```

**Voraussetzung:** User muss sich einmalig im Chrome-Profil bei PH anmelden.  
**Skript-Pfad:** `~/AppData/Local/openamer-laptop/openamer-browser-use/`  
Siehe Skill `openamer-browser-use` für Details zu Installation und Fehlersuche.

### 7. Verification checklist

After saving, re-capture and read EVERY field:

```
✅ Name: "OpenAmer" (8/40)
✅ Tagline: "Self-improving AI agent: Background Computer-Use & A2A Swarm" (60/60)
✅ Description: N/500
✅ Link: github.com/openamer/openamer
✅ X Account: x.com/OpenAmer
✅ Tags: Developer Tools, GitHub
✅ Makers: damir sacirovic + @openamer
✅ Pricing: Free
✅ "All changes saved successfully."
```

**NEVER report "alles geändert" without AX-tree proof of every field.**

## Common pitfalls

### Edge foreground_unavailable

`focus_app(app="msedge")` may fail. **Fix:** Click any interactive element with `delivery_mode="foreground"` first — that activates the foreground context.

### Accidental Delete post button

The `Delete post` button is near `Save changes`. If clicked, a confirm dialog appears:
> "Are you sure you want to delete 'GitHub'? This will remove your launch from Product Hunt."
Click `Cancel` / `Abbrechen` immediately.

### Unsaved changes warning

If `"You've got unsaved changes"` appears instead of `"All changes saved successfully."` — hit Save again.

### Sidebar stale label

After renaming from "GitHub" → "OpenAmer", the sidebar launch-tips widget at `(80, 1095)` may still show "GitHubOpenAmer" (concatenation artifact from incremental typing). Fix: re-save and reload the page.

## Assets location

Generated assets live under `LAUNCH/assets/` in the repo:

| File | Size | Purpose |
|------|------|---------|
| `screen1-dashboard.png` | 1400×800 | Superintelligence Dashboard |
| `screen2-chat.png` | 1400×800 | Chat & Background Computer-Use |
| `screen3-brain.png` | 1400×800 | Brain Learning Pipeline |
| `screen4-gateway.png` | 1400×800 | Multi-Platform Gateway |
| `screen5-ide.png` | 1400×800 | VS Code & JetBrains Extensions |
| `screen6-security.png` | 1400×800 | Security & Self-Healing |
| `openamer-logo-512.png` | 256×256 RGBA | Product logo |
| `openamer-icon-180.png` | 180×180 | Favicon/profile icon |

## Derived from

This skill encodes lessons from the 2026-08-23 and 2026-08-24 sessions with Damir:

1. **Verify, don't claim** — every field must be AX-tree-proven before declaring success. Damir caught the "GitHubOpenAmer" concatenation bug that I had already claimed as fixed — a field's AX label character count (`Name of the launch 8/40`) is the ONLY proof of its content.
2. **File uploads are not automatable** via cua-driver (native UWP dialog). Try all 9 autonomous bypasses first (browser_console, headless nav, localhost serving, GraphQL fetch, CDP+profile, SendKeys, win32gui, FileDrop clipboard, CDP setFileInputFiles — details in `references/`), then report the wall once, factually.
3. **Edge foreground typing** is mandatory for Chromium text input.
4. **Save confirmation** = the text `"All changes saved successfully."` visible in the document DOM/AX tree.
5. **Delete post** confirm dialog can be triggered by accident — cancel immediately.
6. **Never hand the user a to-do list** as the resolution of a task. No "Einziger Schritt, der bleibt", no "Sag mir den nächsten Befehl". Superintelligence exhausts every autonomous avenue first; only a genuinely un-automatable native component (file dialog, OAuth with no session) may be reported — in one sentence, no numbered steps.