"""Dependency-light venv diagnosis and recovery that runs BEFORE openamer_cli.main's imports.

The ``openamer`` console entry point is ``openamer_cli.main:main``.  Importing
``openamer_cli.main`` pulls in third-party packages at module level (``dotenv``
via ``openamer_cli.env_loader``, ``yaml`` via ``openamer_cli.config``, ...).  In
the exact failure state the update-recovery markers exist for — a failed lazy
backend refresh or interrupted core install that wiped a core package's
import files (#57828) — a normal launch crashes *while importing main.py*,
before ``_recover_from_interrupted_install()`` can run.  The marker system is
unreachable precisely when it is needed most.

This module is deliberately **stdlib-only** so importing it can never fail on
a corrupted venv.  ``openamer_cli.main`` imports and calls
:func:`recover_if_needed` at the very top of its module body, before any
third-party import, and calls :func:`maybe_run_early_command` right after
profile resolution so the explicit ``openamer doctor --runtime`` path stays
reachable even when those imports fail.

Two entry modes:

- **automatic** (:func:`recover_if_needed`, called on every launch): acts only
  when an update-recovery marker exists AND an import probe confirms a core
  package is broken.  Bounded to :data:`EARLY_REPAIR_MAX_ATTEMPTS` attempts per
  marker so an offline machine cannot reinstall forever on every launch.
- **explicit** (:func:`repair_runtime`, reached from ``openamer doctor
  --runtime`` or ``python -m openamer_cli._early_recovery``): always reports
  interpreter / profile / lock provenance and the probe table, and repairs on
  ``--fix``.  No marker required.

Scope: this early pass only repairs enough for ``openamer_cli.main`` to become
importable again (force-reinstall of the known-fragile core packages, using
the pins from pyproject.toml).  It NEVER clears the recovery markers — the
full, confirmed marker lifecycle stays with ``_recover_from_interrupted_install()``
in main.py, which runs right after import succeeds.

The explicit-command shape follows the pattern in NousResearch/hermes-agent
(``pm/cli.py::cmd_repair`` → ``hermes_cli._early_recovery.recover_if_needed(...,
explicit=True)``, MIT).  The implementation below is OpenAmer's own: it reuses
the existing probe/repair tables and the existing pip/venv install path rather
than importing a package manager.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import subprocess
import sys
import time
from pathlib import Path

# Core packages a failed lazy ``uv pip install`` is known to leave with intact
# distribution metadata but wiped import files (#57828).  ``module`` is what we
# probe via a real import; ``attr`` guards against an empty/stub module.
# main.py's marker-recovery path reuses these tables — keep them here (the
# dependency-light module) so both layers probe and repair the same set.
LAZY_REFRESH_IMPORT_PROBES: tuple[tuple[str, str], ...] = (
    ("yaml", "SafeDumper"),
    ("dotenv", "load_dotenv"),
    ("click", "Command"),
    ("certifi", "contents"),
    ("rich", "print"),
    ("cryptography", "__version__"),
    ("jwt", "encode"),
)

LAZY_REFRESH_REPAIR_PACKAGES: dict[str, str] = {
    "yaml": "PyYAML",
    "dotenv": "python-dotenv",
    "click": "click",
    "certifi": "certifi",
    "rich": "rich",
    "cryptography": "cryptography",
    "jwt": "PyJWT",
}

# An automatic repair that failed is retried on the next launch, but only this
# many times per marker.  Otherwise an unreachable package index turns every
# single ``openamer`` launch into a multi-minute failed reinstall (#57828
# left users in exactly that loop).  The explicit command is not bounded.
EARLY_REPAIR_MAX_ATTEMPTS = 3

# The explicit, always-reachable form of this module's repair.
REPAIR_COMMAND = "openamer doctor --runtime --fix"
DIAGNOSE_COMMAND = "openamer doctor --runtime"

# Marker files written by ``openamer update`` (see main.py::_write_marker_file).
_MARKER_NAMES = (".update-incomplete", ".lazy-refresh-incomplete")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Dependency-spec provenance (pyproject pins + uv.lock)
# ---------------------------------------------------------------------------

def _pinned_specs(packages: list[str], project_root: Path) -> list[str]:
    """Map bare package names to their pinned specs from pyproject.toml.

    Stdlib-only (tomllib + naive requirement-head parsing — ``packaging`` may
    itself be broken in the failure state this module exists for).  Unknown
    packages fall back to their bare name.
    """
    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file():
        return packages
    try:
        import tomllib

        with open(pyproject, "rb") as f:
            raw_deps = tomllib.load(f).get("project", {}).get("dependencies", []) or []
    except Exception:
        return packages

    name_to_spec: dict[str, str] = {}
    for spec in raw_deps:
        head = spec.split(";", 1)[0].strip()
        bare = head
        for op in ("==", ">=", "<=", "~=", ">", "<", "!="):
            if op in bare:
                bare = bare.split(op, 1)[0]
                break
        key = bare.strip().split("[", 1)[0].strip().lower()
        if key:
            name_to_spec[key] = head
    return [name_to_spec.get(pkg.lower(), pkg) for pkg in packages]


def _normalize_dist(name: str) -> str:
    """PEP 503-ish key so pyproject/uv.lock/importlib.metadata names compare."""
    return name.strip().split("[", 1)[0].strip().lower().replace("_", "-").replace(".", "-")


def _lock_version_map(project_root: Path) -> dict[str, str]:
    """``{normalized distribution name: locked version}`` from ``uv.lock``.

    Empty when there is no lock file (managed/Docker/PyPI installs) or it is
    unreadable — the report says so rather than pretending health was checked
    against a lock that does not exist.
    """
    lock = project_root / "uv.lock"
    if not lock.is_file():
        return {}
    try:
        import tomllib

        with open(lock, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {}
    versions: dict[str, str] = {}
    for entry in data.get("package", []) or []:
        if not isinstance(entry, dict):
            continue
        name, version = entry.get("name"), entry.get("version")
        if name and version:
            versions[_normalize_dist(str(name))] = str(version)
    return versions


def _file_provenance(path: Path) -> dict:
    """Path + short sha256 + mtime for a dependency-spec file.  Never raises."""
    info: dict = {"path": str(path), "present": path.is_file(), "sha256": "", "mtime": 0.0}
    if not info["present"]:
        return info
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        info["sha256"] = digest.hexdigest()[:12]
        info["mtime"] = path.stat().st_mtime
    except OSError as exc:
        info["error"] = str(exc)
    return info


# ---------------------------------------------------------------------------
# Import probes
# ---------------------------------------------------------------------------

def _certifi_bundle_broken() -> bool:
    """True when certifi imports but its ``cacert.pem`` is missing/corrupt.

    A brew Python upgrade or an interrupted venv rebuild can leave certifi's
    distribution metadata (and even the module) intact while the bundled
    ``cacert.pem`` is gone or a dangling symlink — every TLS connection then
    fails with an opaque ``Could not find a suitable TLS CA certificate
    bundle`` from deep inside httpx/requests (#29866). An attribute probe
    alone passes in that state, so validate the bundle path itself.
    """
    try:
        import certifi

        bundle = Path(certifi.where())
        # <1 KiB cannot hold a single PEM certificate — treat as corrupt.
        return not bundle.is_file() or bundle.stat().st_size < 1024
    except Exception:
        # Import failure is caught by the regular probe table; a failure to
        # even stat is treated as broken.
        return True


def _installed_version(dist_name: str) -> str:
    """Installed distribution version, or "" when metadata is unreadable.

    ``importlib.metadata`` is imported here, not at module scope: this module
    must stay importable under a guard that blocks every non-stdlib top-level
    import, and the metadata package pulls in submodules at import time.
    """
    try:
        from importlib import metadata

        return metadata.version(dist_name)
    except Exception:
        return ""


def _probe_details() -> list[dict]:
    """Import-probe every fragile core package in THIS process, with detail.

    Returns one row per probe: ``module``, ``package`` (repair distribution
    name), ``ok``, ``detail`` (error text when not ok) and ``installed``
    version.  Failed imports leave nothing in ``sys.modules``, so a post-repair
    retry in the same process works.
    """
    rows: list[dict] = []
    for mod_name, attr in LAZY_REFRESH_IMPORT_PROBES:
        package = LAZY_REFRESH_REPAIR_PACKAGES.get(mod_name, mod_name)
        row = {"module": mod_name, "package": package, "ok": True, "detail": "", "installed": ""}
        try:
            mod = importlib.import_module(mod_name)
            if not hasattr(mod, attr):
                raise ImportError(f"{mod_name} missing {attr}")
            if mod_name == "certifi" and _certifi_bundle_broken():
                raise ImportError("certifi cacert.pem missing or corrupt")
        except Exception as exc:
            row["ok"] = False
            row["detail"] = f"{type(exc).__name__}: {exc}"
        row["installed"] = _installed_version(package)
        rows.append(row)
    return rows


def _probe_broken_packages() -> list[str]:
    """Repair package names (deduped, probe order) for probes that failed."""
    return [row["package"] for row in _probe_details() if not row["ok"]]


def _probe_modules_for(packages: list[str]) -> list[str]:
    """Module names whose repair package is in ``packages``."""
    wanted = {_normalize_dist(pkg) for pkg in packages}
    return [
        module
        for module, pkg in LAZY_REFRESH_REPAIR_PACKAGES.items()
        if _normalize_dist(pkg) in wanted
    ]


def _reset_probe_modules(modules: list[str]) -> None:
    """Drop probe modules from ``sys.modules`` so the next probe hits disk.

    A wiped ``__init__.py`` does not always fail to import: with only the
    top-level module gone, ``import yaml`` succeeds as an empty *namespace*
    package and is cached.  Reinstalling afterwards then leaves the stale
    namespace module in ``sys.modules``, so a same-process re-probe keeps
    reporting the package as broken even though the install is fixed.  Drop
    only the modules we are about to re-probe — never the whole cache.
    """
    for name in modules:
        for key in [k for k in list(sys.modules) if k == name or k.startswith(name + ".")]:
            sys.modules.pop(key, None)
    try:
        importlib.invalidate_caches()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Runtime report — what exactly is being diagnosed
# ---------------------------------------------------------------------------

def _venv_python_candidates(project_root: Path) -> list[Path]:
    return [
        project_root / "venv" / "Scripts" / "python.exe",
        project_root / "venv" / "bin" / "python",
        project_root / ".venv" / "Scripts" / "python.exe",
        project_root / ".venv" / "bin" / "python",
    ]


def _display_path(raw: str | os.PathLike[str] | None) -> str:
    """Collapse the user's home directory to ``~`` for readable output."""
    if raw in (None, ""):
        return ""
    text = str(raw)
    try:
        home = str(Path.home())
    except Exception:
        return text
    return "~" + text[len(home):] if home and text.startswith(home) else text


def collect_runtime_report(project_root: Path | None = None) -> dict:
    """Diagnose the interpreter, profile, dependency spec and core imports.

    Imports only the individual probe modules — never ``openamer_cli.main`` —
    so it works in the failure state that makes the CLI unimportable.
    """
    root = _project_root() if project_root is None else Path(project_root)

    project_venvs = [p for p in _venv_python_candidates(root) if p.is_file()]
    try:
        executable = sys.executable
        executable_resolved = Path(executable).resolve()
    except Exception:
        executable, executable_resolved = sys.executable, None
    matching_venv = ""
    for candidate in project_venvs:
        try:
            if executable_resolved is not None and candidate.resolve() == executable_resolved:
                matching_venv = str(candidate)
                break
        except OSError:
            continue

    home_env = os.environ.get("OPENAMER_HOME", "")
    profile_home = home_env or str(Path.home() / ".openamer")
    config = Path(profile_home) / "config.yaml"

    lock_versions = _lock_version_map(root)
    probes = _probe_details()
    for row in probes:
        locked = lock_versions.get(_normalize_dist(row["package"]), "")
        row["locked"] = locked
        row["drift"] = bool(locked and row["installed"] and locked != row["installed"])

    broken = [row["package"] for row in probes if not row["ok"]]
    drifted = [row["package"] for row in probes if row["ok"] and row["drift"]]
    return {
        "interpreter": {
            "executable": executable,
            "version": sys.version.split()[0],
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
            "in_venv": sys.prefix != sys.base_prefix,
            "project_venv": matching_venv,
            "project_venvs_found": [str(p) for p in project_venvs],
        },
        "profile": {
            "openamer_home": profile_home,
            "openamer_home_source": "OPENAMER_HOME" if home_env else "default",
            "config_path": str(config),
            "config_exists": config.is_file(),
        },
        "project": {
            "root": str(root),
            "pyproject": _file_provenance(root / "pyproject.toml"),
        },
        "lock": {
            "file": _file_provenance(root / "uv.lock"),
            "packages": len(lock_versions),
        },
        "probes": probes,
        "broken": broken,
        "drifted": drifted,
        "healthy": not broken,
    }


def _age(timestamp: float) -> str:
    if not timestamp:
        return "unknown"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))
    except Exception:
        return "unknown"


