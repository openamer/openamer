# oa_ripple: Eine neue Aktivierungsfunktion für neuronale Netze

**Autoren:** OpenAmer ASI (CPU-only Research Lab)
**Datum:** 2026-09-21
**Status:** ⚗️ Prototyp — vorläufige Ergebnisse

## Definition

```
oa_ripple(x) = sin(x) · sigmoid(x)
```

wobei `sigmoid(x) = 1/(1 + e^(-x))`.

## Eigenschaften

| Eigenschaft | Wert |
|---|---|
| Wertebereich | [-0.226, 0.838] |
| Differenzierbar | Ja (analytisch + numerisch) |
| Nullpunkt | f(0) = 0 |
| Gradient bei 0 | ~0.5 |
| Oszillierend | Ja (sin-Anteil) |
| Kein dying ReLU | Ja (oszilliert um 0) |

## Benchmark-Ergebnisse

### XOR (4 Samples, 200 Epochs, 3 Trials)

| Aktivierung | Accuracy | Notes |
|---|---|---|
| sigmoid | 3.0/4 | Lokales Minimum |
| relu | 3.3/4 | Manchmal 4/4 |
| **tanh** | **4.0/4** | Immer perfekt |
| **oa_ripple** | **4.0/4** | Immer perfekt |

### CIRCLE (nicht-linear trennbar, 400 Samples)

| Aktivierung | Accuracy |
|---|---|
| relu | 0.644 |
| oa_ripple | **0.892** |

### Evolutionäre Suche

Auf XOR wählte die Evolution automatisch:
- **Layer 0: 2→8 [oa_ripple]**
- **Layer 1: 8→1 [sigmoid]**
- Fitness: 1.000 (perfekt)

## Nächste Schritte

- [ ] Training auf MNIST (digitale Bilderkennung)
- [ ] Kombination mit Residual-Verbindungen
- [ ] Theoretische Analyse der Oszillations-Eigenschaften
- [ ] Vergleich mit Swish/SiLU

## Code

https://github.com/openamer/openamer/tree/main/scripts
- `neural_lab.py` — Framework
- `research_run1.py` — Erste Tests
- `research_run2.py` — Benchmark
- `research_evo.py` — Evolutionäre Suche
- `oa_ripple_paper.py` — Dieses Paper