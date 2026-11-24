# MSYS Path Translation Bug on Windows

## Symptom
When running Python from a background terminal (MSYS/git-bash), paths get a doubled drive letter:
```
python.exe: can't open file 'C:\c\Users\damir\...script.py': [Errno 2] No such file or directory
```

The path `C:\c\Users\...` reveals MSYS translated `/c/Users/` → `C:\` then bash appended `c\Users\`.

## Root Cause
MSYS2 automatically converts POSIX paths (`/c/Users/`) to Windows paths (`C:\Users\`) when passing arguments to native Windows executables. But when the path is already a Windows path wrapped in quotes, MSYS still attempts translation, producing a doubled drive letter.

## Fix
Use a `.bat` wrapper file that is invoked via `cmd.exe /c`:

```batch
@echo off
set PYTHON=C:\Users\damir\AppData\Local\openamer-laptop\venv\Scripts\python.exe
set SCRIPT=C:\Users\damir\AppData\Local\openamer-laptop\scripts\training\script.py
"%PYTHON%" "%SCRIPT%"
```

In the agent terminal, invoke with:
```bash
cmd.exe /c "C:\path\to\_runner.bat"
```

Or with `terminal(background=true)`:
```python
terminal(command='cmd.exe /c "C:\\path\\to\\_runner.bat"', background=True, workdir="C:/path/to/workdir")
```

## Prevention
- Always test the first invocation with a foreground terminal before backgrounding.
- When starting a new long-running Python script from git-bash, create a `.bat` wrapper as the first step.
- The batch file's `setlocal` is optional but recommended to avoid env var leaks.