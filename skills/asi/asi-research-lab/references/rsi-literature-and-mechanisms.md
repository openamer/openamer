# RSI: die Literatur, die Messungen, der Bauplan

Gemessen und gebaut 2026-10-11. Alles unten ist zitierbar oder gemessen — keine
Zuschreibung. Zweck: die nächste Session soll die Paper nicht neu suchen und
nicht dieselben drei Messfehler wiederholen.

## 1. Die vier Mechanismen (arXiv, per API gelesen)

Rezept für die Suche selbst: `curl -sL` ist Pflicht — `http://export.arxiv.org`
antwortet **301 ohne Body**, erst `https` (oder `-L`) liefert 200. Und der
Endpoint mag **keine** Default-Sortierung für Klassiker; für die Gründungspapiere
`max_results` + Relevanzsuche nutzen, für Neues `sortBy=submittedDate`.

**Mendel Gödel Machine — arXiv 2608.07645**
> *„Self-improving coding agents that iteratively rewrite their own source code
> have demonstrated impressive performance on coding tasks. However, existing
> solutions generally derive self-modification from a **single failure
> trajectory** at a time, overlooking rich comparative signals available in the
> agent's **expanding archive** of past attempts."*

Neue Operatoren dort: **reaction-norm mutation** (aus Trajektorien über MEHRERE
Tasks) und **cross-lineage hybridization** (aus einer Referenz-Linie). Verlangt:
ein Archiv, das mehr als den letzten Versuch hält.

**Red Queen Gödel Machine — 2606.26294**
> *„Self-improving agents are state-of-the-art on agentic coding benchmarks, yet
> their search methods **assume a stationary evaluation criterion**. This ignores
> a central feature of evolution: species adapt as their environments change with
> them."*

Lösung: *„learned evaluators to improve alongside the agents they guide"* — der
ko-evolvierte Reviewer benotet Patches und lenkt die Suche. Gemeldet: 82,1 % vs.
75,0 % gehaltene Tasks. **Das ist die exakte Beschreibung des Fehlers, der hier
gemessen wurde** (siehe §2): eine feste Rauschschwelle ist ein stationäres
Kriterium, und sie ließ ein Rauschen als Gewinn durch.

**Huxley-Gödel Machine — 2510.21614**
> *„they grow a tree of self-modifications through expansion strategies that favor
> higher software engineering benchmark performance, assuming that this implies
> more promising subsequent self-modifications. However, we identify a mismatch
> between the agent's self-improvement potential (**metaproductivity**) and its
> coding benchmark performance."*

Metrik **CMP**: aggregiert die Benchmark-Leistungen der **Nachkommen** als
Indikator für das Potenzial. Konsequenz für jede eigene Schleife: eine Variante
ist nicht durch ihren eigenen Score bewertet, sondern durch das, was unter ihr
im Baum erreicht wird.

**Self-Taught Optimizer (STOP) — 2310.02304**
> *„we use a language-model-infused scaffolding program to improve itself … A
> variety of self-improvement strategies are proposed by the language model,
> including beam search, genetic algorithms, and simulated annealing."*

Und die Grenze, die die Autoren **selbst** nennen — für jede ehrliche Meldung
dieser Klasse wörtlich übernehmbar:
> *„Since the language models themselves are not altered, this is **not full
> recursive self-improvement**."*

## 2. Der gemessene Fehler: Rauschen als Fortschritt

Erste Fassung einer Verbesserungsschleife acceptierte einen Kandidaten, wenn er
die Schwelle schlug. Erster Live-Lauf:

```
baseline 0.8
  step 1: epochs: 1 -> 1  -> 0.8    rejected
  step 2: epochs: 1 -> 1  -> 1.0    ACCEPTED   ← +0.2, PARAMETER UNVERÄNDERT
  step 3: epochs: 1 -> 1  -> 1.0    rejected
  step 4: epochs: 1 -> 1  -> 0.7    rejected
  step 5: epochs: 1 -> 1  -> 0.9    rejected
STOPPING — 3 proposals in a row moved nothing
```

Zwei Defekte auf einmal: der Vorschlag mutierte nichts (Ganzzahl-Mutation
`round(1 * [0.5,1.5])` ist immer 1), **und** der Wert wanderte von selbst.

Nachmessung mit fünf Läufen pro Konfiguration:

```
"gewonnen":   0.6406 0.7813 0.6563 0.5781 0.6719     Streuung 0.20
Ausgangslage: 0.5000 0.5417 0.6250 0.4792 0.5938     Streuung 0.15
```

