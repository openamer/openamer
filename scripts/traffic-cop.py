#!/usr/bin/env python3
"""
Traffic Cop v1.0 — API-Key-Health-Check + Rate-Limit-Rotation + Key-Pool-Management
==================================================================================
Liest alle API-Keys aus .env, checkt live HTTP-Health gegen Provider-Endpoints,
rotiert bei Rate-Limit (429) / Auth-Fail (401), und zeigt Nutzungsstatistiken.

Exit-Codes:
  0 = alle Keys OK
  1 = einige Keys gedrosselt / fehlerhaft
  2 = alle Keys tot
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Pfade ───────────────────────────────────────────────────────────────────
HOME = Path.home()
_raw_openamer_home = os.environ.get("OPENAMER_HOME")
if _raw_openamer_home:
    # Normalisiere MSYS-/Cygwin-Pfade (/c/Users/... → C:/Users/...)
    _norm = re.sub(r"^/([a-zA-Z])/", lambda m: f"{m.group(1).upper()}:/", _raw_openamer_home)
    OPENAMER_HOME = Path(_norm).resolve()
else:
    OPENAMER_HOME = HOME / "AppData" / "Local" / "openamer-laptop"
TRAFFIC_COP_DIR = HOME / ".traffic-cop"
STATE_FILE = TRAFFIC_COP_DIR / "state.json"
SCRIPTS_DIR = HOME / "scripts"

# ── Provider-Map: env-var → Endpoint + Health-Check ─────────────────────────
# Jeder Eintrag: (env_var_name, display_name, [endpoint_url], auth_header_format, key_prefix)
# auth_header_format: "Bearer {key}" oder "Basic {key}" oder None (wenn key=token direkt)
PROVIDER_MAP = [
    # OpenAI-kompatibel (Bearer Token)
    ("OPENROUTER_API_KEY",  "OpenRouter",  "https://api.openrouter.ai/v1/models",        "Bearer {key}",     "sk-or-"),
    ("OLLAMA_API_KEY",      "Ollama",      "https://ollama.com/v1/models",               "Bearer {key}",     None),
    ("OPENAI_API_KEY",      "OpenAI",      "https://api.openai.com/v1/models",           "Bearer {key}",     "sk-"),
    ("ANTHROPIC_API_KEY",   "Anthropic",   "https://api.anthropic.com/v1/messages",      "Bearer {key}",     "sk-ant-"),
    ("GROQ_API_KEY",        "Groq",        "https://api.groq.com/openai/v1/models",      "Bearer {key}",     "gsk_"),
    ("FIREWORKS_API_KEY",   "Fireworks",   "https://api.fireworks.ai/v1/models",         "Bearer {key}",     None),
    ("DEEPSEEK_API_KEY",    "DeepSeek",    "https://api.deepseek.com/v1/models",          "Bearer {key}",     "sk-"),
    ("MISTRAL_API_KEY",     "Mistral",     "https://api.mistral.ai/v1/models",            "Bearer {key}",     None),
    ("COHERE_API_KEY",      "Cohere",      "https://api.cohere.ai/v1/models",             "Bearer {key}",     None),
    ("TOGETHER_API_KEY",    "Together",    "https://api.together.xyz/v1/models",          "Bearer {key}",     None),
    ("PERPLEXITY_API_KEY",  "Perplexity",  "https://api.perplexity.ai/v1/models",         "Bearer {key}",     None),
    ("REPLICATE_API_KEY",   "Replicate",   "https://api.replicate.com/v1/models",         "Bearer {key}",     "r8_"),
    ("GEMINI_API_KEY",      "Gemini",      "https://generativelanguage.googleapis.com/v1beta/models", None, None),
    ("GOOGLE_API_KEY",      "Google AI",   "https://generativelanguage.googleapis.com/v1beta/models", None, None),
    ("NOVITA_API_KEY",      "NovitaAI",    "https://api.novita.ai/openai/v1/models",      "Bearer {key}",     None),
    ("GLM_API_KEY",         "GLM (z.ai)",  "https://api.z.ai/api/paas/v4/models",         "Bearer {key}",     None),
    ("KIMI_API_KEY",        "Kimi",        "https://api.moonshot.cn/v1/models",            "Bearer {key}",     None),
    ("DEEPINFRA_API_KEY",   "DeepInfra",   "https://api.deepinfra.com/v1/models",           "Bearer {key}",     None),
    ("AI21_API_KEY",        "AI21",        "https://api.ai21.com/studio/v1/models",        "Bearer {key}",     None),
    ("FAL_KEY",             "FAL",         "https://fal.run/v1/models",                    "Key {key}",        None),
    ("HUGGINGFACE_API_KEY", "HuggingFace", "https://huggingface.co/api/models?limit=1",    "Bearer {key}",     "hf_"),
    ("ELEVENLABS_API_KEY",  "ElevenLabs",  "https://api.elevenlabs.io/v1/models",          "Bearer {key}",     None),
]


def _load_env(path: Path) -> dict:
    """Parsiert eine .env-Datei und gibt {KEY: value} zurück."""
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Nur echte Zuweisungen (ungesetztes mit leerem Wert === unset)
        m = re.match(r"^(export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not m:
            continue
        key = m.group(2)
        val = m.group(3).strip()
        # Entferne Quotes
        if (val.startswith('"') and val.endswith('"')) or \
           (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        if val and val not in ("", "your_key_here", "your_google_ai_studio_key_here"):
            env[key] = val
    return env


def _load_state() -> dict:
    """Lade oder initialisiere state.json."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "keys": {},
        "rotation": {},
        "last_run": None,
        "stats": {
            "total_checks": 0,
            "total_rotations": 0,
            "total_errors": 0,
            "total_429": 0,
            "total_401": 0,
        },
    }


