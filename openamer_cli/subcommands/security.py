"""``openamer security`` subcommand — audit & harden OpenAmer's security posture."""
import sys


def build_security_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "security", help="Audit / harden OpenAmer security posture")
    sub = p.add_subparsers(dest="security_cmd")
    sc = sub.add_parser("check", help="Show current security posture")
    sc.set_defaults(func=_cmd_security)
    sm = sub.add_parser("safe-mode", help="Apply the conservative (safe) profile")
    sm.set_defaults(func=_cmd_security)
    sp = sub.add_parser("posture", help="One-line posture summary")
    sp.set_defaults(func=_cmd_security)
    p.set_defaults(func=_cmd_security)


def _cmd_security(args) -> int:
    from openamer_cli import security as sec
    act = getattr(args, "security_cmd", "posture")
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
    # default / posture
    print(sec.posture())
    return 0