"""Build the swarm lane list from the live free-model catalog.

One lane = one (provider, model) pair, because a free tier's rate limit is per
model, not per account. Measured on this install: OpenRouter advertises 13 free
models while the translation scripts used one of them, so 12 rate pools sat idle
and a single 429 stalled the whole fleet.

Writes HOME/tmp/swarm-backends.json, which the workers read in
`backend_chain()`. Nothing is hard-coded except the provider endpoints and the
key env names; the model list comes from the provider itself.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("OPENAMER_HOME")
            or (Path.home() / "AppData" / "Local" / "openamer-laptop"))
OUT = HOME / "tmp" / "swarm-backends.json"

OPENROUTER = "https://openrouter.ai/api/v1"
TOKENHARBOR = "https://tokenharbor.ai/v1"

# Free models that are useless for translation but cheap to keep out.
SKIP = re.compile(r"(code|vl$|omni|embed)", re.I)


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for p in (HOME / ".env", Path.home() / "openamer-repo" / ".env"):
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)", line)
            if m:
                env.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))
    return env


def openrouter_free(env: dict[str, str]) -> list[dict]:
    key = env.get("OPENROUTER_API_KEY", "")
    if not key:
        return []
    req = urllib.request.Request(f"{OPENROUTER}/models", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    lanes = []
    for model in data.get("data", []):
        mid = str(model.get("id", ""))
        if not mid.endswith(":free"):
            continue
        if model.get("pricing", {}).get("prompt") not in (0, 0.0, "0", None):
            continue
        if SKIP.search(mid):
            continue
        lanes.append({"name": "or-" + mid.split("/")[-1].replace(":free", ""),
                      "url": f"{OPENROUTER}/chat/completions",
                      "key_env": "OPENROUTER_API_KEY", "model": mid})
    return lanes


def tokenharbor_free() -> list[dict]:
    return [{"name": f"th-{model.split(':')[0]}", "url": f"{TOKENHARBOR}/chat/completions",
             "key_env": "TOKENHARBOR_API_KEY", "model": model}
            for model in ("deepseek-v4.1-flash:free", "deepseek-v4-flash:free", "mimo-v2.5:free")]


def ollama_cloud() -> list[dict]:
    return [{"name": f"ollama-{model}", "url": "https://ollama.com/v1/chat/completions",
             "key_env": "OLLAMA_API_KEY", "model": model}
            for model in ("deepseek-v4.1-flash", "minimax-m3.1-flash")]


def keyless() -> list[dict]:
    return [{"name": "pollinations-openai-fast", "url": "https://text.pollinations.ai/openai",
             "key_env": "-", "model": "openai-fast"}]


def main() -> int:
    env = load_env()
    lanes: list[dict] = []
    errors = []
    for build in (lambda: openrouter_free(env), tokenharbor_free, ollama_cloud, keyless):
        try:
            lanes.extend(build())
        except Exception as exc:  # noqa: BLE001 - one dead provider must not stop the build
            errors.append(f"{type(exc).__name__}: {exc}")
    usable = [lane for lane in lanes if lane["key_env"] == "-" or env.get(lane["key_env"])]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(usable, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps({"lanes": len(usable), "providers": sorted({l['url'].split('/')[2] for l in usable}),
                      "models": [l["model"] for l in usable], "errors": errors},
                     ensure_ascii=False, indent=1))
    return 0 if usable else 1


if __name__ == "__main__":
    sys.exit(main())