def _save_state(state: dict):
    TRAFFIC_COP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _health_check(provider_name: str, env_var: str, api_key: str,
                  url: str, auth_fmt: str | None, state: dict) -> tuple[int, str, int]:
    """
    Führt einen HTTP-Health-Check gegen den Provider-Endpoint durch.

    Returns: (exit_flag, status_label, http_status)
      exit_flag: 0=OK, 1=throttled/error, 2=dead
      status_label: "ok", "rate_limited", "auth_fail", "timeout", "error"
      http_status: HTTP-Status-Code oder 0
    """
    key_state = state["keys"].setdefault(env_var, {
        "provider": provider_name,
        "health": "unknown",
        "last_checked": None,
        "last_ok": None,
        "error_count": 0,
        "429_count": 0,
        "401_count": 0,
        "total_calls": 0,
    })
    key_state["last_checked"] = _now_iso()

    if not api_key or len(api_key) < 6:
        key_state["health"] = "no_key"
        return 1, "no_key", 0

    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "OpenAmer-TrafficCop/1.0")
    req.add_header("Accept", "application/json")

    if auth_fmt is not None:
        header_val = auth_fmt.replace("{key}", api_key)
        req.add_header("Authorization", header_val)
    elif api_key:
        # Gemini / Google: key=... als Query-Parameter
        parsed = urllib.parse.urlparse(url)
        qs = dict(urllib.parse.parse_qsl(parsed.query))
        qs["key"] = api_key
        new_qs = urllib.parse.urlencode(qs)
        req.full_url = urllib.parse.urlunparse(parsed._replace(query=new_qs))

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            if 200 <= status < 300:
                key_state["health"] = "ok"
                key_state["last_ok"] = _now_iso()
                key_state["error_count"] = 0
                return 0, "ok", status
            else:
                key_state["health"] = "error"
                key_state["error_count"] += 1
                return 1, "error", status

    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace")[:200] if e.fp else ""
        if status == 429:
            key_state["health"] = "rate_limited"
            key_state["429_count"] += 1
            key_state["error_count"] += 1
            state["stats"]["total_429"] += 1
            return 1, "rate_limited", status
        elif status == 401:
            key_state["health"] = "auth_fail"
            key_state["401_count"] += 1
            key_state["error_count"] += 1
            state["stats"]["total_401"] += 1
            return 2, "auth_fail", status
        elif status == 403:
            key_state["health"] = "auth_fail"
            key_state["401_count"] += 1
            key_state["error_count"] += 1
            state["stats"]["total_401"] += 1
            return 2, "auth_fail", status
        else:
            key_state["health"] = "error"
            key_state["error_count"] += 1
            return 1, "error", status

    except urllib.error.URLError as e:
        reason = str(e.reason) if hasattr(e, "reason") else str(e)
        if "timed out" in reason.lower() or "timeout" in reason.lower():
            key_state["health"] = "timeout"
            key_state["error_count"] += 1
            return 1, "timeout", 0
        key_state["health"] = "error"
        key_state["error_count"] += 1
        return 1, "error", 0

    except (OSError, ValueError) as e:
        key_state["health"] = "error"
        key_state["error_count"] += 1
        return 1, "error", 0


