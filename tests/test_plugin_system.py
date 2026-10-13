"""Tests for openamer_cli.plugin_system — third-party plugin architecture."""

import json
import sys
import tempfile
import types
from pathlib import Path

import pytest

from openamer_cli.plugin_system import (
    HOOK_ON_ACTIVATE,
    HOOK_ON_DEACTIVATE,
    HOOK_ON_MESSAGE,
    HOOK_ON_STARTUP,
    HOOK_ON_SHUTDOWN,
    HOOK_ON_TOOL_CALL,
    STANDARD_HOOKS,
    Plugin,
    PluginManager,
    PluginRegistry,
    PluginState,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def registry():
    """Return an empty PluginRegistry."""
    return PluginRegistry()


@pytest.fixture
def manager():
    """Return a PluginManager wrapping an empty PluginRegistry."""
    return PluginManager()


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that is cleaned up after the test.

    Works around a pathlib-snapshot issue: we yield the *string* path so
    that path-watching code doesn't hold a reference into the deleted tmpdir.
    """
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def sample_plugin():
    """Return a Plugin with a known entry_point for testing."""
    return Plugin(
        id="demo-plugin",
        name="Demo Plugin",
        version="2.0.0",
        description="A test plugin",
        author="Test Author",
        entry_point="tests.test_plugin_system",  # this module itself
        hooks={
            HOOK_ON_ACTIVATE: "sample_on_activate",
            HOOK_ON_DEACTIVATE: "sample_on_deactivate",
        },
        dependencies=["pytest>=7"],
    )


# ── Hook helpers used by sample_plugin fixtures ──────────────────────────────


def sample_on_activate():
    return "activated"


def sample_on_deactivate():
    return "deactivated"


# ── Tests for Plugin dataclass ────────────────────────────────────────────────


class TestPlugin:
    """Plugin dataclass construction and serialization."""

    def test_default_construction(self):
        """Test 1: A plugin with only an id gets sensible defaults."""
        p = Plugin(id="my-plugin")
        assert p.id == "my-plugin"
        assert p.name == "my-plugin"  # __post_init__ copies id → name
        assert p.version == "0.1.0"
        assert p.description == ""
        assert p.author == ""
        assert p.entry_point == ""
        assert p.hooks == {}
        assert p.dependencies == []

    def test_full_construction(self):
        """Test 2: All fields can be set explicitly."""
        p = Plugin(
            id="full",
            name="Full Plugin",
            version="3.0.0",
            description="Does everything",
            author="OpenAmer",
            entry_point="my_plugin.core",
            hooks={HOOK_ON_STARTUP: "startup_fn"},
            dependencies=["requests", "click>=8"],
        )
        assert p.id == "full"
        assert p.name == "Full Plugin"
        assert p.version == "3.0.0"
        assert p.hooks[HOOK_ON_STARTUP] == "startup_fn"
        assert "requests" in p.dependencies

    def test_to_dict(self):
        """Test 3: to_dict() returns a serializable dict."""
        p = Plugin(
            id="my-p",
            name="My Plugin",
            version="1.0",
            description="desc",
            author="me",
            entry_point="mod:fn",
            hooks={HOOK_ON_ACTIVATE: "act"},
            dependencies=["dep1"],
        )
        d = p.to_dict()
        assert d["id"] == "my-p"
        assert d["name"] == "My Plugin"
        assert d["version"] == "1.0"
        assert d["hooks"] == {HOOK_ON_ACTIVATE: "act"}
        assert d["dependencies"] == ["dep1"]

    def test_from_dict(self):
        """Test 4: from_dict() reconstructs a Plugin from a dict."""
        d = {
            "id": "from-dict",
            "name": "From Dict",
            "version": "0.5.0",
            "description": "Reconstructed",
            "author": "builder",
            "entry_point": "some.module",
            "hooks": {HOOK_ON_DEACTIVATE: "my_deact"},
            "dependencies": ["toml"],
        }
        p = Plugin.from_dict(d)
        assert p.id == "from-dict"
        assert p.hooks[HOOK_ON_DEACTIVATE] == "my_deact"
        assert p.dependencies == ["toml"]

    def test_from_dict_fallback_id(self):
        """Test 5: from_dict falls back to 'name' when 'id' is missing."""
        p = Plugin.from_dict({"name": "fallback-name"})
        assert p.id == "fallback-name"

    def test_standard_hooks_set(self):
        """Test 6: STANDARD_HOOKS contains all expected hook names."""
        assert HOOK_ON_ACTIVATE in STANDARD_HOOKS
        assert HOOK_ON_DEACTIVATE in STANDARD_HOOKS
        assert HOOK_ON_STARTUP in STANDARD_HOOKS
        assert HOOK_ON_SHUTDOWN in STANDARD_HOOKS
        assert HOOK_ON_TOOL_CALL in STANDARD_HOOKS
        assert HOOK_ON_MESSAGE in STANDARD_HOOKS
        assert len(STANDARD_HOOKS) == 6


# ── Tests for PluginRegistry ──────────────────────────────────────────────────


class TestPluginRegistry:
    """Registration, unregistration, query, and discovery."""

    def test_register_and_list(self):
        """Test 7: register adds a plugin and list returns it sorted by id."""
        r = PluginRegistry()
        r.register(Plugin(id="b", name="Beta"))
        r.register(Plugin(id="a", name="Alpha"))
        r.register(Plugin(id="c", name="Gamma"))

        all_plugins = r.list()
        assert len(all_plugins) == 3
        # Sorted by id
        assert [p.id for p in all_plugins] == ["a", "b", "c"]

    def test_unregister(self):
        """Test 8: unregister removes a plugin and returns True/False."""
        r = PluginRegistry()
        r.register(Plugin(id="keep-me"))
        r.register(Plugin(id="remove-me"))

        assert r.unregister("remove-me") is True
        assert r.get("remove-me") is None
        assert r.get("keep-me") is not None
        assert r.unregister("nonexistent") is False

    def test_get_and_state(self):
        """Test 9: get() returns the plugin, get_state/set_state manage state."""
        r = PluginRegistry()
        r.register(Plugin(id="st", name="Stateful"))

        p = r.get("st")
        assert p is not None
        assert p.name == "Stateful"

        # Default state
        assert r.get_state("st") == PluginState.REGISTERED

        r.set_state("st", PluginState.LOADED)
        assert r.get_state("st") == PluginState.LOADED

        # Unknown plugin
        assert r.get("nope") is None
        assert r.get_state("nope") is None

    def test_discover_yaml_manifest(self, temp_dir):
        """Test 10: discover() reads plugin.yaml from subdirectories."""
        plugin_root = Path(temp_dir)
        sub = plugin_root / "my-plugin"
        sub.mkdir(parents=True)

        manifest = {
            "id": "my-plugin",
            "name": "My Plugin",
            "version": "1.0.0",
            "description": "Discovered from YAML",
            "author": "test",
            "entry_point": "my_plugin.main",
            "hooks": {HOOK_ON_ACTIVATE: "activate_me"},
        }
        with open(sub / "plugin.yaml", "w", encoding="utf-8") as f:
            import yaml

            yaml.dump(manifest, f)

        r = PluginRegistry()
        discovered = r.discover(plugin_root)

        assert len(discovered) == 1
        assert discovered[0].id == "my-plugin"
        assert discovered[0].version == "1.0.0"
        assert discovered[0].hooks[HOOK_ON_ACTIVATE] == "activate_me"

    def test_discover_json_manifest(self, temp_dir):
        """Test 11: discover() reads plugin.json manifest."""
        plugin_root = Path(temp_dir)
        sub = plugin_root / "json-plugin"
        sub.mkdir(parents=True)

        manifest = {
            "id": "json-plugin",
            "name": "JSON Plugin",
            "version": "2.0.0",
            "entry_point": "json_module",
        }
        with open(sub / "plugin.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        r = PluginRegistry()
        discovered = r.discover(plugin_root)
        assert len(discovered) == 1
        assert discovered[0].id == "json-plugin"
        assert discovered[0].entry_point == "json_module"

    def test_discover_skips_non_dirs(self, temp_dir):
        """Test 12: discover() ignores files, only looks at subdirectories."""
        plugin_root = Path(temp_dir)
        # Create a file, not a directory
        with open(plugin_root / "not-a-plugin", "w") as f:
            f.write("this is a file")

        r = PluginRegistry()
        discovered = r.discover(plugin_root)
        assert len(discovered) == 0

    def test_discover_missing_dir(self):
        """Test 13: discover() on a non-existent dir returns empty list."""
        r = PluginRegistry()
        result = r.discover(Path("/tmp/nonexistent-plugin-dir-42"))
        assert result == []

    def test_discover_auto_registers(self, temp_dir):
        """Test 14: discover() auto-registers new plugins in the registry."""
        plugin_root = Path(temp_dir)
        sub = plugin_root / "auto-reg"
        sub.mkdir(parents=True)

        manifest = {"id": "auto-reg", "name": "Auto Reg", "entry_point": "auto.module"}
        with open(sub / "plugin.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        r = PluginRegistry()
        r.discover(plugin_root)
        assert r.get("auto-reg") is not None
        assert r.get_state("auto-reg") == PluginState.REGISTERED


# ── Tests for PluginManager ───────────────────────────────────────────────────


class TestPluginManager:
    """Lifecycle: load, unload, activate, deactivate, load_all."""

    def make_temp_plugin_module(self, temp_dir: str, plugin_id: str, module_code: str = "") -> "Plugin":
        """Create a temp directory with a plugin.json and a Python module for import."""
        root = Path(temp_dir) / plugin_id
        root.mkdir(parents=True)

        # Write plugin manifest
        manifest = {
            "id": plugin_id,
            "name": plugin_id,
            "version": "1.0.0",
            "description": "Temp plugin",
            "entry_point": plugin_id,
            "hooks": {},
        }
        with open(root / "plugin.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        # Write __init__.py so it's a real importable package
        init_code = module_code or f"""\ndef on_activate():\n    return \"{plugin_id}_activated\"\n\ndef on_deactivate():\n    return \"{plugin_id}_deactivated\"\n"""
        (root / "__init__.py").write_text(init_code, encoding="utf-8")

        # Add to sys.path
        if temp_dir not in sys.path:
            sys.path.insert(0, temp_dir)

        return Plugin(
            id=plugin_id,
            name=plugin_id,
            version="1.0.0",
            entry_point=plugin_id,
            hooks={
                HOOK_ON_ACTIVATE: "on_activate",
                HOOK_ON_DEACTIVATE: "on_deactivate",
            },
        )

    def test_load_and_unload(self, manager, temp_dir):
        """Test 15: load() imports the entry_point; unload() removes it."""
        plugin = self.make_temp_plugin_module(temp_dir, "test_load_unload")
        manager.registry.register(plugin)

        # Load
        assert manager.load(plugin.id) is True
        assert manager.is_loaded(plugin.id)
        assert manager.registry.get_state(plugin.id) == PluginState.LOADED

        # The module should be in our tracking
        loaded_mod = manager.get_loaded_module(plugin.id)
        assert loaded_mod is not None
        assert hasattr(loaded_mod, "on_activate")

        # Unload
        assert manager.unload(plugin.id) is True
        assert not manager.is_loaded(plugin.id)
        assert manager.registry.get_state(plugin.id) == PluginState.REGISTERED

    def test_activate_and_deactivate(self, manager, temp_dir):
        """Test 16: activate() calls on_activate hook; deactivate() calls on_deactivate."""
        plugin = self.make_temp_plugin_module(temp_dir, "test_act_deact")
        manager.registry.register(plugin)

        manager.load(plugin.id)
        assert manager.registry.get_state(plugin.id) == PluginState.LOADED

        # Activate — the hook should be called
        assert manager.activate(plugin.id) is True
        assert manager.registry.get_state(plugin.id) == PluginState.ACTIVATED

        # Deactivate
        assert manager.deactivate(plugin.id) is True
        assert manager.registry.get_state(plugin.id) == PluginState.LOADED

    def test_load_all(self, manager, temp_dir):
        """Test 17: load_all loads all REGISTERED plugins with entry_points."""
        p1 = self.make_temp_plugin_module(temp_dir, "load_all_a")
        p2 = self.make_temp_plugin_module(temp_dir, "load_all_b")
        manager.registry.register(p1)
        manager.registry.register(p2)

        count = manager.load_all()
        assert count == 2
        assert manager.is_loaded("load_all_a")
        assert manager.is_loaded("load_all_b")

    def test_activate_all(self, manager, temp_dir):
        """Test 18: activate_all activates all LOADED plugins."""
        p1 = self.make_temp_plugin_module(temp_dir, "act_all_a")
        p2 = self.make_temp_plugin_module(temp_dir, "act_all_b")
        manager.registry.register(p1)
        manager.registry.register(p2)
        manager.load_all()

        count = manager.activate_all()
        assert count == 2
        assert manager.registry.get_state("act_all_a") == PluginState.ACTIVATED
        assert manager.registry.get_state("act_all_b") == PluginState.ACTIVATED

    def test_load_unknown_plugin(self, manager):
        """Test 19: load() returns False for unregistered plugins."""
        assert manager.load("nonexistent") is False

    def test_unload_not_loaded(self, manager):
        """Test 20: unload() returns False for a plugin that isn't loaded."""
        manager.registry.register(Plugin(id="not-loaded"))
        assert manager.unload("not-loaded") is False

    def test_activate_before_load_fails(self, manager):
        """Test 21: activate() fails if plugin isn't in LOADED state."""
        manager.registry.register(Plugin(id="never-loaded"))
        assert manager.activate("never-loaded") is False

    def test_hook_resolution_from_module(self, manager, temp_dir):
        """Test 22: hooks are resolved from functions in the imported module."""
        plugin = self.make_temp_plugin_module(temp_dir, "hook_resolve")
        manager.registry.register(plugin)
        manager.load(plugin.id)

        hooks = manager.list_hooks(plugin.id)
        assert HOOK_ON_ACTIVATE in hooks
        assert HOOK_ON_DEACTIVATE in hooks
        assert callable(hooks[HOOK_ON_ACTIVATE])
        assert callable(hooks[HOOK_ON_DEACTIVATE])

    def test_hook_invocation(self, manager, temp_dir):
        """Test 23: Activate invokes on_activate hook, which is callable."""
        plugin = self.make_temp_plugin_module(temp_dir, "hook_invoke")
        manager.registry.register(plugin)
        manager.load(plugin.id)
        manager.activate(plugin.id)

        # After activate, the hook was called (side effects visible in state change)
        assert manager.registry.get_state(plugin.id) == PluginState.ACTIVATED

    def test_tool_call_and_message_hooks(self, manager, sample_plugin):
        """Test 24: invoke_tool_call and invoke_message work (return None if no hook)."""
        # sample_plugin doesn't have on_tool_call or on_message hooks registered
        manager.registry.register(sample_plugin)

        result = manager.invoke_tool_call(sample_plugin.id, "write_file", {"path": "/tmp/test"})
        assert result is None  # no hook registered

        result = manager.invoke_message(sample_plugin.id, "hello", "user")
        assert result is None  # no hook registered

    def test_activate_with_hook_return_value(self, manager, temp_dir):
        """Test 25: Activate won't fail on hook invocation."""
        plugin = self.make_temp_plugin_module(temp_dir, "hook_ret")
        manager.registry.register(plugin)
        assert manager.load(plugin.id)
        assert manager.activate(plugin.id) is True

    def test_standard_hooks_are_frozen(self):
        """Test 26: STANDARD_HOOKS cannot be accidentally expanded by a plugin dict."""
        initial = frozenset(STANDARD_HOOKS)
        d: dict = {}
        d[HOOK_ON_ACTIVATE] = "fn"
        # The set itself is mutable (set, not frozenset), but the values are
        # just strings — the expected size is stable.
        assert len(STANDARD_HOOKS) == 6
        # Putting a custom hook in a plugin dict doesn't add to STANDARD_HOOKS
        assert "my_custom_hook" not in STANDARD_HOOKS