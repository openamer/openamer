"""
provenance — PROV-AGENT-inspiriertes Provenance-Tracking für OpenAmer.

Trackt jeden Tool-Call des Agenten mit Kontext (Prompt → Reasoning → Tool → Ergebnis)
als W3C-PROV-artiges JSON. Gibt einen Audit-Trail über:
  - Welcher Prompt hat welchen Tool-Call ausgelöst?
  - Was war das Ergebnis?
  - Wie lang hat der Call gedauert?
  - Welche Tool-Argumente wurden verwendet?

Struktur folgt dem W3C PROV-Standard (vereinfacht):
  - prov:Activity = Tool-Call
  - prov:Agent = User / OpenAmer
  - prov:Entity = Prompt / Result
  - prov:wasStartedBy = User startet Activity
  - prov:wasGeneratedBy = Result von Activity
  - prov:used = Activity nutzt Prompt/Input
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Globale Session-Daten (pro Plugin-Load, also pro Agent-Start) ──────────

import uuid as _uuid

_session_id: str = _uuid.uuid4().hex
_session_start: str = ""
_tool_counter: int = 0
_current_prompt: str = ""
_current_message_id: str = ""
_records: list[dict] = []
_output_dir: Path = Path()
_max_entries: int = 500

# ─── Hilfsfunktionen ────────────────────────────────────────────────────────


def _now_iso() -> str:
    """ISO-8601 Timestamp für PROV-Konformität."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def _truncate(text: str, max_len: int = 500) -> str:
    """Kürze lange Texte für JSON-Lesbarkeit + Dateigröße."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... [truncated, {len(text)} total chars]"


def _prov_activity(name: str, label: str, start: str, end: str,
                   args: dict) -> dict:
    """Erzeuge einen PROV-Activity-Eintrag."""
    return {
        "prov:type": "prov:Activity",
        "prov:label": label,
        "prov:startTime": start,
        "prov:endTime": end,
        "prov:arguments": {k: _truncate(str(v), 200) for k, v in args.items()},
    }


def _prov_entity(eid: str, label: str, value: str,
                 etype: str = "prov:Entity") -> dict:
    """Erzeuge einen PROV-Entity-Eintrag."""
    return {
        "prov:type": etype,
        "prov:label": label,
        "prov:value": _truncate(value, 1000),
    }


def _flush(session_end: bool = False) -> None:
    """Schreibe aktuelle Records als PROV-JSON-Datei."""
    global _records
    if not _records:
        return

    output_dir = _output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d-%H%M%S")
    suffix = "final" if session_end else f"batch-{ts}"
    filename = f"prov-{_session_id[:12]}-{suffix}.json"
    filepath = output_dir / filename

    # PROV-Container
    prov_doc = {
        "prefix": {
            "prov": "http://www.w3.org/ns/prov#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "openamer": "https://openamer.ai/prov/",
        },
        "session": {
            "id": _session_id,
            "start": _session_start,
            "end": _now_iso() if session_end else None,
        },
        "entity": {},
        "activity": {},
        "agent": {
            "openamer:user": {
                "prov:type": "prov:Person",
                "prov:label": "User (Damir)",
            },
            "openamer:agent": {
                "prov:type": "prov:SoftwareAgent",
                "prov:label": "OpenAmer Agent",
                "prov:wasStartedBy": "openamer:user",
            },
        },
        "wasGeneratedBy": {},
        "used": {},
        "wasStartedBy": {},
        "wasAssociatedWith": {},
        "records": _records,  # Full chronological list for playback
    }

    for rec in _records:
        aid = rec["activity_id"]
        eid_input = rec["entity_id_input"]
        eid_output = rec["entity_id_output"]

        prov_doc["activity"][aid] = _prov_activity(
            aid, rec["tool_label"], rec["start"], rec.get("end", rec["start"]),
            rec.get("arguments", {}),
        )
        prov_doc["entity"][eid_input] = _prov_entity(
            eid_input,
            f"Input: {rec['tool_name']}",
            rec.get("prompt_snapshot", ""),
        )
        prov_doc["entity"][eid_output] = _prov_entity(
            eid_output,
            f"Output: {rec['tool_name']}",
            str(rec.get("result_snapshot", "")),
        )
        prov_doc["wasStartedBy"][aid] = "openamer:agent"
        prov_doc["wasAssociatedWith"][aid] = "openamer:agent"
        prov_doc["used"][aid] = [eid_input]
        prov_doc["wasGeneratedBy"][eid_output] = aid

    filepath.write_text(
        json.dumps(prov_doc, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(
        f"📝 Provenance flushed: {len(_records)} records → {filepath.name}"
    )

    # PROV-Index für das Dashboard aktualisieren
    _update_index()

    # HTML-Report bei Session-Ende generieren
    if session_end:
        _export_html(_records, session_end=True)

    _records = []


# ─── HTML-Export ────────────────────────────────────────────────────────────


def _update_index() -> None:
    """Schreibe/aktualisiere prov-index.json als Manifest für das Dashboard."""
    output_dir = _output_dir
    if not output_dir.is_dir():
        return
    try:
        json_files = sorted(
            [p.name for p in output_dir.iterdir() if p.name.startswith("prov-") and p.suffix == ".json" and p.name != "prov-index.json"],
            key=lambda n: n, reverse=True,
        )
        index_path = output_dir / "prov-index.json"
        index_path.write_text(
            json.dumps({"files": json_files}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning(f"⚠️ prov-index.json konnte nicht geschrieben werden: {exc}")


def _export_html(records: list[dict], session_end: bool = False) -> None:
    """Erzeuge einen standalone HTML-Report mit eingebetteten Daten.

    Wird nur bei session_end=True aufgerufen. Erzeugt eine Datei
    prov-report-<timestamp>.html im reports/provenance/ Verzeichnis.
    """
    if not session_end or not records:
        return

    output_dir = _output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d-%H%M%S")
    filename = f"prov-report-{ts}.html"
    filepath = output_dir / filename

    # Daten als JSON ins HTML einbetten
    data_json = json.dumps({
        "session_id": _session_id,
        "session_start": _session_start,
        "session_end": _now_iso(),
        "total_records": len(records),
        "records": records,
    }, ensure_ascii=False)

    # Statistik
    total = len(records)
    errors = sum(1 for r in records if r.get("exit_success") is False)
    total_dur = sum(r.get("duration_ms", 0) or 0 for r in records)
    unique_tools = sorted(set(r.get("tool_name", "") for r in records if r.get("tool_name")))
    sorted_records = sorted(records, key=lambda r: r.get("start", ""))

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Provenance Report — {ts}</title>
<style>
  :root {{
    --bg: #1a1a2e;
    --surface: #16213e;
    --surface2: #1f2b4a;
    --text: #e0e0e0;
    --text-dim: #8a8aa0;
    --accent: #00d4aa;
    --accent-dim: #009b7a;
    --red: #e74c3c;
    --green: #2ecc71;
    --badge-bg: #2a3a5c;
    --border: #2a3a5c;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); padding: 24px; min-height: 100vh;
  }}
  h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
  .subtitle {{ color: var(--text-dim); font-size: 0.9rem; margin-bottom: 20px; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 20px; }}
  .meta-item {{ font-size: 0.85rem; }}
  .meta-item strong {{ color: var(--accent); }}
  .meta-item span {{ color: var(--text-dim); font-family: monospace; font-size: 0.8rem; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }}
  .stat-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px 18px; flex: 0 0 auto; min-width: 120px;
  }}
  .stat-card .num {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
  .stat-card .label {{ font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; }}
  .controls {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; align-items: center; }}
  .controls input, .controls select {{
    background: var(--surface2); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 10px; font-size: 0.85rem;
  }}
  .controls input {{ min-width: 160px; }}
  .filter-count {{ font-size: 0.85rem; color: var(--text-dim); margin-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; }}
  th {{ text-align: left; padding: 8px 10px; background: var(--surface2); color: var(--text-dim); font-weight: 600; border-bottom: 2px solid var(--border); white-space: nowrap; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  tr:hover td {{ background: rgba(0,212,170,0.04); }}
  .badge {{
    display: inline-block; background: var(--badge-bg); color: var(--accent);
    border-radius: 4px; padding: 2px 7px; font-size: 0.72rem; font-family: monospace;
  }}
  .badge.err {{ color: var(--red); background: rgba(231,76,60,0.12); }}
  .badge.ok {{ color: var(--green); background: rgba(46,204,113,0.12); }}
  .dur-bar {{
    display: inline-block; height: 10px; border-radius: 5px;
    background: linear-gradient(90deg, var(--accent), var(--accent-dim));
    min-width: 6px; vertical-align: middle;
  }}
  .dur-bar.slow {{ background: linear-gradient(90deg, var(--yellow), var(--red)); }}
  .ts-cell {{ font-size: 0.75rem; color: var(--text-dim); white-space: nowrap; font-family: monospace; }}
  .prompt-preview {{ color: var(--text-dim); font-size: 0.78rem; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .no-data {{ text-align: center; padding: 40px 20px; color: var(--text-dim); }}
  @media (max-width: 768px) {{
    body {{ padding: 12px; }}
    .controls {{ flex-direction: column; align-items: stretch; }}
    table {{ font-size: 0.75rem; }}
    td, th {{ padding: 4px 6px; }}
    .prompt-preview {{ max-width: 120px; }}
  }}
</style>
</head>
<body>

<h1>📋 Provenance Report</h1>
<p class="subtitle">Erstellt am {ts}</p>

<div class="meta">
  <div class="meta-item"><strong>Session:</strong> <span>{_session_id[:16]}…</span></div>
  <div class="meta-item"><strong>Start:</strong> <span>{_session_start}</span></div>
  <div class="meta-item"><strong>Ende:</strong> <span>{_now_iso()}</span></div>
</div>

<div class="stats">
  <div class="stat-card"><div class="num">{total}</div><div class="label">Records</div></div>
  <div class="stat-card"><div class="num">{errors}</div><div class="label">Fehler</div></div>
  <div class="stat-card"><div class="num">{len(unique_tools)}</div><div class="label">Tools</div></div>
  <div class="stat-card"><div class="num">{total_dur / 1000:.1f}s</div><div class="label">Dauer</div></div>
</div>

<div class="controls">
  <label>Tool: <select id="ftool"><option value="">Alle</option></select></label>
  <label>Status: <select id="fstatus"><option value="">Alle</option><option value="ok">Erfolg</option><option value="err">Fehler</option></select></label>
  <label>Suche: <input id="fsearch" type="text" placeholder="Prompt/Result …"></label>
</div>
<div class="filter-count" id="fcount"></div>

<table>
<thead><tr>
  <th>#</th>
  <th>Tool</th>
  <th>Label</th>
  <th>Start</th>
  <th>Dauer</th>
  <th>Status</th>
  <th>Prompt</th>
</tr></thead>
<tbody id="tbody"></tbody>
</table>

<script>
const DATA = {data_json};

function render() {{
  const ft = document.getElementById('ftool').value;
  const fs = document.getElementById('fstatus').value;
  const fq = document.getElementById('fsearch').value.toLowerCase();

  let filtered = DATA.records;
  if (ft) filtered = filtered.filter(r => r.tool_name === ft);
  if (fs === 'ok') filtered = filtered.filter(r => r.exit_success !== false);
  if (fs === 'err') filtered = filtered.filter(r => r.exit_success === false);
  if (fq) filtered = filtered.filter(r =>
    (r.prompt_snapshot || '').toLowerCase().includes(fq) ||
    (r.result_snapshot || '').toLowerCase().includes(fq) ||
    (r.tool_name || '').toLowerCase().includes(fq)
  );

  document.getElementById('fcount').textContent = filtered.length + ' von ' + DATA.records.length + ' Einträgen';

  const maxDur = Math.max(...filtered.map(r => r.duration_ms || 0), 1);
  let body = '';
  filtered.forEach((r, i) => {{
    const dur = r.duration_ms || 0;
    const pct = Math.min((dur / maxDur) * 100, 100);
    const isSlow = dur > 5000;
    const status = r.exit_success === false ? '❌' : '✅';
    const badgeClass = r.exit_success === false ? 'badge err' : 'badge ok';
    const start = r.start || '';
    const prompt = (r.prompt_snapshot || '').slice(0, 60);

    body += '<tr>' +
      '<td>' + (i+1) + '</td>' +
      '<td><span class="' + badgeClass + '">' + (r.tool_name || '-') + '</span></td>' +
      '<td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + (r.tool_label || '').slice(0, 50) + '</td>' +
      '<td class="ts-cell">' + start.slice(11, 19) + '</td>' +
      '<td><div style="display:flex;align-items:center;gap:6px;"><span class="dur-bar' + (isSlow ? ' slow' : '') + '" style="width:' + pct + '%;max-width:100px;"></span><span style="font-family:monospace;font-size:0.72rem;">' + (dur < 1000 ? dur.toFixed(0) + 'ms' : (dur/1000).toFixed(2) + 's') + '</span></div></td>' +
      '<td>' + status + '</td>' +
      '<td><div class="prompt-preview">' + prompt + '</div></td>' +
      '</tr>';
  }});
  document.getElementById('tbody').innerHTML = body || '<tr><td colspan="7" class="no-data">🔍 Keine Treffer</td></tr>';
}}

// Filter-Optionen befüllen
const tools = [...new Set(DATA.records.map(r => r.tool_name).filter(Boolean))].sort();
tools.forEach(t => {{
  const opt = document.createElement('option');
  opt.value = t; opt.textContent = t;
  document.getElementById('ftool').appendChild(opt);
}});

document.getElementById('ftool').addEventListener('change', render);
document.getElementById('fstatus').addEventListener('change', render);
document.getElementById('fsearch').addEventListener('input', render);
render();
</script>
</body>
</html>"""

    filepath.write_text(html, encoding="utf-8")
    logger.info(
        f"📄 Provenance HTML-Report: {filepath.name} ({total} records)"
    )


