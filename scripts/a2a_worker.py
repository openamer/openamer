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


def _ask_llm(prompt: str, model: str = DEFAULT_MODEL) -> dict:
    """Answer via the first AVAILABLE provider, most-capable first — agnostic.

    Operator preference / reality:
      1. Cloud, IF the operator has a key for it (their choice; costs their credits):
         OpenRouter / generic OpenAI-compatible (OpenAI, DeepSeek, Groq, Gemini
         via /chat/completions) / Anthropic. Each tried only when its env key is set.
      2. Local zero-cost: Ollama (if installed).
      3. HuggingFace public Inference (free, no key).
    No key anywhere -> we never dial a paid API; we silently drop to Ollama then HF.
    Each adapter is guarded so a failure just moves to the next available backend.
    """
    import os as _os

    # --- order of preference, one of which will answer ---
    candidates = []

    # 1a) OpenRouter
    or_key = _os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        candidates.append(("openrouter", lambda: _ask_openrouter(prompt, model, or_key)))

    # 1b) generic OpenAI-compatible (any of several keys / base url)
    oai_key = _os.environ.get("OPENAI_API_KEY", "")
    oai_base = _os.environ.get("OPENAI_BASE_URL", "")
    groq = _os.environ.get("GROQ_API_KEY", "")
    deepseek = _os.environ.get("DEEPSEEK_API_KEY", "")
    gemini = _os.environ.get("GEMINI_API_KEY", "")
    for name, k, base, default_model in (
                ("openai", oai_key, oai_base, model),
                ("groq", groq, "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
                ("deepseek", deepseek, "https://api.deepseek.com/v1", "deepseek-chat"),
                ("gemini", gemini, "https://generativelanguage.googleapis.com/v1beta/openai",
                 "gemini-2.0-flash"),
        ):
            if k:
                b = (base or oai_base) if name == "openai" else base
                candidates.append((name,
                    lambda _m=default_model, _k=k, _b=b: _ask_openai_compat(prompt, _m, _k, _b)))
    # local base url without a key -> probably a local/vLLM server (free)
    if not oai_key and oai_base:
        candidates.append(("local-openai", lambda: _ask_openai_compat(prompt, "local-model", "", oai_base)))

    # 1c) Anthropic
    anthro = _os.environ.get("ANTHROPIC_API_KEY", "")
    if anthro:
        candidates.append(("anthropic", lambda: _ask_anthropic(prompt, "claude-sonnet-4-5", anthro)))

    # 2) Local Ollama (zero-cost)
    candidates.append(("ollama", lambda: _ask_ollama(prompt)))

    # 3) HuggingFace (free, no key)
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