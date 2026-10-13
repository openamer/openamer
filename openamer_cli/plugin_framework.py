"""
Plugin Composability Framework
===============================

A lightweight plugin composability system for OpenAmer. Provides:

- ``PluginSpec`` dataclass for declaring plugin metadata
- ``PluginRegistry`` for registering, discovering, enabling/disabling, and listing plugins
- ``PluginHost`` for loading plugins and managing their lifecycle
- ``PluginHook`` enum of lifecycle hook points
- ``plugin_context`` decorator for marking functions as discoverable plugins
- Hot-reload support via file-change watchers
- Discovery scanning ``~/.openamer/plugins/`` and ``optional-skills/``
"""

from __future__ import annotations

import enum
import hashlib
import importlib
import importlib.util
import inspect
import json
import logging
import os
import sys
import threading
import time
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_PLUGIN_DIRS = [
    Path.home() / ".openamer" / "plugins",
    # optional-skills/ relative to the repo root (discovered at runtime)
]

HOOK_ATTR = "_plugin_hooks_"
PLUGIN_ATTR = "_plugin_spec_"

# ── PluginHook Enum ───────────────────────────────────────────────────────────


class PluginHook(str, enum.Enum):
    """Lifecycle hook points a plugin can attach to."""

    PRE_TOOL_CALL = "pre_tool_call"
    POST_TOOL_CALL = "post_tool_call"
    PRE_LLM_CALL = "pre_llm_call"
    POST_LLM_CALL = "post_llm_call"
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"


# ── PluginSpec Dataclass ──────────────────────────────────────────────────────


@dataclass
class PluginSpec:
    """Declarative specification of a plugin."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    entry_point: str = ""
    dependencies: List[str] = field(default_factory=list)
    hooks: List[PluginHook] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "entry_point": self.entry_point,
            "dependencies": self.dependencies,
            "hooks": [h.value for h in self.hooks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginSpec":
        hooks = []
        for h in data.get("hooks", []):
            try:
                hooks.append(PluginHook(h))
            except ValueError:
                pass
        return cls(
            name=data.get("name", "unknown"),
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            entry_point=data.get("entry_point", ""),
            dependencies=data.get("dependencies", []),
            hooks=hooks,
        )


# ── PluginState ────────────────────────────────────────────────────────────────


class PluginState(str, enum.Enum):
    """Runtime state of a loaded plugin."""

    DISABLED = "disabled"
    ENABLED = "enabled"
    LOADED = "loaded"
    ERROR = "error"


# ── PluginRecord ────────────────────────────────────────────────────────────────


@dataclass
class PluginRecord:
    """Internal record tracking a plugin's metadata and runtime state."""

    spec: PluginSpec
    path: Optional[Path] = None
    module: Optional[types.ModuleType] = None
    state: PluginState = PluginState.DISABLED
    error: Optional[str] = None
    file_hash: Optional[str] = None  # for hot-reload detection
    registered_functions: Dict[str, Callable] = field(default_factory=dict)


# ── PluginContext Decorator ───────────────────────────────────────────────────


def plugin_context(
    *,
    name: Optional[str] = None,
    version: str = "0.1.0",
    description: str = "",
    author: str = "",
    hooks: Optional[List[PluginHook]] = None,
    dependencies: Optional[List[str]] = None,
) -> Callable:
    """Decorator that marks a function or class as a discoverable plugin.

    Usage::

        @plugin_context(
            name="my-plugin",
            version="1.0.0",
            description="Does something useful",
            hooks=[PluginHook.POST_TOOL_CALL],
        )
        def my_hook(tool_result, **kwargs):
            ...
    """

    def decorator(obj: Callable) -> Callable:
        spec = PluginSpec(
            name=name or obj.__name__,
            version=version,
            description=description or (obj.__doc__ or "").strip(),
            author=author,
            entry_point=f"{obj.__module__}:{obj.__qualname__}",
            dependencies=dependencies or [],
            hooks=hooks or [],
        )
        setattr(obj, PLUGIN_ATTR, spec)
        if hooks:
            hook_names = {h.value for h in hooks}
            setattr(obj, HOOK_ATTR, hook_names)
        return obj

    return decorator