Die Bereiche überlappen fast vollständig — aus fünf Messungen **kein** belegbarer
Fortschritt. Die Schwelle der Schleife lag bei **0,0104**, die echte Streuung bei
**~0,2**: drei Messungen eines verrauschten Werts waren zufällig dicht
beieinander gelandet, und dieser Glücksfall war zur Messlatte geworden.

**Nach den drei Fixes** (§1c) war die Schwelle 0,1562 aus neun Messungen und
deckte sich mit der unabhängigen Fünf-Lauf-Prüfung — und derselbe Kandidatentyp,
der vorher durchkam (+0,073), wurde korrekt abgelehnt.

## 3. CMP auf einem echten Artefakt — der Befund

Subjekt: S_5-Produktaufgabe (`perm_state_lab.py`), Metrik = beste Genauigkeit,
aus der **geschriebenen Datendatei** gelesen (`reports/perm_state_results.json`),
nicht aus der Konsole — Konsolenzahlen sind unbelegt.

```
seed fitness 0.02439   (repeats spread 0.0 — deterministisch)
margin      0.0004878  (aus der eigenen Wiederholbarkeit)

gen 1-6: alle rejected   (delta -0.012, -0.011, -0.012, -0.012, -0.012, -0.012)
0 accepted of 6.  seed 0.02439 -> 0.02439
CMP of the seed (was seine NACHKOMMEN erreichten) = 0.01319
```

**Der Samen steht bei 0,02439, seine Nachkommen erreichen 0,01319.** Der Mutator
bringt nichts Besseres hervor als sich selbst — Huxleys Mismatch, an der eigenen
Maschine gemessen. Das ist die Erklärung für die 891 Rotationen mit 0 Vorschlägen.

## 4. Der Bauplan (was gebaut wurde, was fehlt)

**Gebaut, mit Tests:**
- `scripts/rsi_loop.py` — generische Schleife: Subjekt druckt `METRIC <float>`,
  Schleife misst Baseline → **Rauschschwelle (9 Läufe)** → Vorschlag → Ausführung
  → Annahme nur oberhalb der Schwelle **und** bei Wiederholbarkeit. Jedes Ereignis
  schreibt `delta` + `verdict` (das Feld, das allen 27.211 Darwin-Events fehlte).
  Plateau-Stopp nach N Fehlschlägen.
- `scripts/rsi_godel.py` — Archiv + Ko-Evaluator + CMP: jeder Score trägt seine
  eigene Streuung; `cmp_score()` summiert die Nachkommen; Operatoren sind reale,
  syntaktisch geprüfte Code-Edits.
- `state/rsi_godel/archive.jsonl` — Felder: `id parent ancestor_root generation
  operator fitness spread delta verdict code_sha at`.

**Bewusst nicht gebaut / offen:**
- **Kein Cron an diesen Schleifen.** Die CMP liegt unter der eigenen Fitness —
  eine Schleife, die nichts hervorbringt, gehört nicht in einen Zeitplan.
- Der Mutator ist eine Python-Funktion. Damit gilt STOPs Grenze wörtlich: das ist
  ein Gerüst mit den geforderten Mechanismen, **kein** vollständiges RSI.
- Nächster echter Schritt wäre ein **LLM-Proposer** für Code-Änderungen plus ein
  ko-evolvierter Reviewer als zweiter Fitness-Term — Red Queens Mechanismus, nicht
  ein weiterer Parameter-Sweep.

## 5. Fallen, die beim Bau zugeschlagen haben

- **Zwei eingebettete Code-Strings in einem Kernel-Skript zerrissen die Datei.**
  Das eingebettete Ziel nutzte `'''` innerhalb eines `r'''…'''`-Strings →
  `invalid-syntax` bei ruff, 38 Fehler. Fix: das Ziel als **eigene Datei**
  schreiben. Weniger Verschachtelung schlägt mehr Escaping.
- **Der Runner aus einem handgebauten `subprocess`-Env gibt rc=2** (ohne echtes
  `HOME` findet er sein venv nicht) — das ist **kein gültiger kanonischer Lauf**.
  Nur aus einem echten Terminal/Shell gilt `exit=0`. Wer darauf mergt, hat Glück,
  nicht Prozess.
- **Hintergrundläufe in eine Datei umleiten, nie in eine Pipe.** `… | tail -40`
  im Hintergrund verliert die Ausgabe und beendet den Prozess früh.
- **Ein Modul-Dir im CWD verdeckt das installierte Paket.** Ein Fremdverzeichnis
  `openamer_cli/` ohne `__init__.py` im Arbeitsverzeichnis macht
  `openamer_cli.__file__ is None`, `__version__` verschwindet und Plugins
  scheitern mit `(unknown location)`. Prüfen: `python -c "import openamer_cli;
  print(openamer_cli.__file__)"`.
