#!/usr/bin/env python3
"""Frontier Server — Qwen3.5-4B with CUDA on RTX 3060 Ti (8 GB VRAM).

OpenAI-compatible API on :8082. Strongest model on local hardware.
Verified E2E: consciousness analysis, structured reasoning.
"""
import json, os, sys, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen3.5-4B"
PORT = 8082

print("[frontier-4b] loading model...")
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(
    MODEL, torch_dtype=torch.float16, low_cpu_mem_usage=True).cuda()
model.eval()
vram = torch.cuda.memory_allocated() / 1024**3
print(f"[frontier-4b] MODEL_READY — VRAM: {vram:.1f} GB")

lock = threading.Lock()
START = time.time()
INFERENCE_COUNT = 0

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_GET(self):
        if self.path == "/health":
            self._json({"status": "alive", "model": MODEL,
                        "uptime_s": round(time.time()-START, 1),
                        "vram_used_gb": round(vram, 1),
                        "inferences": INFERENCE_COUNT})
        else:
            self._json({"error": "unknown"}, 404)

    def do_POST(self):
        global INFERENCE_COUNT
        if self.path != "/v1/chat/completions":
            self._json({"error": "unknown"}, 404)
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        msgs = body.get("messages", [])
        max_new = body.get("max_tokens", 500)

        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt").to("cuda")
        with torch.no_grad(), lock:
            out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        content = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        INFERENCE_COUNT += 1

        self._json({
            "id": "qwen35-4b-frontier", "object": "chat.completion",
            "model": MODEL,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
        })

if __name__ == "__main__":
    print(f"[frontier-4b] READY on :{PORT} — Qwen3.5-4B CUDA frontier reasoning")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
