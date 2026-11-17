"""Measure candidate translation backends: status, latency, shape, script.

Not a unit test — a benchmark. Each candidate translates the same four UI
strings into Torbeski (Cyrillic) and the result is judged on what actually
matters for this pipeline: did it answer, how fast, did it keep the array
shape, and did it answer in the right writing system.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HOME = pathlib.Path(os.path.expanduser("~/AppData/Local/openamer-laptop"))
ENV_FILE = HOME / ".env"
STRINGS = ["Settings", "Terminal", "Cancel", "Save changes"]
LANG = "Torbeski (Macedonian-based, Cyrillic script)"

CANDIDATES = [
    # (name, url, key_env, model)
    ("openrouter/nemotron-ultra", "https://openrouter.ai/api/v1/chat/completions",
     "OPENROUTER_API_KEY", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    ("openrouter/nemotron-light", "https://openrouter.ai/api/v1/chat/completions",
     "OPENROUTER_API_KEY", "nvidia/nemotron-3.5-lightning:free"),
    ("openrouter/gemma-4-31b", "https://openrouter.ai/api/v1/chat/completions",
     "OPENROUTER_API_KEY", "google/gemma-4-31b-it:free"),
    ("openrouter/dots-note", "https://openrouter.ai/api/v1/chat/completions",
     "OPENROUTER_API_KEY", "dots-studio/dots-3-note-preview:free"),
    ("openrouter/ling-flash", "https://openrouter.ai/api/v1/chat/completions",
     "OPENROUTER_API_KEY", "inclusionai/ling-3.1-flash"),
    ("tokenharbor/deepseek-free", "https://tokenharbor.ai/v1/chat/completions",
     "TOKENHARBOR_API_KEY", "deepseek-v4.1-flash:free"),
    ("tokenharbor/gemini-flash", "https://tokenharbor.ai/v1/chat/completions",
     "TOKENHARBOR_API_KEY", "gemini-3.8-flash"),
    ("tokenharbor/qwen-flash", "https://tokenharbor.ai/v1/chat/completions",
     "TOKENHARBOR_API_KEY", "qwen3.6-flash"),
    ("tokenharbor/glm-flash", "https://tokenharbor.ai/v1/chat/completions",
     "TOKENHARBOR_API_KEY", "glm-5.3-flash"),
    ("tokenharbor/mimo-flash", "https://tokenharbor.ai/v1/chat/completions",
     "TOKENHARBOR_API_KEY", "mimo-v2.6-flash"),
    ("kilo/auto-free", "https://ai-gateway.kilo.ai/api/v1/chat/completions",
     "KILO_API_KEY", "kilo-auto/free"),
    ("kilo/nemotron-nano", "https://ai-gateway.kilo.ai/api/v1/chat/completions",
     "KILO_API_KEY", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"),
    ("pollinations/openai-fast", "https://text.pollinations.ai/openai",
     "", "openai-fast"),
    ("ollama/deepseek-flash", "https://ollama.com/v1/chat/completions",
     "OLLAMA_API_KEY", "deepseek-v4.1-flash"),
    ("ollama/minimax-flash", "https://ollama.com/v1/chat/completions",
     "OLLAMA_API_KEY", "minimax-m3.1-flash"),
    ("ollama/gemma4-31b", "https://ollama.com/v1/chat/completions",
     "OLLAMA_API_KEY", "gemma4:31b"),
    ("ollama/gpt-oss-20b", "https://ollama.com/v1/chat/completions",
     "OLLAMA_API_KEY", "gpt-oss:20b-cloud"),
]

CYRILLIC = re.compile(r"[\u0400-\u04FF]")


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)", line)
            if m:
                env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return env


def extract_array(text: str):
    if not isinstance(text, str):
        return None
    start, depth, in_str, esc = text.find("["), 0, False, False
    if start < 0:
        return None
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
                if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                    return parsed
                return None
    return None


def run_one(cand, env) -> dict:
    name, url, keyenv, model = cand
    key = env.get(keyenv, "") if keyenv else ""
    if keyenv and not key:
        return {"name": name, "status": "no-key", "ms": 0, "shape": "-", "script": "-", "out": ""}
    system = (f"You are a professional software localizer translating a desktop app into {LANG}. "
              "Translate every element of the JSON array. Keep the array length and order. "
              "Never translate the product name OpenAmer. Output ONLY a JSON array of strings.")
    body = json.dumps({"model": model, "temperature": 0,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": json.dumps(STRINGS, ensure_ascii=False)}]}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=body, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode())
        ms = int((time.time() - t0) * 1000)
        text = data["choices"][0]["message"]["content"]
        arr = extract_array(text)
        shape = f"{len(arr)}/{len(STRINGS)}" if arr else "bad"
        cyr = sum(1 for s in (arr or []) if CYRILLIC.search(s))
        script = f"{cyr}/{len(STRINGS)} cyr"
        return {"name": name, "status": "ok", "ms": ms, "shape": shape,
                "script": script, "out": " | ".join((arr or [])[:4])[:70]}
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")[:80].replace("\n", " ")
        return {"name": name, "status": f"HTTP {e.code}", "ms": int((time.time() - t0) * 1000),
                "shape": "-", "script": "-", "out": body_txt}
    except Exception as e:  # noqa: BLE001 - a benchmark reports every failure kind
        return {"name": name, "status": type(e).__name__, "ms": int((time.time() - t0) * 1000),
                "shape": "-", "script": "-", "out": str(e)[:70]}


def main() -> int:
    env = load_env()
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(lambda c: run_one(c, env), CANDIDATES))
    rows.sort(key=lambda r: (r["status"] != "ok", r["ms"]))
    print(f"{'backend':30} {'status':10} {'ms':>6} {'shape':>6} {'script':>10}  sample")
    print("-" * 110)
    for r in rows:
        print(f"{r['name']:30} {r['status']:10} {r['ms']:>6} {r['shape']:>6} {r['script']:>10}  {r['out']}")
    ok = [r for r in rows if r["status"] == "ok" and r["shape"] == f"{len(STRINGS)}/{len(STRINGS)}"
          and r["script"] == f"{len(STRINGS)}/{len(STRINGS)} cyr"]
    print(f"\nVoll tauglich (Antwort + Form + Schrift): {len(ok)}/{len(rows)}")
    for r in ok:
        print(f"   {r['name']:30} {r['ms']:>6} ms")
    pathlib.Path(os.path.expanduser("~/AppData/Local/openamer-laptop/reports/i18n-backend-bench.json")).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
