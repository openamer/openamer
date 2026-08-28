"""openamer mcp audit — security posture of configured MCP servers.

Implements a lightweight, read-only "zero-trust / defense-in-depth" audit over
the configured ``mcp_servers`` block, following the recurring Agentic-AI
trend signal that agent-tool security is the foundation (three-layer
defense-in-depth, identity as the base, supply-chain pinning).

Each server is scored across a small set of concrete checks; a failing check
never blocks anything (read-only), it just reports so the operator/agent can
decide. The audit is deterministic given the config, so it's hermetic-testable.

Usage:
    openamer mcp audit
    openamer mcp audit --json
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

# A stdio command is inherently more privileged than a remote HTTP tool, so
# audits flag unknown/naked commands. Well-known package launchers are still
# worth checking (they pin nothing by default).
_KNOWN_LAUNCHERS = {"npx", "npx.cmd", "uvx", "python", "python3", "node", "deno", "bun"}

# Some package launchers take a scope namespace like `@scope/pkg` that is NOT a
# version pin — only a trailing `@<semver>` / `==<ver>` / `=<ver>` is a pin.
_VERSION_PIN_RE = re.compile(
    r"(?:^|[=@])(\d+)(?:\.\d+){1,2}(?:[.-]?[0-9A-Za-z.*+_-]+)?$"
)


def _is_version_pin(arg: str) -> bool:
    """True if ``arg`` names a specific version (a supply-chain pin).

    Accepts `pkg@1.2.3`, `pkg==1.2.3`, `pkg=1.2.3`, and scoped forms like
    `@scope/pkg@1.2.3`. Rejects a bare `@scope/pkg` (namespace, not a pin).
    """
    # match the version token after the last @ or == or = that is numeric+dot
    return bool(_VERSION_PIN_RE.search(arg))


@dataclass
class CheckResult:
    check: str
    ok: bool
    detail: str = ""


@dataclass
class ServerAudit:
    name: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.ok)

    @property
    def total(self) -> int:
        return len(self.checks)


def _is_oauth(cfg: dict) -> bool:
    # `auth: oauth` (HTTP servers) or presence of an oauth client/flow marker.
    auth = cfg.get("auth")
    if isinstance(auth, str):
        return auth.lower() == "oauth"
    return bool(cfg.get("oauth"))


def _is_bearer(cfg: dict) -> bool:
    auth = cfg.get("auth")
    if isinstance(auth, str):
        return auth.lower() in {"header", "bearer"}
    return False


def _visible_secret(cfg: dict) -> bool:
    """A bearer_token / api key embedded directly in config (not env-ref)."""
    for k in ("bearer_token", "api_key", "token", "password"):
        v = cfg.get(k)
        if isinstance(v, str) and v and not v.startswith("${") and not "__CHANGED__" in v:
            # env-var references (${VAR}) are fine; a literal value is a leak
            if not re.match(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$", v):
                return True
    return False


def _pin_ref(cfg: dict) -> Optional[str]:
    """A pinned install ref (commit/tag) if any, else None."""
    return cfg.get("install_ref") or cfg.get("ref") or None


def audit_server(name: str, cfg: dict) -> ServerAudit:
    """Run the posture checks against one server config."""
    a = ServerAudit(name=name)

    # 1) Identity / auth is the base (OAuth > bearer > none). For stdio
    #    (local subprocess) no remote auth is required — don't penalise it.
    is_stdio = bool(cfg.get("command")) and not cfg.get("url")
    if is_stdio:
        a.checks.append(CheckResult("auth", True, "stdio (local subprocess) — no remote auth"))
    elif _is_oauth(cfg):
        a.checks.append(CheckResult("auth", True, "OAuth 2.1 / dynamic client registration"))
    elif _is_bearer(cfg):
        a.checks.append(CheckResult("auth", False,
                                    "static bearer/header token — prefer OAuth or env-ref"))
    else:
        a.checks.append(CheckResult("auth", False, "no auth configured for an HTTP/remote tool"))

    # 2) No secrets embedded in config (defense-in-depth: env refs only).
    if _visible_secret(cfg):
        a.checks.append(CheckResult("secret", False,
                                    "literal credential in config — move to env-var reference"))
    else:
        a.checks.append(CheckResult("secret", True, "no literal secret in config"))

    # 3) Supply-chain pinning (catalog entries are pinned; custom stdio should be).
    if cfg.get("url"):
        a.checks.append(CheckResult("pin", True, "remote endpoint (URL)"))
    elif cfg.get("command"):
        cmd = str(cfg.get("command") or "").lower()
        launcher = cmd.split("/")[-1].split("\\")[-1]
        pinned = bool(_pin_ref(cfg)) or any(
            _is_version_pin(a) for a in (cfg.get("args") or []) if isinstance(a, str)
        )
        if launcher in _KNOWN_LAUNCHERS and not pinned:
            a.checks.append(CheckResult(
                "pin", False,
                f"stdio launcher '{cmd}' with no pinned version — consider pinning",
            ))
        else:
            a.checks.append(CheckResult("pin", True, "stdio command (pinned or explicit path)"))

    # 4) Publicly reachable endpoint on non-loopback is an attack surface.
    server_url = cfg.get("url")
    if server_url:
        if server_url.startswith("http://") and not server_url.startswith(
            ("http://localhost", "http://127.0.0.1", "http://::1", "http://[::1]")
        ):
            a.checks.append(CheckResult("transport", False, "plaintext http endpoint"))
        else:
            a.checks.append(CheckResult("transport", True, "https or loopback http endpoint"))
    else:
        a.checks.append(CheckResult("transport", True, "stdio (no URL)"))

    return a


def audit_all(config: Optional[dict] = None) -> list[ServerAudit]:
    """Audit every configured server. ``config`` optional for hermetic tests."""
    from openamer_cli.mcp_config import _get_mcp_servers
    servers = config if config is not None else _get_mcp_servers()
    return [audit_server(name, cfg) for name, cfg in sorted(servers.items())]


def _format_audit(audits: list[ServerAudit], as_json: bool) -> str:
    if as_json:
        payload = []
        for a in audits:
            payload.append({
                "name": a.name,
                "passed": a.passed,
                "total": a.total,
                "checks": [
                    {"check": c.check, "ok": c.ok, "detail": c.detail}
                    for c in a.checks
                ],
            })
        return json.dumps(payload, indent=2)

    if not audits:
        return "  No MCP servers configured. Add one with `openamer mcp add <name> ...`."
    out = ["  MCP Security Posture Audit", ""]
    for a in audits:
        status = "PASS" if a.passed == a.total else "FAIL"
        out.append(f"  {a.name}  [{a.passed}/{a.total} PASS] {status}")
        for c in a.checks:
            mark = "✓" if c.ok else "✗"
            out.append(f"    {mark} {c.check}: {c.detail}")
        out.append("")
    return "\n".join(out)


def cmd_mcp_audit(args) -> int:
    """`openamer mcp audit` — print posture, or --json."""
    audits = audit_all()
    print(_format_audit(audits, as_json=bool(getattr(args, "json", False))))
    return 1 if any(a.passed != a.total for a in audits) else 0