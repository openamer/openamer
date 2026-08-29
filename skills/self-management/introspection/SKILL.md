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

### Modell-Tool-Anzahl (eindeutige Tool-Namen aus toolsets.py)

Die Tool-Namen stehen als String-Listen (z.B. `_OPENAMER_CORE_TOOLS = [ ... ]`). Zähle alle String-Listen-Elemente, die wie Tool-Namen aussehen:

```bash
python - <<'PY'
import ast
tree = ast.parse(open('toolsets.py', encoding='utf-8').read())
names = set()
for node in ast.walk(tree):
    if isinstance(node, ast.List):
        for e in node.elts:
            if (isinstance(e, ast.Constant) and isinstance(e.value, str)
                    and e.value.isidentifier()   # snake_case-Toolname
                    and '/' not in e.value):      # kein Pfad
                names.add(e.value)
print(f"{len(names)} eindeutige Tool-Namen")
PY
```

> Ergebnis = Anzahl der nativen Modell-Tools (typisch 40-99).

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