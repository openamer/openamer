#!/usr/bin/env python3
"""Mini-OpenAmer: local OpenAI-compatible server for the tuned Qwen3.5-2B LoRA.
CPU inference via transformers. Endpoint: http://localhost:8081/v1/chat/completions
"""
import json, torch, threading, time, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE = "Qwen/Qwen3.5-2B"
ADAPTER = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/lora_out/adapter"
PORT = 8081
IDLE_TIMEOUT = 1800  # seconds — auto-shutdown after 30 min without requests (energy saver)

print("loading model...", flush=True)
tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, low_cpu_mem_usage=True)
model = PeftModel.from_pretrained(model, ADAPTER)
model.eval()
print("MODEL_READY", flush=True)

# energy-saver: track last request time; shutdown thread kills process after idle timeout
last_request = {"ts": time.time()}

def idle_watcher():
    while True:
        time.sleep(60)
        if time.time() - last_request["ts"] > IDLE_TIMEOUT:
            print(f"IDLE_SHUTDOWN: no requests for {IDLE_TIMEOUT}s — freeing RAM", flush=True)
            os._exit(0)

threading.Thread(target=idle_watcher, daemon=True).start()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_POST(self):
        last_request["ts"] = time.time()  # energy-saver: reset idle timer
        if not self.path.startswith("/v1/chat/completions"):
            self.send_response(404); self.end_headers(); return
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n))
        msgs = req.get("messages", [])
        max_new = int(req.get("max_tokens", 200))
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt")
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        content = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        resp = {
            "id": "mini-openamer", "object": "chat.completion", "model": "mini-openamer",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": ids["input_ids"].shape[1], "completion_tokens": max_new},
        }
        body = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
