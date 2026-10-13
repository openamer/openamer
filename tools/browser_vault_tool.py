#!/usr/bin/env python3
"""Model-blind browser autofill from the local credential vault.

One agent-facing tool, ``browser_vault``, with three actions: ``list``,
``save_login``, ``fill``.

THE INVARIANT THIS TOOL EXISTS FOR
    A credential must never reach the model's context. Three separate
    prohibitions, all enforced here:

    1. The value is never returned. Results carry counts and metadata only.
    2. The value is never placed in ``argv``. There is deliberately NO CLI
       ``eval`` fallback for the fill — that path would put the credential in a
       process listing. No supervisor socket, no fill: a typed refusal instead.
    3. The value is registered with the redaction boundary
       (:func:`agent.redact.register_redaction_value`) so a LATER browser call
       that echoes the page back cannot re-expose it.

    The page-side machinery is ``agent.vault_login_classifier``, which already
    existed in this repo (with the identifier/OTP/checkout classifiers and the
    nonce-stamped inspection + fill JS). This tool is the missing other half: the
    store that feeds it and the agent-facing surface.
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any, Dict, List, Optional

from tools.browser_supervisor import SUPERVISOR_REGISTRY
from tools.registry import registry

logger = logging.getLogger(__name__)

_FILL_TIMEOUT_S = 20.0


def _browser_vault_check() -> bool:
    """Availability: a reachable CDP endpoint — the same gate ``browser_dialog`` uses.

    The vault is always local; what can be missing is a supervised browser to
    fill. Gating on a handle existing would hide the feature from the agent that
    has to create the first one.
    """
    try:
        from tools.browser_cdp_tool import _browser_cdp_check  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("browser_vault check: browser_cdp_tool import failed: %s", exc)
        return False
    try:
        return bool(_browser_cdp_check())
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("browser_vault check: cdp probe failed: %s", exc)
        return False


def _supervisor_for(task_id: str):
    """The supervisor attached to ``task_id``, or None.

    Never starts one: attaching is the browser toolset's job, and silently
    launching a browser here would be a side effect nobody asked for.
    """
    try:
        return SUPERVISOR_REGISTRY.get(task_id)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("browser_vault: supervisor lookup failed: %s", exc)
        return None


def _parse(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return raw
    return raw


def _eval_non_secret(task_id: str, expression: str) -> Dict[str, Any]:
    """Evaluate JS carrying NO secret. Supervisor first, ``_browser_eval`` fallback.

    The fallback is the repo's own eval path (what ``browser_console`` uses), so
    it honours the eval-policy and SSRF guards. It is reached only for the
    inspection and the origin read — never for the fill.
    """
    supervisor = _supervisor_for(task_id)
    if supervisor is not None:
        result = supervisor.evaluate_runtime(expression, timeout=_FILL_TIMEOUT_S)
        if result.get("ok"):
            return {"success": True, "result": result.get("result")}
        return {"success": False, "error": str(result.get("error") or "eval failed")}

    from tools.browser_tool import _browser_eval

    result = _browser_eval(expression, task_id)
    parsed = _parse(result) if isinstance(result, str) else result
    if isinstance(parsed, dict):
        if parsed.get("success") is False:
            return {"success": False, "error": str(parsed.get("error") or "eval failed")}
        if "result" in parsed:
            return {"success": True, "result": parsed.get("result")}
    return {"success": True, "result": result}


def _eval_secret(task_id: str, expression: str) -> Dict[str, Any]:
    """Evaluate a SECRET-BEARING expression. Supervisor CDP-WS only; fails closed.

    Intentionally no fallback: the CLI eval path passes its argument through
    subprocess argv, readable by any process listing. Without a socket the
    caller gets ``error_type='supervisor_required'`` and nothing is written.
    """
    supervisor = _supervisor_for(task_id)
    if supervisor is None:
        return {
            "success": False,
            "error_type": "supervisor_required",
            "error": ("Vault fill needs a supervised browser session (direct CDP "
                      "WebSocket). The CLI eval fallback would put the credential in "
                      "the process arguments, so it is never used for secrets. Start "
                      "the browser through the OpenAmer-managed session and retry."),
        }
    result = supervisor.evaluate_runtime(expression, timeout=_FILL_TIMEOUT_S)
    if result.get("ok"):
        return {"success": True, "result": result.get("result")}
    error = str(result.get("error") or "eval failed")
    return {
        "success": False,
        "error_type": "supervisor_required" if "supervisor" in error.lower() else "eval_failed",
        "error": error,
    }


def _current_origin(task_id: str) -> Optional[str]:
    from agent.vault_store import normalize_origin

    result = _eval_non_secret(task_id, "window.location.href")
    if not result.get("success"):
        return None
    href = str(result.get("result") or "").strip().strip('"').strip("'")
    return normalize_origin(href)


def _focus_bound_origin(task_id: str, origin: str) -> Optional[str]:
    """Point the supervisor at the open tab on ``origin``, if it can.

    A browser_exec session may hold several tabs; the fill must target the one
    actually on the credential's origin. Best-effort: on any failure the caller
    falls back to the current page, whose origin is checked anyway.
    """
    supervisor = _supervisor_for(task_id)
    if supervisor is None:
        return None
    focus = getattr(supervisor, "focus_page", None)
    if focus is None:
        return None
    try:
        result = focus(origin)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("browser_vault: focus_page failed: %s", exc)
        return None
    return origin if isinstance(result, dict) and result.get("ok") else None


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def browser_vault_list() -> str:
    """Handles + metadata. A login's identifier is included; passwords never are."""
    from agent.redact import registered_redaction_count

    try:
        from agent.vault_store import get_vault_store

        vault = get_vault_store()
        if vault.needs_unlock():
            return json.dumps({
                "success": False,
                "error_type": "vault_locked",
                "error": "The credential vault could not be opened (missing or damaged key).",
            })
        items = [meta.to_dict() for meta in vault.list_items()]
    except Exception as exc:
        return json.dumps({"success": False, "error": f"vault unavailable: {str(exc)[:200]}"})

    out: Dict[str, Any] = {
        "success": True,
        "items": items,
        "redacted_values": registered_redaction_count(),
    }
    if not items:
        out["hint"] = ("No stored credentials yet. On a login page call browser_vault with "
                       "action='save_login' to ask the user for one — it is stored and filled "
                       "without ever entering this conversation. Never ask the user to paste a "
                       "password into the chat.")
    return json.dumps(out, ensure_ascii=False)


