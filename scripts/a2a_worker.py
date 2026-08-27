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
    """Answer via OpenRouter; fall back to local Ollama, then HuggingFace.

    Rule (per operator): prefer free/zero-cost when the API key is absent/blocked.
      OpenRouter (if OPENROUTER_API_KEY) -> Ollama (if reachable & has a model)
      -> HuggingFace Inference (free, no key) -> error.
    Each phase is guarded so a failure just moves to the next backend.
    """
    import urllib.request
    model = model or DEFAULT_MODEL                     # guard empty model
    key = os.environ.get("OPENROUTER_API_KEY", "")

    # 1) OpenRouter (cloud, if key present)
    if key:
        r = _ask_openrouter(prompt, model, key)
        if r.get("ok"):
            return r
        last_err = r.get("error", "")
    else:
        last_err = "no OPENROUTER_API_KEY"

    # 2) Local Ollama (zero-cost, no key)
    r = _ask_ollama(prompt)
    if r.get("ok"):
        return r
    last_err = f"{last_err}; ollama: {r.get('error','')}"

    # 3) HuggingFace Inference (free, no key for public tiny models)
    r = _ask_huggingface(prompt)
    if r.get("ok"):
        return r
    last_err = f"{last_err}; hf: {r.get('error','')}"

    return {"ok": False, "error": last_err}


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


def _ask_ollama(prompt: str) -> dict:
    """Local Ollama (zero-cost). Uses whichever small local model is present."""
    import subprocess as _sp
    import shutil as _sh
    if not _sh.which("ollama"):
        return {"ok": False, "error": "ollama not installed"}
    # Pick a small, fast locally-installed model (prefer ours; fall back).
    candidates = ("qwen3.5:9b", "qwen3.5:4b-q4_K_M", "qwen3.5:4b")
    picked = None
    for c in candidates:
        try:
            lst = _sp.run(["ollama", "list"], capture_output=True, text=True,
                          timeout=20).stdout
            if c in lst:
                picked = c
                break
        except Exception:
            continue
    model = picked or "llama3.2:3b"          # last-ditch guess
    sys_prompt = ("System: Answer ONLY the final answer, no reasoning/thinking, "
                  "in a short sentence.\nUser: ")
    try:
        rr = _sp.run(["ollama", "run", model, sys_prompt + prompt],
                     capture_output=True, text=True, timeout=120)
        out = (rr.stdout or "").strip()
        if not out:
            return {"ok": False, "error": f"ollama {model} empty"}
        # Extract the LAST plausible sentence to strip internal thinking noise.
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
    """Deliberately drop Ollama/qwen-style chain-of-thought noise and return
    the final concise sentence. Naive but practical for short asks."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return text
    # Prefer the LAST sentence-ish token, but cap at 3 lines to stay concise.
    pick = lines[-1] if len(lines) <= 6 else " ".join(lines[-2:])
    # Trim to first sentence on a single line (stop at the natural end).
    for sep in (".\n", "?\n", "—\n"):
        pass
    # simple: strip double-space + leading bullets
    return pick.strip(" .\n").replace("  ", " ").strip()


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