def _find_key_pool(env: dict, provider_info: tuple) -> list[dict]:
    """
    Findet alle Keys für einen Provider (Key-Pool-Management).
    Unterstützt Multi-Key-Pro-Provider durch NUMERIC-Suffixe:
      OPENAI_API_KEY, OPENAI_API_KEY_2, OPENAI_API_KEY_3 etc.
    """
    env_var = provider_info[0]
    keys = []
    base_key = env.get(env_var)
    if base_key:
        keys.append({"var": env_var, "key": base_key, "index": 0})
    i = 2
    while True:
        suffix_var = f"{env_var}_{i}"
        val = env.get(suffix_var)
        if val:
            keys.append({"var": suffix_var, "key": val, "index": i})
            i += 1
        else:
            break
    return keys


def _rotate_key(state: dict, provider_env_var: str):
    """Manuelle Rotation: markiert aktuellen Key als rotiert."""
    rotation = state["rotation"].setdefault(provider_env_var, {
        "current_index": 0,
        "rotations": [],
        "last_rotation": None,
    })
    rotation["current_index"] += 1
    rotation["last_rotation"] = _now_iso()
    rotation["rotations"].append({
        "timestamp": _now_iso(),
        "to_index": rotation["current_index"],
        "reason": "manual",
    })
    state["stats"]["total_rotations"] += 1
    _save_state(state)
    print(f"[TRAFFIC-COP] ⇄ Key-Rotation für {provider_env_var} → Index {rotation['current_index']}")


# ── CLI-Modi ─────────────────────────────────────────────────────────────────

def cmd_check(env_path: Path):
    """--check: Teste alle Keys live und aktualisiere Zustand."""
    env = _load_env(env_path)
    if not env:
        print("[TRAFFIC-COP] ⚠ Keine API-Keys gefunden in .env", file=sys.stderr)
        return 1

    state = _load_state()
    state["last_run"] = _now_iso()
    state["stats"]["total_checks"] += 1

    overall_exit = 0  # 0=alle ok, 1=einige Probleme, 2=alle tot
    ok_count = 0
    problem_count = 0
    dead_count = 0
    total_keys = 0

    print("┌────────────────────────────────────────────────────────────────┐")
    print("│  🔍 Traffic Cop — API-Key-Health-Check                        │")
    print(f"│  {_now_iso():<56}│")
    print("├────────────────────────────────────────────────────────────────┤")

    for provider in PROVIDER_MAP:
        env_var = provider[0]
        pool = _find_key_pool(env, provider)
        if not pool:
            continue

        for key_entry in pool:
            total_keys += 1
            label = f"{provider[1]} (#{key_entry['index']})" if key_entry["index"] > 0 else provider[1]
            print(f"│  {label:<28} → ", end="", flush=True)

            exit_flag, status_label, http_status = _health_check(
                provider[1], key_entry["var"], key_entry["key"],
                provider[2], provider[3], state,
            )
            key_state = state["keys"][key_entry["var"]]

            if exit_flag == 0:
                print(f"✅ {status_label.upper()} (HTTP {http_status})")
                ok_count += 1
            elif exit_flag == 1:
                icon = "⚠"
                if status_label == "rate_limited":
                    icon = "🔄"
                elif status_label == "timeout":
                    icon = "⏱"
                print(f"{icon} {status_label.upper()} (HTTP {http_status})")
                problem_count += 1
                if overall_exit < 1:
                    overall_exit = 1
            elif exit_flag == 2:
                print(f"❌ {status_label.upper()} (HTTP {http_status})")
                dead_count += 1
                overall_exit = 2

    print("├────────────────────────────────────────────────────────────────┤")
    print(f"│  📊 Ergebnis:  ✅ {ok_count} OK  ⚠ {problem_count} Problem  ❌ {dead_count} Tot  │")
    if overall_exit == 0:
        print("│  🟢 Alle Keys OK                                             │")
    elif overall_exit == 1:
        print("│  🟡 Einige Keys haben Probleme                               │")
    else:
        print("│  🔴 Alle Keys tot — keine API erreichbar                     │")
    print("└────────────────────────────────────────────────────────────────┘")

    _save_state(state)
    return overall_exit