def browser_vault_save_login(label: str = "", task_id: Optional[str] = None) -> str:
    """Store a login for the CURRENT page's origin, then fill it.

    The identifier and password come from the user's own surface through a masked
    prompt — never through the conversation and never as tool arguments.
    """
    from agent.vault_prompt import can_prompt, get_save_login_prompt
    from agent.vault_store import get_vault_store

    effective_task_id = task_id or "default"
    origin = _current_origin(effective_task_id)
    if not origin:
        return json.dumps({
            "success": False,
            "error_type": "no_page",
            "error": "Open the site's login page first — a login is saved for that page's origin.",
        })

    prompt = get_save_login_prompt()
    if prompt is None or not can_prompt():
        return json.dumps({
            "success": False,
            "error_type": "prompt_unavailable",
            "error": (f"This session cannot ask the user for a login (headless/cron/API). "
                      f"Ask them to run `openamer secrets vault add {origin}` instead."),
        })

    host = origin.split("://", 1)[-1]
    answer = prompt(origin, label.strip() or host)
    if not answer or not answer.get("password") or not answer.get("identifier"):
        return json.dumps({
            "success": False,
            "error_type": "save_declined",
            "error": "The user did not save a login for this site. Do not ask again this turn.",
        })

    try:
        meta = get_vault_store().add_item(
            "login", label.strip() or host,
            {"identifier": str(answer["identifier"]).strip(), "password": str(answer["password"])},
            origin=origin,
        )
    except Exception as exc:
        return json.dumps({"success": False, "error_type": "save_failed", "error": str(exc)[:200]})
    finally:
        answer.clear()

    filled = json.loads(browser_vault_fill(meta.id, task_id=effective_task_id))
    return json.dumps({
        "success": True,
        "handle": meta.id,
        "origin": origin,
        "identifier": meta.identifier,
        "identifier_type": meta.identifier_type,
        "fill": filled,
        "next": ("If the form has a separate username field, type the identifier there "
                 "(it is not a secret) and submit."),
    }, ensure_ascii=False)


