# Gumroad Product Automation (2026-10-02, verified E2E)

## Setup facts
- Product created: `damirspark.gumroad.com/l/<slug>` via gumroad.com/products/new
- Publish is BLOCKED until a payout method (identity + IBAN) is connected — the agent
  must never fill identity/IBAN forms; that is strictly the user's manual step.
- **CORRECTION 2026-10-05: the CDP chrome DOES carry the Gumroad session.**
  `--user-data-dir=...openamer-laptop/chrome-profile`, port 9222 was logged in as
  "damir sacirovic" and drove the whole flow via CDP (products list, /payouts,
  content editor, `DOM.setFileInputFiles` upload — all worked). The older note below
  ("no Gumroad session → drive via UIA, not CDP") is SUPERSEDED — verify the session
  live first (`curl :9222/json/list`), then drive CDP. UIA (the section below) is the
  fallback when the CDP profile is actually logged out.

## CDP content-editor upload (2026-10-05, verified E2E — the reliable path)

The `/edit/content` page that holds the deliverable has exactly ONE
`input[type=file]`. Upload via CDP, NOT the native dialog:

```python
# /edit/content after Page.navigate + ~9s wait
doc  = tab.send("DOM.getDocument", {"depth": -1})
root = doc["result"]["root"]["nodeId"]
ids  = tab.send("DOM.querySelectorAll", {"nodeId": root,
                 "selector": "input[type=file]"})["result"]["nodeIds"]
tab.send("DOM.setFileInputFiles", {"files": [ZIP_ABS_PATH], "nodeId": ids[0]})
```

Then **poll to completion before saving** — this is the trap that cost a whole
retry cycle:

```python
DONE = "(()=>{const t=document.body.innerText.replace(/\\s+/g,' ');"
       "return {done: /<ZIPNAME>/i.test(t) && /Download/.test(t)"
       " && !/% of|uploading/i.test(t)};})()"
# poll every 3-4s up to ~20x; a 310 KB file takes ~5-10s to reach S3
```

- **Failure seen:** clicked the content page's `Save changes` at "46% of 310.2 KB"
  → after reload the file row was GONE ("Upload your files or start typing").
  The completion predicate must require the file row present AND `Download` visible
  AND no `/ % of|uploading/i` in the DOM. Then save.
- Save with the CONTENT page's own button — `button` whose innerText is exactly
  `"Save changes"`. Do NOT use `"Save and continue"` / `"Publish and continue"`:
  those navigate away and can leave the upload unsaved. Stay on `/edit/content`.
- **Verify by reload, not by the optimistic DOM**: re-`Page.navigate` to
  `/edit/content` and confirm the file row persists
  (`OpenAmer-...-Skills ZIP 310.2 KB Download`). Only then is it real.
- **Description DOES persist — but NOT via `execCommand('insertText')`** (corrected
  2026-11-01, live E2E). The old note here said the Description could not be saved by
  CDP at all; that was wrong, and it cost a manual step on every listing edit. The
  working sequence on the `/edit` page:
  ```python
  # the editor is a Tiptap/ProseMirror contenteditable DIV
  ev("""(() => { const ed=[...document.querySelectorAll('[contenteditable="true"]')][0];
        ed.scrollIntoView({block:'center'}); ed.focus();
        const r=document.createRange(); r.selectNodeContents(ed); r.collapse(false); return 1; })()""")
  send("Input.insertText", text=DESC)     # real key events -> ProseMirror commits
  ```
  Then click the `Save and continue` button, wait ~7 s, **reload** and read
  `document.querySelector('[contenteditable="true"]').innerText` — measured
  1780/1780 chars persisted. What failed before was the JS-only path
  (`execCommand` / setting `innerHTML`), which ProseMirror discards.
- **Two `input[type=file]` on `/edit`, three on the page**: Cover accepts
  `image/*`, the second slot is `.mp3,.wav,...` (audio). Match on `accept`, not on
  index — a blind `ids[1]` uploads the thumbnail into the audio slot.
- **The description/cover save navigates to `/edit/content`.** Any script that
  re-selects its tab by URL must match `gumroad.com`, not `gumroad.com/products`.
- **Do not drive the user's active tab.** When the human is browsing in the same
  Chrome, `Page.navigate` on "the" tab swaps their page out from under them
  (observed: their Bing search tab replaced twice). Open your own tab with
  `PUT /json/new?<url>` and `GET /json/close/<id>` when done.

## What worked (verified, UIA fallback)
1. `computer_use capture mode=som` on the Gumroad window → element indices for form fields.
2. **`set_value` on Chrome inputs via UIA ValuePattern works reliably** — far better than
   click+keystroke typing, which lands on wrong coordinates after the page scrolls
   (SOM bounds are viewport-relative and shift with scroll).
   - Name field: element 59, Summary: 95 (edit page), Name: 56 (create page).
3. Free-text rich-text editors (Description) still need keystroke typing:
   click into the editor first, then type via `win32api.keybd_event` per char
   (VkKeyScan + shift handling). Small 0.006s delay per char.
4. File dialogs (upload ZIP): click the upload button, then enumerate windows of
   class `#32770`, `SetForegroundWindow`, `WScript.Shell.SendKeys` with a RAW string
   path (`r'C:\...'` — plain string breaks on `\U` escape), then `{ENTER}`.

## Pitfalls
- **Chrome windows die silently**: the pid→window_id from an earlier capture can vanish
  (user closes/minimizes); re-enumerate with `win32gui.EnumWindows` filtering by pid
  before every click sequence. A capture on a dead window_id errors with
  "No window with window_id ... exists".
- **Minimized window = refused foreground click** ("window_minimized",
  "iconic sentinel"): restore with `win32gui.ShowWindow(hwnd, 9)` +
  `SetForegroundWindow(hwnd)` (or `WScript.Shell.AppActivate(pid)`) and re-capture.
- **`set_value` marks effect "unverifiable"** — always follow with a som capture and read
  the live preview card (right column of the edit page) to confirm name/price/description.
- Beware double-typing artifacts: repeated keystroke attempts left "Skillst" in the name.
  Prefer set_value for any single-line field; fix typos by full-field set_value again.
- Product preview (right side of edit page) is the ground truth for what is saved.

## Distribution that needs NO Gumroad payout
Parallel direct-sale path already live (verified HTTP 200):
- PayPal hosted button: `https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS`
- PayPal.me: `https://www.paypal.com/paypalme/openamer`
- Repo shop: `PRODUCTS.md` + `docs/shop/index.html` in openamer/openamer, linked from README.
Product ZIP packaging: skills copied from openamer-laptop/skills + README.md,
Compress-Archive to ZIP, verify with `zipfile.testzip()` + SKILL.md count.