def cmd_status(env_path: Path):
    """--status: Zeige gespeicherte Key-Health an (kein Live-Check)."""
    state = _load_state()
    if not state["keys"]:
        print("[TRAFFIC-COP] ⚠ Noch kein Check gelaufen. Führe --check aus.")
        return 1

    health_counts = {"ok": 0, "rate_limited": 0, "auth_fail": 0, "timeout": 0, "error": 0, "no_key": 0, "unknown": 0}
    print("┌────────────────────────────────────────────────────────────────┐")
    print("│  📋 Traffic Cop — Key-Status (gespeichert)                    │")
    print("├────────────────────────────────────────────────────────────────┤")
    for env_var, ks in sorted(state["keys"].items()):
        label = f"{ks.get('provider', '?')} ({env_var})"
        color = {"ok": "✅", "rate_limited": "🔄", "auth_fail": "❌",
                 "timeout": "⏱", "error": "⚠", "no_key": "⛔", "unknown": "❓"}
        icon = color.get(ks.get("health", "unknown"), "❓")
        last = ks.get("last_checked", "nie")[:19]
        print(f"│  {icon} {label:<40} {last}")
        health_counts[ks.get("health", "unknown")] = health_counts.get(ks.get("health", "unknown"), 0) + 1

    print("├────────────────────────────────────────────────────────────────┤")
    print(f"│  Letzter Lauf: {state.get('last_run', 'nie')[:19]:<37}│")
    print(f"│  Checks: {state['stats']['total_checks']}  Rotations: {state['stats']['total_rotations']}  "
          f"Errors: {state['stats']['total_errors']}  │")
    print(f"│  429s: {state['stats']['total_429']}  401s: {state['stats']['total_401']}  "
          f"Keys: {len(state['keys'])}  │")
    print("└────────────────────────────────────────────────────────────────┘")

    total = sum(health_counts.values())
    if total == 0:
        return 1
    if health_counts.get("ok", 0) == total:
        return 0
    if health_counts.get("auth_fail", 0) + health_counts.get("error", 0) + health_counts.get("no_key", 0) == total:
        return 2
    return 1


def cmd_rotate(env_path: Path, provider: str):
    """--rotate <provider>: Manuelle Key-Rotation für einen Provider."""
    env = _load_env(env_path)

    # Finde den Provider
    matched = None
    for p in PROVIDER_MAP:
        if p[0].lower() == provider.lower() or p[1].lower() == provider.lower():
            matched = p
            break

    if not matched:
        # Versuche Fuzzy-Match
        for p in PROVIDER_MAP:
            if provider.lower() in p[0].lower() or provider.lower() in p[1].lower():
                matched = p
                break

    if not matched:
        # Lade state für verfügbare Provider-Abfrage
        state = _load_state()
        print(f"[TRAFFIC-COP] ❌ Unbekannter Provider: {provider}", file=sys.stderr)
        print("   Verfügbar:", ", ".join(f"{p[0]} ({p[1]})" for p in PROVIDER_MAP if p[0] not in state.get("keys", {})))
        return 1

    pool = _find_key_pool(env, matched)
    state = _load_state()
    rotation = state["rotation"].get(matched[0], {"current_index": 0})
    current_idx = rotation.get("current_index", 0)
    print(f"[TRAFFIC-COP] ⇄ Rotiere {matched[1]} …")
    print(f"   Aktuell: Index {current_idx} ({pool[current_idx]['var'] if current_idx < len(pool) else 'N/A'})")
    _rotate_key(state, matched[0])
    rotation = state["rotation"].get(matched[0], {})
    new_idx = rotation.get("current_index", 0)
    if new_idx < len(pool):
        print(f"   Neu:     Index {new_idx} ({pool[new_idx]['var']})")
    else:
        print(f"   🔄 Neu:     Index {new_idx} (Pool hat nur {len(pool)} Keys — zyklische Rotation)")
        # Zyklisch zurücksetzen
        rotation["current_index"] = 0
        _save_state(state)
    return 0