# ─── Hooks ──────────────────────────────────────────────────────────────────


def register(ctx) -> None:
    """Plugin-Einsprungspunkt — registriert Provenance-Hooks."""
    global _session_id, _session_start, _output_dir, _max_entries

    # ─── Config-Lesen ───────────────────────────────────────────────────
    repo = Path(r"C:\Users\damir\openamer-repo")
    rel_dir = ctx.get_config("output_dir", "reports/provenance")
    _output_dir = repo / rel_dir
    _max_entries = ctx.get_config("max_entries_per_file", 500)

    # ─── onReady: Session initialisieren ────────────────────────────────
    @ctx.on_ready
    def on_ready() -> None:
        global _session_id, _session_start, _records
        _session_id = uuid.uuid4().hex
        _session_start = _now_iso()
        _records = []
        enabled = ctx.get_config("enabled", True)
        if enabled:
            ctx.log_info(
                f"🔍 Provenance-Tracking aktiv — Session {_session_id[:12]}… "
                f"→ {_output_dir}"
            )
        else:
            ctx.log_info("🔍 Provenance-Tracking deaktiviert (config)")

    # ─── onMessage: Aktuellen Prompt merken ─────────────────────────────
    @ctx.on_message(priority=50)
    def on_message(message: str) -> Optional[str]:
        """Merke die aktuelle User-Nachricht als Prompt-Kontext."""
        global _current_prompt, _current_message_id
        if ctx.get_config("enabled", True):
            _current_prompt = message
            _current_message_id = uuid.uuid4().hex[:8]
        return None  # Nie die Nachricht ändern

    # ─── onToolCall: Vor/Nach jedem Tool-Call ──────────────────────────
    @ctx.on_tool_call
    def on_tool_call(
        tool_name: str,
        arguments: dict,
        phase: str,
        result: Any = None,
    ) -> Optional[dict]:
        """Tracke jeden Tool-Call mit PROV-Metadaten."""
        global _tool_counter, _records

        if not ctx.get_config("enabled", True):
            return None

        if phase == "before":
            _tool_counter += 1
            n = _tool_counter
            aid = f"tool-call-{n}"
            label = f"{tool_name}({_truncate(str(arguments), 150)})"

            rec = {
                "activity_id": aid,
                "entity_id_input": f"input-{n}",
                "entity_id_output": f"output-{n}",
                "tool_name": tool_name,
                "tool_label": label,
                "arguments": arguments,
                "start": _now_iso(),
                "prompt_snapshot": _current_prompt,
                "message_id": _current_message_id,
                "session_id": _session_id,
            }
            _records.append(rec)
            return None  # Keine Änderung an Argumenten

        if phase == "after" and _records:
            # Letzten Record mit Ergebnis anreichern
            last = _records[-1]
            last["end"] = _now_iso()
            last["duration_ms"] = _compute_duration_ms(last.get("start"))
            last["result_snapshot"] = _truncate(str(result), 1000)
            last["exit_success"] = _is_success(result)

            # Automatischer Flush bei Erreichen des Limits
            if len(_records) >= _max_entries:
                _flush()

            # Kurz-Log
            logger.debug(
                f"  ⚡ {last['tool_label']} → "
                f"{last.get('duration_ms', '?')}ms"
            )
            return None  # Keine Änderung am Ergebnis

        return None


def _compute_duration_ms(start_str: Optional[str]) -> Optional[float]:
    """Berechne Dauer in ms aus ISO-Start-Zeit."""
    if not start_str:
        return None
    try:
        start_dt = datetime.datetime.fromisoformat(start_str)
        now = datetime.datetime.now(datetime.timezone.utc)
        return (now - start_dt).total_seconds() * 1000
    except Exception:
        return None


def _is_success(result: Any) -> bool:
    """Prüfe ob ein Tool-Ergebnis erfolgreich war."""
    if isinstance(result, dict):
        # Typische Tool-Ergebnisse haben exit_code oder error
        ec = result.get("exit_code")
        if ec is not None:
            return ec == 0
        err = result.get("error")
        return err is None or err == ""
    return True