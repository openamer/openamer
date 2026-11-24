---
description: Use when lsp/ide-tooling-fehler diagnostizieren. Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# LSP/IDE-Tooling-Fehler diagnostizieren

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `lsp_error`):

```
2026-08-21 04:08:54,715 WARNING openamer.lint.lsp: lsp[pyright] unexpected error for /x.py: RuntimeError: boom
```

## Lösung

Prüfe ob pyright/typescript installiert ist. Bei Win32-Fehlern: node-Version prüfen (x64?). `pip install pyright` oder `npm install -g pyright`.

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
