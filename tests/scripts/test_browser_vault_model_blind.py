#!/usr/bin/env python3
"""Tests for the model-blind vault autofill path.

The property under test is not "does it fill a form" — it is "can the credential
reach the model". Every test is written against that invariant:

- the tool result must not contain the secret, not even a masked fragment
- the secret must not reach subprocess argv (the fallback path is refused)
- ``items.json`` on disk must not contain the secret in the clear
- a page on a different origin must be refused
- the classifier that already lives in this repo is the one being driven

A test that only asserted ``filled_fields == 1`` would pass while the password
sat in the result string — exactly the bug this module exists to prevent. Two of
these tests were written after a mutation run showed what the suite could NOT
catch; one is a regression for a real hang found only by executing the CLI.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

PASSWORD = "correct-horse-battery-staple-9000"
IDENTIFIER = "damir@example.com"
ORIGIN = "https://example.com"


@pytest.fixture()
def vault_env(tmp_path, monkeypatch):
    """An isolated OPENAMER_HOME so tests never touch the real vault."""
    home = tmp_path / "openamer-home"
    home.mkdir()
    monkeypatch.setenv("OPENAMER_HOME", str(home))
    import importlib

    import openamer_constants
    importlib.reload(openamer_constants)
    import agent.vault_store as vault_store
    importlib.reload(vault_store)
    vault_store.reset_vault_store_for_tests()
    yield home, vault_store
    vault_store.reset_vault_store_for_tests()


def _add_login(store, origin=ORIGIN):
    return store.get_vault_store().add_item(
        "login", "example", {"identifier": IDENTIFIER, "password": PASSWORD}, origin=origin)


# ── storage ────────────────────────────────────────────────────────────────


def test_metadata_never_contains_the_password(vault_env):
    _, vs = vault_env
    blob = json.dumps(_add_login(vs).to_dict())
    assert PASSWORD not in blob
    assert IDENTIFIER in blob  # the identifier is explicitly NOT a secret


def test_items_file_is_encrypted_at_rest(vault_env):
    home, vs = vault_env
    _add_login(vs)
    raw = (home / "vault" / "items.json").read_bytes()
    assert PASSWORD.encode() not in raw, "password stored in clear text"
    assert IDENTIFIER.encode() not in raw, "identifier stored in clear text"
    assert raw.startswith(b"OPENAMERVAULT1"), "unexpected vault format"


def test_vault_survives_a_fresh_instance(vault_env):
    _, vs = vault_env
    meta = _add_login(vs)
    assert vs.VaultStore().resolve_password(meta.id) == PASSWORD


def test_key_file_is_not_world_readable(vault_env):
    home, vs = vault_env
    _add_login(vs)
    key = home / "vault" / "key.bin"
    assert key.exists() and len(key.read_bytes()) == 32
    if os.name == "posix":
        assert not (key.stat().st_mode & 0o077), "vault key is group/world readable"


def test_key_write_is_binary_not_text_on_windows(vault_env, monkeypatch):
    """Regression: a 0x0A byte in the key must NOT become CRLF.

    Found by running the CLI in a loop: roughly one run in eight left ``key.bin``
    at 33 bytes instead of 32, and the next command reported "missing or damaged
    key". Cause: ``os.open`` on Windows defaults to TEXT mode, so a random 32-byte
    key containing 0x0A got its byte expanded to CRLF. ``os.O_BINARY`` fixes it.

    The key is forced to contain 0x0A so the test is deterministic instead of
    relying on a ~11.8% random chance.
    """
    _, vs = vault_env
    poison = b"\x0a" * 32
    real_token_bytes = vs.secrets.token_bytes

    def _fake(n):
        # Only the KEY is poisoned. The nonce must keep its real length: the blob
        # format slices a fixed _NONCE_LEN on read, so a longer nonce would make
        # the blob undecryptable — a different bug (now asserted in _encrypt).
        return poison if n == 32 else real_token_bytes(n)

    monkeypatch.setattr(vs.secrets, "token_bytes", _fake)

    v = vs.VaultStore()
    assert v._key() == poison, "key changed on the way through _key()"

    written = vs._key_path().read_bytes()
    assert written == poison, (
        f"key file is {len(written)} bytes, expected 32 — it was written in text mode "
        "and 0x0A became CRLF")
    # And it must still be usable: a vault written with this key opens again.
    meta = v.add_item("login", "x", {"identifier": "a@b.com", "password": PASSWORD},
                      origin=ORIGIN)
    assert vs.VaultStore().resolve_password(meta.id) == PASSWORD


def test_remove_item(vault_env):
    _, vs = vault_env
    v = vs.get_vault_store()
    meta = _add_login(vs, ORIGIN) if False else _add_login(vs)
    assert v.remove_item(meta.id) is True
    assert v.get_meta(meta.id) is None
    assert v.remove_item(meta.id) is False


def test_payment_item_requires_an_origin(vault_env):
    _, vs = vault_env
    with pytest.raises(vs.VaultError):
        vs.get_vault_store().add_item("payment", "visa", {"number": "4111111111111111"})


# ── origin binding ─────────────────────────────────────────────────────────


def test_normalize_origin_is_exact_and_never_a_parent_domain():
    from agent.vault_store import normalize_origin

    assert normalize_origin("https://Example.com:443/login?x=1") == "https://example.com"
    assert normalize_origin("http://example.com:80/") == "http://example.com"
    assert normalize_origin("https://example.com:8443/a") == "https://example.com:8443"
    assert normalize_origin("https://login.example.com/") == "https://login.example.com"
    assert normalize_origin("ftp://example.com") is None
    assert normalize_origin("about:blank") is None
    assert normalize_origin("") is None


def test_subdomain_does_not_satisfy_the_binding(vault_env):
    """Not a wildcard and not a parent-domain match."""
    _, vs = vault_env
    v = vs.get_vault_store()
    meta = _add_login(vs, ORIGIN)
    assert v.allowed_origins_for(meta.id) == [ORIGIN]
    assert "https://login.example.com" not in v.allowed_origins_for(meta.id)


# ── the classifier this store feeds ────────────────────────────────────────


def _controls(types=("text", "password")):
    from agent.vault_login_classifier import LoginControl

    return [LoginControl.from_dict({"index": i, "tag": "input", "type": t,
                                    "name": "username" if t == "text" else "passwd",
                                    "nonce": "n"})
            for i, t in enumerate(types)]


def test_classifier_selects_the_password_control():
    from agent.vault_login_classifier import classify_login_control, select_password_fill

    controls = _controls()
    classified = [c for c in (classify_login_control(x) for x in controls) if c]
    fills = select_password_fill(classified, PASSWORD)
    assert len(fills) == 1
    assert fills[0]["value"] == PASSWORD
    assert fills[0]["token"] == "current-password"


def test_classifier_ignores_a_page_without_a_password_field():
    from agent.vault_login_classifier import classify_login_control, select_password_fill

    controls = _controls(types=("search",))
    classified = [c for c in (classify_login_control(x) for x in controls) if c]
    assert select_password_fill(classified, PASSWORD) == []


def test_fill_js_refuses_on_origin_change_and_binds_the_nonce():
    from agent.vault_login_classifier import build_fill_js

    js = build_fill_js([{"index": 1, "token": "current-password", "value": PASSWORD}],
                       expected_origin=ORIGIN, nonce="n1")
    assert "origin_changed" in js, "fill script must refuse when the page moved"
    assert ORIGIN in js
    assert "n1" in js, "fill must be bound to this inspection's nonce"


def test_inspection_js_carries_no_secret_and_stamps_the_nonce():
    from agent.vault_login_classifier import build_inspection_js

    js = build_inspection_js("deadbeef")
    assert PASSWORD not in js
    assert "deadbeef" in js


# ── the tool: model-blindness end to end ───────────────────────────────────


def _fake_supervisor(origin, controls, fill_response):
    """A supervisor stub answering inspection and fill without a browser."""

    class _Sup:
        def __init__(self):
            self.seen = []

        def evaluate_runtime(self, expression, **kw):
            self.seen.append(expression)
            if "data-openamer-vault-slot" in expression and "JSON.stringify(out)" in expression:
                return {"ok": True, "result": json.dumps(controls)}
            if "window.location.href" in expression:
                return {"ok": True, "result": origin}
            return {"ok": True, "result": json.dumps(fill_response)}

    return _Sup()


def _patch(monkeypatch, sup):
    from tools import browser_vault_tool as bvt

    monkeypatch.setattr(bvt, "_supervisor_for", lambda task_id: sup)
    monkeypatch.setattr(bvt, "_focus_bound_origin", lambda task_id, origin: origin)
    monkeypatch.setattr(bvt, "_browser_vault_check", lambda: True)


def _classified_controls():
    from agent.vault_login_classifier import LoginControl

    return [
        {"index": 0, "tag": "input", "type": "text", "name": "username", "nonce": "X"},
        {"index": 1, "tag": "input", "type": "password", "name": "passwd", "nonce": "X"},
    ]


def test_fill_result_never_contains_the_secret(vault_env, monkeypatch):
    home, vs = vault_env
    meta = _add_login(vs)
    _patch(monkeypatch, _fake_supervisor(f"{ORIGIN}/login", _classified_controls(),
                                         {"filled": 1}))

    from tools import browser_vault_tool as bvt
    out = json.loads(bvt.browser_vault_fill(meta.id, task_id="t"))
    assert out["filled_fields"] == 1
    blob = json.dumps(out)
    assert PASSWORD not in blob, "the credential leaked into the tool result"
    assert IDENTIFIER not in blob, "the identifier leaked into the tool result"


def test_fill_is_refused_without_a_supervisor(vault_env, monkeypatch):
    """No supervisor -> typed refusal. The CLI fallback must NOT be used for secrets."""
    home, vs = vault_env
    meta = _add_login(vs)

    from tools import browser_vault_tool as bvt
    monkeypatch.setattr(bvt, "_supervisor_for", lambda task_id: None)
    monkeypatch.setattr(bvt, "_focus_bound_origin", lambda task_id, origin: None)
    monkeypatch.setattr(bvt, "_eval_non_secret",
                        lambda task_id, expr: {"success": True, "result": json.dumps(_classified_controls())}
                        if "data-openamer-vault-slot" in expr
                        else {"success": True, "result": f"{ORIGIN}/login"})

    out = json.loads(bvt.browser_vault_fill(meta.id, task_id="t"))
    assert out["success"] is False
    assert out["error_type"] == "supervisor_required"
    assert PASSWORD not in json.dumps(out)


def test_secret_is_registered_with_the_redaction_boundary(vault_env, monkeypatch):
    """After a fill, a later snapshot of the page cannot echo the password back."""
    home, vs = vault_env
    meta = _add_login(vs)
    _patch(monkeypatch, _fake_supervisor(f"{ORIGIN}/login", _classified_controls(), {"filled": 1}))

    from agent.redact import redact_sensitive_text, registered_redaction_count
    from tools import browser_vault_tool as bvt
    bvt.browser_vault_fill(meta.id, task_id="t")

    assert registered_redaction_count() >= 1
    assert PASSWORD not in redact_sensitive_text(f"the page shows {PASSWORD} in a debug field")


def test_wrong_origin_returns_a_refusal_not_a_fill(vault_env, monkeypatch):
    home, vs = vault_env
    meta = _add_login(vs, ORIGIN)
    _patch(monkeypatch, _fake_supervisor("https://phishing.example.net/login",
                                         _classified_controls(), {"filled": 1}))

    from tools import browser_vault_tool as bvt
    # The page really is on another origin: focus must not be allowed to claim it.
    monkeypatch.setattr(bvt, "_focus_bound_origin", lambda task_id, origin: None)
    out = json.loads(bvt.browser_vault_fill(meta.id, task_id="t"))
    assert out["success"] is False
    assert out["error_type"] == "origin_mismatch"


def test_origin_change_during_fill_is_reported(vault_env, monkeypatch):
    home, vs = vault_env
    meta = _add_login(vs)
    _patch(monkeypatch, _fake_supervisor(f"{ORIGIN}/login", _classified_controls(),
                                         {"refused": "origin_changed", "found": "https://x.test"}))

    from tools import browser_vault_tool as bvt
    out = json.loads(bvt.browser_vault_fill(meta.id, task_id="t"))
    assert out["success"] is False and out["error_type"] == "origin_changed"


def test_list_action_never_returns_a_password(vault_env):
    _, vs = vault_env
    _add_login(vs)

    from tools import browser_vault_tool as bvt
    out = json.loads(bvt.browser_vault_list())
    assert out["success"] is True and len(out["items"]) == 1
    assert PASSWORD not in json.dumps(out)
    assert out["items"][0]["identifier"] == IDENTIFIER


def test_save_login_refuses_when_the_session_cannot_prompt(vault_env, monkeypatch):
    """Cron/gateway/API sessions have no masked prompt: a typed refusal, no hang."""
    from agent.vault_prompt import clear_prompt_callback
    from tools import browser_vault_tool as bvt

    clear_prompt_callback()
    monkeypatch.setattr(bvt, "_current_origin", lambda task_id: f"{ORIGIN}/login")
    out = json.loads(bvt.browser_vault_save_login(task_id="t"))
    assert out["success"] is False
    assert out["error_type"] == "prompt_unavailable"


def test_every_refusal_is_typed_and_never_leaks(vault_env, monkeypatch):
    """The real no-browser case: no CDP session at all.

    Found live: this path returned a refusal with NO ``error_type``, so a caller
    could not tell "no browser" from "bad handle".
    """
    home, vs = vault_env
    meta = _add_login(vs)

    from tools import browser_vault_tool as bvt
    monkeypatch.setattr(bvt, "_supervisor_for", lambda task_id: None)
    monkeypatch.setattr(bvt, "_current_origin", lambda task_id: None)
    monkeypatch.setattr(bvt, "_focus_bound_origin", lambda task_id, origin: None)

    out = json.loads(bvt.browser_vault_fill(meta.id, task_id="t"))
    assert out["success"] is False
    assert out.get("error_type") == "no_page", out
    assert PASSWORD not in json.dumps(out)


def test_unknown_handle_is_reported_clearly(vault_env, monkeypatch):
    from tools import browser_vault_tool as bvt

    monkeypatch.setattr(bvt, "_current_origin", lambda task_id: f"{ORIGIN}/login")
    out = json.loads(bvt.browser_vault_fill("nope", task_id="t"))
    assert out["success"] is False and out["error_type"] == "unknown_handle"


# ── CLI: the piped-stdin hang ──────────────────────────────────────────────


def test_vault_cli_add_does_not_hang_when_stdin_is_piped(tmp_path):
    """Regression: `secrets vault add` under a pipe blocked until timeout.

    Found by RUNNING it, not by reading it. The masked prompt falls back to
    ``getpass.getpass`` for non-TTY streams, and on Windows getpass reads the
    CONSOLE instead of stdin — so a piped credential never arrived and the
    command hung. No unit test could see that; only a real subprocess with a
    real pipe can. A timeout here IS the assertion.
    """
    home = tmp_path / "cli-home"
    home.mkdir()
    env = {**os.environ, "OPENAMER_HOME": str(home), "PYTHONPATH": str(REPO)}
    proc = subprocess.run(
        [sys.executable, "-m", "openamer_cli.main", "secrets", "vault", "add", ORIGIN],
        input=f"{IDENTIFIER}\n{PASSWORD}\n",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(REPO), timeout=180,
    )
    assert proc.returncode == 0, f"exit={proc.returncode}\n{proc.stdout[-600:]}\n{proc.stderr[-600:]}"
    assert "Handle:" in proc.stdout, proc.stdout[-600:]

    listing = subprocess.run(
        [sys.executable, "-m", "openamer_cli.main", "secrets", "vault", "list"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(REPO), timeout=180,
    )
    assert listing.returncode == 0
    assert IDENTIFIER in listing.stdout        # the identifier is not a secret
    assert PASSWORD not in listing.stdout

    blob = (home / "vault" / "items.json").read_bytes()
    assert PASSWORD.encode() not in blob, "credential written in clear text"
