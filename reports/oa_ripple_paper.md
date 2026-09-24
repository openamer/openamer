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

### CIRCLE (non-linearly separable, 10 seeds, 100 epochs, lr=0.3, 2→4→1)

A single-seed run is NOT a measurement here: `relu` shows huge initialization
variance on this task (min 0.694 .. max 1.000 at n=121). Averaged over 10 seeds:

| Grid | Aktivierung | mean | min | max |
|---|---|---|---|---|
| 121 samples | relu | 0.907 | 0.694 | 1.000 |
| 121 samples | gelu | 0.920 | 0.752 | 1.000 |
| 121 samples | **oa_ripple** | **0.948** | 0.926 | 0.975 |
| 441 samples | relu | 0.706 | 0.644 | 0.850 |
| 441 samples | gelu | 0.705 | 0.537 | 0.873 |
| 441 samples | **oa_ripple** | **0.873** | 0.721 | 0.909 |

Honest reading: `oa_ripple` leads on both densities, but the effect is
**variance reduction** — its worst case (0.926) beats relu's worst case (0.694)
by a wide margin — rather than a mean jump. An earlier revision of this file
claimed relu 0.644 vs oa_ripple 0.892; that compared one lucky relu seed against
the ripple mean and is superseded by the table above. Denser sampling makes the
task harder for every activation (relu 0.907 → 0.706), so figures from different
grids are not comparable.

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