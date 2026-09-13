"""The `--plan` CLI flag must reach the gate.

Plan mode has two halves that can drift apart: the gate itself (covered in
tests/test_plan_mode.py) and the path from the command line to the gate. A flag
that parses but is never forwarded looks identical to a working one until you
run it — so this pins the whole chain, not just the parser.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_the_parser_offers_the_flag() -> None:
    """`openamer chat --plan` parses, and defaults to off without it."""
    from openamer_cli._parser import build_top_level_parser

    parser, _subparsers, _chat = build_top_level_parser()

    assert parser.parse_args(["chat", "--plan"]).plan is True
    assert parser.parse_args(["chat"]).plan is False


def test_the_flag_is_threaded_to_the_agent() -> None:
    """Each hop in the chain forwards plan_mode. Drop one and the flag is inert.

    Read as source rather than imported: importing cli.py / run_agent.py pulls
    the full agent stack, which the canonical test runner deliberately scrubs.
    """
    hops = {
        "openamer_cli/cli_agent_setup_mixin.py": "plan_mode=self.plan_mode",
        "run_agent.py": "plan_mode=plan_mode",
        "openamer_cli/main.py": 'plan_mode=getattr(args, "plan", False)',
    }

    for rel, needle in hops.items():
        source = (REPO / rel).read_text(encoding="utf-8")
        assert needle in source, f"{rel} does not forward plan_mode ({needle})"


def test_the_cli_resolves_flag_over_config() -> None:
    """Flag wins, config is the fallback — both must be present in cli.py."""
    source = (REPO / "cli.py").read_text(encoding="utf-8")

    assert "plan_mode: bool = False," in source, "cli.py lost the parameter"
    assert "self.plan_mode = plan_mode or" in source, "cli.py lost the resolution"
    assert 'pm_cfg.get("plan_mode", False)' in source, "config fallback is gone"


def test_the_agent_defaults_to_config_when_the_flag_is_absent() -> None:
    """`None` means "not passed" so agent_init falls back to config, rather than
    silently forcing plan mode off for every gateway/desktop caller."""
    source = (REPO / "agent" / "agent_init.py").read_text(encoding="utf-8")

    assert 'plan_mode: "Optional[bool]" = None' in source
    assert "if plan_mode is None:" in source
    assert 'cfg_get("agent.plan_mode", False)' in source
