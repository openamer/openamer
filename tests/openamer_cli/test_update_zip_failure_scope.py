"""ZIP fallback must not turn dependency/stash failures into source replacement."""
import ast
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("cmd,stderr,eligible", [
    (["uv", "pip", "install", "-e", "."], "Permission denied", False),
    (["git", "stash", "push", "--include-untracked"], "Filename too long", False),
    (["git", "status", "--porcelain"], "Invalid argument", False),
    (["git", "merge", "--ff-only", "origin/main"], "local changes would be overwritten", False),
    (["git", "fetch", "origin", "main"], "fatal: unable to access repository: Authentication failed", False),
    (["git", "fetch", "origin", "main"], "fatal: unable to access repository: The requested URL returned error: 403", False),
    (["git", "fetch", "origin", "main"], "Could not resolve host", True),
    (["git", "-c", "windows.appendAtomically=false", "pull", "origin", "main"], "unable to create file: Invalid argument", True),
])
def test_outer_update_handler_limits_zip_fallback(cmd, stderr, eligible):
    # Exercise the real outer error handler without launching the updater's
    # preflight, network, dependency installation, or service restarts.
    source = Path(__file__).parents[2] / "openamer_cli" / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_cmd_update_impl")
    handler = next(n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)
                   and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                           and call.func.id == "_update_via_zip" for call in ast.walk(n)))
    error = subprocess.CalledProcessError(1, cmd, stderr=stderr)
    probe = ast.Try(body=[ast.Raise(exc=ast.Name(id="error", ctx=ast.Load()))],
                    handlers=[handler], orelse=[], finalbody=[])
    module = ast.fix_missing_locations(ast.Module(body=[probe], type_ignores=[]))
    from openamer_cli import main
    namespace = dict(vars(main))
    fallback = Mock()
    namespace.update(error=error, sys=SimpleNamespace(platform="win32", exit=lambda code: (_ for _ in ()).throw(SystemExit(code))),
                     args=SimpleNamespace(), _update_via_zip=fallback)
    try:
        exec(compile(module, str(source), "exec"), namespace)
    except SystemExit as exc:
        assert exc.code == 1
    assert fallback.called is eligible
