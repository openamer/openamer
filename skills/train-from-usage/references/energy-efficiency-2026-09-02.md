# Energy-Efficiency Optimizations — 02.09.2026 (live verifiziert)

Kontext: User-These — GPU-Backprop ist energetisch eine Sackgasse. GPT-4-Training
~50 GWh vs. Menschenhirn 20 W × 20 Jahre = 3,5 MWh (Faktor ~14 Mio). Konsequenz:
Der ASI-Weg führt über „klüger mit weniger Energie", nicht über mehr GPU.

## 1. Embedding-Cache (longterm_memory.py, gepusht)

- `embed()` hashed den Text (SHA-256 der ersten 4000 Zeichen, key = hash[:24]) →
  persistenter JSON-Cache `memory/embed_cache.json` (LRU-artig, max 5000 Einträge).
- **Gemessen**: erster Call 1381 ms, Cache-Hit **10 ms** (99 % Ersparnis pro
  redundantem Call). Cache wirkt auf wiederholte Queries; Episode-Texte selbst
  sind unique (3012/3012), der Index-Reindex profitiert also nicht.

## 2. Mini-Server Wake-on-Demand + Idle-Timeout (serve_mini.py, gepusht)

- Server startet NICHT beim Boot; nur bei Anfrage oder durch Retrain-Cron (04:00).
- Neu: `IDLE_TIMEOUT = 1800` s; Daemon-Thread prüft minütlich und ruft nach 30 min
  ohne Anfrage `os._exit(0)`; `do_POST` resettet `last_request["ts"]`.
- Effekt: idle ~840 Wh/Tag → ~0 Wh (Prozess existiert nicht).
- Zwei-Layer mit dem bestehenden RAM-Guard im Retrain-Cron (≥8 GB frei).

## 3. Dream-weighted Training (distill_sft.py, gepusht)

- Bio-inspiriert (Hebbian-artig): Motive, die an ≥3 Nächten in dreams.json
  auftauchen, lassen ihre zugehörigen SFT-Paare 3x duplizieren → die begrenzte
  CPU-Trainings-Energie fließt in wiederkehrende Fehler statt Einmal-Rauschen.
- Aktuell 0 recurring nightmares → keine Duplikate; Mechanismus aktiviert sich
  automatisch, sobald der Dream Cycle ein Motiv als Nightmare markiert.

## Messung & K.O.-Rechnung

- System-Fußabdruck heute: **< 1 kWh** (CPU-LoRA ~50 Wh, Dream ~5 Wh, Rest minimal).
- GPT-4-Training: ~50.000.000 kWh. Neuromorphik (BrainChip Akida ~30 mW, Intel
  Loihi 2): Spiking + lokale Plastizität statt globalem Backprop = der langfristige
  Pfad. Roadmap: Repo `docs/GPU-UPGRADE-DECISION.md`; öffentliche Beweis-Seite mit
  Live-Metriken: `docs/superiority.html` (auf GitHub Pages live).
