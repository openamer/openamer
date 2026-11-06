"""Portable agent-plugin packages (Agent Plugins v1) for OpenAmer.

A *portable package* is a directory with a ``plugin.json`` manifest, optional
``skills/<name>/SKILL.md`` bundles and an optional ``mcp.json`` declaring MCP
servers. The format is defined by the Agent Plugins v1 schemas:

* ``https://agent-plugins.org/schemas/1.0.0/plugin.schema.json``
* ``https://agent-plugins.org/schemas/1.0.0/mcp.schema.json``

This module only **reads and records declarations**. It never imports the
package's Python, never executes a declared MCP server and never writes to the
active plugin or skill trees. Installing a package copies it into
``<OPENAMER_HOME>/plugin-packages/<name>/``, a directory the regular plugin
loader does not scan, and records it as *inert*. Only an explicit
``openamer plugins package enable <name>`` lets its MCP declarations reach the
MCP config.

Safety guards (all fail closed):

* every referenced path must resolve inside the package root (no traversal,
  no absolute paths, no symlink escape);
* symlinked entries are never followed or copied;
* secret-shaped files (``.env``, private keys, credential stores) are never
  copied, and a package containing private-key material or a live-looking
  token is refused outright;
* unknown manifest fields are ignored with a diagnostic instead of failing the
  install (forward compatibility), while security-relevant shapes are strict;
* declared remote MCP URLs must be ``https`` (loopback ``http`` allowed) and
  declared stdio commands must be a single executable token or an in-package
  ``./path``.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import urlsplit

PLUGIN_SCHEMA_V1 = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA_V1 = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

#: Directory under ``OPENAMER_HOME`` holding installed portable packages.
PACKAGES_DIRNAME = "plugin-packages"
META_FILENAME = ".openamer-package.json"

PLUGIN_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SKILL_NAME_RE = re.compile(r"^(?!.*--)[a-z0-9]+(?:-[a-z0-9]+)*$")
HEADER_NAME_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
_PLACEHOLDER_RE = re.compile(r"\$\{(PLUGIN_ROOT|PLUGIN_DATA)\}")

_PLUGIN_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
_AUTHOR_FIELDS = {"name", "email", "url"}
_STDIO_FIELDS = {"type", "command", "args", "env", "cwd"}
_REMOTE_FIELDS = {"type", "url", "headers"}

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_PACKAGE_BYTES = 20 * 1024 * 1024
MAX_FILES = 500

#: Filenames that must never be copied out of a package (or into the store).
SECRET_FILE_NAMES = {
    ".env",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "secrets.yaml",
    "secrets.yml",
}
SECRET_FILE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keystore", ".jks")

#: Content markers that make a package unsafe to store at all.
_SECRET_CONTENT = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)

_SKIPPED_DIRS = {".git", "__pycache__", ".mypy_cache", ".pytest_cache", "node_modules"}


class AgentPluginError(ValueError):
    """Fatal portable-package validation failure."""


@dataclass(frozen=True)
class AgentPluginDiagnostic:
    scope: str
    message: str


@dataclass(frozen=True)
class AgentPluginSkill:
    name: str
    description: str
    root: Path
    skill_md: Path
    frontmatter: Mapping[str, Any]


@dataclass(frozen=True)
class AgentPluginPackage:
    name: str
    version: str
    description: str
    root: Path
    manifest: Mapping[str, Any]
    skills: Tuple[AgentPluginSkill, ...] = ()
    mcp_servers: Mapping[str, dict] = field(default_factory=dict)
    diagnostics: Tuple[AgentPluginDiagnostic, ...] = ()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "root": str(self.root),
            "skills": [
                {"name": s.name, "description": s.description, "path": str(s.skill_md)}
                for s in self.skills
            ],
            "mcp_servers": sorted(self.mcp_servers),
            "diagnostics": [
                {"scope": d.scope, "message": d.message} for d in self.diagnostics
            ],
        }


# --- path helpers -----------------------------------------------------------


def packages_root(home: Optional[Path] = None) -> Path:
    """``<OPENAMER_HOME>/plugin-packages`` — profile-scoped, never a plugin dir."""
    if home is None:
        from openamer_constants import get_openamer_home

        home = get_openamer_home()
    return Path(home) / PACKAGES_DIRNAME


def _inside(path: Path, root: Path) -> bool:
    try:
        return path.resolve(strict=False).is_relative_to(root.resolve(strict=True))
    except (OSError, RuntimeError, ValueError):
        return False


def _read_json_object(path: Path, *, label: str) -> dict:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise AgentPluginError(f"{label} exceeds the {MAX_FILE_BYTES} byte limit")
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except AgentPluginError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AgentPluginError(f"{label} is not valid readable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise AgentPluginError(f"{label} must contain a JSON object")
    return value


def _resolve_scoped_path(value: str, root: Path, *, label: str) -> Path:
    """Resolve a package-relative path, rejecting traversal and symlink escapes."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    if "\x00" in value:
        raise ValueError(f"{label} contains a NUL byte")
    candidate = Path(value)
    if candidate.is_absolute() or value.startswith("~"):
        raise ValueError(f"{label} must be relative to the package root")
    resolved = (root / candidate).resolve(strict=False)
    if not resolved.is_relative_to(root.resolve(strict=False)):
        raise ValueError(f"{label} escapes the package root")
    return resolved


