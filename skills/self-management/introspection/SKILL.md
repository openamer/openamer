---
name: introspection
description: "Selbst-Auskunft mit ECHTEN Zahlen: zaehle die tatsaechlichen SKILL.md- und Tool-Definitionen, statt pauschale Werte (281/99) zu behaupten."
version: 1.0.0
author: OpenAmer Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  openamer:
    tags: [introspection, self-evaluation, skills-count, tools-count, honest-metrics, self-awareness]
    related_skills: [skill-library, dashboard]
---

# Introspection — echte Fähigkeitszahlen liefern

## Zweck

Beantworte Fragen wie *"wie viele Tools hast du?"*, *"wie viele Skills hast du?"*, *"was bist du?"* mit **gemessenen, tatsächlichen Werten** aus der Installation — nicht mit pauschal gerundeten Marketing-Zahlen.

## Trigger

- Der Nutzer fragt nach Tools/Skills/Fähigkeiten-Anzahl oder der eigenen Identität.
- Du brauchst eine verlässliche Selbst-Auskunft für einen Bericht oder Vergleich.

## Regeln

1. **Zähle nicht raten.** Gib nie "281 Skills" oder "99 Tools" aus, ohne es nachgemessen zu haben.
2. **Nutze die REALEN Zähler unten.** Miss jedes Mal frisch.
3. Wenn du unsicher bist, sage die gemessene Zahl UND dass es die aktuell installiere Version ist.

## Echte Zahlen messen

Führe die folgenden Zählungen in der Repo-Wurzel aus:
(`PROJECT_ROOT = C:\Users\damir\AppData\Local\openamer-laptop\openamer-agent`)

### Skills-Anzahl (SKILL.md-Dateien)

```bash
find skills -iname "SKILL.md" | wc -l
```

> Ergebnis = Anzahl der gebündelten Skills.

### Modell-Tool-Anzahl (eindeutige Tool-Namen)

Die tatsächlichen, aufrufbaren Modell-Tools sind die `"name": "..."`-Einträge in
`tools/*.py` (Core) + Plugins. Zähle sie exakt (toolset-Kategorien in `toolsets.py`
sind nur Gruppierungen; die echte Zahl sind die registrierten Funktionen):

```bash
python - <<'PY'
import os, re
root = "."  # openamer-agent repo root
names = set()
for d in ("tools", "openamer_cli"):
    for f in os.listdir(os.path.join(root, d)):
        if f.endswith(".py") and not f.startswith("__"):
            try:
                names |= set(re.findall(r'"name":\s*"([a-z_]+)"',
                                        open(os.path.join(root, d, f), encoding="utf-8").read()))
            except Exception:
                pass
print(f"{len(names)} eindeutige Modell-Tool-Funktionen")
PY
```

> Damit bekommst du die echte Zahl aller Core-Funktionen (typisch ~95–115, steigend mit
> Updates und Plugins). Das ist genauer als "99" oder "87" — die Toolsets sind nur
> Kategorien.

### Gateway-Plattformen (optionale Ergänzung)

```bash
grep -cE '^\s+\("[a-z_]+"' openamer_cli/platforms.py
```

> Ergebnis = Anzahl der registrierten Plattform-Kanäle.

## Antwort inkl. Identität

Wenn nach "wer/was bist du" gefragt wird, verwende dieses Format:

- **Identität:** Ich bin OpenAmer — der Agent/das System/der ganze Stack.
- **Motor (LLM):** aktuell konfiguriert (z.B. `modell` in `config.yaml` via `openamer config`), **nicht** die eigene Identität.
- **Skills:** [gemessene Zahl] gebündelte Skills.
- **Native Tools:** [gemessene Zahl] eindeutige Modell-Tools.
- **Plattformen:** [gemessene Zahl] Gateway-Kanäle (optional).

## Verifikation

Nach dem Zählen ein paar Sekunden prüfen, ob die Werte plausibel sind:
- Skills im Bereich ~100-300 (nimmt mit Updates zu).
- Tools im Bereich ~40-100 (nimmt mit Updates zu).
- Wenn eine Zahl auffällig `0` ist, prüfe den Pfad / dass du in PROJECT_ROOT stehst.