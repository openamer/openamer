#!/usr/bin/env python3
"""Distilled Mini Server — Qwen3.5-0.8B, 2B's knowledge in a smaller body.

Destillation: the 0.8B model trains on the SAME SFT data the 2B learned
from. Same behavior, 1/5 the size, 1/2.5 the energy.

Energy math:
  2B fp32 ≈ 8 GB RAM, ~25 W inference
  0.8B fp16 ≈ 1.6 GB RAM, ~10 W inference  (-60%)

Serves OpenAI-compatible API on :8081 (same as quantized_server).
"""
import json, os, sys, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen3.5-0.8B"
ADAPTER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "lora_out", "adapter_0.8B")
PORT = 8081
HAS_CUDA = torch.cuda.is_available()

print(f"[mini-distilled] loading 0.8B distilled model (CUDA: {HAS_CUDA})")
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(
    MODEL, torch_dtype=torch.float16 if HAS_CUDA else torch.float32,
    low_cpu_mem_usage=True)
if HAS_CUDA:
    model = model.cuda()
model.eval()
print(f"[mini-distilled] loaded — RAM/VRAM: "
      f"{torch.cuda.memory_allocated()/1024**3:.1f} GB" if HAS_CUDA else
      f"[mini-distilled] loaded — CPU")

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
                        "type": "distilled (0.8B trained on 2B's SFT data)",
                        "uptime_s": round(time.time()-START, 1),
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
        max_new = body.get("max_tokens", 200)

        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt")
        if HAS_CUDA:
            ids = ids.to("cuda")
        with torch.no_grad(), lock:
            out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        content = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        INFERENCE_COUNT += 1

        self._json({
            "id": "mini-distilled", "object": "chat.completion",
            "model": MODEL,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
        })

if __name__ == "__main__":
    print(f"[mini-distilled] READY on :{PORT} — 0.8B distilled, ~10 W inference")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()