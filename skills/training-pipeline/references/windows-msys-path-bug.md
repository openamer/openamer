# Windows MSYS Path Translation Bug

## The Problem

When running Python scripts from OpenAmer's `terminal` tool (which uses MSYS
git-bash), absolute paths passed to `python.exe` get double-translated:

```
Input:  /c/Users/damir/AppData/Local/.../script.py
MSYS translates: C:\c\Users\damir\AppData\Local\...\script.py
Result: "can't open file 'C:\\c\\Users\\...' — No such file or directory"
```

This happens because MSYS bash transparently translates POSIX paths (`/c/`)
to Windows paths (`C:\`), but a path that *starts* as Windows (e.g. in
quotes) gets the translation *applied again* on top.

## The Fix: Batch Wrappers

Create a `.bat` file alongside each Python script that invokes it:

```batch
@echo off
setlocal
set PYTHON=C:\Users\damir\AppData\Local\openamer-laptop\venv\Scripts\python.exe
set SCRIPT=C:\Users\damir\AppData\Local\openamer-laptop\scripts\training\script.py
"%PYTHON%" "%SCRIPT%"
```

Then invoke via:
```bash
cmd.exe /c "C:\path\to\_wrapper.bat"
```

## Batch Wrappers in this repo

| Batch file | Calls |
|---|---|
| `_run_finetune.bat` | `finetune_cpu.py` |
| `_run_merge.bat` | `merge_and_export.py` |
| `_run_gguf.bat` | `convert_to_gguf.py` (deprecated — use llama.cpp converter) |
| `_cron_longterm_index.py` | `longterm_memory.py index` |
| `_cron_memory_heal.py` | `longterm_memory.py heal` |

## Venv Context

The `terminal` tool runs with `python` from PATH, which points to
`openamer-agent/venv` — NOT `openamer-laptop/venv` where training deps
(torch, transformers, peft, gguf, sentencepiece) are installed.

Always use the *absolute path* to the correct venv when running training scripts:
```
C:\Users\damir\AppData\Local\openamer-laptop\venv\Scripts\python.exe
```