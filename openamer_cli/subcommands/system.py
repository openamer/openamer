"""``openamer system`` subcommand — show OpenAmer's self-system knowledge."""
import json
import sys


def build_system_parser(subparsers) -> None:
    p = subparsers.add_parser(
        "system", help="Show what system OpenAmer is running on (self-knowledge)")
    p.add_argument("--json", action="store_true", help="emit raw JSON profile")
    p.set_defaults(func=_cmd_system)


def _cmd_system(args) -> int:
    from openamer_cli import system_info as si
    if getattr(args, "json", False):
        print(json.dumps(si.collect(), indent=2, ensure_ascii=False))
    else:
        print(si.describe())
    return 0