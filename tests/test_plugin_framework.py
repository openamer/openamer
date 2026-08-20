"""Tests for openamer_cli.plugin_framework — Plugin Composability Framework."""

import json
import pathlib
import sys
import tempfile
from pathlib import Path

import pytest

from openamer_cli.plugin_framework import (
    DEFAULT_PLUGIN_DIRS,
    PluginHook,
    PluginHost,
    PluginRecord,
    PluginRegistry,
    PluginSpec,
    PluginState,
    plugin_context,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_plugin_dir():
    """Create a temporary directory for plugin discovery tests."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def registry():
    """Create an empty PluginRegistry."""
    return PluginRegistry()


@pytest.fixture
def host(temp_plugin_dir):
    """Create a PluginHost with a temp plugin directory."""
    return PluginHost(plugin_dirs=[temp_plugin_dir])


# ── Tests for PluginSpec ──────────────────────────────────────────────────────


class TestPluginSpec:
    def test_default_creation(self):
        spec = PluginSpec(name="test-plugin")
        assert spec.name == "test-plugin"
        assert spec.version == "0.1.0"
        assert spec.description == ""
        assert spec.author == ""
        assert spec.dependencies == []
        assert spec.hooks == []

    def test_full_creation(self):
        spec = PluginSpec(
            name="my-plugin",
            version="2.0.0",
            description="Does stuff",
            author="Test Author",
            entry_point="my_module:handler",
            dependencies=["requests>=2.0"],
            hooks=[PluginHook.PRE_TOOL_CALL, PluginHook.POST_LLM_CALL],
        )
        assert spec.name == "my-plugin"
        assert spec.version == "2.0.0"
        assert len(spec.hooks) == 2
        assert PluginHook.PRE_TOOL_CALL in spec.hooks
        assert PluginHook.POST_LLM_CALL in spec.hooks

    def test_to_dict(self):
        spec = PluginSpec(
            name="p1",
            version="1.0",
            description="desc",
            author="me",
            dependencies=["dep1"],
            hooks=[PluginHook.ON_SESSION_START],
        )
        d = spec.to_dict()
        assert d["name"] == "p1"
        assert d["hooks"] == ["on_session_start"]

    def test_from_dict(self):
        d = {
            "name": "from-json",
            "version": "3.0",
            "description": "Imported",
            "author": "JSON",
            "hooks": ["pre_tool_call", "post_tool_call"],
        }
        spec = PluginSpec.from_dict(d)
        assert spec.name == "from-json"
        assert spec.version == "3.0"
        assert PluginHook.PRE_TOOL_CALL in spec.hooks
        assert PluginHook.POST_TOOL_CALL in spec.hooks

    def test_from_dict_unknown_hook(self):
        """Unknown hooks should be silently ignored."""
        d = {"name": "test", "hooks": ["pre_tool_call", "non_existent_hook"]}
        spec = PluginSpec.from_dict(d)
        assert len(spec.hooks) == 1
        assert spec.hooks[0] == PluginHook.PRE_TOOL_CALL


# ── Tests for PluginHook ──────────────────────────────────────────────────────


class TestPluginHook:
    def test_all_members_present(self):
        values = {h.value for h in PluginHook}
        assert "pre_tool_call" in values
        assert "post_tool_call" in values
        assert "pre_llm_call" in values
        assert "post_llm_call" in values
        assert "on_session_start" in values
        assert "on_session_end" in values

    def test_unique_values(self):
        values = [h.value for h in PluginHook]
        assert len(values) == len(set(values))


# ── Tests for plugin_context decorator ────────────────────────────────────────


class TestPluginContextDecorator:
    def test_decorator_sets_attr(self):
        @plugin_context(name="test-hook", version="1.0", hooks=[PluginHook.PRE_TOOL_CALL])
        def my_hook(tool_name, **kwargs):
            return tool_name

        from openamer_cli.plugin_framework import PLUGIN_ATTR, HOOK_ATTR

        assert hasattr(my_hook, PLUGIN_ATTR)
        assert hasattr(my_hook, HOOK_ATTR)
        spec = getattr(my_hook, PLUGIN_ATTR)
        assert spec.name == "test-hook"
        assert spec.version == "1.0"
        assert PluginHook.PRE_TOOL_CALL in spec.hooks

    def test_decorator_no_hooks(self):
        @plugin_context(name="bare")
        def bare_fn():
            pass

        from openamer_cli.plugin_framework import PLUGIN_ATTR, HOOK_ATTR

        assert hasattr(bare_fn, PLUGIN_ATTR)
        spec = getattr(bare_fn, PLUGIN_ATTR)
        assert spec.name == "bare"

    def test_decorator_default_name(self):
        """If no name given, should use function __name__."""

        @plugin_context()
        def my_auto_named_fn():
            pass

        from openamer_cli.plugin_framework import PLUGIN_ATTR

        spec = getattr(my_auto_named_fn, PLUGIN_ATTR)
        assert spec.name == "my_auto_named_fn"


# ── Tests for PluginRegistry ──────────────────────────────────────────────────


class TestPluginRegistry:
    def test_register_and_list(self, registry):
        spec = PluginSpec(name="p1", version="1.0")
        registry.register(spec)
        plugins = registry.list_plugins()
        assert len(plugins) == 1
        assert plugins[0][0] == "p1"
        assert plugins[0][1] == PluginState.DISABLED

    def test_register_state_loaded(self, registry):
        spec = PluginSpec(name="p1")
        registry.register(spec, module=sys.modules[__name__])
        record = registry.get_record("p1")
        assert record is not None
        assert record.state == PluginState.LOADED

    def test_unregister(self, registry):
        spec = PluginSpec(name="p1")
        registry.register(spec)
        assert registry.unregister("p1") is True
        assert registry.get_record("p1") is None

    def test_unregister_nonexistent(self, registry):
        assert registry.unregister("nope") is False

    def test_enable_disable(self, registry):
        spec = PluginSpec(name="p1", hooks=[PluginHook.PRE_TOOL_CALL])
        registry.register(spec)
        assert registry.enable("p1") is True
        assert registry.is_enabled("p1") is True
        assert registry.disable("p1") is True
        assert registry.is_enabled("p1") is False

    def test_enable_unknown(self, registry):
        assert registry.enable("unknown") is False

    def test_list_exclude_disabled(self, registry):
        registry.register(PluginSpec(name="a"))
        registry.register(PluginSpec(name="b"))
        registry.enable("b")
        plugins = registry.list_plugins(include_disabled=False)
        assert len(plugins) == 1
        assert plugins[0][0] == "b"

    def test_get_record_nonexistent(self, registry):
        assert registry.get_record("nope") is None

    def test_get_hooks_for(self, registry):
        spec = PluginSpec(
            name="hooked",
            hooks=[PluginHook.PRE_TOOL_CALL, PluginHook.POST_LLM_CALL],
        )
        registry.register(spec)
        registry.enable("hooked")
        hooks = registry.get_hooks_for(PluginHook.PRE_TOOL_CALL)
        assert "hooked" in hooks
        assert "hooked" in registry.get_hooks_for(PluginHook.POST_LLM_CALL)
        assert "hooked" not in registry.get_hooks_for(PluginHook.ON_SESSION_START)

    def test_double_register(self, registry):
        """Registering the same name twice updates the record."""
        registry.register(PluginSpec(name="dup", version="1.0"))
        registry.register(PluginSpec(name="dup", version="2.0"))
        record = registry.get_record("dup")
        assert record is not None
        assert record.spec.version == "2.0"


# ── Tests for PluginRegistry discover ─────────────────────────────────────────


class TestPluginDiscovery:
    def test_discover_empty_dir(self, registry, temp_plugin_dir):
        specs = registry.discover(extra_dirs=[temp_plugin_dir])
        assert specs == []

    def test_discover_json_manifest(self, registry, temp_plugin_dir):
        plugin_dir = temp_plugin_dir / "my-plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "plugin.json"
        manifest.write_text(
            json.dumps({
                "name": "my-plugin",
                "version": "2.0",
                "description": "Test",
                "hooks": ["pre_tool_call"],
            })
        )
        specs = registry.discover(extra_dirs=[temp_plugin_dir])
        assert len(specs) == 1
        assert specs[0].name == "my-plugin"
        assert specs[0].version == "2.0"

    def test_discover_yaml_manifest(self, registry, temp_plugin_dir):
        plugin_dir = temp_plugin_dir / "yaml-plugin"
        plugin_dir.mkdir()
        manifest = plugin_dir / "plugin.yaml"
        manifest.write_text("name: yaml-plugin\nversion: 1.5\n")
        specs = registry.discover(extra_dirs=[temp_plugin_dir])
        assert len(specs) == 1
        assert specs[0].name == "yaml-plugin"

    def test_discover_init_only(self, registry, temp_plugin_dir):
        """A directory with only __init__.py should still be discovered."""
        plugin_dir = temp_plugin_dir / "bare-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("# empty")
        specs = registry.discover(extra_dirs=[temp_plugin_dir])
        assert len(specs) == 1
        assert specs[0].name == "bare-plugin"


# ── Tests for PluginRegistry save/load state ──────────────────────────────────


class TestPluginStatePersistence:
    def test_save_and_load_state(self, registry, temp_plugin_dir):
        registry.register(PluginSpec(name="p1"))
        registry.register(PluginSpec(name="p2"))
        registry.enable("p1")

        state_file = temp_plugin_dir / "state.json"
        registry.save_state(state_file)
        assert state_file.is_file()

        # Create a fresh registry and load state
        registry2 = PluginRegistry()
        registry2.register(PluginSpec(name="p1"))
        registry2.register(PluginSpec(name="p2"))
        registry2.load_state(state_file)
        assert registry2.is_enabled("p1") is True
        assert registry2.is_enabled("p2") is False

    def test_load_missing_file(self, registry):
        """Loading from a missing file should be a no-op."""
        registry.load_state(Path("/nonexistent/state.json"))
        assert len(registry.list_plugins()) == 0


# ── Tests for PluginHost ──────────────────────────────────────────────────────


class TestPluginHost:
    def test_load_plugin_from_directory(self, host, temp_plugin_dir):
        """Load a plugin from a properly structured directory."""
        plugin_dir = temp_plugin_dir / "test-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text(
            """
from openamer_cli.plugin_framework import plugin_context, PluginHook

@plugin_context(name="test-plugin", version="1.0", hooks=[PluginHook.PRE_TOOL_CALL])
def my_hook(tool_name, **kwargs):
    return tool_name
"""
        )
        manifest = plugin_dir / "plugin.json"
        manifest.write_text(
            json.dumps({
                "name": "test-plugin",
                "version": "1.0",
                "description": "Test plugin",
                "hooks": ["pre_tool_call"],
            })
        )

        spec = host.load_plugin(plugin_dir)
        assert spec is not None
        assert spec.name == "test-plugin"
        assert spec.version == "1.0"
        assert PluginHook.PRE_TOOL_CALL in spec.hooks

    def test_load_plugin_no_init(self, host, temp_plugin_dir):
        """A directory without __init__.py should still register from manifest."""
        plugin_dir = temp_plugin_dir / "no-init"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(
            json.dumps({"name": "no-init", "version": "0.1"})
        )
        spec = host.load_plugin(plugin_dir)
        assert spec is not None
        assert spec.name == "no-init"

    def test_load_plugin_no_manifest(self, host, temp_plugin_dir):
        """A directory without any manifest should not load."""
        plugin_dir = temp_plugin_dir / "empty"
        plugin_dir.mkdir()
        spec = host.load_plugin(plugin_dir)
        assert spec is None

    def test_start_stop(self, host):
        """Host start/stop should mark plugins appropriately."""
        host.start()
        host.stop()
        # After stop, no plugins should be enabled
        for name, state, _ver in host.registry.list_plugins():
            assert state != PluginState.ENABLED

    def test_reload_all(self, host, temp_plugin_dir):
        """Reload all should not crash on empty host."""
        count = host.reload()
        assert count == 0

    def test_reload_unknown(self, host):
        """Reloading unknown plugin should return 0."""
        count = host.reload(name="nonexistent")
        assert count == 0

    def test_watcher_start_stop(self, host):
        """Starting and stopping the file watcher should not raise."""
        host.start_watcher(interval=1.0)
        host.stop_watcher()
        # Starting twice should not crash
        host.start_watcher(interval=0.5)
        host.stop_watcher()

    def test_install_file_plugin(self, host, temp_plugin_dir):
        """Install a single .py file as a plugin."""
        src = temp_plugin_dir / "my_simple_plugin.py"
        src.write_text(
            """
from openamer_cli.plugin_framework import plugin_context

@plugin_context(name="simple-plugin")
def my_func():
    return 42
"""
        )
        target = temp_plugin_dir / "installed"
        name = host.install(src, target_dir=target)
        assert name == "my_simple_plugin"
        record = host.registry.get_record("my_simple_plugin")
        assert record is not None

    def test_install_directory_plugin(self, host, temp_plugin_dir):
        """Install a directory plugin."""
        src = temp_plugin_dir / "src-plugin"
        src.mkdir()
        (src / "__init__.py").write_text("# test")
        (src / "plugin.json").write_text(
            json.dumps({"name": "src-plugin", "version": "1.0"})
        )
        target = temp_plugin_dir / "installed"
        name = host.install(src, target_dir=target)
        assert name == "src-plugin"

    def test_compute_dir_hash(self, temp_plugin_dir):
        """Directory hash should return a consistent hex string."""
        (temp_plugin_dir / "a.py").write_text("x = 1")
        h1 = PluginHost._compute_dir_hash(temp_plugin_dir)
        assert len(h1) == 32  # md5 hex
        (temp_plugin_dir / "b.py").write_text("y = 2")
        h2 = PluginHost._compute_dir_hash(temp_plugin_dir)
        assert h2 != h1  # changed content changes hash


# ── Tests for invoke_hooks ────────────────────────────────────────────────────


class TestInvokeHooks:
    def test_invoke_hooks_empty(self, registry):
        results = registry.invoke_hooks(PluginHook.PRE_TOOL_CALL, tool_name="test")
        assert results == []

    def test_invoke_hooks_with_results(self, registry):
        """Test registering hook functions and invoking them."""
        # Create a real plugin record with registered function
        from openamer_cli.plugin_framework import PluginRecord

        spec = PluginSpec(
            name="hook-test",
            hooks=[PluginHook.PRE_TOOL_CALL],
        )
        record = PluginRecord(
            spec=spec,
            state=PluginState.ENABLED,
            registered_functions={
                "pre_tool_call": lambda tool_name, **kw: f"hooked:{tool_name}"
            },
        )
        registry._records["hook-test"] = record
        registry._rebuild_hook_index()

        results = registry.invoke_hooks(PluginHook.PRE_TOOL_CALL, tool_name="search")
        assert len(results) == 1
        assert results[0] == "hooked:search"

    def test_invoke_hooks_disabled_skipped(self, registry):
        """Hooks from disabled plugins should be skipped."""
        spec = PluginSpec(name="disabled-hook", hooks=[PluginHook.PRE_TOOL_CALL])
        record = PluginRecord(
            spec=spec,
            state=PluginState.DISABLED,
            registered_functions={"pre_tool_call": lambda **kw: "should not run"},
        )
        registry._records["disabled-hook"] = record
        registry._rebuild_hook_index()

        results = registry.invoke_hooks(PluginHook.PRE_TOOL_CALL)
        assert results == []

    def test_invoke_hooks_error_handling(self, registry):
        """A failing hook should not crash the invocation."""
        spec = PluginSpec(name="crashy", hooks=[PluginHook.PRE_TOOL_CALL])

        def failing_fn(**kwargs):
            raise RuntimeError("oops")

        record = PluginRecord(
            spec=spec,
            state=PluginState.ENABLED,
            registered_functions={"pre_tool_call": failing_fn},
        )
        registry._records["crashy"] = record
        registry._rebuild_hook_index()

        results = registry.invoke_hooks(PluginHook.PRE_TOOL_CALL)
        assert results == []
        # The plugin should now be in error state
        assert registry.get_record("crashy").state == PluginState.ERROR