"""
OpenAmer Plugin System — Third-party Plugin Architecture
=======================================================

A clean, standalone plugin system that lets third-party developers write
Python-based plugins for OpenAmer. Every plugin is a Python package with a
``plugin.yaml`` or ``plugin.json`` manifest and lifecycle hooks.

Features
--------
- ``Plugin`` dataclass for declaring plugin metadata
- ``PluginRegistry`` for registration, discovery, and tracking
- ``PluginManager`` for load/unload/activate/deactivate lifecycle
- Standard lifecycle hooks: on_activate, on_deactivate, on_startup,
  on_shutdown, on_tool_call, on_message
- YAML/JSON manifest discovery
- Thread-safe operations
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import sys
import threading
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ── Standard Lifecycle Hooks ──────────────────────────────────────────────────

HOOK_ON_ACTIVATE = "on_activate"
HOOK_ON_DEACTIVATE = "on_deactivate"
HOOK_ON_STARTUP = "on_startup"
HOOK_ON_SHUTDOWN = "on_shutdown"
HOOK_ON_TOOL_CALL = "on_tool_call"
HOOK_ON_MESSAGE = "on_message"

# All recognised hook names, so consumers can iterate or validate.
STANDARD_HOOKS: Set[str] = {
    HOOK_ON_ACTIVATE,
    HOOK_ON_DEACTIVATE,
    HOOK_ON_STARTUP,
    HOOK_ON_SHUTDOWN,
    HOOK_ON_TOOL_CALL,
    HOOK_ON_MESSAGE,
}

# ── Plugin States ─────────────────────────────────────────────────────────────


class PluginState(str):
    """Runtime state of a plugin."""

    REGISTERED = "registered"
    LOADED = "loaded"
    ACTIVATED = "activated"
    ERROR = "error"


# ── Plugin Dataclass ──────────────────────────────────────────────────────────


@dataclass
class Plugin:
    """Declaration of a third-party plugin.

    Attributes:
        id: Unique identifier (e.g. ``"my-weather-plugin"``).
        name: Human-readable name (e.g. ``"Weather Reporter"``).
        version: Semver string (e.g. ``"1.2.0"``).
        description: One-line summary of what the plugin does.
        author: Author/org name (optional).
        entry_point: Python module or dotted path to load.
            Examples: ``"my_plugin"``, ``"my_plugin.hooks"``.
        hooks: Dict mapping lifecycle hook names → callables.
            The callables are resolved at load time if given as dotted
            strings, or passed directly if they are already callables.
        dependencies: List of dependency specifiers (e.g. ``["requests>=2"]``).
    """

    id: str
    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    entry_point: str = ""
    hooks: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "entry_point": self.entry_point,
            "hooks": dict(self.hooks),
            "dependencies": list(self.dependencies),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plugin":
        return cls(
            id=data.get("id", data.get("name", "unknown")),
            name=data.get("name", ""),
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            entry_point=data.get("entry_point", ""),
            hooks=data.get("hooks", {}),
            dependencies=data.get("dependencies", []),
        )


# ── PluginRegistry ────────────────────────────────────────────────────────────


class PluginRegistry:
    """Manages installed plugins — registration, discovery, and lookup.

    Thread-safe: all mutating operations use a reentrant lock.
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, Plugin] = {}
        self._states: Dict[str, str] = {}
        self._lock = threading.Lock()

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, plugin: Plugin) -> None:
        """Register a *plugin*.

        If a plugin with the same ``id`` already exists it is overwritten
        (the new definition wins).
        """
        with self._lock:
            self._plugins[plugin.id] = plugin
            if plugin.id not in self._states:
                self._states[plugin.id] = PluginState.REGISTERED
            logger.info("Registered plugin: %s v%s", plugin.id, plugin.version)

    def unregister(self, plugin_id: str) -> bool:
        """Remove a plugin from the registry.

        Returns ``True`` if the plugin existed and was removed.
        """
        with self._lock:
            if plugin_id in self._plugins:
                del self._plugins[plugin_id]
                self._states.pop(plugin_id, None)
                logger.info("Unregistered plugin: %s", plugin_id)
                return True
            return False

    # ── Query ─────────────────────────────────────────────────────────────

    def list(self) -> List[Plugin]:
        """Return a sorted list of all registered plugins."""
        with self._lock:
            return [self._plugins[k] for k in sorted(self._plugins.keys())]

    def get(self, plugin_id: str) -> Optional[Plugin]:
        """Look up a plugin by its ``id``."""
        with self._lock:
            return self._plugins.get(plugin_id)

    def get_state(self, plugin_id: str) -> Optional[str]:
        """Return the runtime state of a plugin, or ``None`` if unknown."""
        with self._lock:
            return self._states.get(plugin_id)

    def set_state(self, plugin_id: str, state: str) -> None:
        """Set the runtime state of a plugin."""
        with self._lock:
            if plugin_id in self._plugins:
                self._states[plugin_id] = state

    # ── Discovery ─────────────────────────────────────────────────────────

    def discover(self, plugin_dir: Path) -> List[Plugin]:
        """Scan *plugin_dir* for plugin definitions.

        Looks for ``plugin.yaml`` or ``plugin.json`` inside each immediate
        subdirectory, parses the manifest, and registers the resulting
        ``Plugin`` objects.

        Returns the list of newly discovered plugins.
        """
        discovered: List[Plugin] = []
        if not plugin_dir.is_dir():
            logger.warning("Plugin directory not found: %s", plugin_dir)
            return discovered

        for entry in sorted(plugin_dir.iterdir()):
            if not entry.is_dir():
                continue
            plugin = self._load_manifest(entry)
            if plugin is not None:
                discovered.append(plugin)
                # Auto-register if not already present
                if plugin.id not in self._plugins:
                    self.register(plugin)
        return discovered

    def _load_manifest(self, plugin_dir: Path) -> Optional[Plugin]:
        """Load a plugin manifest from *plugin_dir/plugin.yaml* or ``plugin.json``."""
        yaml_path = plugin_dir / "plugin.yaml"
        yml_path = plugin_dir / "plugin.yml"
        json_path = plugin_dir / "plugin.json"

        data: Dict[str, Any] = {}

        if yaml_path.is_file():
            try:
                import yaml

                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as exc:
                logger.warning("Failed to load YAML %s: %s", yaml_path, exc)
                return None
        elif yml_path.is_file():
            try:
                import yaml

                with open(yml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as exc:
                logger.warning("Failed to load YAML %s: %s", yml_path, exc)
                return None
        elif json_path.is_file():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as exc:
                logger.warning("Failed to load JSON %s: %s", json_path, exc)
                return None
        else:
            return None

        return Plugin.from_dict(data)


# ── PluginManager ─────────────────────────────────────────────────────────────


class PluginManager:
    """Lifecycle management for plugins.

    Wraps a ``PluginRegistry`` and handles the load/unload/activate/deactivate
    lifecycle for each plugin.  Plugins are imported as Python modules via
    their ``entry_point``.
    """

    def __init__(self, registry: Optional[PluginRegistry] = None) -> None:
        self.registry = registry or PluginRegistry()
        self._modules: Dict[str, types.ModuleType] = {}
        self._hook_impls: Dict[str, Dict[str, Callable[..., Any]]] = {}
        self._lock = threading.RLock()

    # ── Load / Unload ─────────────────────────────────────────────────────

    def load(self, plugin_id: str) -> bool:
        """Load (import) a plugin's entry point module.

        The ``entry_point`` must be a Python module path (e.g.
        ``"my_plugin.hooks"``) or dotted path to a callable
        (``"my_plugin:setup``).

        Returns ``True`` on success.
        """
        plugin = self.registry.get(plugin_id)
        if plugin is None:
            logger.warning("Cannot load unknown plugin: %s", plugin_id)
            return False

        if not plugin.entry_point:
            logger.warning("Plugin %s has no entry_point", plugin_id)
            return False

        try:
            module = self._import_entry_point(plugin.entry_point)
            with self._lock:
                self._modules[plugin_id] = module
                self._resolve_hooks(plugin, module)
                self.registry.set_state(plugin_id, PluginState.LOADED)
            logger.info("Loaded plugin: %s", plugin_id)
            return True
        except Exception as exc:
            logger.error("Failed to load plugin %s: %s", plugin_id, exc)
            self.registry.set_state(plugin_id, PluginState.ERROR)
            return False

    def unload(self, plugin_id: str) -> bool:
        """Unload a plugin (remove it from ``sys.modules`` and clear hooks).

        Returns ``True`` if the plugin was loaded and unloaded.
        """
        with self._lock:
            if plugin_id not in self._modules:
                logger.warning("Plugin %s is not loaded", plugin_id)
                return False

            # Remove from sys.modules so a future load() gets a fresh module
            module = self._modules.pop(plugin_id, None)
            self._hook_impls.pop(plugin_id, None)
            if module and module.__name__ in sys.modules:
                del sys.modules[module.__name__]
                # Also remove any submodules the import may have added
                to_delete = [
                    name
                    for name in list(sys.modules.keys())
                    if name.startswith(f"{module.__name__}.")
                ]
                for name in to_delete:
                    del sys.modules[name]

            self.registry.set_state(plugin_id, PluginState.REGISTERED)
            logger.info("Unloaded plugin: %s", plugin_id)
            return True

    # ── Activate / Deactivate ─────────────────────────────────────────────

    def activate(self, plugin_id: str) -> bool:
        """Activate a plugin by calling its ``on_activate`` hook (if defined).

        The plugin must be in ``LOADED`` state first.
        Returns ``True`` on success.
        """
        state = self.registry.get_state(plugin_id)
        if state is None:
            logger.warning("Unknown plugin: %s", plugin_id)
            return False
        if state != PluginState.LOADED:
            logger.warning(
                "Cannot activate plugin %s: state=%s (need %s)",
                plugin_id,
                state,
                PluginState.LOADED,
            )
            return False

        try:
            self._invoke_hook(plugin_id, HOOK_ON_ACTIVATE)
            self.registry.set_state(plugin_id, PluginState.ACTIVATED)
            logger.info("Activated plugin: %s", plugin_id)
            return True
        except Exception as exc:
            logger.error("Failed to activate plugin %s: %s", plugin_id, exc)
            self.registry.set_state(plugin_id, PluginState.ERROR)
            return False

    def deactivate(self, plugin_id: str) -> bool:
        """Deactivate a plugin by calling its ``on_deactivate`` hook.

        Returns ``True`` on success.
        """
        state = self.registry.get_state(plugin_id)
        if state is None:
            logger.warning("Unknown plugin: %s", plugin_id)
            return False

        try:
            self._invoke_hook(plugin_id, HOOK_ON_DEACTIVATE)
            self.registry.set_state(plugin_id, PluginState.LOADED)
            logger.info("Deactivated plugin: %s", plugin_id)
            return True
        except Exception as exc:
            logger.error("Failed to deactivate plugin %s: %s", plugin_id, exc)
            self.registry.set_state(plugin_id, PluginState.ERROR)
            return False

    # ── Bulk operations ───────────────────────────────────────────────────

    def load_all(self) -> int:
        """Load all registered plugins that have an ``entry_point``.

        Returns the count of successfully loaded plugins.
        """
        count = 0
        for plugin in self.registry.list():
            state = self.registry.get_state(plugin.id)
            if state == PluginState.REGISTERED and plugin.entry_point:
                if self.load(plugin.id):
                    count += 1
        return count

    def activate_all(self) -> int:
        """Activate all loaded plugins.

        Returns the count of successfully activated plugins.
        """
        count = 0
        for plugin in self.registry.list():
            if self.registry.get_state(plugin.id) == PluginState.LOADED:
                if self.activate(plugin.id):
                    count += 1
        return count

    # ── Hook invocation ───────────────────────────────────────────────────

    def invoke_tool_call(
        self, plugin_id: str, tool_name: str, args: Dict[str, Any]
    ) -> Optional[Any]:
        """Invoke a plugin's ``on_tool_call`` hook, if present.

        Returns the hook's return value, or ``None`` if no hook is registered.
        """
        return self._invoke_hook(plugin_id, HOOK_ON_TOOL_CALL, tool_name=tool_name, args=args)

    def invoke_message(
        self, plugin_id: str, message: str, role: str
    ) -> Optional[Any]:
        """Invoke a plugin's ``on_message`` hook, if present.

        Returns the hook's return value, or ``None`` if no hook is registered.
        """
        return self._invoke_hook(plugin_id, HOOK_ON_MESSAGE, message=message, role=role)

    def invoke_startup(self, plugin_id: str) -> Optional[Any]:
        """Invoke a plugin's ``on_startup`` hook, if present."""
        return self._invoke_hook(plugin_id, HOOK_ON_STARTUP)

    def invoke_shutdown(self, plugin_id: str) -> Optional[Any]:
        """Invoke a plugin's ``on_shutdown`` hook, if present."""
        return self._invoke_hook(plugin_id, HOOK_ON_SHUTDOWN)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _import_entry_point(self, entry_point: str) -> types.ModuleType:
        """Import a module from a dotted path.

        Supports two forms:
        - ``"my_plugin.hooks"`` — imports the module directly.
        - ``"my_plugin.hooks:setup"`` — imports the module and returns it
          (the callable resolution happens separately).
        """
        module_path = entry_point.split(":")[0] if ":" in entry_point else entry_point
        module = importlib.import_module(module_path)
        return module

    def _resolve_hooks(
        self, plugin: Plugin, module: types.ModuleType
    ) -> None:
        """Resolve hook strings from the manifest into actual callables.

        Each entry in ``plugin.hooks`` maps a hook name to either:
        - A dotted path like ``"my_module:my_function"`` (callable after import)
        - A plain function name like ``"on_activate"`` found in the module
        """
        impls: Dict[str, Callable[..., Any]] = {}

        for hook_name, value in plugin.hooks.items():
            if hook_name not in STANDARD_HOOKS:
                logger.debug("Unknown hook %s for plugin %s", hook_name, plugin.id)
                continue

            resolved: Optional[Callable[..., Any]] = None

            if isinstance(value, str):
                # Try dotted path first (e.g. "my_module:func")
                if ":" in value:
                    mod_path, func_name = value.split(":", 1)
                    try:
                        mod = importlib.import_module(mod_path)
                        resolved = getattr(mod, func_name, None)
                    except ImportError:
                        logger.debug(
                            "Could not import %s for hook %s", mod_path, hook_name
                        )
                else:
                    # Look for the name directly in the imported module
                    resolved = getattr(module, value, None)

            if resolved is not None and callable(resolved):
                impls[hook_name] = resolved
            else:
                logger.debug(
                    "Hook %s for plugin %s: %r is not callable or not found",
                    hook_name,
                    plugin.id,
                    value,
                )

        with self._lock:
            self._hook_impls[plugin.id] = impls

    def _invoke_hook(
        self, plugin_id: str, hook_name: str, **kwargs: Any
    ) -> Optional[Any]:
        """Look up and call a hook implementation, returning its result."""
        impls = self._hook_impls.get(plugin_id, {})
        fn = impls.get(hook_name)
        if fn is None:
            return None
        try:
            return fn(**kwargs)
        except Exception as exc:
            logger.error(
                "Hook %s for plugin %s failed: %s", hook_name, plugin_id, exc
            )
            raise

    def list_hooks(self, plugin_id: str) -> Dict[str, Callable[..., Any]]:
        """Return the resolved hook implementations for a plugin."""
        return dict(self._hook_impls.get(plugin_id, {}))

    def get_loaded_module(self, plugin_id: str) -> Optional[types.ModuleType]:
        """Return the imported module for a loaded plugin."""
        return self._modules.get(plugin_id)

    def is_loaded(self, plugin_id: str) -> bool:
        """Check if a plugin is in LOADED or ACTIVATED state."""
        state = self.registry.get_state(plugin_id)
        return state in (PluginState.LOADED, PluginState.ACTIVATED)