def browser_vault_fill(handle: str, task_id: Optional[str] = None) -> str:
    """Fill the current page from a vault handle. Reports counts, never values."""
    from agent.redact import register_redaction_value
    from agent.vault_login_classifier import (
        LoginControl,
        build_fill_js,
        build_inspection_js,
        classify_checkout_control,
        classify_login_control,
        select_checkout_fills,
        select_password_fill,
    )
    from agent.vault_store import ADDRESS_FIELDS, PAYMENT_FIELDS, get_vault_store

    effective_task_id = task_id or "default"
    try:
        vault = get_vault_store()
        meta = vault.get_meta(handle)
        allowed = vault.allowed_origins_for(handle) if meta else []
    except Exception as exc:
        return json.dumps({"success": False, "error": f"vault unavailable: {str(exc)[:200]}"})
    if meta is None:
        return json.dumps({
            "success": False,
            "error_type": "unknown_handle",
            "error": (f"No vault item with handle {handle!r}. Use action='list'. "
                      "To add one: `openamer secrets vault add <origin>`."),
        })

    # ── Origin binding. Cheap early exit here; the authoritative check runs
    # synchronously inside the injected script (§ fill JS), so a page that
    # navigates in between cannot receive the value. ─────────────────────────
    page_origin = None
    for candidate in (allowed or [""]):
        page_origin = _focus_bound_origin(effective_task_id, candidate) if candidate else None
        if page_origin:
            break
    page_origin = page_origin or _current_origin(effective_task_id)
    if not page_origin:
        return json.dumps({
            "success": False,
            "error_type": "no_page",
            "error": ("Could not determine the current page origin — no CDP session is "
                      "attached, or the tab is on about:blank. Navigate to the form first."),
        })
    if meta.kind != "login" or allowed:
        if page_origin not in allowed:
            return json.dumps({
                "success": False,
                "error_type": "origin_mismatch",
                "error": (f"Refused: the current page origin ({page_origin}) does not match the "
                          f"item's bound origin(s) ({', '.join(allowed) or 'none'}). Fills only "
                          "run on the exact origin the item was saved for."),
            })

    # ── Inspect the page (non-secret JS) ──────────────────────────────────────
    nonce = secrets.token_hex(8)  # binds the write to THIS inspection
    inspect = _eval_non_secret(effective_task_id, build_inspection_js(nonce))
    if not inspect.get("success"):
        return json.dumps({
            "success": False,
            "error_type": "inspect_failed",
            "error": f"could not inspect page inputs: {inspect.get('error')}",
        })
    raw = _parse(_parse(inspect.get("result")))
    if not isinstance(raw, list) or not raw:
        return json.dumps({
            "success": False,
            "error_type": "no_form_controls",
            "error": "No form controls were found on the current page.",
        })

    controls = [LoginControl.from_dict(r) for r in raw if isinstance(r, dict)]
    secret_register: List[str] = []
    try:
        if meta.kind == "login":
            password = vault.resolve_password(handle)
            secret_register.append(password)
            classified = [c for c in (classify_login_control(x) for x in controls) if c]
            fills = select_password_fill(classified, password)
            del password
        else:
            secret = vault.resolve_secret(handle)
            field_tokens = PAYMENT_FIELDS if meta.kind == "payment" else ADDRESS_FIELDS
            secret_register.extend(v for v in secret.values() if v)
            classified = [c for c in (classify_checkout_control(x) for x in controls) if c]
            fills = select_checkout_fills(classified, secret, field_tokens)
            secret.clear()
    finally:
        for value in secret_register:
            # Registered before anything else can observe them: from here on,
            # every redaction call in this process masks these bytes.
            register_redaction_value(value)

    if not fills:
        return json.dumps({
            "success": False,
            "error_type": "no_matching_field",
            "error": (f"No {meta.kind} field this item could fill was found on the current page. "
                      "The form may be inside a frame or only render after interaction."),
        })

    # ── Inject. The secret lives only inside build_fill_js' argument. ─────────
    expression = build_fill_js(fills, expected_origin=page_origin, nonce=nonce)
    injected = _eval_secret(effective_task_id, expression)
    del expression, fills
    if not injected.get("success"):
        return json.dumps({
            "success": False,
            "error_type": injected.get("error_type", "fill_failed"),
            "error": str(injected.get("error"))[:300],
        })

    parsed = _parse(_parse(injected.get("result")))
    if isinstance(parsed, dict) and parsed.get("refused") == "origin_changed":
        return json.dumps({
            "success": False,
            "error_type": "origin_changed",
            "error": "The page navigated between inspection and fill. Nothing was written.",
        })
    filled = int(parsed.get("filled", 0)) if isinstance(parsed, dict) else 0
    # Built from explicit scalars only — nothing from the secret-bearing locals.
    return json.dumps({
        "success": filled > 0,
        "handle": handle,
        "kind": meta.kind,
        "origin": page_origin,
        "filled_fields": filled,
        "next": ("Submit the form now. Type the identifier into any separate username "
                 "field first — it is not a secret."),
    }, ensure_ascii=False)


