"""Regression: ASI code must resolve on a fresh install, without a runtime copy.

The wrappers used to import their scripts as BARE modules from
``$OPENAMER_HOME/scripts/training``. On a fresh installation that directory
does not exist, so every ASI capability raised ModuleNotFoundError while the
same code sat unused in the checkout.

These tests pin the fixed behaviour:

1. a checkout copy resolves when the profile home has no runtime copy,
2. the profile's runtime copy wins over the checkout copy,
3. a bare sibling import inside a legacy script resolves through the same
   resolver and never through a public wrapper,
4. two profiles never share one module object,
5. a legacy script's store stays inside the profile that loaded it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.asi._training import (
    load_script_module,
    load_training_module,
    script_script,
    training_script,
)

ROOT = Path(__file__).resolve().parents[2]


def test_checkout_copy_resolves_on_a_fresh_install(tmp_path, monkeypatch):
    """No runtime copy in the profile: the shipped code is used."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    source = training_script("world_model")
    assert source == (ROOT / "scripts" / "training" / "world_model.py").resolve()

    mod = load_training_module("world_model")
    assert Path(mod.__file__) == source
    # The module reports its plain script name to callers that inspect it.
    assert mod.__name__ == "world_model"


def test_helper_scripts_resolve_from_the_checkout_too(tmp_path, monkeypatch):
    """scripts/<name>.py is resolvable on a fresh install as well."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    assert script_script("darwin_engine") == (
        ROOT / "scripts" / "darwin_engine.py"
    ).resolve()
    mod = load_script_module("darwin_engine")
    assert Path(mod.__file__) == (ROOT / "scripts" / "darwin_engine.py").resolve()


def test_runtime_copy_wins_over_the_checkout(tmp_path, monkeypatch):
    home = tmp_path / "profile"
    training = home / "scripts" / "training"
    training.mkdir(parents=True)
    (training / "world_model.py").write_text("VALUE = 42\n")
    monkeypatch.setenv("OPENAMER_HOME", str(home))

    mod = load_training_module("world_model")
    assert mod.VALUE == 42
    assert Path(mod.__file__) == (training / "world_model.py").resolve()
    # Repeated loads are cached per home+source, not per name.
    assert load_training_module("world_model") is mod


def test_two_profiles_never_share_one_module(tmp_path, monkeypatch):
    for profile, value in (("one", 1), ("two", 2)):
        home = tmp_path / profile
        training = home / "scripts" / "training"
        training.mkdir(parents=True)
        (training / "world_model.py").write_text(f"VALUE = {value}\n")
        monkeypatch.setenv("OPENAMER_HOME", str(home))
        mod = load_training_module("world_model")
        assert mod.VALUE == value
        assert Path(mod.__file__) == (training / "world_model.py").resolve()


def test_bare_sibling_import_is_scoped(tmp_path, monkeypatch):
    """A legacy bare import must not resolve to a public wrapper."""
    training = tmp_path / "scripts" / "training"
    training.mkdir(parents=True)
    (training / "world_model.py").write_text("VALUE = 42\n")
    (training / "probe.py").write_text(
        "import world_model\n"
        "def lazy():\n"
        "    from world_model import VALUE\n"
        "    return VALUE\n"
    )
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    from tools.asi import world_model as public_wrapper

    monkeypatch.setitem(sys.modules, "world_model", public_wrapper)
    before = sys.path[:]
    mod = load_training_module("probe")
    assert mod.world_model.VALUE == mod.lazy() == 42
    assert sys.modules["world_model"] is public_wrapper
    assert sys.path == before


def test_store_stays_in_the_loading_profile(tmp_path, monkeypatch):
    """The legacy world-model store must not fall back to the default install."""
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    mod = load_training_module("world_model")
    assert Path(mod.WM).parent == tmp_path / "memory"
    assert "openamer-laptop" not in mod.WM.lower()


def test_missing_module_and_invalid_names(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    with pytest.raises(ModuleNotFoundError, match="checked:"):
        training_script("openamer_missing_training_module")
    with pytest.raises(ValueError):
        training_script("../world_model")


def test_missing_dependency_names_the_source(tmp_path, monkeypatch):
    """A broken runtime copy must fail loudly, not fall back silently."""
    training = tmp_path / "scripts" / "training"
    training.mkdir(parents=True)
    source = training / "world_model.py"
    source.write_text("import openamer_intentionally_missing_training_dependency\n")
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    with pytest.raises(ImportError) as exc:
        load_training_module("world_model")
    assert str(source) in str(exc.value)
    assert "openamer_intentionally_missing_training_dependency" in str(exc.value)


def test_clean_home_real_wrappers(tmp_path):
    """Real imports and real calls against an empty temporary home."""
    code = """
from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path.cwd() / 'tools/asi'))
from tools.asi import world_model, self_model, reasoning, prediction, improvement, swarm
from tools.asi import cognition
from tools.asi_core import ASICore
home = Path(os.environ['OPENAMER_HOME']).resolve()
for wrapper, loader in [(world_model, '_import_world_model'),
                        (self_model, '_import_self_model'),
                        (reasoning, '_import_reasoning'),
                        (prediction, '_import_predict'),
                        (improvement, '_import_improve'),
                        (swarm, '_import_swarm')]:
    mod = getattr(wrapper, loader)()
    assert Path(mod.__file__).resolve().parent == Path.cwd() / 'scripts/training', mod.__file__
    assert mod is not wrapper
assert Path(world_model._import_world_model().WM).parent == home / 'memory'
assert Path(self_model._import_self_model().STATE).parent == home / 'memory/self_model'
assert Path(improvement._import_improve().T) == home / 'scripts/training'
assert world_model.stats()['total_edges'] == 0
assert reasoning.graph_stats() is not None
assert self_model.gather_state()['world_model_edges'] == 0
# The cognition cycle reached the real world-model module, not a wrapper.
assert cognition.Cognition()._facts() == []
result = ASICore()._run_imported('reasoning_loop', 'graph_stats')
assert result['success'], result
assert 'world_model' not in sys.modules
assert not (home / 'scripts/training/world_model.py').exists()
print('clean-home real imports and calls OK')
"""
    env = dict(os.environ, OPENAMER_HOME=str(tmp_path), PYTHONPATH=str(ROOT))
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
