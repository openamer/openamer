"""Profile-scoped loading of shipped script code and runtime overrides.

Why this module exists
----------------------
The ASI wrappers used to import their training scripts as BARE modules
(``importlib.import_module("reasoning_loop")``) after pushing
``$OPENAMER_HOME/scripts/training`` onto ``sys.path``. That works only on a
machine whose profile home happens to carry a runtime copy of the training
tree. On a fresh installation the directory does not exist, so every ASI
capability raised ``ModuleNotFoundError`` -- while the same code sat unused
in the checkout next to the wrapper.

Bare imports have a second, sharper problem: the module name is global. Two
profiles on one machine, or a checkout module and a runtime module with the
same name, share one ``sys.modules`` entry and one ``sys.path`` entry. The
import that answers is then whichever import happened first -- not the one
the caller asked for.

The rules this module implements:

1. Code resolution is profile-scoped: the active profile's runtime copy
   first, then the code shipped beside the running checkout. Never another
   profile, never a guessed sibling directory.
2. Module identity is derived from the canonical home AND the source path,
   so two profiles never share a module object.
3. Legacy scripts that import their siblings by bare name get the same
   resolver, including for imports that happen inside a function body.
4. Scripts see ``OPENAMER_HOME`` pointing at the active profile through a
   LOCAL ``os`` view -- the process environment is never mutated.
5. Only code falls back. No runtime script, model, credential or private
   state is copied into the checkout.

This is compatibility loading, not a security sandbox for untrusted code.
"""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
import os
import sys
import threading
import types
from pathlib import Path

from openamer_constants import get_openamer_home

_CHECKOUT = Path(__file__).resolve().parents[2]
_LOCK = threading.RLock()

#: Sub-trees that hold importable scripts, relative to a home or checkout.
_SCRIPT_DIRS = ("scripts", "scripts/training")


def _candidate_dirs(home: Path, prefer: str | None) -> list[tuple[Path, str]]:
    """Ordered (base, subdir) candidates.

    The active profile's runtime copy wins over the checkout copy for the
    same sub-tree, and the sub-tree the caller asked for wins over the other
    one. Runtime code in ``scripts/`` must not be shadowed by a checkout
    module of the same name in ``scripts/training/`` and vice versa.
    """
    order = [prefer] if prefer else []
    order += [d for d in _SCRIPT_DIRS if d not in order]
    candidates: list[tuple[Path, str]] = []
    for subdir in order:
        candidates.append((home, subdir))
        candidates.append((_CHECKOUT, subdir))
    return candidates


def _resolve_script(name: str, home: Path, prefer: str | None) -> tuple[Path, str]:
    if not name.isidentifier():
        raise ValueError(f"Invalid script module name: {name!r}")
    checked: list[str] = []
    for base, subdir in _candidate_dirs(home, prefer):
        candidate = base / subdir / f"{name}.py"
        checked.append(str(candidate))
        if candidate.is_file():
            return candidate.resolve(), subdir
    raise ModuleNotFoundError(
        f"OpenAmer script module {name!r} not found; checked: " + ", ".join(checked),
        name=name,
    )


def training_script(name: str, *, home: Path | None = None) -> Path:
    """Resolve a training script (``scripts/training/<name>.py``).

    The profile's runtime copy wins; the checkout copy is the fallback so a
    fresh installation can use the code that ships with it.
    """
    home = Path(home) if home is not None else get_openamer_home()
    return _resolve_script(name, home, "scripts/training")[0]


def script_script(name: str, *, home: Path | None = None) -> Path:
    """Resolve a helper script (``scripts/<name>.py``)."""
    home = Path(home) if home is not None else get_openamer_home()
    return _resolve_script(name, home, "scripts")[0]


def _rebind_profile_stores(module, name: str, home: Path) -> None:
    """Point a legacy script's stores at the profile that loaded it.

    The legacy scripts resolve their own home at import time and fall back to
    the machine's default install when ``OPENAMER_HOME`` does not look like an
    install root. That fallback is right for a standalone run and wrong for a
    profile-scoped load: the caller asked for THIS profile.
    """
    if name == "world_model":
        module._HOME = home
        module.WM = str(home / "memory" / "world_model.jsonl")
    elif name == "self_improve":
        module.T = str(home / "scripts" / "training")
        module.LOG = str(Path(module.T) / "improvements.jsonl")
        module.SANDBOX = str(Path(module.T) / "sandbox")
    elif name == "darwin_engine" and hasattr(module, "SKILLS_DIR"):
        module.HOME = home
        module.SKILLS_DIR = home / "skills"
    elif name == "darwin_publish" and hasattr(module, "SKILLS_DIR"):
        module.SKILLS_DIR = home / "skills"


def _load_module(name: str, home: Path, prefer: str | None):
    source, subdir = _resolve_script(name, home, prefer)
    key = hashlib.sha256(f"{home}\0{source}".encode()).hexdigest()
    qualified = f"_openamer_script_{key}_{name}"
    with _LOCK:
        if qualified in sys.modules:
            return sys.modules[qualified]
        spec = importlib.util.spec_from_file_location(qualified, source)
        module = importlib.util.module_from_spec(spec)
        # Legacy scripts read OPENAMER_HOME themselves, including inside lazy
        # functions. Give them a local os view, not a process-wide mutation.
        scoped_os = types.ModuleType("os")
        scoped_os.__dict__.update(os.__dict__)
        scoped_os.environ = dict(os.environ, OPENAMER_HOME=str(home))

        # os.getenv reads the REAL process environment through its own
        # global reference, so copying the function unchanged would leak the
        # process home into the script. Bind it to the scoped view instead.
        def scoped_getenv(key, default=None):
            return scoped_os.environ.get(key, default)

        scoped_os.getenv = scoped_getenv

        def scoped_import(target, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and target == "os":
                return scoped_os
            if level == 0 and target.isidentifier():
                # A bare sibling import resolves through the SAME resolver:
                # same profile, same source tree, never a public wrapper and
                # never a module cached for another home.
                try:
                    _resolve_script(target, home, subdir)
                except ModuleNotFoundError:
                    pass
                else:
                    return _load_module(target, home, subdir)
            return builtins.__import__(target, globals, locals, fromlist, level)

        module.__dict__["__builtins__"] = dict(vars(builtins), __import__=scoped_import)
        sys.modules[qualified] = module
        old_path = sys.path[:]
        try:
            spec.loader.exec_module(module)
            # These legacy resolvers deliberately reject empty homes or
            # search a laptop install. Their stores must stay in the profile
            # this load belongs to -- otherwise a load for profile A writes
            # into profile B's (or the default install's) data.
            _rebind_profile_stores(module, name, home)
            # After execution the module reports its plain script name to
            # callers that inspect it, while sys.modules keys it by
            # home+source so two profiles never share one object.
            module.__name__ = name
        except Exception as exc:
            sys.modules.pop(qualified, None)
            if isinstance(exc, ImportError):
                raise ImportError(
                    f"OpenAmer script module {name!r} from {source}: {exc}"
                ) from exc
            raise
        finally:
            # Some legacy scripts prepend laptop-specific paths on import.
            sys.path[:] = old_path
        return module


def load_training_module(name: str, *, home: Path | None = None):
    """Load a training script under a private, home-and-source-specific name."""
    home = (Path(home) if home is not None else get_openamer_home()).resolve()
    return _load_module(name, home, "scripts/training")


def load_script_module(name: str, *, home: Path | None = None):
    """Load a helper script under a private, home-and-source-specific name."""
    home = (Path(home) if home is not None else get_openamer_home()).resolve()
    return _load_module(name, home, "scripts")
