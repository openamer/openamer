# Provenance Plugin Pattern — Case Study

Implements: W3C-PROV-inspired tool-call tracking as a self-contained plugin.

## Architecture

- **State**: Module-level globals (`_records: list[dict]`, `_session_id`, `_tool_counter`)
- **Hooks**: onReady (init), onMessage (capture prompt), onToolCall (track calls)
- **Persist**: `_flush()` writes PROV-JSON to `reports/provenance/prov-*.json`
- **Dashboard**: `reports/provenance/dashboard.html` — standalone static HTML, dark theme, loads prov-index.json
- **Export**: `_export_html()` generates prov-report-*.html at session_end

## Key Design Decisions

1. **onToolCall returns None** — instrumentation only, never modifies arguments or results
2. **Batch flush at threshold** (default 500 records) — avoids memory blowout in long sessions
3. **Dual output** — JSON (machine parseable, PROV-conformant) + HTML (human readable)
4. **Index file** (prov-index.json) — manifest for dashboard to discover prov-*.json files
5. **Auto-cleanup** — daily cron at 3am deletes prov-*.json older than 7 days

## JSON Structure

```json
{
  "prefix": {"prov": "http://www.w3.org/ns/prov#", "openamer": "https://openamer.ai/prov/"},
  "session": {"id": "...", "start": "ISO8601", "end": null},
  "entity": {"input-1": {"prov:type": "prov:Entity", "prov:value": "truncated"}},
  "activity": {"tool-call-1": {"prov:type": "prov:Activity", "prov:startTime": "..."}},
  "agent": {"openamer:user": {}, "openamer:agent": {"prov:wasStartedBy": "openamer:user"}},
  "records": [{"tool_name": "web_search", "duration_ms": 1500, "exit_success": true, ...}]
}
```

## Verification

- `plugin-manager.py check provenance` → ✅ Enabled
- Integration test: create 2 fake records, call _flush(session_end=True), assert JSON + HTML + index written
- dashboard.html: DOCTYPE present, dark-theme vars (`0d4aa`), fetch referencing prov-index.json

## Files

- `desktop-plugins/provenance/__init__.py` — 518 lines, 20KB
- `reports/provenance/dashboard.html` — 16.7KB, standalone, vanilla JS
- Cron job: `provenance-cleanup` (9d769e6eb1b6), schedule `0 3 * * *`