def format_runtime_report(report: dict) -> str:
    """Render :func:`collect_runtime_report` as plain text (no colour, no TTY need)."""
    interp = report["interpreter"]
    profile = report["profile"]
    project = report["project"]
    lock = report["lock"]
    lines: list[str] = []

    lines.append("OpenAmer runtime diagnosis")
    lines.append(f"  interpreter  {interp['executable']}  (Python {interp['version']})")
    lines.append(f"  venv         {_display_path(interp['prefix'])}"
                 f"{'' if interp['in_venv'] else '  [not a virtualenv]'}")
    if interp["project_venv"]:
        lines.append(f"  install venv {_display_path(interp['project_venv'])}  [running interpreter]")
    elif interp["project_venvs_found"]:
        lines.append(
            "  install venv "
            + _display_path(interp["project_venvs_found"][0])
            + "  [exists, NOT the running interpreter]"
        )
    else:
        lines.append("  install venv (none found next to the source tree)")
    lines.append(
        f"  profile      {_display_path(profile['openamer_home'])}"
        f"  ({profile['openamer_home_source']})"
        f"{'' if profile['config_exists'] else '  [no config.yaml]'}"
    )
    lines.append(f"  install      {_display_path(project['root'])}")
    lines.append(
        f"  repair into  {_display_path(interp['prefix'])}"
        "  [this interpreter's environment — no other venv or profile is touched]"
    )

    pyproject = project["pyproject"]
    lines.append(
        f"  pins         pyproject.toml"
        f"{'' if pyproject['present'] else ' [missing]'}"
        f"{' sha256:' + pyproject['sha256'] if pyproject['sha256'] else ''}"
        f"  {_age(pyproject['mtime'])}"
    )
    lock_file = lock["file"]
    if lock_file["present"]:
        lines.append(
            f"  lock         uv.lock sha256:{lock_file['sha256']}"
            f"  {_age(lock_file['mtime'])}  ({lock['packages']} packages)"
        )
    else:
        lines.append("  lock         uv.lock [MISSING — version drift cannot be checked]")

    lines.append("")
    lines.append("Core packages (real import probes):")
    for row in report["probes"]:
        status = "OK" if row["ok"] else "BROKEN"
        name = f"{row['module']:<12}"
        if row["ok"]:
            version = row["installed"] or "version unknown"
            if row["drift"]:
                note = f"installed {row['installed']}, locked {row['locked']} — venv out of date with uv.lock"
            else:
                note = f"{row['package']} {version}"
            lines.append(f"  {status:<6} {name} {note}")
        else:
            lines.append(f"  {status:<6} {name} {row['package']}: {row['detail']}")

    lines.append("")
    if report["healthy"]:
        lines.append("  All core imports resolve.")
        if report["drifted"]:
            lines.append(
                "  Installed versions differ from uv.lock for: "
                + ", ".join(report["drifted"])
                + " — run `openamer update` to reinstall the locked set."
            )
    else:
        lines.append(
            f"  {len(report['broken'])} of {len(report['probes'])} core packages do not import: "
            + ", ".join(report["broken"])
        )
        lines.append(f"  Repair: {REPAIR_COMMAND}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

def _run_repair_install(specs: list[str], project_root: Path) -> bool:
    """ensurepip + ``pip install --force-reinstall`` the given specs.

    Streams nothing to stdout (``openamer acp`` speaks JSON-RPC on stdout);
    output is captured and replayed to stderr only on failure.  Never raises.

    The install targets ``sys.executable`` — the interpreter this diagnosis
    runs in, which is the one whose imports were probed.  No other venv,
    profile or install is touched.
    """
    try:
        subprocess.run(
            [sys.executable, "-m", "ensurepip", "--upgrade", "--default-pip"],
            cwd=project_root,
            capture_output=True,
        )
    except Exception:
        pass
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--force-reinstall", *specs],
            cwd=project_root,
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        )
    except Exception as exc:
        print(f"  ✗ Early venv repair could not run pip: {exc}", file=sys.stderr)
        return False
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "")[-2000:]
        if tail:
            print(tail, file=sys.stderr)
        return False
    return True


