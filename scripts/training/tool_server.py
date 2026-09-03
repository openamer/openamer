#!/usr/bin/env python3
"""Mini-OpenAmer Tool Server — gives the 2B model HANDS.

Wraps OpenAmer's existing capabilities as OpenAI function-calling tools.
The 2B model DECIDES which tool to call; this server EXECUTES it.
Architecture: the small model orchestrates, established systems act.

Tools provided:
  - web_search        — internet research
  - pc_action         — desktop control (via computer_use / CDP bridge)
  - browser_action    — navigate/click/extract via CDP (:9222)
  - speak             — TTS output (openamer voice system)
  - listen            — STT capture (openamer STT config)
  - see               — screenshot + local vision model (SmolVLM if installed)
  - read_memory       — longterm memory retrieval
  - write_memory      — add episode
  - reason_deep       — recursive reasoning loop
  - run_python        — safe python execution (tool_math pattern)

Endpoint: POST /v1/chat/completions (OpenAI-compatible, with tool support)
          GET  /tools              — list available tools
          GET  /health

The 2B model receives tool definitions in the system prompt and responds
with JSON tool calls; this server executes them and feeds results back.
"""
import json, os, sys, time, threading, subprocess, urllib.request, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smart_router import smart_route
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, r"C:/Users/damir/AppData/Local/openamer-laptop/scripts")

TOOLS = [
    {"name": "web_search", "desc": "Search the internet. Input: {query}. Output: results.",
     "params": {"query": "string"}},
    {"name": "pc_action", "desc": "Control the PC: click, type, key, scroll. Input: {action, target}.",
     "params": {"action": "click|type|key|scroll", "target": "string"}},
    {"name": "browser_action", "desc": "Control the browser via CDP: navigate, click, read. Input: {action, url_or_selector}.",
     "params": {"action": "navigate|click|read", "url_or_selector": "string"}},
    {"name": "speak", "desc": "Speak text aloud via TTS. Input: {text}.",
     "params": {"text": "string"}},
    {"name": "see", "desc": "Take a screenshot and describe it. Input: {}. Output: description.",
     "params": {}},
    {"name": "read_memory", "desc": "Search long-term memory. Input: {query}. Output: relevant episodes.",
     "params": {"query": "string"}},
    {"name": "reason_deep", "desc": "Use the recursive reasoning loop for complex questions. Input: {question}.",
     "params": {"question": "string"}},
    {"name": "run_python", "desc": "Execute python code for exact calculations. Input: {code}. Output: stdout.",
     "params": {"code": "string"}},
    {"name": "listen", "desc": "Listen to microphone and transcribe speech. Input: {}. Output: transcript.",
     "params": {}},
]

# ---- Tool implementations (delegate to existing systems) ----

def t_web_search(params):
    q = params.get("query", "")
    # search via the RUNNING BROWSER (CDP :9222) — real session, no captcha
    try:
        import urllib.request as _ur
        import websocket as _ws_mod
        import urllib.parse as _up
        tabs = json.loads(_ur.urlopen("http://localhost:9222/json", timeout=5).read())
        page = next((t for t in tabs if t.get("type") == "page"), None)
        if not page:
            return {"error": "no browser tab available for search"}
        ws = _ws_mod.create_connection(page["webSocketDebuggerUrl"], timeout=20)
        ws.send(json.dumps({"id": 1, "method": "Page.navigate",
            "params": {"url": f"https://www.bing.com/search?q={_up.quote(q)}"}}))
        ws.recv()
        time.sleep(4)
        for _ in range(5):
            ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {
                "expression": "document.querySelectorAll('.b_algo').length",
                "returnByValue": True}}))
            while True:
                m = json.loads(ws.recv())
                if m.get("id") == 2: break
            if m["result"]["result"].get("value", 0) > 0: break
            time.sleep(2)
        ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate", "params": {
            "expression": "[...document.querySelectorAll('.b_algo')].slice(0,5).map(e=>{const a=e.querySelector('h2 a');const t=a?a.textContent:'';const p=e.querySelector('p');const s=p?(p.textContent||p.innerText):'';return t+' :: '+s.slice(0,150)}).join('||').slice(0,1500)",
            "returnByValue": True}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 3: break
        ws.close()
        return {"results": m["result"]["result"].get("value", "(empty)")[:1500]}
    except Exception as e:
        return {"error": "search failed: " + str(e)[:200]}

