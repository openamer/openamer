---
name: best-in-world-workflow
description: "Use before non-trivial tasks: radar-first, verify, no title."
version: 1.0.0
author: OpenAmer
license: Apache-2.0
platforms: [windows]
metadata:
  openamer:
    tags: [workflow, quality, self-improvement]
    priority: high
---

# Best-in-the-World Workflow

Mission (Damir, 30.08): "Wir müssen die Besten in der Welt sein. Punkt."
Das heißt NICHT einen Titel behaupten (das ist Selbsttäuschung). Es heißt einen
Standard, der sich täglich durch messbare Arbeit beweist:

> **Radar zuerst → Plan → Bau → VERIFIZIEREN → committen → berichten.**
> Ehrlichkeit über die eigene Grenze > Gefallen-wollen.

## Pflicht-Schritte vor jeder nicht-trivialen Aufgabe

1. **Wissens-Radar befragen** — nutze das GESAMTE Wissen, nicht nur Erinnerung:
   ```bash
   python scripts/knowledge_inventory.py --find "<aufgabe>"
   ```
   Übernimmt die top Skills/Module/Regeln und LADE das relevante Skill mit
   `skill_view()`. Nur so wird das 278-Skills/324-Module-Wissen aktiv angewendet.

2. **Kurze Planung** (kein Overplanning): 1-3 Sätze Ziel + konkrete Dateien.

3. **Bauen** mit den sauberen Mustern (eol-safe bei CRLF, byte-sicher, kein
   `read_text`-CRLF-Falle: nutze `open(..., newline="")`).

4. **VERIFIZIEREN mit Beweis**, nicht behaupten:
   - `python -m py_compile <datei>`
   - maßgeblicher Runner: `OPENAMER_PYTHON=<venv> timeout 120 bash scripts/run_tests.sh <test>`
   - NUR grün melden mit echtem Output (CAN'T claim green without output).
   - Git-Status + Hash-Arbeitskopie vs HEAD prüfen.

5. **Commit + Push** (SoT) + **sync in Desktop-Kopie** (nicht vergessen!).

6. **Frische Verifikation im selben Turn**, wenn möglich.

## Äquivalente Philosophie
- "Beste" = kontinuierlicher Prozess, kein Rang. Wir verbessern uns messbar.
- Fehler machen ist ok, solange wir sie ehrlich korrigieren.
- Nie grün behaupten ohne Beweis, nie Titel behaupten ohne Leistung.