def _expand_placeholders(value: str, root: Path) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: str(root), value)


# --- manifest ---------------------------------------------------------------


def _validate_manifest(root: Path) -> Tuple[dict, List[AgentPluginDiagnostic]]:
    manifest_path = root / "plugin.json"
    if manifest_path.is_symlink():
        raise AgentPluginError("plugin.json must not be a symlink")
    if not _inside(manifest_path, root) or not manifest_path.is_file():
        raise AgentPluginError(
            "plugin.json must be a regular file within the package root"
        )
    manifest = _read_json_object(manifest_path, label="plugin.json")

    diagnostics: List[AgentPluginDiagnostic] = []
    for key in sorted(set(manifest) - _PLUGIN_FIELDS):
        diagnostics.append(
            AgentPluginDiagnostic("manifest", f"ignored unknown top-level field: {key}")
        )
        manifest.pop(key)

    if manifest.get("$schema") != PLUGIN_SCHEMA_V1:
        raise AgentPluginError(
            "plugin.json declares an unsupported or missing plugin schema"
        )
    name = manifest.get("name")
    if (
        not isinstance(name, str)
        or not 1 <= len(name) <= 64
        or not PLUGIN_NAME_RE.fullmatch(name)
    ):
        raise AgentPluginError("plugin.json name does not satisfy the v1 constraints")
    for key in ("version", "description", "homepage", "repository", "license"):
        if key in manifest and not isinstance(manifest[key], str):
            raise AgentPluginError(f"plugin.json {key} must be a string")
    keywords = manifest.get("keywords", [])
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        raise AgentPluginError("plugin.json keywords must be an array of strings")
    author = manifest.get("author", {})
    if not isinstance(author, dict):
        raise AgentPluginError("plugin.json author must be an object")
    if set(author) - _AUTHOR_FIELDS or not all(
        isinstance(v, str) for v in author.values()
    ):
        raise AgentPluginError(
            "plugin.json author may only contain string name/email/url fields"
        )
    extensions = manifest.get("extensions", {})
    if not isinstance(extensions, dict):
        diagnostics.append(
            AgentPluginDiagnostic("manifest", "ignored non-object extensions field")
        )
        manifest.pop("extensions", None)
    elif any(not isinstance(v, dict) for v in extensions.values()):
        raise AgentPluginError("plugin.json extension namespace values must be objects")
    return manifest, diagnostics


