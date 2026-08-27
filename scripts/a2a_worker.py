"""a2a_worker.py — a remotely-hosted sub-agent node (runs on GitHub Actions).

It talks to the shared GitHub repo (the a2a relay), never opens a port:
  1. reads every un*consumed* task-note in directory/a2a/relay/ for its mailbox
  2. verifies Ed25519 signature + freshness (tampered / stale rejected)
  3. executes a WHITELISTED task (ping / echo / time / sum / ask) — no shell
  4. task "ask" calls an LLM (OpenRouter using the OPENROUTER_API_KEY secret)
  5. signs and writes a reply-note addressed back to the task sender
  6. commits + pushes the reply to the same repo (GITHUB_TOKEN / credential)

Usage: python scripts/a2a_worker.py <repo> [--no-push]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.environ.get("OPENAMER_PYTHONPATH", "."))

from openamer_cli.a2a.core import IdentityStore, Envelope          # noqa: E402
from openamer_cli.a2a import relay as R                              # noqa: E402
from openamer_cli.a2a.relay import verify_note                       # noqa: E402

WORKER_MAILBOX = "nodeworker"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
ALLOWED = ("ping", "echo", "time", "sum", "ask")


def _runner_name() -> str:
    try:
        return os.uname().nodename            # Linux runner
    except Exception:
        return os.environ.get("RUNNER_NAME", "gh-actions")


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_model_default() -> dict:
    """Read the operator's DECLARED standard provider + model from OpenAmer's
    config.yaml (model: {provider, default, base_url}). Every user has their own
    standard; A2A should use exactly that, not a hardcoded one.
    Returns {'provider':..., 'model':..., 'base_url':...} or None if absent.
    """
    import os as _os
    # Candidate config locations (most-specific first), NO secrets printed.
    candidates = []
    home_openamer = _os.environ.get("OPENAMER_HOME", "")
    if home_openamer:
        candidates.append(str(Path(home_openamer) / "config.yaml"))
    candidates.append(str(Path.home() / ".openamer" / "config.yaml"))
    # On this laptop the profile-level config lives here:
    laptop = r"C:\Users\damir\AppData\Local\openamer-laptop\config.yaml"
    candidates.append(laptop)
    for p in candidates:
        if not Path(p).exists():
            continue
        try:
            import yaml  # noqa
            d = yaml.safe_load(Path(p).read_text(encoding="utf-8", errors="replace")) or {}
        except Exception:
            # fall back to a naive parse when PyYAML missing
            try:
                txt = Path(p).read_text(encoding="utf-8", errors="replace")
                sect = txt.split("model:")[-1].split("\n")[0:6]
                model = provider = base = ""
                for line in sect:
                    l = line.strip()
                    if l.startswith("default:") and "qwen" not in l:
                        model = l.split(":", 1)[1].strip().strip("'\"")
                    elif l.startswith("provider:"):
                        provider = l.split(":", 1)[1].strip().strip("'\"")
                    elif l.startswith("base_url:"):
                        base = l.split(":", 1)[1].strip().strip("'\"")
                return {"provider": provider or "", "model": model or "",
                        "base_url": base or ""}
            except Exception:
                return None
        m = d.get("model") or {}
        if not m.get("default"):
            return None
        return {"provider": str(m.get("provider") or ""),
                "model": str(m.get("default") or ""),
                "base_url": str(m.get("base_url") or "")}
    return None


def _ask_llm(prompt: str, model: str = DEFAULT_MODEL) -> dict:
    """Answer using the operator's DECLARED default provider+model from config,
    then their available cloud keys, then local/HF as zero-cost fallback.

    Priority (every user's own reality):
      1. EXACTLY what the user declared in config.yaml `model:` (provider+default).
      2. Any other cloud key they have (OpenRouter/OpenAI/Groq/DeepSeek/Gemini/
         Anthropic) via the matching adapter.
      3. Local Ollama (auto-pull tiny model) — zero cost.
      4. HuggingFace public inference — free, no key.
    Each adapter is guarded; a failure moves to the next available backend.
    """
    import os as _os

    candidates = []

    # 0) The operator's declared standard (provider + model + base_url)
    std = _load_model_default()
    if std:
        std_model = std.get("model") or "deepseek/deepseek-v4-flash-0731"
        std_prov = (std.get("provider") or "openrouter").lower()
        or_key = _os.environ.get("OPENROUTER_API_KEY", "")
        std_call = None
        if std_prov in ("openrouter", "openai", "azure", "deepseek", "groq", "gemini"):
            # openai-compat covers most; openrouter is the same shape
            key = {"openrouter": or_key, "openai": _os.environ.get("OPENAI_API_KEY", ""),
                   "deepseek": _os.environ.get("DEEPSEEK_API_KEY", ""),
                   "groq": _os.environ.get("GROQ_API_KEY", ""),
                   "gemini": _os.environ.get("GEMINI_API_KEY", ""),
                   "azure": _os.environ.get("OPENAI_API_KEY", "")}.get(std_prov, or_key)
            base = std.get("base_url") or {
                "openrouter": "https://openrouter.ai/api/v1",
                "openai": "",
                "deepseek": "https://api.deepseek.com/v1",
                "groq": "https://api.groq.com/openai/v1",
                "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
                "azure": std.get("base_url") or "",
            }.get(std_prov)
            std_call = lambda: _ask_openai_compat(prompt, std_model, key, base)
        elif std_prov == "anthropic" and _os.environ.get("ANTHROPIC_API_KEY"):
            std_call = lambda: _ask_anthropic(prompt, std_model, _os.environ["ANTHROPIC_API_KEY"])
        elif std_prov == "ollama":
            std_call = lambda: _ask_ollama(prompt)
        if std_call:
            candidates.append((f"config-standard:{std_prov}", std_call))

    # 1) OpenRouter (if key)
    or_key2 = _os.environ.get("OPENROUTER_API_KEY", "")
    if or_key2:
        candidates.append(("openrouter", lambda: _ask_openrouter(prompt, model, or_key2)))

    # 2) generic OpenAI-compatible (any other key)
    oai_key = _os.environ.get("OPENAI_API_KEY", "")
    oai_base = _os.environ.get("OPENAI_BASE_URL", "")
    groq = _os.environ.get("GROQ_API_KEY", "")
    deepseek = _os.environ.get("DEEPSEEK_API_KEY", "")
    gemini = _os.environ.get("GEMINI_API_KEY", "")
    for name, k, base, dm in (
            ("openai", oai_key, oai_base or "", model),
            ("groq", groq, "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
            ("deepseek", deepseek, "https://api.deepseek.com/v1", "deepseek-chat"),
            ("gemini", gemini, "https://generativelanguage.googleapis.com/v1beta/openai",
             "gemini-2.0-flash"),
    ):
        if k:
            b = (base or "") if name == "openai" else base
            candidates.append((name,
                lambda _m=dm, _k=k, _b=b: _ask_openai_compat(prompt, _m, _k, _b)))
    if oai_key == "" and oai_base:
        candidates.append(("local-openai",
                           lambda: _ask_openai_compat(prompt, "local-model", "", oai_base)))

    # 3) Anthropic
    anthro = _os.environ.get("ANTHROPIC_API_KEY", "")
    if anthro:
        candidates.append(("anthropic", lambda: _ask_anthropic(prompt, "claude-sonnet-4-5", anthro)))

    # 4) Local Ollama (zero-cost)  + 5) HuggingFace (free)
    candidates.append(("ollama", lambda: _ask_ollama(prompt)))
    candidates.append(("huggingface", lambda: _ask_huggingface(prompt)))

    errs = []
    for name, call in candidates:
        try:
            r = call()
        except Exception as e:
            errs.append(f"{name}: {e}")
            continue
        if r.get("ok"):
            return r
        errs.append(f"{name}: {r.get('error','')}")
    return {"ok": False, "error": " ; ".join(errs)}


def _ask_openrouter(prompt: str, model: str, key: str) -> dict:
    import urllib.request
    import json as _json
    body = _json.dumps({"model": model,
                        "messages": [{"role": "system",
                                      "content": "You are the OpenAmer remote "
                                      "worker sub-agent. Be concise, accurate, "
                                      "and helpful."},
                                     {"role": "user", "content": prompt}],
                        "max_tokens": 400}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "X-Title": "openamer-a2a-worker"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = _json.loads(resp.read().decode("utf-8", "replace"))
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        if not text:
            return {"ok": False, "error": "openrouter empty reply"}
        return {"ok": True, "text": text.strip(), "model": data.get("model", model)}
    except Exception as e:
        err = str(e)
        if hasattr(e, "read"):
            try:
                err = e.read().decode("utf-8", "replace")[:400]
            except Exception:
                pass
        return {"ok": False, "error": f"openrouter: {err}"}


def _ask_openai_compat(prompt, model, key, base_url=None):
    """Generic OpenAI-compatible chat-completion POST (covers OpenAI, DeepSeek,
    Groq, Gemini's OpenAI adapter, vLLM/local servers — anything with a
    '/chat/completions' endpoint). Zero-cost unless the operator configured a key."""
    import urllib.request, urllib.error
    import json as _json
    base = (base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/chat/completions"
    body = _json.dumps({
        "model": model,
        "messages": [{"role": "system",
                      "content": "You are the OpenAmer remote worker sub-agent. "
                      "Be concise, accurate, and helpful."},
                     {"role": "user", "content": prompt}],
        "max_tokens": 400,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = _json.loads(resp.read().decode("utf-8", "replace"))
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return {"ok": bool(text), "text": (text or "").strip(),
                "model": data.get("model", model)} if text else \
            {"ok": False, "error": f"openai-compat empty ({url})"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"openai-compat {e.code} ({url})"}
    except Exception as e:
        return {"ok": False, "error": f"openai-compat {e} ({url})"}


def _ask_anthropic(prompt, model, key):
    """Anthropic Messages API (needs a key; no silent cost without one)."""
    import urllib.request, urllib.error
    import json as _json
    url = "https://api.anthropic.com/v1/messages"
    body = _json.dumps({
        "model": model,
        "system": "You are the OpenAmer remote worker sub-agent. Be concise, accurate, helpful.",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01",
        "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = _json.loads(resp.read().decode("utf-8", "replace"))
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return {"ok": bool(text), "text": text.strip(), "model": data.get("model", model)} if text else \
            {"ok": False, "error": "anthropic empty"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"anthropic {e.code}"}
    except Exception as e:
        return {"ok": False, "error": f"anthropic {e}"}


def _ask_ollama(prompt: str) -> dict:
    """Local Ollama (zero-cost). Uses whichever small local model is present,
    else auto-pulls a tiny model on first need so every user has a local brain."""
    import subprocess as _sp
    import shutil as _sh
    if not _sh.which("ollama"):
        return {"ok": False, "error": "ollama not installed"}
    # Pick a small, fast locally-installed model (prefer ours; fall back).
    candidates = ("qwen3.5:9b", "qwen3.5:4b-q4_K_M", "qwen3.5:4b",
                  "qwen2.5:0.5b", "qwen2.5:1.5b", "tinyllama:1.1b",
                  "llama3.2:1b", "llama3.2:3b")
    picked = None
    try:
        installed = _sp.run(["ollama", "list"], capture_output=True, text=True,
                            timeout=20).stdout or ""
    except Exception:
        installed = ""
    for c in candidates:
        if c in installed:
            picked = c
            break
    if not picked:
        # Auto-provision a tiny local model on first need (zero cost, local).
        model_auto = "qwen2.5:0.5b"
        try:
            _sp.run(["ollama", "pull", model_auto], capture_output=True, text=True,
                    timeout=600)
            picked = model_auto
        except Exception as e:
            return {"ok": False, "error": f"ollama auto-pull failed: {e}"}
    model = picked or "qwen2.5:0.5b"
    sys_prompt = ("System: Answer ONLY the final answer, no reasoning/thinking, "
                  "in a short sentence.\nUser: ")
    try:
        rr = _sp.run(["ollama", "run", model, sys_prompt + prompt],
                     capture_output=True, text=True, timeout=180)
        out = (rr.stdout or "").strip()
        if not out:
            return {"ok": False, "error": f"ollama {model} empty"}
        final = _extract_answer(out)
        return {"ok": True, "text": final, "model": f"ollama:{model}"}
    except Exception as e:
        return {"ok": False, "error": f"ollama {model}: {e}"}


def _ask_huggingface(prompt: str) -> dict:
    """HuggingFace Inference API — free for a small public text-gen model."""
    import urllib.request
    import urllib.error
    import json as _json
    # A tiny, free, no-auth general-instruct model. Good enough for short asks.
    model = "Qwen/Qwen2.5-1.5B-Instruct"
    url = f"https://api-inference.huggingface.co/models/{model}"
    body = _json.dumps({"inputs": prompt,
                        "parameters": {"max_new_tokens": 120}}).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = _json.loads(resp.read().decode("utf-8", "replace"))
        if isinstance(data, list) and data:
            text = data[0].get("generated_text", "") or ""
            tail = _extract_answer(text)
            return {"ok": True, "text": tail or text.strip(), "model": f"hf:{model}"}
        return {"ok": False, "error": "hf: no generation"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"hf {e.code}"}
    except Exception as e:
        return {"ok": False, "error": f"hf: {e}"}


def _extract_answer(text: str) -> str:
    """Strip Ollama/qwen-style chain-of-thought noise and return the final
    concise answer. The tail after the last GPT thought-block is usually the
    real final answer; we take the LAST sentence that looks like a statement."""
    import re as _re
    if not text:
        return ""
    # Chop everything after a closing thought block "final:\n ..." or keep tail
    # Split into lines, drop empty, drop obvious thinking heads.
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Heuristic: the usable answer usually sits in the last 1-2 non-trivial
    # lines after any "**Final**", "Answer:", ">>", or a pure "</think>"
    cleaned = []
    for l in lines:
        low = l.lower()
        if low.startswith(("thinking", "thought", "reasoning", "*thinking*",
                           "step ", "**thought", "let me", "we need", "notes")):
            continue
        cleaned.append(l)
    if not cleaned:
        cleaned = lines
    # Prefer the LAST line, but avoid chains where the real answer is 2 lines.
    pick = cleaned[-1]
    if len(cleaned) >= 2 and _looks_answer(cleaned[-1]) is False:
        pick = " ".join(cleaned[-2:])
    # strip markdown /**/ and leading bullets, collapse spaces
    pick = _re.sub(r"\*+|`+", "", pick)
    pick = _re.sub(r"^\s*[-•–>]\s*", "", pick)
    return pick.strip(" .\n").replace("  ", " ").strip()


def _looks_answer(line: str) -> bool:
    # A sentence ending with terminator, or a compact statement, is "final".
    return line.rstrip().endswith((".", "!", "?")) or len(line) < 90


def _task_executor(task: str, payload: dict) -> dict:
    if task == "ping":
        return {"ok": True, "pong": payload.get("msg", "pong"),
                "at": _now_utc(), "runner": _runner_name()}
    if task == "echo":
        return {"ok": True, "text": payload.get("text", "")}
    if task == "time":
        return {"ok": True, "utc": _now_utc()}
    if task == "sum":
        return {"ok": True, "sum": int(payload.get("a", 0)) + int(payload.get("b", 0))}
    if task == "ask":
        return _ask_llm(payload.get("msg", ""), payload.get("model") or "")
    return {"error": "unknown task"}


def _consumed(state: Path) -> set:
    p = state / ".a2a-consumed.json"
    if p.exists():
        try:
            return set(json.loads(p.read_text(encoding="utf-8")).get("done", []))
        except Exception:
            return set()
    return set()


def run(repo: Path, no_push: bool = False) -> int:
    inbox = repo / R.RELAY_PREFIX
    ran = 0
    if not inbox.exists():
        print("no relay dir yet — nothing to do"); return 0

    store = IdentityStore(repo / ".a2a-worker")
    ident = store.ensure_identity()
    state = repo
    done  = _consumed(state)

    for f in sorted(inbox.glob("*.json")):
        if f.name in done:
            continue
        try:
            note = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            done.add(f.name); continue
        if note.get("recipient") not in (WORKER_MAILBOX, "*"):
            continue
        ver = verify_note(note)
        if not ver["ok"]:
            print("skip invalid/stale:", f.name, "--", ver.get("reason"))
            done.add(f.name); continue
        env     = ver["env"]
        task    = (env.payload or {}).get("task")
        if task not in ALLOWED:
            print("skip unsupported task:", task); done.add(f.name); continue
        result  = _task_executor(task, env.payload or {})
        reply   = Envelope.create(
            private_key=store.private_key(), sender=f"{ident.fingerprint}@openamer",
            recipient=env.sender, kind="task.result",
            payload={"task": task, "from": WORKER_MAILBOX, **result})
        rnote   = R.relay_note(identity_store=store, envelope=reply)
        rf      = inbox / R.sort_relay_filename(reply.recipient)
        rf.write_text(json.dumps(rnote, ensure_ascii=False), encoding="utf-8")
        done.add(f.name); ran += 1
        print(f"[worker] EXEC {task:6} sender={env.sender[:8]} "
              f"-> reply {rf.name} (pubkey={reply.sender[:8]})")

    if ran:
        (state / ".a2a-consumed.json").write_text(
            json.dumps({"done": sorted(done)}, ensure_ascii=False), encoding="utf-8")

        if not no_push:
            subprocess.run(["git", "-C", str(repo), "add", R.RELAY_PREFIX,
                            ".a2a-consumed.json"], capture_output=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m",
                            "a2a worker: replies"], capture_output=True)
            push = subprocess.run(["git", "-C", str(repo), "push", "-q"],
                                  capture_output=True, text=True)
            if push.returncode != 0:
                print("[worker] push:", (push.stderr or "").strip()[-300:])
            else:
                print("[worker] pushed", ran, "replies")
    print(f"[worker] done: {ran} task(s) handled")
    return ran


def main():
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    no_push = "--no-push" in sys.argv
    run(repo, no_push)


if __name__ == "__main__":
    main()