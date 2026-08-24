#!/usr/bin/env python3
"""
Hunger-Reserve: Fallback-Kette gegen 429-Rate-Limits.
====================================================
Wenn stealth/ox-alpha hungrig ist (429), weicht die Fleet auf komplett-freie
OpenRouter-Modelle aus. Diese Datei ist die Warteschlange + der Tester.

Usage:
  hunger_reserve.py check     -> welche freien Modelle antworten JETZT?
  hunger_reserve.py best      -> das erste funktionierende Fallback-Modell

Der Output von 'best' kann von Wrapper-Jobs als OPENAMER_FALLBACK_MODEL
gelesen werden. Kein Key im Repo - .env bleibt die einzige Key-Quelle.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OA_HOME = Path(r"C:\Users\damir\AppData\Local\openamer-laptop")
ENV_FILE = OA_HOME / ".env"
STATE = OA_HOME / "hunger_reserve.json"

# Reihenfolge = Praeferenz (klein+schnell zuerst, groessere danach)
FALLBACK_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "dots-studio/dots-3-note-preview:free",
    "thinkingmachines/inkling-small:free",
    "poolside/laguna-xs-2.1:free",
    "liquid/lfm-2.5-2.6b:free",
]


def api_key():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENROUTER_API_KEY=") and line.count("=") > 0:
            v = line.split("=", 1)[1].strip()
            if v:
                return v
    return ""


def probe(model, key):
    """Minimaler Chat-Ping (max_tokens=1) - zahlt praktisch nichts."""
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST")
    try:
        urllib.request.urlopen(req, timeout=20)
        return True, ""
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:60]


def cmd_check():
    key = api_key()
    if not key:
        print("kein OPENROUTER_API_KEY in .env - Abbruch")
        return 1
    results = {}
    print(f"{'Modell':<48} Status")
    print("-" * 62)
    for m in FALLBACK_MODELS:
        ok, err = probe(m, key)
        results[m] = {"ok": ok, "error": err}
        print(f"{m:<48} {'✓ lebt' if ok else '✗ ' + err}")
        # freundlich bleiben: kleiner Abstand zwischen Pings
        import time
        time.sleep(1)
    state = {"checked_at": datetime.now(timezone.utc).isoformat(), "models": results}
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    alive = [m for m, r in results.items() if r["ok"]]
    print(f"\n{len(alive)}/{len(FALLBACK_MODELS)} Reserve-Modelle lebendig")
    return 0


def cmd_best():
    key = api_key()
    if not key:
        print("")
        return 1
    for m in FALLBACK_MODELS:
        ok, _ = probe(m, key)
        if ok:
            print(m)
            return 0
    return 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    sys.exit(cmd_check() if cmd == "check" else cmd_best())
