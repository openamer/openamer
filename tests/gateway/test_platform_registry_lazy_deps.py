"""The lazy dependency installer a platform entry can carry.

Measured live 2026-10-11: the feishu platform failed to load on every gateway
start with

    PlatformEntry.__init__() got an unexpected keyword argument 'ensure_deps_fn'

because a port dropped the field from PlatformEntry while the plugin kept
passing it. check_fn (passive) and ensure_deps_fn (active) are one mechanism:
the first is called from status displays and config loading, so it must never
install; the second is the single place allowed to, and it runs from
create_adapter() when check_fn says the deps are missing (#79812).
"""

from __future__ import annotations

import pytest

from gateway.platform_registry import PlatformEntry, _deps_ready


def _entry(check, ensure=None):
    return PlatformEntry(
        name="t", label="T", adapter_factory=lambda cfg: None,
        check_fn=check, **({"ensure_deps_fn": ensure} if ensure else {}),
    )


class TestField:
    def test_entry_accepts_the_field(self):
        """The TypeError that stopped feishu from loading must stay gone."""
        state = {"ready": False}
        e = _entry(lambda: state["ready"], lambda: state.update(ready=True) or True)
        assert e.ensure_deps_fn is not None

    def test_field_defaults_to_none(self):
        """A platform without an installer keeps working unchanged."""
        assert _entry(lambda: True).ensure_deps_fn is None


class TestDepsReady:
    def test_present_deps_never_call_the_installer(self):
        called = []
        e = _entry(lambda: True, lambda: called.append(1) or True)
        assert _deps_ready(e) is True
        assert called == [], "check_fn said True - the installer must not run"

    def test_missing_deps_trigger_the_installer(self):
        state = {"ready": False}
        e = _entry(lambda: state["ready"], lambda: state.update(ready=True) or True)
        assert _deps_ready(e) is True
        assert state["ready"] is True

    def test_installer_claim_is_not_trusted(self):
        """An installer that reports success while check_fn still fails does not pass."""
        e = _entry(lambda: False, lambda: True)
        assert _deps_ready(e) is False

    def test_no_installer_keeps_the_missing_verdict(self):
        assert _deps_ready(_entry(lambda: False)) is False

    def test_a_raising_installer_is_not_fatal(self):
        def boom():
            raise RuntimeError("pip died")
        assert _deps_ready(_entry(lambda: False, boom)) is False


class TestRegistryIntegration:
    def test_feishu_registers_with_ensure_deps_fn(self):
        """End-to-end: the shipped plugin registers and lands in the registry."""
        import importlib.util
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        plugin = root / "plugins" / "platforms" / "feishu" / "adapter.py"
        if not plugin.is_file():
            pytest.skip("feishu plugin not present in this tree")

        sys.path.insert(0, str(plugin.parent))
        spec = importlib.util.spec_from_file_location("feishu_adapter", plugin)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["feishu_adapter"] = mod          # before exec_module: @dataclass needs it
        spec.loader.exec_module(mod)

        from gateway.platform_registry import PlatformRegistry

        reg = PlatformRegistry()

        class Ctx:
            def register_platform(self, **kw):
                # PlatformEntry(**kw) is exactly where the port used to raise
                reg._entries["feishu"] = PlatformEntry(**kw)

        mod.register(Ctx())
        assert "feishu" in reg._entries
        assert reg._entries["feishu"].ensure_deps_fn is not None
