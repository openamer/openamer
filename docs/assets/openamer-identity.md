# OpenAmer visual identity

The permanent OpenAmer signature is a bold **O enclosing A**: a closed circular
O and a substantial, geometric A, separated by midnight negative space. There
are no letters outside the mark, fonts, filters, or linked resources. Cyan
(`#75f5ff` / `#22d3ee`) descends into teal (`#14b8a6`) against a midnight tile
(`#12283c` / `#060e1c`). The same silhouette is used from 16px favicons to native
application icons; never substitute the old DNA or eye logo.

## Source and regeneration

`docs/assets/openamer-logo.svg` is the only editable master. From the repository
root, with the desktop workspace dependencies installed:

```sh
node apps/desktop/scripts/generate-icons.mjs
node apps/bootstrap-installer/scripts/check-branding.mjs
```

The generator uses Playwright Chromium (or installed Chrome), renders each size
at its native resolution, and writes the committed PNG, ICO, ICNS, favicon SVG,
and contact sheet. `OPENAMER_CHROME_PATH` can select an installed Chromium binary.
Normal product builds consume the committed files and require no browser.

Generated surfaces:

- Canonical docs SVG/512px PNG and `openamer-identity-preview.png` contact sheet.
- Desktop `assets/icon.{png,ico,icns}`, `public/openamer.png`, favicon and Apple icon.
- Setup/update `public/openamer-logo.png` and all configured Tauri native icons.
- Website `static/img` logos, favicons and Apple icon.
- Web `public/favicon.ico`, VS Code `icon.png`, and LAUNCH logo/icon exports.

Windows ICO files deliberately contain seven classic 32-bit BMP entries
(16, 24, 32, 48, 64, 128, 256px), rather than PNG-only entries, to preserve
Windows shell/taskbar compatibility. ICNS is an actual container with native
PNG representations through 1024px. Branding checks validate shared asset
identity, PNG dimensions, ICO bitmap headers, and ICNS container boundaries.

The contact sheet shows actual-size samples down to 16px. Keep the full tile,
the O/A spacing and the A's open counter; do not place a wordmark inside an icon.
Character/avatar illustrations and historical screenshots are not logos and are
intentionally outside this regeneration pipeline.