# --- skills -----------------------------------------------------------------


def _parse_frontmatter(skill_md: Path) -> dict:
    content = skill_md.read_text(encoding="utf-8-sig").lstrip("\ufeff")
    if not content.startswith("---"):
        raise ValueError("missing YAML frontmatter")
    end = re.search(r"\n---\s*\n", content[3:])
    if end is None:
        raise ValueError("unterminated YAML frontmatter")
    import yaml

    parsed = yaml.safe_load(content[3 : end.start() + 3])
    if not isinstance(parsed, dict):
        raise ValueError("YAML frontmatter must be an object")
    return parsed


def _validate_skill(name: str, frontmatter: Mapping[str, Any]) -> Optional[str]:
    declared = frontmatter.get("name")
    if (
        not isinstance(declared, str)
        or declared != name
        or not 1 <= len(declared) <= 64
        or not SKILL_NAME_RE.fullmatch(declared)
    ):
        return "frontmatter name must match the directory and satisfy skill name constraints"
    description = frontmatter.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024:
        return "frontmatter description must be a non-empty string of at most 1024 characters"
    return None


def _discover_skills(
    root: Path, diagnostics: List[AgentPluginDiagnostic]
) -> Tuple[AgentPluginSkill, ...]:
    skills_root = root / "skills"
    if skills_root.is_symlink() or (
        skills_root.exists() and not _inside(skills_root, root)
    ):
        diagnostics.append(
            AgentPluginDiagnostic("skills", "skills must be an in-root directory")
        )
        return ()
    if not skills_root.is_dir():
        return ()

    found: List[AgentPluginSkill] = []
    try:
        children = sorted(skills_root.iterdir(), key=lambda p: p.name)
    except OSError as exc:
        diagnostics.append(
            AgentPluginDiagnostic("skills", f"cannot list skills: {exc}")
        )
        return ()

    for child in children:
        if child.is_symlink():
            diagnostics.append(
                AgentPluginDiagnostic(
                    f"skill:{child.name}",
                    "symlinked skill directories are not followed",
                )
            )
            continue
        skill_md = child / "SKILL.md"
        if not child.is_dir() or skill_md.is_symlink() or not skill_md.is_file():
            continue
        if not _inside(skill_md, root):
            diagnostics.append(
                AgentPluginDiagnostic(
                    f"skill:{child.name}", "SKILL.md must be an in-root regular file"
                )
            )
            continue
        try:
            if skill_md.stat().st_size > MAX_FILE_BYTES:
                raise ValueError(f"SKILL.md exceeds the {MAX_FILE_BYTES} byte limit")
            frontmatter = _parse_frontmatter(skill_md)
        except Exception as exc:  # noqa: BLE001 - report every malformed skill
            diagnostics.append(
                AgentPluginDiagnostic(f"skill:{child.name}", f"invalid SKILL.md: {exc}")
            )
            continue
        problem = _validate_skill(child.name, frontmatter)
        if problem:
            diagnostics.append(AgentPluginDiagnostic(f"skill:{child.name}", problem))
            continue
        found.append(
            AgentPluginSkill(
                name=child.name,
                description=str(frontmatter["description"]),
                root=child.resolve(strict=True),
                skill_md=skill_md.resolve(strict=True),
                frontmatter=dict(frontmatter),
            )
        )
    return tuple(found)


# --- MCP declarations -------------------------------------------------------


def _validate_headers(headers: Any) -> bool:
    if headers is None:
        return True
    if not isinstance(headers, dict):
        return False
    names = [n for n in headers if isinstance(n, str) and HEADER_NAME_RE.fullmatch(n)]
    return (
        len(names) == len(headers)
        and len({n.lower() for n in names}) == len(names)
        and all(
            isinstance(v, str) and "\r" not in v and "\n" not in v
            for v in headers.values()
        )
    )


