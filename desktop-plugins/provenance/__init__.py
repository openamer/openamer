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
    _records = []


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