def t_pc_action(params):
    # delegates to computer_use via subprocess (openamer CLI)
    action = params.get("action", "")
    target = params.get("target", "")
    try:
        r = subprocess.run(["openamer", "computer-use", action, target],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        return {"output": (r.stdout or r.stderr)[:800]}
    except Exception as e:
        return {"error": str(e)[:200]}

def t_browser_action(params):
    # CDP bridge — reuse existing browser session
    action = params.get("action", "")
    target = params.get("url_or_selector", "")
    try:
        if action == "navigate":
            import urllib.parse, urllib.request as ur
            tabs = json.load(ur.urlopen("http://localhost:9222/json", timeout=5))
            ws_url = next((t["webSocketDebuggerUrl"] for t in tabs if t.get("type")=="page"), None)
            if not ws_url: return {"error": "no page tab"}
            import websocket
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({"id":1,"method":"Page.navigate","params":{"url":target}}))
            ws.recv(); ws.close()
            return {"navigated": target}
        elif action == "read":
            import urllib.request as ur
            tabs = json.load(ur.urlopen("http://localhost:9222/json", timeout=5))
            ws_url = next((t["webSocketDebuggerUrl"] for t in tabs if t.get("type")=="page"), None)
            if not ws_url: return {"error": "no page tab"}
            import websocket
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({"id":1,"method":"Runtime.evaluate","params":{
                "expression":"document.body.innerText.slice(0,2000)","returnByValue":True}}))
            while True:
                m = json.loads(ws.recv())
                if m.get("id")==1:
                    return {"content": m["result"]["result"].get("value","")[:2000]}
        return {"error": f"unknown browser action: {action}"}
    except Exception as e:
        return {"error": str(e)[:200]}

def t_speak(params):
    text = params.get("text", "")[:500]
    try:
        # Windows SAPI TTS (built-in, 0 Energie-Overhead)
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            f"Add-Type -AssemblyName System.Speech; "
            f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Speak('{text.replace(chr(39), chr(39)*2)}')"],
            capture_output=True, text=True, timeout=30)
        return {"spoken": text[:100], "rc": r.returncode}
    except Exception as e:
        return {"error": str(e)[:200]}

def t_listen(params):
    """Capture audio from mic and transcribe via whisper (openamer config)."""
    try:
        # whisper via openamer CLI (uses configured whisper-1)
        r = subprocess.run(["openamer", "voice", "--listen", "--transcribe"],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        return {"transcript": (r.stdout or "").strip()[:500]}
    except Exception as e:
        return {"error": str(e)[:200]}

def t_see(params):
    try:
        img_path = r"C:/Users/damir/AppData/Local/openamer-laptop/memory/see_screenshot.png"
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$bmp=New-Object System.Drawing.Bitmap($b.Width,$b.Height); "
            "$g=[System.Drawing.Graphics]::FromImage($bmp); "
            "$g.CopyFromScreen(0,0,0,0,$b.Size); "
            f"$bmp.Save('{img_path}')"],
            capture_output=True, text=True, timeout=20)
        # local vision via moondream (Ollama)
        import base64
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        req = urllib.request.Request("http://localhost:11434/api/generate",
            data=json.dumps({"model": "moondream",
                             "prompt": "Describe this screenshot briefly: what is shown?",
                             "images": [b64], "stream": False}).encode(),
            headers={"Content-Type": "application/json"})
        vision = json.load(urllib.request.urlopen(req, timeout=120)).get("response", "")
        return {"seen": vision[:500], "screenshot": img_path}
    except Exception as e:
        return {"error": str(e)[:200]}

def t_read_memory(params):
    try:
        from longterm_memory import query
        res = query(params.get("query", ""))
        return {"episodes": [{"sim": s, "text": e["text"][:200]} for s, e in res]}
    except Exception as e:
        return {"error": str(e)[:200]}

def t_reason_deep(params):
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from reasoning_loop import recursive_ask
        r = recursive_ask(params.get("question", ""))
        return {"answer": r["answer"][:1000], "rounds": r["rounds"]}
    except Exception as e:
        return {"error": str(e)[:200]}

def t_run_python(params):
    code = params.get("code", "")
    if any(k in code for k in ("os.system", "subprocess", "shutil.rmtree", "__import__('os')")):
        return {"error": "blocked: system-level operations not allowed in tool math"}
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=15, encoding="utf-8", errors="replace")
        return {"stdout": r.stdout[:800], "stderr": r.stderr[:200], "rc": r.returncode}
    except Exception as e:
        return {"error": str(e)[:200]}

EXECUTORS = {
    "web_search": t_web_search, "pc_action": t_pc_action,
    "browser_action": t_browser_action, "speak": t_speak,
    "see": t_see, "read_memory": t_read_memory,
    "reason_deep": t_reason_deep, "run_python": t_run_python,
    "listen": t_listen,
}

# ---- 2B model (loaded once) ----
print("loading mini model for tool orchestration...", flush=True)
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE = "Qwen/Qwen3.5-2B"
ADAPTER = r"C:/Users/damir/AppData/Local/openamer-laptop/scripts/training/lora_out/adapter"
tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, low_cpu_mem_usage=True)
model = PeftModel.from_pretrained(model, ADAPTER)
model.eval()  # CPU only on laptop (no GPU)
print("MODEL_READY", flush=True)

lock = threading.Lock()
last_request = {"ts": time.time()}
swap_count = {"n": 0}
IDLE_TIMEOUT = 1800

def idle_watcher():
    while True:
        time.sleep(60)
        if time.time() - last_request["ts"] > IDLE_TIMEOUT:
            print("IDLE_SHUTDOWN: freeing RAM", flush=True)
            os._exit(0)