# ── PluginRegistry ────────────────────────────────────────────────────────────


class PluginRegistry:
    """Central registry for discovering, registering, and tracking plugins."""

    def __init__(self, plugin_dirs: Optional[List[Path]] = None) -> None:
        self._records: Dict[str, PluginRecord] = {}
        self._plugin_dirs: List[Path] = plugin_dirs or list(DEFAULT_PLUGIN_DIRS)
        self._hook_registry: Dict[PluginHook, List[str]] = {
            hook: [] for hook in PluginHook
        }
        self._lock = threading.Lock()

    # ── Registration ──────────────────────────────────────────────────────

    def register(
        self,
        spec: PluginSpec,
        path: Optional[Path] = None,
        module: Optional[types.ModuleType] = None,
    ) -> None:
        """Register a plugin from a PluginSpec."""
        with self._lock:
            record = PluginRecord(spec=spec, path=path, module=module)
            if module is not None:
                record.state = PluginState.LOADED
            self._records[spec.name] = record
            self._rebuild_hook_index()
            logger.info("Registered plugin: %s v%s", spec.name, spec.version)

    def unregister(self, name: str) -> bool:
        """Remove a plugin from the registry."""
        with self._lock:
            if name in self._records:
                del self._records[name]
                self._rebuild_hook_index()
                logger.info("Unregistered plugin: %s", name)
                return True
            return False

    # ── Discovery ─────────────────────────────────────────────────────────

    def discover(self, extra_dirs: Optional[List[Path]] = None) -> List[PluginSpec]:
        """Scan plugin directories for plugin manifests and register them."""
        all_dirs = list(self._plugin_dirs)
        if extra_dirs:
            all_dirs.extend(extra_dirs)

        discovered: List[PluginSpec] = []
        for directory in all_dirs:
            if not directory.exists():
                continue
            for entry in sorted(directory.iterdir()):
                if not entry.is_dir():
                    continue
                spec = self._load_manifest(entry)
                if spec is not None:
                    discovered.append(spec)
                    if spec.name not in self._records:
                        self.register(spec, path=entry)
        return discovered

    def _load_manifest(self, plugin_dir: Path) -> Optional[PluginSpec]:
        """Load a plugin manifest from ``plugin_dir/plugin.yaml`` or ``plugin.json``."""
        yaml_path = plugin_dir / "plugin.yaml"
        yml_path = plugin_dir / "plugin.yml"
        json_path = plugin_dir / "plugin.json"

        data: Dict[str, Any] = {}
        if yaml_path.is_file():
            try:
                import yaml  # lazy import

                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as exc:
                logger.warning("Failed to load YAML manifest %s: %s", yaml_path, exc)
                return None
        elif yml_path.is_file():
            try:
                import yaml

                with open(yml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as exc:
                logger.warning("Failed to load YAML manifest %s: %s", yml_path, exc)
                return None
        elif json_path.is_file():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as exc:
                logger.warning("Failed to load JSON manifest %s: %s", json_path, exc)
                return None
        else:
            # No manifest — check __init__.py for decorated functions
            init_py = plugin_dir / "__init__.py"
            if init_py.is_file():
                return PluginSpec(name=plugin_dir.name, version="0.1.0", description="Auto-discovered plugin")
            return None

        return PluginSpec.from_dict(data)

    # ── Enable / Disable ──────────────────────────────────────────────────

    def enable(self, name: str) -> bool:
        """Enable a registered plugin."""
        with self._lock:
            record = self._records.get(name)
            if record is None:
                logger.warning("Cannot enable unknown plugin: %s", name)
                return False
            record.state = PluginState.ENABLED
            self._rebuild_hook_index()
            logger.info("Enabled plugin: %s", name)
            return True

    def disable(self, name: str) -> bool:
        """Disable a registered plugin."""
        with self._lock:
            record = self._records.get(name)
            if record is None:
                return False
            record.state = PluginState.DISABLED
            self._rebuild_hook_index()
            logger.info("Disabled plugin: %s", name)
            return True

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        record = self._records.get(name)
        if record is None:
            return False
        return record.state == PluginState.ENABLED

    # ── Listing ───────────────────────────────────────────────────────────

    def list_plugins(
        self, include_disabled: bool = True
    ) -> List[Tuple[str, PluginState, str]]:
        """List all registered plugins with their state and version.

        Returns list of (name, state, version) tuples.
        """
        results: List[Tuple[str, PluginState, str]] = []
        with self._lock:
            for name, record in sorted(self._records.items()):
                if not include_disabled and record.state == PluginState.DISABLED:
                    continue
                results.append((name, record.state, record.spec.version))
        return results

    def get_record(self, name: str) -> Optional[PluginRecord]:
        """Get a plugin record by name."""
        return self._records.get(name)

    # ── Hooks ─────────────────────────────────────────────────────────────

    def get_hooks_for(self, hook: PluginHook) -> List[str]:
        """Return list of plugin names registered for a given hook."""
        with self._lock:
            return list(self._hook_registry.get(hook, []))

    def invoke_hooks(
        self, hook: PluginHook, **kwargs: Any
    ) -> List[Any]:
        """Invoke all enabled plugins registered for the given hook.

        Returns a list of return values from each invoked hook.
        """
        results: List[Any] = []
        plugin_names = self.get_hooks_for(hook)
        for name in plugin_names:
            record = self._records.get(name)
            if record is None or record.state != PluginState.ENABLED:
                continue
            fn = record.registered_functions.get(hook.value)
            if fn is None:
                continue
            try:
                result = fn(**kwargs)
                results.append(result)
            except Exception as exc:
                logger.error("Plugin %s hook %s failed: %s", name, hook.value, exc)
                record.state = PluginState.ERROR
                record.error = str(exc)
        return results

    def _rebuild_hook_index(self) -> None:
        """Rebuild the hook-to-plugins index from enabled records."""
        for hook in PluginHook:
            self._hook_registry[hook] = []
        for name, record in self._records.items():
            if record.state != PluginState.ENABLED:
                continue
            for hook in record.spec.hooks:
                self._hook_registry[hook].append(name)

    # ── Persistence ───────────────────────────────────────────────────────

    def save_state(self, path: Path) -> None:
        """Save enabled/disabled state to a JSON file."""
        state = {}
        with self._lock:
            for name, record in self._records.items():
                state[name] = {
                    "enabled": record.state == PluginState.ENABLED,
                }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def load_state(self, path: Path) -> None:
        """Load enabled/disabled state from a JSON file."""
        if not path.is_file():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            with self._lock:
                for name, data in state.items():
                    record = self._records.get(name)
                    if record is not None and data.get("enabled", False):
                        record.state = PluginState.ENABLED
            self._rebuild_hook_index()
        except Exception as exc:
            logger.warning("Failed to load plugin state: %s", exc)


# ── PluginHost ────────────────────────────────────────────────────────────────


class PluginHost:
    """Manages plugin lifecycle: init, start, stop, reload.

    ``PluginHost`` wraps a ``PluginRegistry`` and provides lifecycle management
    — loading plugin modules, starting/stopping them, and hot-reloading.
    """

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        plugin_dirs: Optional[List[Path]] = None,
    ) -> None:
        self.registry = registry or PluginRegistry(plugin_dirs=plugin_dirs)
        self._loaded_modules: Dict[str, types.ModuleType] = {}
        self._running: bool = False
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_watch: threading.Event = threading.Event()
        self._file_hashes: Dict[str, str] = {}

    # ── Load ──────────────────────────────────────────────────────────────

    def load_plugin(self, path: Path) -> Optional[PluginSpec]:
        """Load a plugin from a directory path.

        1. Reads the manifest (plugin.yaml/json).
        2. Imports the entry point module.
        3. Scans for decorated functions (``plugin_context``).
        4. Registers the plugin in the registry.
        """
        if not path.is_dir():
            logger.warning("Plugin path is not a directory: %s", path)
            return None

        spec = self.registry._load_manifest(path)
        if spec is None:
            return None

        # Compute file hash for hot-reload
        file_hash = self._compute_dir_hash(path)
        self._file_hashes[spec.name] = file_hash

        # Try to load the __init__.py or entry point module
        module = self._import_plugin_module(path, spec)
        if module is not None:
            self._loaded_modules[spec.name] = module
            # Scan module for decorated functions
            self._scan_decorated_functions(spec, module)

        self.registry.register(spec, path=path, module=module)
        return spec

    def load_all(self, extra_dirs: Optional[List[Path]] = None) -> int:
        """Discover and load all plugins from configured directories.

        Returns the number of plugins loaded.
        """
        specs = self.registry.discover(extra_dirs=extra_dirs)
        loaded = 0
        for spec in specs:
            record = self.registry.get_record(spec.name)
            if record and record.path:
                module = self._import_plugin_module(record.path, spec)
                if module:
                    self._loaded_modules[spec.name] = module
                    self._scan_decorated_functions(spec, module)
                    record.module = module
                    record.state = PluginState.LOADED
                loaded += 1
        return loaded

    def _import_plugin_module(
        self, path: Path, spec: PluginSpec
    ) -> Optional[types.ModuleType]:
        """Import a plugin's entry point module."""
        init_py = path / "__init__.py"
        if not init_py.is_file():
            return None

        module_name = f"_openamer_plugin_{spec.name}"
        try:
            if module_name in sys.modules:
                module = sys.modules[module_name]
                importlib.reload(module)
            else:
                loader = importlib.machinery.SourceFileLoader(module_name, str(init_py))
                spec_mod = importlib.util.spec_from_loader(module_name, loader)
                if spec_mod is None:
                    return None
                module = importlib.util.module_from_spec(spec_mod)
                sys.modules[module_name] = module
                loader.exec_module(module)
            return module
        except Exception as exc:
            logger.error("Failed to import plugin %s: %s", spec.name, exc)
            return None

    def _scan_decorated_functions(
        self, spec: PluginSpec, module: types.ModuleType
    ) -> None:
        """Scan a loaded module for ``plugin_context``-decorated functions."""
        for _name, obj in inspect.getmembers(module):
            if hasattr(obj, PLUGIN_ATTR):
                plugin_spec: PluginSpec = getattr(obj, PLUGIN_ATTR)
                hooks = getattr(obj, HOOK_ATTR, set())
                for hook in hooks:
                    try:
                        plugin_hook = PluginHook(hook)
                        if plugin_hook not in spec.hooks:
                            spec.hooks.append(plugin_hook)
                    except ValueError:
                        pass
                record = self.registry.get_record(spec.name)
                if record:
                    record.registered_functions.update(
                        {h: obj for h in hooks}
                    )

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the plugin host — load all plugins and start the watcher."""
        logger.info("PluginHost starting...")
        self.load_all()
        self._running = True
        # Mark all loaded as enabled by default
        for name, record in self.registry._records.items():
            if record.state == PluginState.LOADED:
                record.state = PluginState.ENABLED
        self.registry._rebuild_hook_index()
        logger.info("PluginHost started with %d plugin(s)", len(self.registry._records))

    def stop(self) -> None:
        """Stop the plugin host — disable hot-reload watcher."""
        logger.info("PluginHost stopping...")
        self._running = False
        self._stop_watch.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=5)
        # Disable all plugins
        for name, record in self.registry._records.items():
            if record.state == PluginState.ENABLED:
                self.registry.disable(name)
        logger.info("PluginHost stopped")

    def reload(self, name: Optional[str] = None) -> int:
        """Reload one or all plugins.

        Args:
            name: Plugin name to reload, or ``None`` to reload all.

        Returns:
            Number of plugins successfully reloaded.
        """
        if name is not None:
            record = self.registry.get_record(name)
            if record is None or record.path is None:
                logger.warning("Cannot reload unknown plugin: %s", name)
                return 0
            return 1 if self._reload_one(record) else 0

        count = 0
        for _n, record in list(self.registry._records.items()):
            if record.path and self._reload_one(record):
                count += 1
        return count

    def _reload_one(self, record: PluginRecord) -> bool:
        """Reload a single plugin by its record."""
        if record.path is None:
            return False
        try:
            spec = self.registry._load_manifest(record.path)
            if spec is None:
                return False
            module = self._import_plugin_module(record.path, spec)
            if module:
                self._loaded_modules[record.path.name] = module
                self._scan_decorated_functions(spec, module)
                record.module = module
                record.spec = spec
                record.error = None
                record.state = PluginState.ENABLED
                self.registry._rebuild_hook_index()
                return True
            return False
        except Exception as exc:
            record.error = str(exc)
            record.state = PluginState.ERROR
            logger.error("Reload failed for %s: %s", record.spec.name, exc)
            return False

    # ── Hot-Reload Support ────────────────────────────────────────────────

    def start_watcher(self, interval: float = 5.0) -> None:
        """Start a background thread that watches plugin files for changes.

        When a change is detected, the affected plugin is reloaded automatically.
        """
        if self._watch_thread and self._watch_thread.is_alive():
            logger.warning("Watcher already running")
            return

        self._stop_watch.clear()

        def _watch_loop() -> None:
            while not self._stop_watch.is_set():
                for name, record in list(self.registry._records.items()):
                    if record.path and record.path.is_dir():
                        new_hash = self._compute_dir_hash(record.path)
                        old_hash = self._file_hashes.get(name)
                        if old_hash is not None and new_hash != old_hash:
                            logger.info("Hot-reload detected change in plugin: %s", name)
                            self._reload_one(record)
                        self._file_hashes[name] = new_hash
                self._stop_watch.wait(interval)

        self._watch_thread = threading.Thread(
            target=_watch_loop, daemon=True, name="plugin-watcher"
        )
        self._watch_thread.start()
        logger.info("Plugin watcher started (interval=%ss)", interval)

    def stop_watcher(self) -> None:
        """Stop the hot-reload background watcher."""
        self._stop_watch.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=5)
        self._watch_thread = None

    @staticmethod
    def _compute_dir_hash(directory: Path) -> str:
        """Compute a hash of all Python files in a directory for change detection."""
        hasher = hashlib.md5()
        for filepath in sorted(directory.rglob("*.py")):
            try:
                with open(filepath, "rb") as f:
                    hasher.update(filepath.name.encode())
                    hasher.update(f.read())
            except OSError:
                pass
        return hasher.hexdigest()

    def install(self, source_path: Path, target_dir: Optional[Path] = None) -> Optional[str]:
        """Install a plugin from a source path into the plugin directory.

        Args:
            source_path: Path to the plugin directory or file to install.
            target_dir: Target installation directory (default: first plugin dir).

        Returns:
            The name of the installed plugin, or ``None`` on failure.
        """
        if target_dir is None:
            if not self.registry._plugin_dirs:
                return None
            target_dir = self.registry._plugin_dirs[0]

        target_dir.mkdir(parents=True, exist_ok=True)

        if source_path.is_dir():
            # Install directory plugin
            spec = self.registry._load_manifest(source_path)
            plugin_name = spec.name if spec else source_path.name
            dest = target_dir / plugin_name
            if dest.exists():
                import shutil
                shutil.rmtree(dest)
            import shutil
            shutil.copytree(source_path, dest)
            self.load_plugin(dest)
            return plugin_name
        elif source_path.is_file() and source_path.suffix == ".py":
            # Install single-file plugin
            plugin_name = source_path.stem
            dest_dir = target_dir / plugin_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            init_py = dest_dir / "__init__.py"
            import shutil
            shutil.copy2(source_path, init_py)
            # Create minimal manifest
            manifest = dest_dir / "plugin.yaml"
            manifest.write_text(
                f"name: {plugin_name}\nversion: 0.1.0\ndescription: Installed from {source_path.name}\n"
            )
            self.load_plugin(dest_dir)
            return plugin_name

        return None