BROWSER_VAULT_SCHEMA: Dict[str, Any] = {
    "name": "browser_vault",
    "description": (
        "Read and fill stored website credentials without the password ever entering "
        "this conversation.\n\n"
        "**Actions:**\n"
        "- ``list`` — handles + metadata for every stored item. A login's identifier "
        "(email/username) is included, because it is not a secret; passwords are never "
        "returned.\n"
        "- ``save_login`` — on a login page, ask the user (through their surface's masked "
        "prompt) to store a login for the current page's origin, then fill it.\n"
        "- ``fill`` — fill the current page's login field (or payment/address fields) from "
        "a handle. Requires the page origin to exactly match an origin the item was saved "
        "for; a mismatch is a hard refusal.\n\n"
        "**Why the password stays hidden:** it is resolved locally and written into the "
        "page over the browser's CDP WebSocket — never into process arguments, never into "
        "tool output. The result reports how many fields were filled, not their contents. "
        "The bytes are also registered with the redaction boundary, so a later page "
        "snapshot cannot echo them back.\n\n"
        "**Never** ask the user to paste a password into the chat and never type one you "
        "were shown. If the item does not exist, use ``save_login`` or tell the user to run "
        "``openamer secrets vault add <origin>``.\n\n"
        "After filling, the agent types the identifier into any separate username field "
        "itself (it is metadata, not a secret) and submits.\n\n"
        "**Availability:** needs a supervised browser session (CDP). Without one the fill "
        "refuses by design rather than falling back to a path that would expose the "
        "credential."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "save_login", "fill"],
                "description": "'list' handles, 'save_login' to store+fill, 'fill' an existing handle.",
            },
            "handle": {
                "type": "string",
                "description": "Vault handle from action='list'. Required for action='fill'.",
            },
            "label": {
                "type": "string",
                "description": "Optional human label when saving (defaults to the site host).",
            },
        },
        "required": ["action"],
    },
}


def browser_vault(action: str, handle: str = "", label: str = "", task_id: Optional[str] = None) -> str:
    """Dispatch for the agent-facing tool."""
    action = (action or "").strip().lower()
    if action == "list":
        return browser_vault_list()
    if action == "save_login":
        return browser_vault_save_login(label=label, task_id=task_id)
    if action == "fill":
        if not handle:
            return json.dumps({"success": False,
                               "error": "action='fill' needs a handle from action='list'."})
        return browser_vault_fill(handle, task_id=task_id)
    return json.dumps({"success": False,
                       "error": f"unknown action {action!r} (expected list, save_login, fill)"})


registry.register(
    name="browser_vault",
    toolset="browser",
    schema=BROWSER_VAULT_SCHEMA,
    handler=lambda args, **kw: browser_vault(
        action=args.get("action", ""),
        handle=args.get("handle", ""),
        label=args.get("label", ""),
        task_id=kw.get("task_id"),
    ),
    check_fn=_browser_vault_check,
    emoji="🔐",
)