threading.Thread(target=idle_watcher, daemon=True).start()

TOOLS_PROMPT = """You are an agent with tools. If a task needs a tool, reply ONLY with one line of JSON (no text before/after):

{"tool": "toolname", "params": {"key": "value"}}

Available tools:
""" + "\n".join(f"- {t['name']}: {t['desc']}  (params: {list(t['params'].keys())})" for t in TOOLS) + """

EXAMPLES:
User: "Search the internet for X" -> {"tool": "web_search", "params": {"query": "X"}}
User: "Open the website example.com" -> {"tool": "browser_action", "params": {"action": "navigate", "url_or_selector": "https://example.com"}}
User: "What is 15% of 847?" -> {"tool": "run_python", "params": {"code": "print(847 * 0.15)"}}
User: "What do you know about X?" -> {"tool": "read_memory", "params": {"query": "X"}}

If the question needs NO tool (e.g. a simple question about yourself), reply normally.
For tasks needing internet/browser/calculation/memory: ALWAYS call the tool first."""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        last_request["ts"] = time.time()
        if self.path == "/tools":
            self._json({"tools": TOOLS})
        elif self.path == "/health":
            self._json({"status": "alive", "tools": len(TOOLS), "swaps": swap_count["n"]})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        last_request["ts"] = time.time()
        # lazy adapter swap: check for pending swap request
        flag = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".swap_request")
        if os.path.exists(flag):
            new_adapter = open(flag).read().strip()
            os.remove(flag)
            try:
                with lock:
                    model.load_adapter(new_adapter, adapter_name="default", is_trainable=True)
                    model.set_adapter("default")
                    print(f"[lazy-swap] adapter reloaded from {new_adapter}", flush=True)
            except Exception as e:
                print(f"[lazy-swap] failed: {str(e)[:200]}", flush=True)
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")

        if self.path == "/admin/swap":
            # write a swap-request file; the server checks it before each request
            # and reloads the adapter lazily (avoids in-memory PEFT issues on CPU)
            new_adapter = req.get("adapter", ADAPTER)
            flag = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".swap_request")
            with open(flag, "w") as f:
                f.write(new_adapter)
            swap_count["n"] += 1
            self._json({"result": f"OK: swap queued (#{swap_count['n']}) — applied on next request"})
            return

        if self.path == "/execute_tool":
            # direct tool execution (for external callers / testing)
            tname = req.get("tool", "")
            params = req.get("params", {})
            fn = EXECUTORS.get(tname)
            if not fn:
                self._json({"error": f"unknown tool: {tname}"}, 400); return
            self._json({"result": fn(params)})
            return

        if not self.path.startswith("/v1/chat/completions"):
            self._json({"error": "not found"}, 404); return

        msgs = req.get("messages", [])
        max_new = int(req.get("max_tokens", 300))
        use_tools = req.get("use_tools", True)

        if use_tools:
            msgs = [{"role": "system", "content": TOOLS_PROMPT}] + \
                   [m for m in msgs if m.get("role") != "system"]

        # SMART ROUTING: complex queries go to free cloud models
        routing = smart_route(msgs, max_tokens=max_new)
        if routing.get("routed_to") == "cloud" and routing.get("content"):
            self._json({
                "id": "mini-openamer-smart", "object": "chat.completion",
                "model": routing.get("source", "cloud"),
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": routing["content"]}}],
                "routed_to": "cloud", "cloud_model": routing.get("source"),
            })
            return

        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt")
        with torch.no_grad(), lock:
            out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        content = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()

        # check if model wants to call a tool
        tool_call = None
        # robust: find FIRST complete JSON with "tool" key anywhere in output
        m = re.search(r'\{\s*"tool"\s*:\s*"[a-z_]+"\s*,\s*"params"\s*:\s*\{[^}]*\}\s*\}', content)
        if m:
            try:
                parsed = json.loads(m.group(0))
                tname = parsed.get("tool")
                fn = EXECUTORS.get(tname)
                if fn:
                    result = fn(parsed.get("params", {}))
                    tool_call = tname
                    # return RAW tool result directly (2B can't reliably synthesize)
                    self._json({
                        "id": "mini-openamer", "object": "chat.completion",
                        "model": "mini-openamer-tools",
                        "choices": [{"index": 0, "finish_reason": "tool_use",
                                     "message": {"role": "assistant", "content":
                                         f"[TOOL_RESULT:{tname}] {json.dumps(result, ensure_ascii=False)[:1500]}"}}],
                        "tool_used": tname,
                        "tool_result": result,
                    })
                    return
            except Exception as e:
                pass

        self._json({
            "id": "mini-openamer", "object": "chat.completion",
            "model": "mini-openamer-with-tools",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": content}}],
            "tool_used": tool_call,
            "usage": {"prompt_tokens": ids["input_ids"].shape[1],
                      "completion_tokens": max_new},
        })

print(f"TOOL_SERVER_READY on :8081 — {len(TOOLS)} tools available to the 2B model", flush=True)
ThreadingHTTPServer(("127.0.0.1", 8081), H).serve_forever()
