# Rust/Go-Evaluation für OpenAmer (2026-08-31)

## Entscheidung: **GO** (nicht Rust) — und nur für 2 Komponenten

## Begründung (kurz)
- Go: einfacher zu lernen, schnelle Kompilierung, exzellente Windows-Binaries
  (eine .exe, keine Runtime), erstklassige Concurrency (Goroutines) — genau
  richtig für Watchdog/Mesh-Netzwerkcode.
- Rust: ~40 % schnellere Latenz in Benchmarks, aber deutlich steilere
  Lernkurve und langsamere Iteration. Für unseren Nutzen (Daemons mit
  Sekunden-Takt, keine harte Echtzeit) ist der Vorteil irrelevant.
- Beide: single-binary, geringer RAM-Footprint vs. Python-Daemons (~30-60 MB
  Ersparnis pro Prozess realistisch).

## Kandidaten (nach Nutzen sortiert)
1. **service-watchdog** (läuft alle 5 min als Python): Go-Port als echter
   Resident-Daemon mit 1/5 RAM. Nutzen: hoch, Aufwand: mittel.
2. **agent-mesh worker/master** (HTTP-Delegation): Go-Port für echte
   Nebenläufigkeit. Nutzen: mittel-hoch, Aufwand: mittel.
3. Darwin-Engine: BLEIBT Python (tastet Skills an, braucht Python-Ökosystem).

## Lernpfad (konkret)
1. Go installieren (winget install GoLang.Go) + "A Tour of Go" durcharbeiten.
2. Erste Übung: agent-mesh status als Go-CLI nachbauen (nur Lesen von
   nodes.json + Health-Check) — klein, abgeschlossen, real nutzbar.
3. Dann service-watchdog-Daemon portieren, parallel betreiben (A/B via
   AB-Test-Engine), bei Parität Python-Version pausieren.

## Nicht tun
- Nicht alles umschreiben. Python bleibt die Kernsprache (Ökosystem,
  LLM-Tooling, Skills). Go nur für langlebige System-Daemons.