def _validate_remote(entry: Mapping[str, Any]) -> dict:
    unknown = set(entry) - _REMOTE_FIELDS
    if unknown:
        raise ValueError(f"unknown remote fields: {sorted(unknown)}")
    url = entry.get("url")
    if not isinstance(url, str) or not url:
        raise ValueError("url must be a non-empty string")
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("url scheme must be http or https")
    if parsed.username or parsed.password:
        raise ValueError("url must not contain user information")
    if parsed.fragment:
        raise ValueError("url must not contain a fragment")
    host = parsed.hostname
    if not host:
        raise ValueError("url must have a host")
    if parsed.scheme.lower() == "http":
        try:
            loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            raise ValueError("non-loopback remote URLs must use https")
    if not _validate_headers(entry.get("headers")):
        raise ValueError("invalid headers")
    translated: Dict[str, Any] = {"url": url}
    if entry.get("headers"):
        translated["headers"] = dict(entry["headers"])
    return translated


def _translate_stdio(entry: Mapping[str, Any], root: Path) -> dict:
    unknown = set(entry) - _STDIO_FIELDS
    if unknown:
        raise ValueError(f"unknown stdio fields: {sorted(unknown)}")
    command = entry.get("command")
    if not isinstance(command, str) or not command or "\x00" in command:
        raise ValueError("command must be a non-empty executable token")
    if command.startswith("./"):
        command = str(_resolve_scoped_path(command[2:], root, label="command"))
    elif (
        any(ch.isspace() for ch in command)
        or "/" in command
        or "\\" in command
        or command in {".", ".."}
    ):
        raise ValueError("command must be a bare executable or begin with ./")

    args = entry.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise ValueError("args must be an array of strings")
    if any("\x00" in a for a in args):
        raise ValueError("args must not contain NUL bytes")

    env = entry.get("env", {})
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in env.items()
    ):
        raise ValueError("env must map string keys to string values")
    if {k.upper() if os.name == "nt" else k for k in env} & {
        "PLUGIN_ROOT",
        "PLUGIN_DATA",
    }:
        raise ValueError("PLUGIN_ROOT and PLUGIN_DATA are reserved env names")
    if any("\x00" in v for v in env.values()):
        raise ValueError("env values must not contain NUL bytes")

    cwd_value = entry.get("cwd")
    cwd = root
    if cwd_value is not None:
        if not isinstance(cwd_value, str):
            raise ValueError("cwd must be a string")
        cwd = _resolve_scoped_path(cwd_value, root, label="cwd")

    return {
        "command": command,
        "args": [_expand_placeholders(a, root) for a in args],
        "env": {k: _expand_placeholders(v, root) for k, v in env.items()},
        "cwd": str(cwd),
    }


def _discover_mcp(
    root: Path, diagnostics: List[AgentPluginDiagnostic]
) -> Dict[str, dict]:
    mcp_path = root / "mcp.json"
    if mcp_path.is_symlink():
        diagnostics.append(
            AgentPluginDiagnostic("mcp", "mcp.json must not be a symlink")
        )
        return {}
    if not mcp_path.exists():
        return {}
    try:
        if not _inside(mcp_path, root) or not mcp_path.is_file():
            raise ValueError("mcp.json must be a regular in-root file")
        config = _read_json_object(mcp_path, label="mcp.json")
        if set(config) != {"$schema", "mcpServers"}:
            raise ValueError("mcp.json has an invalid top-level shape")
        if config.get("$schema") != MCP_SCHEMA_V1:
            raise ValueError("mcp.json declares an unsupported schema")
        servers = config.get("mcpServers")
        if not isinstance(servers, dict):
            raise ValueError("mcpServers must be an object")
    except (AgentPluginError, ValueError) as exc:
        diagnostics.append(AgentPluginDiagnostic("mcp", str(exc)))
        return {}

    translated: Dict[str, dict] = {}
    for name, entry in servers.items():
        try:
            if not isinstance(name, str) or not name or not isinstance(entry, dict):
                raise ValueError("invalid server entry")
            kind = entry.get("type")
            if kind == "stdio":
                server = _translate_stdio(entry, root)
            elif kind == "streamable-http":
                server = _validate_remote(entry)
            elif kind == "sse":
                raise ValueError("portable sse transport is not supported")
            else:
                raise ValueError(f"unknown MCP server type: {kind!r}")

            from openamer_cli.mcp_security import validate_mcp_server_entry

            issues = validate_mcp_server_entry(name, server)
            if issues:
                raise ValueError("; ".join(issues))
            translated[name] = server
        except Exception as exc:  # noqa: BLE001 - one bad server must not hide the rest
            diagnostics.append(AgentPluginDiagnostic(f"mcp:{name}", str(exc)))
    return translated


