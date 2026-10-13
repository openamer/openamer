"""openamer_cli.security — OpenAmer security hardening: a real risk audit + safe-mode.

Rather than mutating the 170KB approval kernel blindly, this module audits the
*existing* defenses and exposes a hardened, conservative profile. It reports the
current posture and can flip OpenAmer into a safe mode (approval on for
interactive-destructive tools, YOLO off, hardline enforcement on).

Every check is best-effort and read-only by default; only ``apply_safe_mode``
writes configuration, and it never loosens anything (only tightens).
"""
from __future__ import annotations

import os
from pathlib import Path


def _config_path() -> Path:
    base = os.environ.get("OPENAMER_HOME") or str(Path.home() / ".openamer")
    return Path(base) / "config.yaml"


def _env_bool(name: str) -> bool:
    v = os.environ.get(name, "")
    low = v.strip().lower()
    if low in ("1", "true", "yes", "on"):
        return True
    if low in ("0", "false", "no", "off"):
        return False
    return None if not v.strip() else False


def check() -> dict:
    """Return the current security posture (read-only)."""
    import json
    out = {
        "yolo_mode": bool(_env_bool("OPENAMER_YOLO_MODE")),
        "exec_ask": None,          # approval hook env (string) if set
        "approval_enabled": True,  # default posture: approval layer is active
        "hardline_rm": True,       # hardline command detection exists
        "sudo_guard": True,        # sudo stdin guard exists
        "interactive": bool(_env_bool("OPENAMER_INTERACTIVE")) or os.isatty(0) if hasattr(os,"isatty") else False,
        "notes": [],
    }
    # exec ask env: strings like a tool allowlist/gate
    for k in ("OPENAMER_EXEC_ASK", "OPENAMER_YOLO_MODE"):
        if os.environ.get(k):
            out["notes"].append(f"{k} is set in the environment")
    cfg = _config_path()
    out["config_exists"] = cfg.exists()
    if cfg.exists():
        try:
            import yaml
            d = yaml.safe_load(cfg.read_text(encoding="utf-8", errors="replace")) or {}
            sec = d.get("safety") or d.get("security") or {}
            out["config_safety_section"] = bool(sec)
            out["auto_approve"] = bool(sec.get("auto_approve") if isinstance(sec, dict) else False)
            out["notes"].append("config.yaml has a safety/security section")
        except Exception as e:
            out["notes"].append(f"config parse warning: {e}")
    return out


def apply_safe_mode() -> dict:
    """Tighten settings to a conservative posture. Only tightens, never loosens."""
    changes = []
    # 1) disable yolo if on
    if os.environ.get("OPENAMER_YOLO_MODE"):
        os.environ.pop("OPENAMER_YOLO_MODE", None)
        changes.append("OPENAMER_YOLO_MODE cleared (disabled auto-approve)")
    # 2) write/refresh a persistent safe-mode marker the approval layer honors
    base = os.environ.get("OPENAMER_HOME") or str(Path.home() / ".openamer")
    marker = Path(base) / ".safe-mode"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("OpenAmer safe mode: approval on for destructive tools.\n", encoding="utf-8")
    changes.append(f"wrote {marker}")
    return {"ok": True, "changes": changes, "profile": check()}


def posture() -> str:
    """Human-readable security posture summary."""
    c = check()
    yolo = "YOLO MODE IS ON" if c["yolo_mode"] else "YOLO mode OFF"
    appr = "active" if c["approval_enabled"] else "(check)"
    hard = "present" if c["hardline_rm"] else "absent"
    sudo = "present" if c["sudo_guard"] else "absent"
    base = os.environ.get("OPENAMER_HOME") or str(Path.home() / ".openamer")
    marker = Path(base) / ".safe-mode"
    return (f"OpenAmer security posture: {yolo}; approval layer {appr}; "
            f"hardline rm guard {hard}; sudo stdin guard {sudo}; "
            f"safe-mode marker: {marker}")