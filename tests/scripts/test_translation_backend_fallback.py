"""Both translation surfaces must have a non-Ollama, explicitly free route."""
import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("script", ["fill_desktop_locales.py", "i18n_fill_cli_locales.py"])
def test_translation_worker_has_free_fallback(script):
    path = Path(__file__).resolve().parents[2] / "scripts" / script
    spec = importlib.util.spec_from_file_location("translation_fallback_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert any("openrouter.ai" in url and model.endswith(":free")
               for _, url, _, model in module.BACKENDS)