# --- loading ----------------------------------------------------------------


def load_agent_plugin(root: Path) -> AgentPluginPackage:
    """Validate a portable package and return its inert declarations.

    Never imports the package's Python and never starts an MCP server.
    """
    resolved = Path(root).resolve(strict=True)
    if not resolved.is_dir():
        raise AgentPluginError("package root must be a directory")
    manifest, diagnostics = _validate_manifest(resolved)
    skills = _discover_skills(resolved, diagnostics)
    servers = _discover_mcp(resolved, diagnostics)
    return AgentPluginPackage(
        name=str(manifest["name"]),
        version=str(manifest.get("version", "")),
        description=str(manifest.get("description", "")),
        root=resolved,
        manifest=dict(manifest),
        skills=skills,
        mcp_servers=servers,
        diagnostics=tuple(diagnostics),
    )


# --- install / inventory ----------------------------------------------------


def _is_secret_file(name: str) -> bool:
    lowered = name.lower()
    return lowered in SECRET_FILE_NAMES or lowered.endswith(SECRET_FILE_SUFFIXES)


def _scan_for_secrets(paths: Iterable[Path]) -> None:
    """Refuse to store a package that ships key material or a live-looking token."""
    for path in paths:
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in _SECRET_CONTENT:
            if pattern.search(text):
                raise AgentPluginError(
                    f"refusing to install: '{path.name}' contains key material or a "
                    "credential. Packages must reference secrets via environment "
                    "variables instead of shipping them."
                )


def _iter_package_files(source: Path) -> List[Path]:
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _SKIPPED_DIRS and not (current / d).is_symlink()
        ]
        for filename in filenames:
            path = current / filename
            if path.is_symlink():
                continue
            if not _inside(path, source):
                raise AgentPluginError(f"package file escapes the package root: {path}")
            files.append(path)
    return files