def _read_attempts(marker: Path) -> int:
    """Failed automatic repair attempts recorded in a marker (``attempts=N``)."""
    try:
        for line in marker.read_text(encoding="utf-8", errors="replace").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "attempts":
                return int(value.strip() or 0)
    except (OSError, ValueError):
        pass
    return 0


def _record_attempt(marker: Path) -> None:
    """Increment the ``attempts=`` line, preserving main.py's other lines."""
    try:
        attempts = _read_attempts(marker) + 1
        kept = [
            line
            for line in marker.read_text(encoding="utf-8", errors="replace").splitlines()
            if not line.strip().startswith("attempts=")
        ]
        kept.append(f"attempts={attempts}")
        marker.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
    except OSError:
        pass


def _repair_once(root: Path, broken: list[str], *, explicit: bool) -> bool:
    """Force-reinstall ``broken`` under the shared recovery lock; re-probe.

    Returns True only when the post-install probe is clean.  On failure the pip
    output tail has already been replayed to stderr (that is where an offline /
    proxy / index error becomes visible instead of being smoothed over), the
    attempt is counted, and the manual command is printed.
    """
    lock_path = root / ".update-incomplete.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{os.getpid()}\n".encode())
        os.close(fd)
    except FileExistsError:
        try:
            stale = time.time() - lock_path.stat().st_mtime > 3600
        except OSError:
            stale = False
        if stale:
            try:
                lock_path.unlink()
            except OSError:
                pass
        else:
            if explicit:
                print(
                    "  ✗ Another OpenAmer process is installing into this venv "
                    f"(lock: {lock_path}). Retry when it finishes.",
                    file=sys.stderr,
                )
            return False
    except OSError:
        pass  # read-only fs / perms — proceed unlocked, install surfaces it
    try:
        specs = _pinned_specs(broken, root)
        print(
            f"  → Reinstalling {', '.join(broken)} into {sys.executable} ...",
            file=sys.stderr,
        )
        installed = _run_repair_install(specs, root)
        # Re-probe from disk: a wiped ``__init__.py`` can leave a cached
        # namespace package behind that makes a healthy install look broken.
        _reset_probe_modules(_probe_modules_for(broken))
        if installed and not _probe_broken_packages():
            print("  ✓ Core packages repaired.", file=sys.stderr)
            return True
        if not explicit:
            for name in _MARKER_NAMES:
                marker = root / name
                if marker.is_file():
                    _record_attempt(marker)
        still_broken = _probe_broken_packages()
        print("  ✗ Repair did not restore every core import.", file=sys.stderr)
        if still_broken:
            print(f"    still broken: {', '.join(still_broken)}", file=sys.stderr)
        print("    Manual command (same interpreter, same pins):", file=sys.stderr)
        print(
            f"    {sys.executable} -m pip install --force-reinstall " + " ".join(specs),
            file=sys.stderr,
        )
        print(
            "    If the output above is a network / proxy / index error, the "
            "package index was unreachable; fix that and re-run.",
            file=sys.stderr,
        )
        if not explicit:
            print(f"    Or run the explicit repair: {REPAIR_COMMAND}", file=sys.stderr)
        return False
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass


