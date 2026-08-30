# 🧬 Darwin Engine — 15 Phasen eines selbst-evolvierenden Ökosystems

> **Die Fähigkeit, die kein anderes Agent-Framework hat: eine Skill-Population,
> die sich ohne menschliches Zutun selbst entwickelt — und jede ihrer
> Entscheidungen auf Verlangen beweisen kann.**

Dies ist die Chronik von 15 Phasen. Jede Phase wurde live gebaut, mit echten
Tests bewiesen und auf GitHub gepusht. Keine Simulation.

---

## Act I — Grundlagen (Phase 1–3)

**Phase 1 · Fitness.** Skills werden nach *echten* Signalen bewertet:
Session-Nutzung (60k+ Messages gescannt), Cron-Gesundheit, Strafpunkte für
Stagnation. Keine Schätzungen — echte Ausführungsdaten aus `state.db`.

**Phase 2 · Live-Trials.** Ein Kind-Skill ersetzt seinen Eltern-Skill
*temporär in einem echten Cron-Job*. Der Sieger wird von `executions.db`
entschieden — realen Exit-Codes, nicht Benchmarks. Verliert das Kind,
kehrt der Elternteil zurück, als wäre nichts gewesen.

**Phase 3 · Autopilot.** Semantische, section-bewusste Mutationen (kein
Text-Boilerplate). Ein Befehl (`--autopilot`) läuft den kompletten Zyklus.
Quarantäne statt Löschung — alles reversibel, mit Cron-Schutzschild.

## Act II — Autonomie (Phase 4–6)

**Phase 4 · Lineage & Genome.** Jedes Evolutionsereignis wird in einer
persistenten Familie verzeichnet (Mermaid-Baum im Report). Portable Genome
ermöglichen Fleet-Evolution über mehrere Maschinen — höchster W/L-Score
gewinnt Konflikte.

**Phase 5 · Turnier.** Der Autopilot wählt selbst, welche Kandidaten er
testet: gerankt nach Eltern-Fitness, max 2 parallel, doppelbuchungs-sicher.

**Phase 6 · Echte Ausführung.** Der Head-to-Head-Runner führt Skills
*wirklich* aus und misst echte Exit-Codes. Bewies er zwei Pfad-Bugs auf
einen Schlag — und sagt ehrlich `neither`, wenn kein Operator gewinnt.

## Act III — Evolution der Evolution (Phase 7–10)

**Phase 7 · Speciation.** Arten entstehen aus Blueprints —
genuin neue Skills ohne Elternteil. Live: Population 9 → 11.

**Phase 8 · Gedächtnis & Arena.** Fitness-Historie (append-only), Trend-
analyse, und ein Arena-Ring, in dem Arten mit echten Ausführungen kämpfen.

**Phase 9 · Selbsternährung.** Der Blueprint-Pool wächst aus der eigenen
Vergangenheit: wiederkehrende Fehler-Muster werden aus 28k Messages geerntet
(642 Treffer gefunden, 31 Blueprints gewonnen).

**Phase 10 · Kreislauf.** Ruhestand nach 3 Arena-Niederlagen (reversibel),
Pipeline vollständig: *harvest → speciate → promote → arena → retire.*

## Act IV — Beweis & Reife (Phase 11–12)

**Phase 11 · Sichtbarkeit.** Live-HTTP-Dashboard (Port 8910, Auto-Refresh),
wöchentlicher GitHub-Report als Issue, generiert vom Cron.

**Phase 12 · Reife.** Fitness-Cache: 0.82s → 0.003s (273×). Lesbare
Artnamen (`git-credentials` statt `c-users-damir-...`). gh-Fallback mit
Pending-Queue — nichts geht verloren.

## Act V — Rekursion & Rechenschaft (Phase 13–15)

**Phase 13 · Meta-Evolution.** Die Mutations-Operatoren *selbst* werden
selektiert: Epsilon-Greedy mit Laplace-Glättung — Operatoren, die Champions
zeugen, dominieren; der Rest wird erforscht.

**Phase 14 · Rechenschaft.** `--explain <skill>` liefert die volle
Beweiskette: Fitness-Dekomposition, Genome W/L, Lineage, Trials, Operator-
Qualität, Cron-Schutz. Jede Entscheidung in Sekunden auditierbar.
`--unretire` holt pensionierte Arten korrekt in ihr Art-Verzeichnis zurück.

**Phase 15 · Selbstabstimmung.** Die Konstanten des Systems (explorations-
rate, parallel-trials, retire-schwelle) stellen sich selbst ein — abgeleitet
aus der Ökosystem-Gesundheit:
- *Stagnierend* → mehr Exploration (ε=0.5), mehr Experimente
- *Fallend* → bewährte Operatoren nutzen (ε=0.15), schneller ausmerzen
- *Steigend* → Defaults bestätigen

Live bewiesen: `tuning: healthy (rising) -> defaults`.

---

## Der Beweis (Live-Stand)

```
Population:  18 skills, trend rising
Arten:       installiert, Kandidaten, Ruhestand — alles laufend
Trials:      laufen in Produktions-Crons
Harvest:     19+ Blueprints aus echter Systemerfahrung
Tuning:      passt sich selbst an
```

## Garantien (über alle Phasen)

| Garantie | Beweis |
|---|---|
| Löscht nie | Archive + Quarantäne + Rollback-Log, Phase 3/10/14 |
| Rät nie | Jede Entscheidung aus echten Exit-Codes, Phase 2/6 |
| Bricht Cron nie | Referenz-Schutzschild, Phase 3 |
| Reproduzierbar | Seed 42, deterministische Mutationen |
| Erklärbar | `--explain` für jeden Skill, Phase 14 |
| Selbstanpassend | Tuning aus Gesundheitssignalen, Phase 15 |

---

*68 Tests · 15 Phasen · ein Ökosystem, das sich selbst ernährt, selektiert,
erinnert, erklärt und abstimmt.*

**Darwin ist keine Funktion. Es ist eine lebende Population.**

— Teil von [OpenAmer Agent](https://github.com/openamer/openamer)
