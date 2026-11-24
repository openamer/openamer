# WSL/MSYS Path Conversion for subprocess.run

When calling `subprocess.run(["bash", path, ...])` from Python on Windows,
MSYS converts `C:\Users\...` to `C:Users...` (stripping backslashes and colon).

## The Fix

Keep BOTH a Windows Path (for Python-side `exists()` checks) and a POSIX string
(for bash-side `subprocess.run` calls):

```python
from pathlib import Path

def _posix(path: Path) -> str:
    """Convert Windows path to POSIX for bash. C:\ → /c/"""
    return str(path).replace("\\", "/").replace("C:", "/c")

REPO = Path(r"C:\Users\damir\openamer-repo")
RUNNER_PATH = REPO / "scripts" / "run_tests.sh"
RUNNER_S = _posix(RUNNER_PATH)  # → "/c/Users/damir/openamer-repo/scripts/run_tests.sh"

# Python-side check uses Windows Path
if RUNNER_PATH.exists():
    ...

# bash-side call uses POSIX string
subprocess.run(["bash", RUNNER_S, target])
```

## Why it happens

MSYS (bash on Windows) interprets `C:\Users` as `C:` followed by escape
`\U`, `\s`, etc. and strips backslashes. The `/c/Users/` prefix is the
only reliable way to pass Windows paths to bash subprocesses.

## Verification

```bash
bash -c 'test -f "/c/Users/damir/openamer-repo/scripts/run_tests.sh" && echo OK'
```