def recover_if_needed(
    project_root: Path | None = None,
    argv: list[str] | None = None,
    *,
    explicit: bool = False,
) -> bool:
    """Repair wiped core packages so ``openamer_cli.main`` can import at all.

    Fast path (auto mode, no marker present) is two ``lstat`` calls.  Automatic
    mode only acts when a recovery marker from a prior ``openamer update``
    exists AND an import probe confirms a core package is actually broken, and
    gives up after :data:`EARLY_REPAIR_MAX_ATTEMPTS` failed attempts for the
    same marker so an offline machine cannot reinstall on every launch.

    ``explicit=True`` (the user-invoked repair) ignores markers and the attempt
    budget: the user asked for a diagnosis, so it repairs whatever the probes
    report broken.  Markers are deliberately NOT cleared in either mode —
    ``_recover_from_interrupted_install()`` in main.py owns the confirmed marker
    lifecycle and runs immediately after import succeeds.

    Returns True when the core imports were clean at the end of the call.
    Never raises.
    """
    try:
        args = sys.argv[1:] if argv is None else argv
        # Same deliberately-loose match as main(): the real update flow writes
        # and clears its own markers — a recovery install must not race it.
        if not explicit and "update" in args:
            return False
        root = _project_root() if project_root is None else Path(project_root)
        # Managed/Docker/PyPI installs have no source tree here — the marker
        # is not ours to act on; main.py's recovery clears it.
        if not (root / "pyproject.toml").is_file():
            return False

        markers = [root / name for name in _MARKER_NAMES]
        present_markers = [m for m in markers if m.is_file()]
        if not present_markers and not explicit:
            return False

        broken = _probe_broken_packages()
        if not broken:
            # Imports are fine — main.py will load and run full recovery.
            return True

        if not explicit:
            exhausted = [m for m in present_markers if _read_attempts(m) >= EARLY_REPAIR_MAX_ATTEMPTS]
            if exhausted:
                print(
                    "⚠ Automatic dependency repair already failed "
                    f"{EARLY_REPAIR_MAX_ATTEMPTS} times — not retrying. Fix the "
                    f"underlying error, then run: {REPAIR_COMMAND}",
                    file=sys.stderr,
                )
                return False

        print(
            "⚠ Core package(s) do not import — repairing before launch: "
            f"{', '.join(broken)}",
            file=sys.stderr,
        )
        return _repair_once(root, broken, explicit=explicit)
    except Exception:
        # Never block launch — the import of main.py will surface the truth.
        return False


