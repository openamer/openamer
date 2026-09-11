#!/usr/bin/env python3
"""Central model resolver — single source of truth for model selection.

Every training/reasoning script should read its model from HERE, not hardcode
a string. When you switch the default model/provider (via `openamer model` or
config.yaml `model.default`), every script that uses resolve_default_model()
follows automatically. No more hunting for hardcoded "mini-openamer" or
"granite4.2:3b" scattered across scripts.

Two distinct purposes are kept apart deliberately:
  - DEFAULT_MODEL  — the reasoning/agent model (follows config.yaml model.default)
  - MINI_MODEL     — the small tuned orchestrator on :8081 (tool_server) with the
                     GPU-trained LoRA adapter. This stays FIXED on purpose: it is
                     the purpose-built tool orchestrator, not a general reasoning
                     model, and should not silently switch.

CLI:
  python model_config.py resolve           # print the current default model
  python model_config.py mini              # print the fixed mini model name
  python model_config.py list              # JSON {default, provider, mini, base_url}
"""
import json, os, pathlib, sys

_HOME = pathlib.Path(os.environ.get(
    "OPENAMER_HOME", str(pathlib.Path.home() / "AppData" / "Local" / "openamer-laptop")))
_CONFIG = _HOME / "config.yaml"

# Fixed: the tuned 2B orchestrator served on :8081 (carries the GPU LoRA adapter).
MINI_MODEL = "mini-openamer"

# Hardcoded fallbacks IF config.yaml can't be read or has no model.default.
_FALLBACK_DEFAULT = "mini-openamer"
_FALLBACK_PROVIDER = "custom:local-(127.0.0.1:11434)"


def _load_model_cfg():
    """Return the model section (dict) from config.yaml, or {} on any failure."""
    try:
        import yaml
        if not _CONFIG.exists():
            return {}
        cfg = yaml.safe_load(open(_CONFIG, encoding="utf-8"))
        if not isinstance(cfg, dict):
            return {}
        m = cfg.get("model") or {}
        return m if isinstance(m, dict) else {"default": str(m)}
    except Exception:
        return {}


def resolve_default_model() -> str:
    """Return the current default reasoning model name from config.yaml."""
    m = _load_model_cfg()
    name = (m.get("default") or "").strip()
    if not name:
        return _FALLBACK_DEFAULT
    return name


def resolve_provider() -> str:
    """Return the current default provider, or a fallback."""
    m = _load_model_cfg()
    return (m.get("provider") or _FALLBACK_PROVIDER).strip()


def is_ollama_cloud():
    """True if the default provider routes through Ollama Cloud (no local load)."""
    p = resolve_provider().lower()
    return "cloud" in p or "ollama-cloud" in p


def _read_env_file():
    """Parse the profile .env into a dict (name -> value). Secrets only, no exec."""
    out = {}
    envf = _HOME / ".env"
    try:
        for line in envf.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def _env(name: str) -> str:
    """Env var, falling back to the .env file (so scripts work outside the agent shell)."""
    v = os.environ.get(name)
    if v:
        return v.strip()
    return _read_env_file().get(name, "").strip()


def _strip_v1(url: str) -> str:
    return url.rstrip("/").removesuffix("/v1").rstrip("/")


def endpoint_for_default():
    """Best-effort inference endpoint base for the current default provider.

    Order matters: cloud/hosted providers must be matched BEFORE the local
    Ollama fallback, otherwise a cloud model name gets POSTed to :11434 and
    returns HTTP 404. Returns a base URL (no trailing /v1).
    """
    p = resolve_provider().lower()
    if "openrouter" in p:
        return "https://openrouter.ai/api"
    if "token" in p or "harbor" in p:
        u = _env("TOKENHARBOR_BASE_URL")
        if u:
            return _strip_v1(u)
    if "cloud" in p or "ollama" in p:
        u = _env("OLLAMA_BASE_URL")
        if u:
            return _strip_v1(u)
    return "http://localhost:11434"


def auth_headers() -> dict:
    """Authorization header for the current provider (empty for local Ollama)."""
    p = resolve_provider().lower()
    if "openrouter" in p:
        k = _env("OPENROUTER_API_KEY")
        return {"Authorization": f"Bearer {k}"} if k else {}
    if "token" in p or "harbor" in p:
        k = _env("TOKENHARBOR_API_KEY")
        return {"Authorization": f"Bearer {k}"} if k else {}
    if "cloud" in p:
        k = _env("OLLAMA_API_KEY")
        return {"Authorization": f"Bearer {k}"} if k else {}
    return {}


def summary() -> dict:
    return {
        "default": resolve_default_model(),
        "provider": resolve_provider(),
        "mini": MINI_MODEL,
        "base_url": endpoint_for_default(),
        "ollama_cloud": is_ollama_cloud(),
        "config_path": str(_CONFIG),
    }


def chat_default(messages, max_tokens=400):
    """One-call chat helper that follows the configured default model.

    For pure reasoning scripts (deep_task, reasoning_loop, analog, active_learn)
    that previously hardcoded "mini-openamer" on :8081. Now they call the
    active default from config.yaml, so switching providers/model updates every
    reasoning script automatically.

    DeepSeek-style models return their answer in a `reasoning` field when
    `content` is empty; we fall back to `reasoning` then. Strips thinking-trace
    preambles.
    """
    import urllib.request
    url = endpoint_for_default() + "/v1/chat/completions"
    body = {"model": resolve_default_model(), "messages": messages,
            "max_tokens": max_tokens}
    headers = {"Content-Type": "application/json"}
    headers.update(auth_headers())
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers)
    r = json.load(urllib.request.urlopen(req, timeout=300))
    msg = r["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    if not content:
        content = (msg.get("reasoning") or "").strip()
    return content


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps(summary(), ensure_ascii=False, indent=2))
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "resolve":
        print(resolve_default_model())
    elif cmd == "mini":
        print(MINI_MODEL)
    elif cmd == "provider":
        print(resolve_provider())
    elif cmd == "list":
        print(json.dumps(summary(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summary(), ensure_ascii=False, indent=2))
