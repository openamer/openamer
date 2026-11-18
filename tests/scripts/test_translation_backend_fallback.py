"""Both translation surfaces must have a non-Ollama, explicitly free route.

The intent is that every locale-fill worker can keep working without paid or
rate-limited credentials — OpenRouter `:free`, keyless `NO_AUTH`, or any
other `:free` route. OpenRouter itself sat first for months and answered every
request with `free-models-per-day-high-balance`, so a hard-coded `openrouter.ai`
assertion would pass while the worker starves.
"""
import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.parametrize(
    "script", ["fill_desktop_locales.py", "i18n_fill_cli_locales.py"]
)


def _has_free_fallback(module) -> bool:
    for name, url, keyenv, model in module.BACKENDS:
        if "openrouter.ai" in url and model.endswith(":free"):
            return True
        if "NO_AUTH" in keyenv or "NO_AUTH" in name or ":free" in model:
            return True
    return False


def test_translation_worker_has_free_fallback(script):
    path = Path(__file__).resolve().parents[2] / "scripts" / script
    spec = importlib.util.spec_from_file_location("translation_fallback_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _has_free_fallback(module), f"{script} has no free, non-Ollama fallback backend"
