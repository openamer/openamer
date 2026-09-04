#!/usr/bin/env python3
"""Smart Router — routes queries to the best available model.

Simple -> local 2B (0ms, 0 EUR, offline)
Complex -> OpenRouter free model (0 EUR, frontier reasoning)
Rate-limited -> rotate through free model chain
"""
import json, os, sys, time, re, urllib.request, threading, datetime

def _load_env():
    env_path = r"C:/Users/damir/AppData/Local/openamer-laptop/.env"
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY=") and len(line.split("=", 1)[1]) > 10:
                os.environ.setdefault("OPENROUTER_API_KEY", line.split("=", 1)[1])
                break
_load_env()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".router_state.json")

FREE_CHAIN = [
    "nvidia/nemotron-3.5-lightning:free",
    "minimax/minimax-m3:free",
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "thinkingmachines/inkling:free",
]

_rate_limits = {}
_rate_lock = threading.Lock()

COMPLEX_WORDS = frozenset([
    "explain", "compare", "analyze", "prove", "derive", "optimize",
    "architecture", "design", "wissenschaftlich", "beweis", "herleiten",
    "komplex", "mehrschrittig", "vergleiche", "differences", "implications",
    "alternatives", "scalability", "why", "because", "describe", "evaluate",
])

def is_complex(text):
    if len(text) > 500:
        return True
    words = set(re.findall(r"[a-z]+", text.lower()))
    if words & COMPLEX_WORDS:
        return True
    if text.count(".") + text.count("?") + text.count("!") > 4:
        return True
    return False

def _available_free_models():
    now = time.time()
    with _rate_lock:
        return [m for m in FREE_CHAIN if _rate_limits.get(m, 0) < now]

def route_to_cloud(messages, max_tokens=500):
    available = _available_free_models()
    if not available:
        with _rate_lock:
            oldest = min(_rate_limits.items(), key=lambda x: x[1])
            _rate_limits[oldest[0]] = 0
            available = [oldest[0]]
    err = ""
    for model in available[:3]:
        try:
            req = urllib.request.Request(OPENROUTER_URL,
                data=json.dumps({"model": model, "messages": messages,
                                 "max_tokens": max_tokens}).encode(),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}"})
            r = json.load(urllib.request.urlopen(req, timeout=120))
            content = r.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                return {"source": model, "content": content, "fallback_used": False}
        except Exception as e:
            err = str(e)
            if "429" in err or "rate" in err.lower():
                with _rate_lock:
                    _rate_limits[model] = time.time() + 300
                continue
            err = err[:150]
    # FINAL FALLBACK: frontier reasoning via SSH to GPU worker (Qwen3.5-4B)
    try:
        import subprocess
        payload = json.dumps({"model": "Qwen3.5-4B",
            "messages": messages, "max_tokens": max_tokens}).replace(chr(34), chr(92)+chr(34))
        r2 = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
            "damir@192.168.178.23",
            f"curl -s -m 60 http://localhost:8082/v1/chat/completions -H 'Content-Type: application/json' -d '{payload}'"],
            capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
        if r2.returncode == 0 and r2.stdout.strip().startswith("{"):
            resp = json.loads(r2.stdout)
            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                return {"source": "gpu-worker-4b", "content": content, "fallback_used": True}
    except Exception as e2:
        err += f"; gpu-worker: {str(e2)[:80]}"

    return {"source": "none", "content": "", "error": err,
            "fallback_used": True}

def refresh_free_models():
    try:
        r = json.load(urllib.request.urlopen(MODELS_URL, timeout=15))
        free = sorted([m["id"] for m in r["data"] if ":free" in m.get("id", "")])
        priority = [m for m in free if any(k in m for k in ("lightning", "550b", "minimax", "glm", "inkling"))]
        other = [m for m in free if m not in priority]
        new_chain = (priority + other)[:10]
        state = {"free_chain": new_chain,
                 "last_refresh": datetime.datetime.now().isoformat()}
        with open(CACHE, "w") as f:
            json.dump(state, f)
        return new_chain
    except Exception:
        return FREE_CHAIN

def smart_route(messages, max_tokens=500):
    user_text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_text = m.get("content", "")
            break
    if is_complex(user_text):
        cloud = route_to_cloud(messages, max_tokens)
        if cloud.get("content"):
            return {"routed_to": "cloud", **cloud}
    return {"routed_to": "local"}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        print(json.dumps({"chain": refresh_free_models()}, indent=1))
    elif len(sys.argv) > 2 and sys.argv[1] == "test":
        r = smart_route([{"role": "user", "content": " ".join(sys.argv[2:])}])
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(__doc__)
