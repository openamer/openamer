#!/usr/bin/env python3
"""Mini-OpenAmer LIVE server — never sleeps (dolphin architecture).

The LIVE instance never goes down. Hot-swap of adapters happens at runtime
via a POST to /admin/swap (called by the training pipeline after a nightly
retrain). The TRAINING process runs separately and may crash freely —
it can never take this server down.

Endpoints:
  POST /v1/chat/completions   — OpenAI-compatible inference
  POST /admin/swap            — hot-load a new adapter from disk (no restart)
  GET  /health                — liveness probe
"""
import json, torch, threading, time, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE = "Qwen/Qwen3.5-2B"
ADAPTER_DIR = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/lora_out"
ADAPTER_DEFAULT = os.path.join(ADAPTER_DIR, "adapter")
PORT = 8081
IDLE_TIMEOUT = 1800  # energy saver — but server PROCESS stays up, only RAM freed on swap

print("loading live model...", flush=True)
tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, low_cpu_mem_usage=True)
model = PeftModel.from_pretrained(model, ADAPTER_DEFAULT, adapter_name="default")
model.eval()
print("MODEL_READY", flush=True)

lock = threading.Lock()          # serialize generation + swap
last_request = {"ts": time.time()}
swap_count = {"n": 0}

def do_swap(new_adapter_path):
    """Hot-load a fresh adapter without restarting. Returns status string."""
    global model
    with lock:
        if not os.path.isdir(new_adapter_path):
            return f"ERR: adapter path missing: {new_adapter_path}"
        try:
            # deterministic name; PEFT overwrites same-name adapter on load
            model.load_adapter(new_adapter_path, adapter_name="default",
                               is_trainable=False)
            model.set_adapter("default")
            swap_count["n"] += 1
            return f"OK: swapped to {os.path.basename(new_adapter_path)} (swap #{swap_count['n']})"
        except Exception as e:
            # if load_adapter fails because 'default' exists, use delete+reload
            try:
                model.delete_adapter("default")
                model.load_adapter(new_adapter_path, adapter_name="default")
                model.set_adapter("default")
                swap_count["n"] += 1
                return f"OK (after delete): swapped (swap #{swap_count['n']})"
            except Exception as e2:
                return f"ERR: {e} | fallback: {e2}"

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        last_request["ts"] = time.time()
        if self.path == "/health":
            self._json({"status": "alive", "uptime_s": round(time.time()-START,1),
                        "swaps": swap_count["n"]})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        last_request["ts"] = time.time()
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")

        if self.path == "/admin/swap":
            path = req.get("adapter", ADAPTER_DEFAULT)
            self._json({"result": do_swap(path)})
            return

        if not self.path.startswith("/v1/chat/completions"):
            self._json({"error": "not found"}, 404)
            return

        msgs = req.get("messages", [])
        max_new = int(req.get("max_tokens", 200))
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt")
        with torch.no_grad(), lock:
            out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        content = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        self._json({
            "id": "mini-openamer", "object": "chat.completion", "model": "mini-openamer",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": ids["input_ids"].shape[1],
                      "completion_tokens": max_new},
        })

START = time.time()
print(f"LIVE_SERVER_READY on :{PORT} — dolphin architecture, never down", flush=True)
ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
