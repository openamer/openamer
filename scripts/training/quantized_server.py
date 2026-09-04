#!/usr/bin/env python3
"""Quantized inference — energy-efficient model serving.

LAPTOP (CPU): dynamic int8 quantization via torch.ao (no CUDA needed)
PC (GPU):     4-bit via bitsandbytes (needs CUDA)

Energy math:
  fp16 2B ≈ 4 GB RAM, ~25 W inference
  int8 2B ≈ 2 GB RAM, ~15 W inference  (-40%)
  int4 2B ≈ 1 GB RAM, ~10 W inference  (-60%)

Both paths serve the same OpenAI-compatible API on :8081.
"""
import json, os, sys, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import torch

# detect environment
HAS_CUDA = torch.cuda.is_available()
MODEL_ID = "Qwen/Qwen3.5-2B"
PORT = 8081

print(f"[quantized-server] CUDA: {HAS_CUDA}")

if HAS_CUDA:
    # PC path: 4-bit via bitsandbytes
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, quantization_config=bnb)
    print(f"[quantized-server] 4-bit loaded, VRAM: {torch.cuda.memory_allocated()/1024**3:.1f} GB")
else:
    # Laptop path: dynamic int8 (CPU)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from torch.ao.quantization import quantize_dynamic
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.float32)
    # quantize linear layers to int8 (dynamic — activates on the fly)
    model = quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)
    print("[quantized-server] int8 dynamic quantization loaded (CPU)")

model.eval()
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
            self._json({"status": "alive", "model": MODEL_ID,
                        "quantization": "4-bit CUDA" if HAS_CUDA else "int8 CPU",
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
            "id": "mini-quantized", "object": "chat.completion",
            "model": MODEL_ID,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
        })

if __name__ == "__main__":
    mode = "4-bit GPU" if HAS_CUDA else "int8 CPU"
    print(f"[quantized-server] READY on :{PORT} ({mode}) — energy-optimized inference")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
