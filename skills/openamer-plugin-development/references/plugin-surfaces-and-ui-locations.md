# Plugin surfaces and UI locations — measured 2026-11-22

Session trigger: user asked *"du hast auch plugins, aber ich sehe nicht in openamer
desktop app, wo plugins sind, wo kann ich anklicken, auswaehlen"*. Everything below
was measured on this laptop, not read off a doc.

## 1. The tab exists — under a translated name

The Settings nav id is `plugins` (source: `apps/desktop/src/app/settings/index.tsx`
line ~234, component `./plugins-settings`). The i18n key `settings.nav.plugins`
renders:

| Locale | Nav label | Page title |
|---|---|---|
| de | **Erweiterungen** | Desktop-Plugins |
| en | Plugins | Desktop plugins |

Verified in the running app: AX tree of `OpenAmer.exe` (PID 17828) while the
Settings modal was open, left rail in order:

```
Modell · Unterhaltung · Darstellung · Arbeitsbereich · Sicherheit ·
Speicher & Kontext · Sprache · Erweitert · Benachrichtigungen · Abrechnung ·
Anbieter · Zugang · Tastaturkürzel · Tools & Schlüssel · Erweiterungen ·
Archivierte Chats · Über
```

Open it: gear icon top-right (AX label `Einstellungen öffnen`) or **`Ctrl+,`**
(keybind `nav.settings` = `mod+,`, `apps/desktop/src/lib/keybinds/actions.ts`).
Command palette is `Ctrl+K` / `Ctrl+P` (`nav.commandPalette`), command center
`Ctrl+.` (`nav.commandCenter`).

## 2. What the page renders

i18n block `settings.plugins` (German, from the built bundle):

```js
plugins: {
  title: 'Desktop-Plugins',
  blurb: 'UI-Erweiterungen, die in diese App geladen werden — entweder im Build
          enthalten oder in den Desktop-Plugins-Ordner gelegt …',
  count: n => `${n} installiert`,
  openFolder: 'Plugins-Ordner öffnen',
  rescan: 'Erneut scannen',
  reveal: 'Im Dateimanager anzeigen',
  enable: 'Aktivieren',
  disable: 'Deaktivieren',
  failed: 'fehlgeschlagen',
  empty: 'Noch keine Desktop-Plugins installiert.',
  kinds: { bundled: 'integriert', disk: 'auf Datenträger', runtime: 'Laufzeit' }
}
```

`%LOCALAPPDATA%\openamer-laptop\desktop-plugins\` contained only
`agent-builder\plugin.js` and `examples\` — **no `manifest.json` / `plugin.yaml`**
⇒ templates, therefore the empty state was the correct rendering.

## 3. Three separate surfaces (do not conflate)

```bash
# desktop UI plugins (what the tab shows)
ls "$LOCALAPPDATA/openamer-laptop/desktop-plugins"/

# agent plugins (capabilities) — CLI is the ONLY surface
openamer plugins list | grep -c "not enabled"        # measured: 86
openamer plugins list | grep -v "not enabled" | grep -E "^│ [a-z]"
#   -> text-stats, vitals   (measured: exactly 2 enabled)

# skills (third pot, not plugins)
ls "$LOCALAPPDATA/openamer-laptop/skills" | wc -l    # measured: 236
```

Legacy host `<OPENAMER_HOME>\plugins\` (`plugin_system.py`, `plugin_cli.py`,
`browser-control`, `openamer-skill-booster`, `text-stats`, `vitals`) is a parallel
loader; the live manager is `openamer_cli/plugins.py`.

## 4. Build proof: grep the renderer bundle, never the asar

```bash
D="$LOCALAPPDATA/openamer-laptop/openamer-agent/apps/desktop"
grep -l "Erweiterungen" "$D/dist/assets/"*.js      # -> index-V-u5VAUI.js  (52 MB bundle)
```

- `dist/` is what the renderer actually renders (electron-main resolves
  `resolveRendererIndex(...)`, `isPackaged`, `resourcesPath`).
- `release/win-unpacked/resources/app.asar` byte-search for the same strings
  returned **0 hits** — but the asar is only 4.4 MB while its own header lists a
  52 MB `dist/assets/index-*.js` entry. It is a stub; parsing it is a dead end.
  Never report "the build doesn't have feature X" from an asar grep.
- `install-stamp.json` next to the asar carries `commit` / `builtAt` / `dirty` —
  read it when you need "which build is running".

## 5. Driving the app to show the tab (cua-driver specifics)

- `capture(app="OpenAmer", mode="som")` on an **unfocused** Electron window
  returned only 3 elements (minimize/restore/close). After one foreground action
  the SAME capture returned 227 elements with full German labels and the whole
  nav list. So: foreground once, then re-capture before concluding the AX tree
  is empty.
- `key(keys="ctrl+,")` in background was **refused**
  (`background_unavailable`, `event kind: key_combo`,
  `escalation.recommended: "foreground"`) — the escalation opened the Settings
  modal, yet the result still said `"Sent, effect not verified"`. Re-capture and
  read the modal; "effect not verified" is a claim about the driver's certainty,
  not about the app.
- `click(element=45)` was refused with
  `click: unknown argument element_index; accepted: … element_token, capture_id,
  x, y …` — a wrapper/driver param mismatch. Either pass coordinates from a
  capture of that window, or navigate by keyboard/hotkey instead of clicking the
  nav entry.

## 6. Standing answer for the user

> Zahnrad oben rechts (oder `Ctrl+,`) → linke Leiste **„Erweiterungen"**. Dort
> liegen nur **Desktop**-Plugins. Die 86 **Agent**-Plugins (`browser`, `kanban`,
> `disk-cleanup`, `google_meet`, …) haben keine Desktop-Oberfläche und werden per
> `openamer plugins enable <name>` geschaltet.
