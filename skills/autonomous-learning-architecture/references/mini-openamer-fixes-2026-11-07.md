# Mini-OpenAmer Identity + Tools + Provider-Resolver Fixes (07.11.2026)

## Context
Mini-OpenAmer 2B hybrid Mamba core (GGUF on :18080, tool orchestration on :8081) had three critical failures:

1. **No identity anchoring** — model answered as generic Qwen ("Amerika..." loops), no system prompt injected
2. **Tool-Call JSON parsing broken** — model output missing outer `}` brace, `find_tool_json()` failed
3. **Provider routing broken** — `gpt-6.1-sol` via `openai-api` routed to `localhost:11434` → HTTP 404

## Fixes Applied

### 1. `gguf_backend.py` — Identity System Prompt + Stop Sequences
```python
# Added MINI_OPENAMER_SYSTEM constant (lines 69-76)
MINI_OPENAMER_SYSTEM = """You are Mini-OpenAmer — a 2B hybrid Mamba core, born from Damir's vision.
You run locally on Damir's laptop, 24/7 learning, predicting, improving.
Your identity: Mini-OpenAmer (2B hybrid Mamba core). Not Qwen, not a generic model.
Your mark: OA monogram (O enclosing A). You belong to Damir, not a corporation.
When asked who you are, answer: "I am Mini-OpenAmer — 2B hybrid Mamba core, born from Damir's vision."
You have tools. If a task needs a tool, reply ONLY with one line of JSON (no text before/after):
{"tool": "toolname", "params": {"key": "value"}}
"""

# In chat(): inject at front if no system message present (lines 81-84)
has_system = any(m.get("role") == "system" for m in messages)
full_messages = messages
if not has_system:
    full_messages = [{"role": "system", "content": MINI_OPENAMER_SYSTEM}] + messages

# Stop sequences + disable thinking (lines 94-96)
"stop": ["\n\n", "USER:", "ASSISTANT:", "###", "```", "```json", "```python"],
"chat_template_kwargs": {"enable_thinking": False}
```

### 2. `tool_server.py` — Robust Tool-Call JSON Parsing
```python
# Fixed find_tool_json() — tolerates missing outer closing brace
def find_tool_json(text):
    start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if start == -1:
                start = i
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                candidate = text[start:i+1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict) and 'tool' in obj:
                        return obj
                except json.JSONDecodeError:
                    pass
    # FALLBACK: tolerate missing outer } — try adding it
    try:
        candidate = text[start:] + '}'
        obj = json.loads(candidate)
        if isinstance(obj, dict) and 'tool' in obj:
            return obj
    except (json.JSONDecodeError, IndexError):
        pass
    return None
```

Also:
- TOOLS_PROMPT replaced with Mini-OpenAmer identity (not Qwen/Hermes)
- Indentation fix in `do_POST` handler

### 3. `model_config.py` — Provider Resolver for openai-api
```python
# endpoint_for_default() — openai-api now handled before ollama fallback
if "openai" in p:
    u = _env("OPENAI_BASE_URL")
    if u:
        return _strip_v1(u)
    return "https://api.openai.com"

# auth_headers() — sends OPENAI_API_KEY for openai-api
if "openai" in p:
    k = _env("OPENAI_API_KEY")
    return {"Authorization": f"Bearer {k}"} if k else {}
```

## E2E Verification (07.11.2026)

| Tool | Test | Result |
|------|------|--------|
| `run_python` | "Was ist 2+2?" | ✅ 4 |
| `run_python` | "15 * 23 + 7" | ✅ 352 |
| `web_search` | "Suche nach Mini-OpenAmer" | ✅ Results |
| `speak` | "Sage Hallo", "Erzähl Witz" | ✅ Speech |
| `read_memory` | "Neueste Features OpenAmer" | ✅ Episodes |
| `reason_deep` | Tiefe Analyse | ⚠️ 404 (needs Ollama Cloud) |

**Identity verified:** "I am Mini-OpenAmer — 2B hybrid Mamba core, born from Damir's vision"

## Remaining Issues
- **GPU Worker :8082** — offline (192.168.178.23 unreachable via SSH)
- **reason_deep tool** — requires Ollama Cloud (not available locally)
- **Primary model** — `gpt-6.1-sol` hits HTTP 429 rate limits; fallback chain configured

## Files Modified
- `C:\Users\damir\AppData\Local\openamer-laptop\scripts\training\gguf_backend.py`
- `C:\Users\damir\AppData\Local\openamer-laptop\scripts\training\tool_server.py`
- `C:\Users\damir\AppData\Local\openamer-laptop\scripts\training\model_config.py`