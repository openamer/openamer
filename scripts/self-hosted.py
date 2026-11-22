#!/usr/bin/env python3
"""
Self-Hosted Independence v1.0 — Ollama/Local-LLM-Detection + Auto-Failover + Health
===================================================================================
Prüft Verfügbarkeit von Ollama (localhost:11434), llama.cpp, und lokalen Modellen.
Generiert Fallback-Config, testet Health-Endpoints (primary + fallback) alle 60s,
und schaltet bei 3x Fehlschlag automatisch auf local um.

CLI:
  --check       Prüft alle verfügbaren Provider (Ollama, llama.cpp, lokale Modelle)
  --status      Zeigt aktuelle Config + Health-Status
  --switch-to   Manuell umschalten: 'local' | 'remote' | 'auto'
  --bench       Benchmark-Latenz: remote vs local
  --report      JSON-Report aller Checks und Health
  --setup       Automatische Ollama-Installation + Modell-Download via API

Exit-Codes:
  0 = alles OK (primary aktiv)
  1 = Fallback aktiv (local läuft, primary down)
  2 = kein LLM verfügbar
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Pfade ───────────────────────────────────────────────────────────────────
HOME = Path.home()
_RAW_OPENAMER_HOME = os.environ.get("OPENAMER_HOME")
if _RAW_OPENAMER_HOME:
    _NORM = re.sub(r"^/([a-zA-Z])/", lambda m: f"{m.group(1).upper()}:\\", _RAW_OPENAMER_HOME)
    OPENAMER_HOME = Path(_NORM).resolve()
else:
    OPENAMER_HOME = HOME / "AppData" / "Local" / "openamer-laptop"

SELF_HOSTED_DIR = HOME / ".self-hosted"
CONFIG_FILE = SELF_HOSTED_DIR / "config.json"
STATE_FILE = SELF_HOSTED_DIR / "state.json"
SCRIPTS_DIR = HOME / "scripts"
OPENAMER_CONFIG = OPENAMER_HOME / "config.yaml"
ENV_FILE = OPENAMER_HOME / ".env"

# Provider id -> (inference base url, env var holding the key). Mirrors
# openamer_cli/auth.py for the providers this install can run on, so the check
# can probe the provider the agent is actually configured to use.
PROVIDER_ENDPOINTS = {
    "ollama-cloud": ("https://ollama.com/v1", "OLLAMA_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "token-harbor": ("https://tokenhub.tencentmaas.com/v1", "TOKENHARBOR_API_KEY"),
}


def load_dotenv_secrets(path: Path = ENV_FILE) -> int:
    """Load KEY=VALUE secrets from ``$OPENAMER_HOME/.env`` into ``os.environ``.

    Cron runs with a bare environment. The API keys live in ``.env``, so a
    check that only reads ``os.environ`` reports "kein API-Key gefunden" while
    the agent itself is answering requests through that very key (measured
    2026-11-21: OPENROUTER_API_KEY / OLLAMA_API_KEY present in .env, absent
    from the cron process). Values already present in the environment win, so
    an explicit export in the calling process is never overridden.
    """
    loaded = 0
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = value.strip().strip('"').strip("'")
        if value and key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


load_dotenv_secrets()

# ── Defaults ────────────────────────────────────────────────────────────────
# IPv4 explizit, NICHT "localhost": auf diesem Host loest "localhost" zuerst auf
# ::1 (IPv6) auf, der Ollama-Server lauscht aber nur auf 127.0.0.1. urllib
# probiert die getaddrinfo-Liste in Reihenfolge und hat KEINEN Fallback auf die
# naechste Adresse -> jeder Request verbrannte den vollen Timeout (5s/30s) und
# meldete danach faelschlich "Ollama nicht verfuegbar".
# Gemessen 2026-10-25: /api/tags via 127.0.0.1 = 200, via localhost = Timeout.
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_TAGS_URL = f"{OLLAMA_URL}/api/tags"
LLAMACPP_URL = "http://127.0.0.1:8080"
DEFAULT_LOCAL_MODEL = "qwen3.5:4b-q4_K_M"  # 9.7B ('latest') eats 6GB RAM and OOMs the loops; 4b-q4 costs ~3.4GB (verified tag)
LOCAL_MODEL_FALLBACK = "phi4-mini:latest"
TINY_MODEL = "qwen3:1.7b"  # CPU-Modus (kleines Modell)

# Für OpenRouter als Primary (falls in .env oder config.yaml)
PRIMARY_PROVIDER_URL = "https://openrouter.ai/api/v1/chat/completions"
PRIMARY_TIMEOUT = 10
LOCAL_TIMEOUT = 60
# /api/tags braucht unter Windows 6-17s (alle Manifeste werden gescannt).
# Gemessen 2026-10-25. 5s war zu knapp -> Health-Check meldete faelschlich
# "Ollama nicht verfuegbar".
OLLAMA_TAGS_TIMEOUT = 30
FAILOVER_THRESHOLD = 3


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_json(url: str, timeout: int = 10) -> tuple[int, Any, float]:
    """GET-Request, gibt (status, parsed_json_or_None, elapsed_seconds) zurück."""
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            data = json.loads(raw) if raw else None
            elapsed = time.monotonic() - t0
            return resp.status, data, elapsed
    except urllib.error.HTTPError as e:
        return e.code, None, time.monotonic() - t0
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        return 0, {"_error": str(e)}, time.monotonic() - t0
    except json.JSONDecodeError as e:
        return 0, {"_error": f"json: {e}"}, time.monotonic() - t0


# ═══════════════════════════════════════════════════════════════════════════════
#  OLLAMA-DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def check_ollama() -> dict:
    """Prüft ob Ollama läuft und listet verfügbare Modelle.

    Zwei Stufen, weil /api/tags unter Windows SEHR langsam ist: der Ollama-App
    scannt dafuer alle Modell-Manifeste auf Platte. Gemessen 2026-10-25:
    /api/version = 0.02s, /api/tags = 6-17s (41 Modelle). Mit einem 5s-Timeout
    auf /api/tags meldete der Health-Check faelschlich "Ollama nicht
    verfuegbar", obwohl der Server laeuft.

    Also: /api/version (schnell) entscheidet die Verfuegbarkeit, /api/tags
    liefert nur die Modelliste und ist best-effort - ein Timeout dort darf die
    Verfuegbarkeit NICHT verneinen.
    """
    result: dict[str, Any] = {
        "available": False,
        "version": None,
        "models": [],
        "error": None,
    }
    # Stufe 1: Liveness (schnell, fail-closed fuer "available")
    # Ein einzelner Fehlschlag ist noch kein Ausfall: gemessen 2026-11-16
    # scheiterten 36 von 183 Laeufen in SCHUEBEN (12 in einer Stunde, 10 in
    # einer anderen) — der Server ist unter Last kurz busy bzw. startet neu.
    # Ein Retry mit kurzer Pause trennt "Huster" von "wirklich weg"; ein echter
    # Ausfall scheitert weiterhin an BEIDEN Versuchen und failt korrekt.
    vstatus, vdata, _ = _http_json(f"{OLLAMA_URL}/api/version", timeout=5)
    if vstatus != 200:
        time.sleep(1.0)
        vstatus, vdata, _ = _http_json(f"{OLLAMA_URL}/api/version", timeout=5)
    if vstatus != 200:
        result["error"] = f"HTTP {vstatus}" if vstatus else "unreachable"
        return result

    result["available"] = True
    result["version"] = (
        vdata.get("version", "ollama (unknown ver)")
        if isinstance(vdata, dict)
        else "ollama (unknown ver)"
    )

    # Stufe 2: Modelliste (langsam, best-effort)
    status, data, elapsed = _http_json(OLLAMA_TAGS_URL, timeout=OLLAMA_TAGS_TIMEOUT)
    if status == 200 and data and "models" in data:
        result["models"] = [
            {
                "name": m.get("name", "?"),
                "size_gb": round(m.get("size", 0) / 1e9, 2) if m.get("size") else None,
                "quantization": m.get("details", {}).get("quantization", "?"),
            }
            for m in data["models"]
        ]
        # Pruef ob empfehlenswerte Modelle da sind
        model_names = {m.get("name", "") for m in data["models"]}
        result["has_coder_model"] = any("deepseek-coder" in n for n in model_names)
        result["has_qwen_coder"] = any("qwen2.5-coder" in n for n in model_names)
        result["has_tiny"] = any("llama3.2:1b" in n for n in model_names) or any("tiny" in n for n in model_names)
    else:
        # Liveness steht fest - nur die Liste fehlt. Nicht als Fehler werten.
        result["model_list_error"] = (
            f"HTTP {status}" if status else (data or {}).get("_error", "unreachable")
        )
    return result


def check_ollama_version() -> str | None:
    """Ermittelt Ollama-Version über /api/version."""
    try:
        _, data, _ = _http_json(f"{OLLAMA_URL}/api/version", timeout=3)
        if data and isinstance(data, dict):
            return data.get("version", str(data))
        if isinstance(data, str):
            return data
        return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  LLAMA.CPP-DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def check_llamacpp() -> dict:
    """Prüft ob llama.cpp server (localhost:8080) läuft."""
    result: dict[str, Any] = {
        "available": False,
        "endpoint": LLAMACPP_URL,
        "models": [],
        "error": None,
    }
    status, data, elapsed = _http_json(f"{LLAMACPP_URL}/v1/models", timeout=4)
    if status == 200 and data:
        result["available"] = True
        if isinstance(data, dict) and "data" in data:
            result["models"] = [m.get("id", "?") for m in data["data"]]
        else:
            result["models"] = ["unknown"]
    elif status != 0:
        result["error"] = f"HTTP {status}"
    else:
        err = data.get("_error", "unreachable") if data else "unreachable"
        result["error"] = err
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  PRIMARY-PROVIDER HEALTH (OpenRouter / konfigurierter Remote-Provider)
# ═══════════════════════════════════════════════════════════════════════════════

def check_primary_health(config: dict) -> dict:
    """Testet ob der primäre (Remote-)Provider erreichbar ist."""
    result: dict[str, Any] = {
        "available": False,
        "latency_ms": None,
        "error": None,
    }
    # Schau in der Config nach
    primary_url = config.get("primary", {}).get("endpoint", PRIMARY_PROVIDER_URL)
    api_key = os.environ.get("OPENROUTER_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        result["error"] = "kein API-Key gefunden (OPENROUTER_API_KEY oder OPENAI_API_KEY)"
        return result

    # Leichter Health-Check: versuche einen kleinen Request
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(
            f"{primary_url.rstrip('/')}/models" if "chat/completions" not in primary_url
            else "https://openrouter.ai/api/v1/models",
            method="GET",
        )
        req.add_header("Accept", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(req, timeout=PRIMARY_TIMEOUT) as resp:
            _ = resp.read()
            elapsed = time.monotonic() - t0
            result["available"] = True
            result["latency_ms"] = round(elapsed * 1000)

            # Prüf konkrete Endpoint-Reachability
            if "openrouter" in primary_url:
                result["provider"] = "openrouter"
            else:
                result["provider"] = "custom"
    except urllib.error.HTTPError as e:
        result["error"] = f"HTTP {e.code}: {e.reason}"
        result["latency_ms"] = round((time.monotonic() - t0) * 1000)
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        result["error"] = str(e)
        result["latency_ms"] = round((time.monotonic() - t0) * 1000)
    return result


def check_configured_provider(config: dict | None = None) -> dict:
    """Probe the provider the agent is actually configured to run on.

    The rest of this script models a local-Ollama + OpenRouter world. The
    agent's real chain is whatever ``model.provider`` says in config.yaml, and
    on this install that is ``ollama-cloud``. A health check that never looks
    there reports "kein LLM verfügbar" (exit 2, every 5 minutes) while the
    assistant answers every request fine — the alarm measures a landscape that
    no longer exists. Probe the configured provider instead.
    """
    result: dict[str, Any] = {
        "available": False,
        "provider": None,
        "endpoint": None,
        "latency_ms": None,
        "error": None,
    }
    agent_cfg = _read_agent_config()
    provider_id = str(agent_cfg.get("provider") or "").strip()
    result["provider"] = provider_id or None
    if not provider_id:
        result["error"] = "kein model.provider in config.yaml"
        return result

    base_url = str(agent_cfg.get("base_url") or "").strip()
    key_env = None
    if provider_id in PROVIDER_ENDPOINTS:
        default_url, key_env = PROVIDER_ENDPOINTS[provider_id]
        base_url = base_url or default_url
    if not base_url:
        result["error"] = f"unbekannter Provider ohne base_url: {provider_id}"
        return result
    result["endpoint"] = base_url

    api_key = os.environ.get(key_env, "") if key_env else ""
    if key_env and not api_key:
        result["error"] = f"kein API-Key ({key_env})"
        return result

    url = f"{base_url.rstrip('/')}/models"
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(req, timeout=PRIMARY_TIMEOUT) as resp:
            _ = resp.read()
        result["available"] = True
        result["latency_ms"] = round((time.monotonic() - t0) * 1000)
    except urllib.error.HTTPError as e:
        result["error"] = f"HTTP {e.code}: {e.reason}"
        result["latency_ms"] = round((time.monotonic() - t0) * 1000)
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        result["error"] = str(e)
        result["latency_ms"] = round((time.monotonic() - t0) * 1000)
    return result


def _read_agent_config() -> dict:
    """Read ``$OPENAMER_HOME/config.yaml``; best effort, no hard PyYAML need."""
    try:
        import yaml  # type: ignore

        with OPENAMER_CONFIG.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if isinstance(data, dict):
            model_block = data.get("model")
            if isinstance(model_block, dict):
                return model_block
            return data
    except Exception:
        pass
    # Regex fallback for the top-level ``model:`` block only.
    out: dict[str, Any] = {}
    try:
        text = OPENAMER_CONFIG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    block = re.search(r"^model:\s*$(.*?)(?=^\S|\Z)", text, re.M | re.S)
    if block:
        for key in ("provider", "default", "base_url"):
            m = re.search(rf"^\s+{key}:\s*(.+)$", block.group(1), re.M)
            if m:
                out[key] = m.group(1).strip().strip('"').strip("'")
    return out


# ═══════════════════════════════════════════════════════════════════════════════
#  LOCAL LLM HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

def check_local_health(config: dict) -> dict:
    """Testet ob der lokale LLM (Ollama antwortet) gesund ist."""
    result: dict[str, Any] = {
        "available": False,
        "latency_ms": None,
        "model": None,
        "error": None,
    }
    local_config = config.get("fallback", {})
    local_model = local_config.get("model", DEFAULT_LOCAL_MODEL)
    result["model"] = local_model

    # Prüf via Ollama Generate (leichter Prompt).
    # keep_alive=0: der 5-Minuten-Probe darf das Modell NICHT im RAM festhalten.
    # Ohne das blieb ein 3-6 GB Modell dauerhaft geladen (RAM ~90%) und die
    # Cloud-Calls anderer Cron-Jobs liefen in den 600s-Idle-Timeout.
    # Timeout 60s (vorher 30s): gemessene Generate-Latenz 11-14s, auf
    # ausgelastetem Host bis 25s. Bei 30s lief der Check ins Timeout und
    # meldete faelschlich "Local nicht verfuegbar". Gemessen 2026-10-25.
    t0 = time.monotonic()
    try:
        payload = json.dumps({
            "model": local_model,
            "prompt": "Hello",
            "stream": False,
            "keep_alive": 0,
            "options": {"num_predict": 10, "num_ctx": 2048},
        }).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=LOCAL_TIMEOUT) as resp:
            _ = resp.read()
            elapsed = time.monotonic() - t0
            result["available"] = True
            result["latency_ms"] = round(elapsed * 1000)
            result["provider"] = "ollama"
    except urllib.error.HTTPError as e:
        result["error"] = f"HTTP {e.code}: {e.reason}"
        result["latency_ms"] = round((time.monotonic() - t0) * 1000)
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        result["error"] = str(e)
        result["latency_ms"] = round((time.monotonic() - t0) * 1000)

    # Ein langsamer Generate-Call ist kein Ausfall.
    # Gemessen 2026-11-16: der 5-Minuten-Probe kippte in Schueben auf
    # "kein Provider" (36 von 183 Laeufen), obwohl der Ollama-Server weiterhin
    # antwortete — der Generate-Call lief unter Last in seinen Timeout. Eine
    # REACHABILITY-Probe (/api/version, kein Modell-Load) trennt "Server weg"
    # von "Server langsam": erreichbar -> degraded=True, verfuegbar=True.
    # Ein echter Ausfall bleibt ein Ausfall, weil /api/version dann ebenfalls
    # scheitert.
    if not result["available"]:
        lstatus, _ldata, _ = _http_json(f"{OLLAMA_URL}/api/version", timeout=5)
        if lstatus == 200:
            result["available"] = True
            result["degraded"] = True
            result["provider"] = "ollama"
            result["note"] = "reachable, generate probe failed or timed out"
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG + STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def load_state() -> dict:
    """Lade den Failover-State (consecutive_failures, active_provider, ...)."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "active_provider": "auto",
        "consecutive_failures": 0,
        "last_failover_at": None,
        "last_switch_reason": None,
        "health_history": [],
    }


