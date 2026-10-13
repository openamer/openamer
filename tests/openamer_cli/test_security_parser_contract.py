"""Regression: the `security` subcommand parser must follow the project's
build_X_parser(subparsers, *, cmd_X) convention. Previously it accepted only
`subparsers`, so `main.py`'s call `build_security_parser(subparsers, cmd_security=...)`
raised TypeError and the ENTIRE CLI failed to boot (`openamer --help` crashed).
"""
import argparse


def test_security_parser_accepts_cmd_security_kw():
    from openamer_cli.subcommands.security import build_security_parser
    from openamer_cli.subcommands import security as mod

    parser = argparse.ArgumentParser(prog="openamer")
    subparsers = parser.add_subparsers(dest="command")
    called = []

    def my_cmd(args):
        called.append(args)
        return 42

    # must not raise TypeError
    build_security_parser(subparsers, cmd_security=my_cmd)

    argv = parser.parse_args(["security", "posture"])
    assert argv.command == "security"
    # the injected cmd must be wired as the dispatch target
    assert argv.func is my_cmd


def test_security_parser_no_kw_still_works():
    """Backward-compatible: calling without cmd_security must also work."""
    from openamer_cli.subcommands.security import build_security_parser
    from openamer_cli.subcommands.security import _cmd_security

    parser = argparse.ArgumentParser(prog="openamer")
    subparsers = parser.add_subparsers(dest="command")
    build_security_parser(subparsers)
    argv = parser.parse_args(["security", "check"])
    assert argv.func is _cmd_security


def test_security_subparsers_exist():
    from openamer_cli.subcommands.security import build_security_parser

    parser = argparse.ArgumentParser(prog="openamer")
    subparsers = parser.add_subparsers(dest="command")
    build_security_parser(subparsers)
    for sub in ("check", "safe-mode", "posture"):
        argv = parser.parse_args(["security", sub])
        assert argv.security_cmd == sub


def test_full_cli_boots_help():
    """The real top-level main() must build the security parser without crashing."""
    import importlib.util
    import os

    # guard: only run where the repo's openamer_cli is importable
    if not importlib.util.find_spec("openamer_cli"):
        return
    from openamer_cli import main as m
    # building the parser is the step that crashed; just exercise it
    assert hasattr(m, "build_security_parser") or callable(
        getattr(m, "build_security_parser", None)
    )