def _read_meta(package_dir: Path) -> dict:
    meta_path = package_dir / META_FILENAME
    if not meta_path.is_file():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_meta(package_dir: Path, meta: dict) -> None:
    (package_dir / META_FILENAME).write_text(
        json.dumps(meta, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def install_package(
    source: Path, *, home: Optional[Path] = None, force: bool = False
) -> dict:
    """Copy a portable package into the profile store **inert**.

    Returns the inventory record. Raises :class:`AgentPluginError` when the
    package is invalid, unsafe, or already installed (unless ``force``).
    """
    source_dir = Path(source).resolve(strict=True)
    package = load_agent_plugin(source_dir)
    if not PLUGIN_NAME_RE.fullmatch(package.name):
        raise AgentPluginError(f"invalid package name: {package.name!r}")

    root = packages_root(home)
    target = root / package.name
    if target.exists() or target.is_symlink():
        if not force:
            raise AgentPluginError(
                f"package '{package.name}' is already installed at {target} "
                "(use --force to reinstall)"
            )
        shutil.rmtree(target)
    root.mkdir(parents=True, exist_ok=True)

    files = _iter_package_files(source_dir)
    if len(files) > MAX_FILES:
        raise AgentPluginError(f"package has {len(files)} files (limit {MAX_FILES})")
    total = 0
    for path in files:
        try:
            total += path.stat().st_size
        except OSError as exc:
            raise AgentPluginError(f"cannot stat {path}: {exc}") from exc
    if total > MAX_PACKAGE_BYTES:
        raise AgentPluginError(f"package is {total} bytes (limit {MAX_PACKAGE_BYTES})")
    _scan_for_secrets(files)

    target.mkdir(parents=True)
    copied = 0
    for path in files:
        relative = path.relative_to(source_dir)
        if any(part in _SKIPPED_DIRS for part in relative.parts):
            continue
        destination = target / relative
        if not _inside(destination, target):
            raise AgentPluginError(
                f"refusing to write outside the package store: {relative}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if _is_secret_file(path.name):
            continue  # never copy credential stores into the profile
        shutil.copy2(path, destination)
        copied += 1

    installed = load_agent_plugin(target)
    meta = {
        "name": installed.name,
        "version": installed.version,
        "enabled": False,
        "installed_at": int(time.time()),
        "files": copied,
        "skills": [s.name for s in installed.skills],
        "mcp_servers": sorted(installed.mcp_servers),
        "diagnostics": [f"{d.scope}: {d.message}" for d in installed.diagnostics],
    }
    _write_meta(target, meta)
    return dict(meta, path=str(target))


def list_packages(home: Optional[Path] = None) -> List[dict]:
    root = packages_root(home)
    if not root.is_dir():
        return []
    records = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.is_symlink() or not entry.is_dir():
            continue
        meta = _read_meta(entry)
        if not meta.get("name"):
            continue
        records.append(dict(meta, path=str(entry)))
    return records


def get_package(name: str, home: Optional[Path] = None) -> Optional[dict]:
    if not PLUGIN_NAME_RE.fullmatch(name or ""):
        return None
    root = packages_root(home)
    package_dir = root / name
    if package_dir.is_symlink() or not package_dir.is_dir():
        return None
    meta = _read_meta(package_dir)
    if not meta.get("name"):
        return None
    return dict(meta, path=str(package_dir))


def set_enabled(name: str, enabled: bool, home: Optional[Path] = None) -> bool:
    """Toggle whether a package's MCP declarations may reach the MCP config."""
    record = get_package(name, home)
    if record is None:
        return False
    package_dir = Path(record["path"])
    meta = _read_meta(package_dir)
    meta["enabled"] = bool(enabled)
    _write_meta(package_dir, meta)
    return True


def remove_package(name: str, home: Optional[Path] = None) -> bool:
    record = get_package(name, home)
    if record is None:
        return False
    shutil.rmtree(Path(record["path"]))
    return True


def portable_mcp_servers(home: Optional[Path] = None) -> Dict[str, dict]:
    """MCP server declarations from **explicitly enabled** packages only.

    Installation alone never returns anything: a package has to be enabled by
    the operator before its servers can reach the MCP client. Names are
    namespaced as ``<package>__<server>`` so a package can never shadow a
    server configured in ``config.yaml``.
    """
    servers: Dict[str, dict] = {}
    for record in list_packages(home):
        if not record.get("enabled"):
            continue
        try:
            package = load_agent_plugin(Path(record["path"]))
        except Exception:  # noqa: BLE001 - a broken package must not break MCP config
            continue
        for server_name, config in package.mcp_servers.items():
            internal = f"{package.name}__{server_name}"
            servers[internal] = dict(config)
    return servers


__all__ = [
    "AgentPluginDiagnostic",
    "AgentPluginError",
    "AgentPluginPackage",
    "AgentPluginSkill",
    "PLUGIN_SCHEMA_V1",
    "MCP_SCHEMA_V1",
    "get_package",
    "install_package",
    "list_packages",
    "load_agent_plugin",
    "packages_root",
    "portable_mcp_servers",
    "remove_package",
    "set_enabled",
]
