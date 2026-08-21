---
name: security-agent
description: Use for pip CVE scanning and auto-patching via OSV.dev API.
---

# Security Agent – CVE Scanner & Auto-Patcher

Autonomer Security Agent, der alle installierten pip-Pakete gegen die [OSV.dev](https://osv.dev) Vulnerability Database scannt und bei kritischen CVEs automatisch patched.

## Komponenten

### 1. CVE-Scan-Script (`scripts/security-cve-scan.py`)

**Standort:** `C:\Users\damir\AppData\Local\openamer-laptop\scripts\security-cve-scan.py`

**Funktionsweise:**
1. Holt alle installierten pip-Pakete per `pip list --format=json`
2. Batch-Query an OSV.dev API (`/v1/querybatch`) — bis zu 500 Pakete pro Request
3. Extrahiert CVE-IDs, Severity, Fix-Versionen aus den API-Ergebnissen
4. Bei kritischen (`CRITICAL`) oder hohen (`HIGH`) CVEs: automatisches `pip install --upgrade`
5. Speichert Report als JSON in `.security-cve/last-report.json`
6. Dedupliziert bekannte CVEs via `.security-cve/state.json`

**State-Verzeichnis:** `C:\Users\damir\AppData\Local\openamer-laptop\.security-cve\`
- `state.json` – bekannte CVEs, Scan-Stats
- `cve-scan.log` – detailliertes Log
- `last-report.json` – letzter Scan-Report

**Auto-Patching:**
- Nur für CRITICAL/HIGH Severity
- Max 10 Patches pro Run (`MAX_PATCHES_PER_RUN`)
- pip wird automatisch übersprungen (kann sich nicht selbst patchen)
- Zusätzliche Pakete via `SKIP_PACKAGES` konfigurierbar

**Exit-Codes:**
- `0` – Erfolg (keine kritischen CVEs gefunden oder alle gepatched)
- `1` – Kritische CVEs gefunden, die nicht automatisch patcht werden konnten
- `130` – Abbruch durch Benutzer

### 2. Cron-Job (alle 6h)

Der Cron-Job läuft im OpenAmer-Cron-System und führt das Script automatisch aus.

**Schedule:** `0 */6 * * *` (alle 6 Stunden)

**Script-Pfad:** `scripts/security-cve-scan.py`

## Verwendung

### Manueller Scan
```bash
cd /c/Users/damir/AppData/Local/openamer-laptop
python3 scripts/security-cve-scan.py
```

### Letzten Report als JSON ansehen
```bash
python3 scripts/security-cve-scan.py --json
```

### Logs prüfen
```bash
cat /c/Users/damir/AppData/Local/openamer-laptop/.security-cve/cve-scan.log
cat /c/Users/damir/AppData/Local/openamer-laptop/.security-cve/last-report.json
```

## API-Referenz: OSV.dev

- **Endpoint:** `POST https://api.osv.dev/v1/querybatch`
- **Ecosystem:** `PyPI`
- **Payload:** `{"queries": [{"package": {"name": "...", "ecosystem": "PyPI"}, "version": "..."}]}`
- **Dokumentation:** https://google.github.io/osv.dev/post-v1-querybatch/

## Fehlerbehandlung

| Problem | Lösung |
|---------|--------|
| OSV.dev API rate-limited (429) | Automatisches Retry mit exponential backoff |
| pip kann nicht gepatched werden | In `SKIP_PACKAGES` konfiguriert |
| Scan zu langsam | Reduziere `MAX_PATCHES_PER_RUN` im Script |
| Log voll | Log leeren: `> /c/Users/damir/AppData/Local/openamer-laptop/.security-cve/cve-scan.log` |

## Integration mit anderen Agents

Der Security Agent harmoniert mit:
- **Bugbot** – erstellt Issues aus Sicherheitsfunden
- **PR Agent** – reviewed Code auf Sicherheitsmuster