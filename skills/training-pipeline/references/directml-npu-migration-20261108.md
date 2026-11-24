# DirectML/NPU Migration for Mini-OpenAmer (2026-11-08)

## Summary

Migrated Mini-OpenAmer 2B backend from llama.cpp (CPU, ~28-30 tok/s) to DirectML server (NPU/Radeon 860M) for hardware-accelerated inference.

## Changes in `scripts/training/gguf_backend.py`

**Added constants:**
```python
DIRECTML_SERVER = os.environ.get("DIRECTML_SERVER", r"C:\\Users\\damir\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe")
DIRECTML_SCRIPT = os.environ.get("DIRECTML_SCRIPT", r"C:\\Users\\damir\\directml_server.py")
```

**Replaced `_start()` function** - now spawns DirectML Python server instead of llama-server.exe:
```python
cmd = [DIRECTML_SERVER, DIRECTML_SCRIPT]
env = {**os.environ, "PYTHONPATH": ""}
_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
```

**Updated `__main__` block** - removed model file check, llama-server command, changed log messages to "DirectML server".

## Verification Results

| Test | Result |
|------|--------|
| `test_tool_server_gguf.py` | ✅ ALL TESTS PASSED (6/6) |
| `gguf_backend.health()` | ✅ `{"status":"ok"}` |
| `gguf_backend.chat()` | ✅ ~28.8 tok/s, Tool-Calls functional |
| DirectML Server (`:18080`) | ✅ Health, Models, Chat all OK |

## Test Updates

Updated `test_tool_server_gguf.py`:
- Health check: `tools` count 9 → 10 (added `group_state`)
- Tools list: added `"group_state"` to expected names

## Key Learnings

1. **DirectML server is a separate Python 3.14 process** - GGUF backend manages it as a subprocess
2. **Clean env critical** - `PYTHONPATH=""` prevents venv pollution
3. **Health contract unchanged** - Both backends expose `/health` → `{"status":"ok"}`
4. **Tool server unchanged** - Still calls `gguf_backend.chat()` identically
5. **NPU model is 4B ONNX** - `amd/Qwen3.5_4B_rai_1.9.0_npu` vs old 2B GGUF

## Related Files

- `scripts/training/gguf_backend.py` (patched)
- `scripts/training/test_tool_server_gguf.py` (patched)
- `C:\Users\damir\directml_server.py` (external NPU server)
- Skill: `laptop-hardware-optimization` (NPU hardware details)