def save_state(state: dict) -> None:
    """Persistiere den State."""
    SELF_HOSTED_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_config() -> dict:
    """Lade die Konfiguration oder generiere Default."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return _gen_default_config()


def _gen_default_config() -> dict:
    # Versuche, das beste verfügbare Modell zu erkennen
    best_model = DEFAULT_LOCAL_MODEL
    tiny_model = TINY_MODEL
    try:
        status, data, _ = _http_json(OLLAMA_TAGS_URL, timeout=3)
        if status == 200 and data and "models" in data:
            names = [m.get("name", "") for m in data["models"]]
            # Bevorzuge coder-Modelle, dann aktuelle qwen/gemma, dann phi.
            # WICHTIG: "qwen3.5:latest" (9.7B) NICHT in dieser Liste — es belegt
            # 6 GB RAM. Der 5-Minuten-Health-Check lädt das Fallback-Modell bei
            # jedem Lauf und drückte den RAM auf ~90%, wodurch die Cloud-Calls
            # anderer Cron-Jobs in den 600s-Idle-Timeout liefen (11 Crons rot).
            for pref in ["deepseek-coder", "qwen3.5:4b-q4_K_M", "qwen3.5:4b", "phi4-mini", "qwen3.5:2b"]:
                if any(pref in n for n in names):
                    best_model = next(n for n in names if pref in n)
                    break
            for tiny in ["llama3.2:1b", "qwen3:1.7b", "phi4-mini"]:
                if any(tiny in n for n in names):
                    tiny_model = next(n for n in names if tiny in n)
                    break
    except Exception:
        pass

    return {
        "primary": {
            "provider": "openrouter",
            "endpoint": "https://openrouter.ai/api/v1",
            "model": "nex-agi/nex-n2.5-mini:free",
            "timeout_s": PRIMARY_TIMEOUT,
        },
        "fallback": {
            "provider": "ollama",
            "endpoint": OLLAMA_URL,
            "model": best_model,
            "timeout_s": LOCAL_TIMEOUT,
        },
        "cpu_fallback": {
            "enabled": True,
            "model": tiny_model,
            "provider": "ollama",
        },
        "failover": {
            "threshold": FAILOVER_THRESHOLD,
            "cooldown_s": 60,
            "auto_recover": True,
            "recover_checks": 3,
        },
        "health": {
            "interval_s": 60,
            "timeout_s": 10,
        },
    }


def save_config(config: dict) -> None:
    SELF_HOSTED_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
#  FAILOVER-ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_health_cycle(config: dict) -> dict:
    """Führe einen Health-Check-Zyklus durch. Aktualisiert State + ggf. Failover."""
    state = load_state()
    active = state.get("active_provider", "auto")

    # Primary check
    primary = check_primary_health(config)
    # Local check
    local = check_local_health(config)

    # History-Eintrag
    entry = {
        "ts": _ts(),
        "primary_ok": primary.get("available", False),
        "primary_latency_ms": primary.get("latency_ms"),
        "local_ok": local.get("available", False),
        "local_latency_ms": local.get("latency_ms"),
        "active_provider": active,
    }
    history = state.get("health_history", [])
    history.append(entry)
    # Nur die letzten 100 Einträge behalten
    if len(history) > 100:
        history = history[-100:]
    state["health_history"] = history

    if active == "local":
        # Im Fallback-Modus: prüf ob primary wieder da ist
        if primary.get("available"):
            state["consecutive_failures"] = max(0, state.get("consecutive_failures", 0) - 1)
            recover_checks = config.get("failover", {}).get("recover_checks", 3)
            if state["consecutive_failures"] <= 0 and config.get("failover", {}).get("auto_recover", True):
                state["active_provider"] = "primary"
                state["consecutive_failures"] = 0
                state["last_failover_at"] = _ts()
                state["last_switch_reason"] = "auto-recover: primary wieder erreichbar"
        else:
            state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
    elif active == "primary" or active == "auto":
        if not primary.get("available"):
            state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
            threshold = config.get("failover", {}).get("threshold", FAILOVER_THRESHOLD)
            if state["consecutive_failures"] >= threshold:
                # Failover!
                if local.get("available"):
                    state["active_provider"] = "local"
                    state["last_failover_at"] = _ts()
                    state["last_switch_reason"] = f"auto-failover: primary {state['consecutive_failures']}x ausgefallen"
                    state["consecutive_failures"] = 0
                else:
                    state["last_switch_reason"] = f"failover-required, aber kein lokales LLM verfügbar"
        else:
            state["consecutive_failures"] = 0

    save_state(state)
    return {
        "state": state,
        "health": entry,
        "primary": primary,
        "local": local,
    }


def switch_provider(target: str, config: dict) -> dict:
    """Manuelles Umschalten: 'local', 'primary', 'auto'."""
    state = load_state()
    valid = ["local", "primary", "auto"]
    if target not in valid:
        return {"ok": False, "error": f"Ungültig: {target}. Gültig: {', '.join(valid)}"}

    old = state.get("active_provider", "auto")
    state["active_provider"] = target
    state["last_failover_at"] = _ts()
    state["last_switch_reason"] = f"manual switch: {old} → {target}"
    state["consecutive_failures"] = 0
    save_state(state)
    return {"ok": True, "previous": old, "current": target}


# ═══════════════════════════════════════════════════════════════════════════════
#  BENCHMARK
# ═══════════════════════════════════════════════════════════════════════════════

def run_benchmark(config: dict, rounds: int = 3) -> dict:
    """Vergleich: Latenz remote vs local."""
    results: dict[str, Any] = {"remote": [], "local": [], "summary": {}}

    for i in range(rounds):
        primary = check_primary_health(config)
        results["remote"].append({
            "round": i + 1,
            "latency_ms": primary.get("latency_ms"),
            "ok": primary.get("available", False),
            "error": primary.get("error"),
        })
        time.sleep(0.5)

        local = check_local_health(config)
        results["local"].append({
            "round": i + 1,
            "latency_ms": local.get("latency_ms"),
            "ok": local.get("available", False),
            "error": local.get("error"),
            "model": local.get("model"),
        })
        time.sleep(0.5)

    # Summary
    remote_lats = [r["latency_ms"] for r in results["remote"] if r.get("latency_ms")]
    local_lats = [r["latency_ms"] for r in results["local"] if r.get("latency_ms")]
    results["summary"] = {
        "remote_avg_ms": round(sum(remote_lats) / len(remote_lats), 1) if remote_lats else None,
        "remote_min_ms": min(remote_lats) if remote_lats else None,
        "remote_max_ms": max(remote_lats) if remote_lats else None,
        "local_avg_ms": round(sum(local_lats) / len(local_lats), 1) if local_lats else None,
        "local_min_ms": min(local_lats) if local_lats else None,
        "local_max_ms": max(local_lats) if local_lats else None,
        "remote_ok_count": sum(1 for r in results["remote"] if r.get("ok")),
        "local_ok_count": sum(1 for r in results["local"] if r.get("ok")),
    }
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  SETUP — Automatische Ollama-Installation + Modell-Download
# ═══════════════════════════════════════════════════════════════════════════════

def run_setup(models: list[str] | None = None) -> dict:
    """Automatische Ollama-Installation (Windows) + Modell-Download."""
    result: dict[str, Any] = {"ollama_installed": False, "models_pulled": [], "errors": []}

    if models is None:
        models = [DEFAULT_LOCAL_MODEL]

    # 1. Prüf ob Ollama schon installiert ist
    try:
        subprocess.run(["ollama", "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        result["ollama_installed"] = True
        result["ollama_version"] = "present"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if not result["ollama_installed"]:
        # 2. Automatische Installation (Windows)
        print("✦ Ollama nicht gefunden. Installiere...")
        try:
            # Windows: Powershell-Install via winget oder Download
            # Versuch winget
            wp = subprocess.run(
                ["winget", "install", "Ollama.Ollama", "--accept-source-agreements", "--accept-package-agreements"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
            )
            if wp.returncode == 0:
                result["ollama_installed"] = True
                result["ollama_version"] = "installed via winget"
            else:
                # Fallback: Download von ollama.com
                print("  Winget nicht verfügbar, lade von ollama.com...")
                installer_url = "https://ollama.com/download/OllamaSetup.exe"
                dest = HOME / "Downloads" / "OllamaSetup.exe"
                try:
                    urllib.request.urlretrieve(installer_url, str(dest))
                    result["download_path"] = str(dest)
                    result["ollama_installed"] = False  # muss manuell installiert werden
                    result["errors"].append(
                        "OllamaSetup.exe nach Downloads/OllamaSetup.exe geladen. "
                        "Bitte manuell ausführen, dann --setup erneut starten."
                    )
                except Exception as e:
                    result["errors"].append(f"Download fehlgeschlagen: {e}")
        except Exception as e:
            result["errors"].append(f"Installation fehlgeschlagen: {e}")

    # 3. Ollama starten, falls installiert
    if result["ollama_installed"]:
        # Prüf ob es läuft
        ollama_check = check_ollama()
        if not ollama_check["available"]:
            # Starte Ollama im Hintergrund
            print("✦ Starte Ollama Service...")
            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
                time.sleep(3)
            except Exception as e:
                result["errors"].append(f"Ollama-Start: {e}")

        # 4. Modelle pullen
        for model in models:
            print(f"✦ Pulling {model}...")
            try:
                sp = subprocess.run(
                    ["ollama", "pull", model],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                )
                if sp.returncode == 0:
                    result["models_pulled"].append(model)
                else:
                    result["errors"].append(f"Pull {model}: {sp.stderr[:200]}")
            except subprocess.TimeoutExpired:
                result["errors"].append(f"Pull {model}: timeout")
            except Exception as e:
                result["errors"].append(f"Pull {model}: {e}")

    # 5. Config generieren
    config = load_config()
    if result["models_pulled"]:
        config["fallback"]["model"] = result["models_pulled"][0]
    save_config(config)

    result["config"] = config
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_check() -> int:
    """--check: Prüft alle verfügbaren Provider."""
    config = load_config()
    ollama = check_ollama()
    llamacpp = check_llamacpp()
    primary = check_primary_health(config)
    local = check_local_health(config)
    configured = check_configured_provider()
    state = load_state()

    print("╔══════════════════════════════════════════════╗")
    print("║  Self-Hosted Independence — Provider-Check   ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    # Ollama
    print(f"🦙  Ollama:       {'✅ Verfügbar' if ollama['available'] else '❌ Nicht verfügbar'}")
    if ollama["available"]:
        if ollama["version"]:
            print(f"    Version:      {ollama['version']}")
        print(f"    Modelle:      {len(ollama['models'])} gefunden")
        for m in ollama["models"][:5]:
            sz = f" ({m['size_gb']}GB)" if m.get("size_gb") else ""
            print(f"      · {m['name']}{sz}")
        if len(ollama["models"]) > 5:
            print(f"      … und {len(ollama['models']) - 5} weitere")
    elif ollama.get("error"):
        print(f"    Fehler:       {ollama['error']}")

    # llama.cpp
    print(f"\n🔨  llama.cpp:    {'✅ Verfügbar' if llamacpp['available'] else '❌ Nicht verfügbar'}")
    if llamacpp["available"] and llamacpp["models"]:
        print(f"    Modelle:      {', '.join(llamacpp['models'][:3])}")
    elif llamacpp.get("error"):
        print(f"    Fehler:       {llamacpp['error']}")

    # Primary (Remote)
    print(f"\n☁️  Primary:      {'✅ Verfügbar' if primary['available'] else '❌ Nicht verfügbar'}")
    if primary.get("latency_ms"):
        print(f"    Latenz:       {primary['latency_ms']} ms")
    if primary.get("provider"):
        print(f"    Provider:     {primary['provider']}")
    if primary.get("error"):
        print(f"    Fehler:       {primary['error']}")

    # Configured provider — the one the agent actually runs on
    print(f"\n⚙️  Configured:   {'✅ Verfügbar' if configured['available'] else '❌ Nicht verfügbar'}")
    if configured.get("provider"):
        print(f"    Provider:     {configured['provider']}")
    if configured.get("endpoint"):
        print(f"    Endpoint:     {configured['endpoint']}")
    if configured.get("latency_ms"):
        print(f"    Latenz:       {configured['latency_ms']} ms")
    if configured.get("error"):
        print(f"    Fehler:       {configured['error']}")

    # Local Health
    _local_label = "✅ Verfügbar" if local["available"] else "❌ Nicht verfügbar"
    if local.get("degraded"):
        _local_label = "⚠️  Verfügbar (degraded)"
    print(f"\n🏠  Local:        {_local_label}")
    if local.get("latency_ms"):
        print(f"    Latenz:       {local['latency_ms']} ms")
    if local.get("model"):
        print(f"    Modell:       {local['model']}")
    if local.get("note"):
        print(f"    Hinweis:      {local['note']}")
    if local.get("error"):
        print(f"    Fehler:       {local['error']}")

    # Active Provider
    active = state.get("active_provider", "auto")
    print(f"\n▶️  Aktiver Provider: {active}")
    if state.get("last_switch_reason"):
        print(f"    Letzter Wechsel:  {state['last_switch_reason']}")
    if state.get("last_failover_at"):
        print(f"    Letzter Failover: {state['last_failover_at']}")

    print()

    if primary["available"] or configured["available"]:
        return 0
    elif local["available"]:
        return 1
    else:
        return 2


def cmd_status() -> int:
    """--status: Zeigt aktuelle Config + Health."""
    config = load_config()
    state = load_state()
    ollama = check_ollama()

    print("╔══════════════════════════════════════════════╗")
    print("║  Self-Hosted Independence — Status           ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    print(f"Konfiguration ({CONFIG_FILE})")
    print(f"  Primary:    {config['primary']['provider']} → {config['primary']['model']}")
    print(f"  Fallback:   {config['fallback']['provider']} → {config['fallback']['model']}")
    print(f"  CPU-Modus:  {'an' if config['cpu_fallback']['enabled'] else 'aus'} ({config['cpu_fallback']['model']})")
    print(f"  Failover:   nach {config['failover']['threshold']} Fehlern, Auto-Recovery: {config['failover']['auto_recover']}")
    print()

    print(f"State ({STATE_FILE})")
    print(f"  Aktiv:      {state.get('active_provider', 'auto')}")
    print(f"  Failures:   {state.get('consecutive_failures', 0)}")
    print(f"  Letzter Wechsel: {state.get('last_switch_reason', 'nie')}")
    print()

    history = state.get("health_history", [])
    if history:
        last = history[-1]
        print("Letzter Health-Check:")
        print(f"  Primary: {'✅' if last.get('primary_ok') else '❌'} ({last.get('primary_latency_ms', '?')}ms)")
        print(f"  Local:   {'✅' if last.get('local_ok') else '❌'} ({last.get('local_latency_ms', '?')}ms)")
        print(f"  Zeit:    {last.get('ts', '?')}")

        # Kurze History-Statistik
        total = len(history)
        primary_ok = sum(1 for h in history if h.get("primary_ok"))
        local_ok = sum(1 for h in history if h.get("local_ok"))
        print(f"\n  History: {total} Einträge | Primary {primary_ok}/{total} OK | Local {local_ok}/{total} OK")
    print()

    if ollama["available"] and ollama["models"]:
        print("Lokale Modelle:")
        for m in ollama["models"]:
            sz = f" ({m['size_gb']}GB)" if m.get("size_gb") else ""
            print(f"  · {m['name']}{sz}")
    print()

    return 0


def cmd_switch_to(target: str) -> int:
    """--switch-to: Manuell umschalten."""
    config = load_config()
    result = switch_provider(target, config)
    if result.get("ok"):
        print(f"✅ Umschaltung: {result['previous']} → {result['current']}")
        return 0
    else:
        print(f"❌ Fehler: {result.get('error', 'unbekannt')}")
        return 1


def cmd_bench() -> int:
    """--bench: Benchmark Latenz remote vs local."""
    config = load_config()
    print("╔══════════════════════════════════════════════╗")
    print("║  Self-Hosted Independence — Benchmark        ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print("Führe Benchmark mit 3 Runden aus...\n")
    results = run_benchmark(config, rounds=3)
    s = results["summary"]

    print(f"{'Round':<8} {'Remote (ms)':<16} {'Local (ms)':<16}")
    print("-" * 42)
    for i in range(len(results["remote"])):
        r = results["remote"][i]
        l_ = results["local"][i]
        r_ok = "✅" if r.get("ok") else "❌"
        l_ok = "✅" if l_.get("ok") else "❌"
        r_lat = f"{r.get('latency_ms', '?')}ms" if r.get("latency_ms") else r.get("error", "N/A")
        l_lat = f"{l_.get('latency_ms', '?')}ms" if l_.get("latency_ms") else l_.get("error", "N/A")
        print(f"{i + 1:<8} {r_ok} {r_lat:<12} {l_ok} {l_lat:<12}")

    print()
    print("Zusammenfassung:")
    print(f"  Remote:  Ø {s.get('remote_avg_ms', '?')} ms  (Min {s.get('remote_min_ms', '?')} · Max {s.get('remote_max_ms', '?')})  ✅ {s['remote_ok_count']}/{len(results['remote'])} OK")
    print(f"  Local:   Ø {s.get('local_avg_ms', '?')} ms  (Min {s.get('local_min_ms', '?')} · Max {s.get('local_max_ms', '?')})  ✅ {s['local_ok_count']}/{len(results['local'])} OK")
    print()

    return 0


def cmd_report() -> int:
    """--report: JSON-Report aller Checks und Health."""
    config = load_config()
    state = load_state()
    ollama = check_ollama()
    llamacpp = check_llamacpp()
    primary = check_primary_health(config)
    local = check_local_health(config)

    report = {
        "timestamp": _ts(),
        "config": config,
        "state": state,
        "checks": {
            "ollama": ollama,
            "llamacpp": llamacpp,
            "primary": primary,
            "local": local,
        },
        "overall": {
            "primary_available": primary.get("available", False),
            "local_available": local.get("available", False),
            "active_provider": state.get("active_provider", "auto"),
            "status": "healthy" if primary.get("available") else "fallback" if local.get("available") else "dead",
        },
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_setup() -> int:
    """--setup: Automatische Ollama-Installation + Modell-Download."""
    print("╔══════════════════════════════════════════════╗")
    print("║  Self-Hosted Independence — Setup            ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    models_to_pull = [DEFAULT_LOCAL_MODEL, LOCAL_MODEL_FALLBACK, TINY_MODEL]
    result = run_setup(models=models_to_pull)

    if result.get("ollama_installed"):
        print(f"✅ Ollama: installiert ({result.get('ollama_version', '?')})")
    else:
        print("❌ Ollama: nicht installiert")

    if result.get("models_pulled"):
        print(f"✅ Modelle geladen: {', '.join(result['models_pulled'])}")
    if result.get("download_path"):
        print(f"📥 Installer gespeichert: {result['download_path']}")
    for err in result.get("errors", []):
        print(f"⚠️  {err}")

    if result.get("config"):
        print(f"\n✅ Config gespeichert: {CONFIG_FILE}")
        print(f"  Fallback-Modell: {result['config']['fallback']['model']}")

    print()
    if result["ollama_installed"] and result["models_pulled"]:
        print("🏁 Setup abgeschlossen! Führe --check aus, um den Status zu prüfen.")
        return 0
    else:
        return 1


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_utf8_stdout() -> None:
    """Make `print` survive the cron pipe.

    This script prints box-drawing characters. Cron captures stdout through a
    pipe, which on this host defaults to cp1252, and cp1252 cannot encode them -
    so `print` raised UnicodeEncodeError before the first line and the entire run
    died. Measured 2026-10-10: `rc=1` with an EMPTY stdout, which is why it looked
    like a silent failure rather than a crash. Reconfigure stdout once instead.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def main() -> int:
    _ensure_utf8_stdout()
    if len(sys.argv) < 2:
        print(__doc__)
        return 0

    cmd = sys.argv[1]

    if cmd == "--check":
        return cmd_check()
    elif cmd == "--status":
        return cmd_status()
    elif cmd == "--switch-to":
        if len(sys.argv) < 3:
            print("Usage: self-hosted.py --switch-to <local|primary|auto>")
            return 1
        return cmd_switch_to(sys.argv[2])
    elif cmd == "--bench":
        return cmd_bench()
    elif cmd == "--report":
        return cmd_report()
    elif cmd == "--setup":
        return cmd_setup()
    else:
        print(f"Unbekannter Befehl: {cmd}")
        print(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main())