"""``openamer security`` subcommand — audit & harden OpenAmer's security posture."""
import sys
from typing import Callable, Optional


def build_security_parser(subparsers, *, cmd_security: Optional[Callable] = None) -> None:
    p = subparsers.add_parser(
        "security", help="Audit / harden OpenAmer security posture")
    sub = p.add_subparsers(dest="security_cmd")
    dispatch = cmd_security or _cmd_security
    sc = sub.add_parser("check", help="Show current security posture")
    sc.set_defaults(func=dispatch)
    sm = sub.add_parser("safe-mode", help="Apply the conservative (safe) profile")
    sm.set_defaults(func=dispatch)
    sp = sub.add_parser("posture", help="One-line posture summary")
    sp.set_defaults(func=dispatch)
    p.set_defaults(func=dispatch)
    audit = sub.add_parser("audit", help="On-demand supply-chain audit (OSV.dev)")
    audit.add_argument("--skip-venv", action="store_true", help="Do not scan the OpenAmer venv")
    audit.add_argument("--skip-plugins", action="store_true", help="Do not scan user plugins")
    audit.add_argument("--skip-mcp", action="store_true", help="Do not scan MCP server packages")
    audit.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    audit.add_argument("--fail-on", default="critical",
                      help="Exit non-zero at this severity or above (low|moderate|high|critical)")
    audit.set_defaults(func=_cmd_audit)
    assessment = sub.add_parser("assess", help="Run authorized local HTTP security checks")
    assessment.add_argument("manifest", help="JSON origin and check definitions")
    assessment.add_argument("--authorized", action="store_true", help="Confirm permission for this target")
    assessment.add_argument("--output", required=True, help="New private JSON evidence file")
    assessment.set_defaults(func=_cmd_assessment)
    lab = sub.add_parser("lab", help="Verify active checks against vulnerable and fixed local fixtures")
    lab.add_argument("--output", required=True, help="New evidence directory")
    lab.set_defaults(func=_cmd_assessment)


def _cmd_assessment(args) -> int:
    from openamer_cli.security_assessment import command
    return command(args)


def _cmd_audit(args) -> int:
    from openamer_cli.security_audit import cmd_security_audit
    return int(cmd_security_audit(args) or 0)


def _cmd_security(args) -> int:
    from openamer_cli import security as sec
    act = getattr(args, "security_cmd", None) or getattr(args, "security_command", "posture")
    if act == "check":
        c = sec.check()
        print("OpenAmer security posture:")
        for k, v in c.items():
            print(f"  {k}: {v}")
        return 0
    if act == "safe-mode":
        r = sec.apply_safe_mode()
        print("Safe mode applied:")
        for ch in r["changes"]:
            print(f"  - {ch}")
        return 0
    if act == "audit":
        return _cmd_audit(args)
    if act in ("assess", "lab"):
        return _cmd_assessment(args)
    # default / posture
    print(sec.posture())
    return 0