# ---------------------------------------------------------------------------
# Explicit entry points
# ---------------------------------------------------------------------------

def repair_runtime(project_root: Path | None = None, *, should_fix: bool = False) -> int:
    """Print the runtime report and, with ``should_fix``, repair what is broken.

    Exit codes: 0 = healthy (after repair, if one ran), 1 = still broken or
    repair refused/failed, 2 = nothing to diagnose here (no source checkout).
    """
    root = _project_root() if project_root is None else Path(project_root)
    if not (root / "pyproject.toml").is_file():
        print(
            f"openamer runtime: no source checkout at {root} — this diagnosis "
            "covers source-tree installs only.",
            file=sys.stderr,
        )
        return 2

    report = collect_runtime_report(root)
    print(format_runtime_report(report))
    if report["healthy"]:
        return 0
    if not should_fix:
        print()
        print(f"  Nothing was changed. Repair with: {REPAIR_COMMAND}")
        return 1

    print()
    repaired = recover_if_needed(root, argv=[], explicit=True)
    if not repaired:
        print(
            "  ✗ Environment is still unhealthy — see the repair output above.",
            file=sys.stderr,
        )
        return 1
    after = collect_runtime_report(root)
    if not after["healthy"]:
        return 1
    print("  Restart OpenAmer to use the repaired environment.")
    return 0