def cmd_stats(env_path: Path):
    """--stats: Nutzungsstatistik anzeigen."""
    state = _load_state()
    if not state["keys"]:
        print("[TRAFFIC-COP] ⚠ Noch keine Daten. Führe --check aus.")
        return 1

    print("┌────────────────────────────────────────────────────────────────┐")
    print("│  📊 Traffic Cop — Nutzungsstatistik                           │")
    print("├────────────────────────────────────────────────────────────────┤")
    print(f"│  Letzter Check:  {state.get('last_run', 'nie')[:19]:<39}│")
    print(f"│  Gesamt-Checks:  {state['stats']['total_checks']:<7}                           │")
    print(f"│  Rotationen:     {state['stats']['total_rotations']:<7}                           │")
    print(f"│  Gesamt-Fehler:  {state['stats']['total_errors']:<7}                           │")
    print(f"│  Rate-Limits:    {state['stats']['total_429']:<7}                           │")
    print(f"│  Auth-Fails:     {state['stats']['total_401']:<7}                           │")
    print("├────────────────────────────────────────────────────────────────┤")

    # Pro-Provider-Details
    print("│  📌 Provider-Details:                                         │")
    for env_var, ks in sorted(state["keys"].items()):
        prov = ks.get("provider", "?")
        health = ks.get("health", "?")
        calls = ks.get("total_calls", 0)
        errs = ks.get("error_count", 0)
        rl = ks.get("429_count", 0)
        af = ks.get("401_count", 0)
        last = ks.get("last_ok") or "nie"
        print(f"│  {prov:<20} {health:<12} Errors:{errs:<3} "
              f"429:{rl:<2} 401:{af:<2} OK:{last}  │")

    print("├────────────────────────────────────────────────────────────────┤")

    # Rotation-Log
    rotations = []
    for prov_var, rot in state.get("rotation", {}).items():
        for r in rot.get("rotations", [])[-5:]:
            rotations.append((r["timestamp"], prov_var, r["reason"], r["to_index"]))
    if rotations:
        rotations.sort(reverse=True)
        print("│  🔄 Letzte Rotationen:                                      │")
        for ts, pv, reason, idx in rotations[:5]:
            print(f"│  {ts[:19]}  {pv:<20} → Index {idx} ({reason})")
    else:
        print("│  🔄 Keine Rotationen bisher                                 │")

    print("└────────────────────────────────────────────────────────────────┘")
    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: traffic-cop.py --check | --status | --rotate <provider> | --stats")
        print("")
        print("  --check              Live-Health-Check aller API-Keys")
        print("  --status             Zeigt gespeicherten Key-Status")
        print("  --rotate <provider>  Manuelle Key-Rotation (Name oder Env-Var)")
        print("  --stats              Nutzungsstatistik")
        print("")
        print("Exit-Codes: 0=alle OK, 1=einige Probleme, 2=alle tot")
        return 1

    # Suche .env: zuerst OpenAmer Home, dann ~/.env, dann Repo
    env_paths = [
        OPENAMER_HOME / ".env",
        HOME / ".env",
        HOME / "openamer-repo" / ".env",
    ]
    found_env = None
    for p in env_paths:
        if p.exists():
            found_env = p
            break

    if not found_env:
        # Fallback: OpenAmer Home .env.example
        alt = OPENAMER_HOME / ".env"
        alt.parent.mkdir(parents=True, exist_ok=True)
        if not alt.exists():
            alt.write_text("# Traffic-Cop .env — Bitte API-Keys hier eintragen\n", encoding="utf-8")
        found_env = alt

    cmd = sys.argv[1]
    if cmd == "--check":
        return cmd_check(found_env)
    elif cmd == "--status":
        return cmd_status(found_env)
    elif cmd == "--rotate":
        if len(sys.argv) < 3:
            print("Usage: traffic-cop.py --rotate <provider>", file=sys.stderr)
            return 1
        return cmd_rotate(found_env, sys.argv[2])
    elif cmd == "--stats":
        return cmd_stats(found_env)
    else:
        print(f"[TRAFFIC-COP] ❌ Unbekannter Befehl: {cmd}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())