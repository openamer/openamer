---
description: Use when fehlende dateien und pfad-probleme diagnostizieren. Automatisch generiert aus dem Continuous Learning Loop.
category: learning-loop
---

# Fehlende Dateien und Pfad-Probleme diagnostizieren

Automatisch generierter Skill aus dem Learning Loop.

## Auslöser

Wiederkehrender Fehler (Kategorie: `file_not_found`):

```
File "C:\Users\damir\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\Lib\pathlib.py", line 1013, in stat return os.stat(self, follow_symlinks=follow_symlinks) ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ FileNotFoundError: [WinError 3] Das System kann den angegebenen Pfad nicht...
```

## Lösung

Prüfe ob der Pfad existiert. Bei relativen Pfaden: Arbeitsverzeichnis prüfen. Bei OpenAmer: `HOME` Umgebungsvariable prüfen.

## Prävention

- Regelmäßige Log-Analyse mit `learning-loop.py --auto`
- Bei erneuten Auftreten: Skill aktualisieren und Lösung verfeinern
- Monitoring auf diesen Fehlertyp einrichten