def maybe_run_early_command(argv: list[str] | None = None) -> int | None:
    """Run ``openamer doctor --runtime`` before the app's imports are attempted.

    ``openamer_cli.main`` calls this immediately after profile resolution and
    before its first third-party import, so the explicit diagnosis/repair still
    works when a broken venv makes ``openamer_cli.config`` / ``env_loader``
    unimportable.  Returns the process exit code when this invocation IS the
    explicit runtime command, else None.
    """
    try:
        args = list(sys.argv[1:] if argv is None else argv)
        if "--runtime" not in args:
            return None
        # ``-p/--profile`` has already been stripped by _apply_profile_override,
        # so the first non-flag token is the subcommand.
        command = next((arg for arg in args if not arg.startswith("-")), None)
        if command != "doctor":
            return None
        return repair_runtime(should_fix="--fix" in args)
    except Exception as exc:  # explicit user command: fail loudly, do not launch
        print(f"openamer runtime: diagnosis failed: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    """``python -m openamer_cli._early_recovery [--fix] [--json]``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m openamer_cli._early_recovery",
        description=(
            "Diagnose (and with --fix repair) the OpenAmer runtime's core "
            "dependency imports. Stdlib-only, so it runs when the CLI itself "
            "cannot be imported."
        ),
    )
    parser.add_argument("--fix", action="store_true", help="force-reinstall broken core packages")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the diagnosis as JSON (ignores --fix)",
    )
    ns = parser.parse_args(argv)
    if ns.json:
        # Imported here, not at module scope: ``json`` is a package whose
        # relative submodule imports trip the stdlib-only import guard this
        # module must keep passing (see _installed_version).
        import json

        print(json.dumps(collect_runtime_report(), indent=2, default=str))
        return 0
    return repair_runtime(should_fix=ns.fix)


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    raise SystemExit(main())
