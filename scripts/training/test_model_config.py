#!/usr/bin/env python3
"""Guard test for the model resolver — the single source of truth for routing.

Regression target (live 2026-09-11): `endpoint_for_default()` only knew
`openrouter` and fell through to local Ollama for every other provider, so a
cloud model name was POSTed to `http://localhost:11434/v1/chat/completions`
and every reasoning script (`reasoning_loop`, `deep_task`, `analogy_engine`,
`active_learn`) died with `HTTP Error 404: Not Found`.

These tests pin the provider→endpoint mapping and the auth-header contract so
that class of mis-routing cannot silently return.
"""
import importlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
mc = importlib.import_module("model_config")


def _with_provider(monkeypatch_provider, monkeypatch_env, fn):
    """Run fn() with a patched provider + env, restoring afterwards."""
    saved = (mc.resolve_provider, mc._env)
    mc.resolve_provider = lambda: monkeypatch_provider
    mc._env = lambda name: monkeypatch_env.get(name, "")
    try:
        return fn()
    finally:
        mc.resolve_provider, mc._env = saved


def test_cloud_provider_routes_to_ollama_base_url():
    """ollama-cloud must never fall back to the local port."""
    base = _with_provider("ollama-cloud", {"OLLAMA_BASE_URL": "https://ollama.com/v1"}, mc.endpoint_for_default)
    assert base == "https://ollama.com", base
    assert "localhost" not in base


def test_token_harbor_routes_to_its_own_base_url():
    base = _with_provider("custom:token-harbor-(free)",
                          {"TOKENHARBOR_BASE_URL": "https://tokenharbor.ai/v1"},
                          mc.endpoint_for_default)
    assert base == "https://tokenharbor.ai", base


def test_openrouter_base_has_no_trailing_v1():
    """Callers append '/v1/chat/completions' — the base must not carry its own /v1."""
    base = _with_provider("openrouter", {}, mc.endpoint_for_default)
    assert base == "https://openrouter.ai/api", base


def test_local_provider_still_reaches_local_ollama():
    """A genuinely local provider keeps the localhost fallback."""
    base = _with_provider("custom:local-(127.0.0.1:11434)", {}, mc.endpoint_for_default)
    assert base == "http://localhost:11434", base


def test_auth_header_present_for_cloud_from_env_file():
    """Keys come from the env OR the profile .env, so scripts work outside the shell."""
    h = _with_provider("ollama-cloud", {"OLLAMA_API_KEY": "sk-test"}, mc.auth_headers)
    assert h.get("Authorization") == "Bearer sk-test", h


def test_auth_header_empty_for_local():
    """Local Ollama needs no Authorization header."""
    h = _with_provider("custom:local-(127.0.0.1:11434)", {}, mc.auth_headers)
    assert h == {}, h


def test_chat_default_posts_to_v1_path(monkeypatch=None):
    """chat_default must target <base>/v1/chat/completions (the '/v1' lives here,
    not in the base) — the exact bug that produced the 404."""
    import inspect
    src = inspect.getsource(mc.chat_default)
    assert 'endpoint_for_default() + "/v1/chat/completions"' in src, src[:400]
    assert "auth_headers()" in src


# --- thinking-trace post-processing (a truncated cloud reply must not leak CoT) ---

_TRACE_CASES = [
    ("We need answer in German. Need evaluate the previous answer.", True, "meta-opener"),
    ("1. **Analyze** the request\nblah", True, "list-opener"),
    ("The user asks about skills. So the final should be short.", True, "meta-mid"),
    ("", True, "empty"),
    ("Eine Woche hat sieben Tage.", False, "clean-answer"),
    ("Die Hauptstadt von Frankreich ist Paris.", False, "clean-answer-2"),
    ("Thinking... </think>Berlin ist die Hauptstadt.", False, "tagged-answer"),
]


def test_meta_rambling_classifier_both_directions():
    """Every trace case rejects; every real answer passes."""
    wrong = [n for t, want, n in _TRACE_CASES if mc._is_meta_rambling(t) != want]
    assert not wrong, f"misclassified: {wrong}"


def test_last_clean_block_recovers_answer_from_truncated_trace():
    trace = "We need answer.\n\n1. Analyze\n2. Decide\n\nDie Antwort lautet zweiundvierzig."
    assert mc._last_clean_block(trace) == "Die Antwort lautet zweiundvierzig."


def test_strip_thinking_keeps_text_after_close_tag():
    assert mc._strip_thinking("Thinking... </think>Berlin.") == "Berlin."
    assert mc._strip_thinking("Eine Woche hat sieben Tage.") == "Eine Woche hat sieben Tage."
