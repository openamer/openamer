"""Tests for openamer_cli/mcp_audit.py (security posture of MCP servers).

Hermetic: the audit is a pure function of the config dict, so we exercise it
directly with representative server configs — no network, no OPENAMER_HOME.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from openamer_cli.mcp_audit import (  # noqa: E402
    audit_server,
    audit_all,
    _format_audit,
)


def test_oauth_https_passes_all():
    cfg = {"url": "https://mcp.example.com/mcp", "auth": "oauth"}
    a = audit_server("good", cfg)
    assert a.passed == a.total


def test_bearer_flagged_oauth_preferred():
    cfg = {"url": "https://mcp.example.com/mcp", "auth": "header"}
    a = audit_server("bearer", cfg)
    bycheck = {c.check: c.ok for c in a.checks}
    assert bycheck["auth"] is False  # static bearer < OAuth


def test_literal_secret_flagged():
    cfg = {"url": "https://x.example.com/mcp", "auth": "header",
           "bearer_token": "sk-literal-secret"}
    a = audit_server("leak", cfg)
    bycheck = {c.check: c.ok for c in a.checks}
    assert bycheck["secret"] is False
    # env-ref is fine
    cfg2 = {"url": "https://x.example.com/mcp", "auth": "header",
            "bearer_token": "${MY_TOKEN}"}
    bycheck2 = {c.check: c.ok for c in audit_server("ref", cfg2).checks}
    assert bycheck2["secret"] is True


def test_unpinned_stdio_flagged():
    # `npx @scope/pkg` is NOT pinned (no version); a bare launcher w/ no version
    # should be flagged for the operator to pin.
    cfg = {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]}
    a = audit_server("unpinned", cfg)
    bycheck = {c.check: c.ok for c in a.checks}
    # The `@scope/pkg` is not a version pin (just package path), so expect flagged.
    assert bycheck["pin"] is False


def test_pinned_stdio_passes():
    cfg = {"command": "npx", "args": ["-y", "@scope/pkg@1.2.3"]}
    a = audit_server("pinned", cfg)
    bycheck = {c.check: c.ok for c in a.checks}
    assert bycheck["pin"] is True
    # stdio (local subprocess) doesn't need remote auth — don't penalise it.
    assert bycheck["auth"] is True


def test_plaintext_http_flagged():
    cfg = {"url": "http://mcp.example.com/mcp", "auth": "oauth"}
    a = audit_server("plainhttp", cfg)
    bycheck = {c.check: c.ok for c in a.checks}
    assert bycheck["transport"] is False


def test_loopback_http_is_ok():
    cfg = {"url": "http://127.0.0.1:9999/mcp", "auth": "none"}
    a = audit_server("local", cfg)
    bycheck = {c.check: c.ok for c in a.checks}
    assert bycheck["transport"] is True


def test_audit_all_sorts_and_json():
    cfg = {
        "zzz": {"url": "https://z.example.com/mcp", "auth": "oauth"},
        "aaa": {"url": "https://a.example.com/mcp", "auth": "oauth"},
    }
    audits = audit_all(config=cfg)
    assert [a.name for a in audits] == ["aaa", "zzz"]  # sorted
    out = _format_audit(audits, as_json=True)
    assert '"name": "aaa"' in out


def test_empty_config():
    assert _format_audit(audit_all(config={}), as_json=False).startswith(
        "  No MCP servers configured."
    )