import argparse
import os
import subprocess
import sys

import pytest

from openamer_constants import set_openamer_home_override, reset_openamer_home_override

from openamer_cli.main import _read_ssh_session_token_file, cmd_dashboard
from openamer_cli.subcommands.dashboard import build_dashboard_parser


def _harden_token_file(path) -> None:
    """Restrict *path* to its owner, the way 0o600 does on POSIX.

    chmod(0o600) is a no-op on Windows — there is no mode bit to set — so the file kept
    the inheritable ACEs of %TEMP% (Users, Administrators, SYSTEM), and the product's
    hardening check refused it: "permissive DACL"
    (openamer_cli/windows_ssh_runtime.py:129). That refusal is correct; the precondition,
    not the check, is what this fixture failed to establish. icacls is not enough either:
    measured, "/inheritance:r /grant:r <user>:F" still leaves Administrators and OWNER
    RIGHTS ACEs, neither of which is in _allowed_sids(). Build the DACL explicitly with
    exactly the owner and SYSTEM, and protect it against inheritance.
    """
    if sys.platform == "win32":
        import ntsecuritycon
        import win32api
        import win32security

        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
        )
        user_sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
        system_sid = win32security.CreateWellKnownSid(
            win32security.WinLocalSystemSid, None
        )
        dacl = win32security.ACL()
        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION, ntsecuritycon.FILE_ALL_ACCESS, user_sid
        )
        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION, ntsecuritycon.FILE_ALL_ACCESS, system_sid
        )
        descriptor = win32security.SECURITY_DESCRIPTOR()
        descriptor.SetSecurityDescriptorOwner(user_sid, 0)
        descriptor.SetSecurityDescriptorDacl(1, dacl, 0)
        descriptor.SetSecurityDescriptorControl(
            win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED
        )
        win32security.SetFileSecurity(
            str(path),
            win32security.DACL_SECURITY_INFORMATION
            | win32security.OWNER_SECURITY_INFORMATION,
            descriptor,
        )
    os.chmod(str(path), 0o600)


def dashboard_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    build_dashboard_parser(
        subparsers,
        cmd_dashboard=lambda _args: None,
        cmd_dashboard_register=lambda _args: None,
    )
    return parser


def test_serve_help_advertises_secure_ssh_bootstrap_flags(capsys):
    with pytest.raises(SystemExit) as exit_info:
        dashboard_parser().parse_args(["serve", "--help"])
    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "--ssh-session-token-file PATH" in output
    assert "--ssh-owner-nonce NONCE" in output


def test_serve_accepts_owner_nonce():
    args = dashboard_parser().parse_args(["serve", "--ssh-owner-nonce", "0123456789abcdef"])
    assert args.ssh_owner_nonce == "0123456789abcdef"


@pytest.mark.parametrize("operation", ["--status", "--stop"])
def test_one_shot_token_file_rejects_non_starting_operations(operation):
    args = dashboard_parser().parse_args([
        "serve", operation, "--ssh-session-token-file", "/tmp/token",
    ])
    with pytest.raises(SystemExit, match="cannot be used"):
        cmd_dashboard(args)


def test_token_file_is_read_and_unlinked_through_private_directory(tmp_path, monkeypatch):
    home = tmp_path / "home"
    openamer_home = home / ".openamer"
    token_dir = openamer_home / "desktop-ssh" / ("a" * 32)
    token_dir.mkdir(parents=True, mode=0o700)
    token_path = token_dir / "0123456789abcdef.token"
    token_path.write_text("b" * 64)
    _harden_token_file(token_path)
    override = set_openamer_home_override(openamer_home)
    try:
        assert _read_ssh_session_token_file(str(token_path)) == "b" * 64
        assert not token_path.exists()
    finally:
        reset_openamer_home_override(override)


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink contract")
def test_token_file_rejects_symlink(tmp_path, monkeypatch):
    home = tmp_path / "home"
    token_dir = home / ".openamer" / "desktop-ssh" / ("a" * 32)
    token_dir.mkdir(parents=True, mode=0o700)
    target = tmp_path / "token"
    target.write_text("b" * 64)
    _harden_token_file(target)
    token_path = token_dir / "0123456789abcdef.token"
    token_path.symlink_to(target)
    override = set_openamer_home_override(home / ".openamer")
    try:
        with pytest.raises(SystemExit, match="symlink|not accessible"):
            _read_ssh_session_token_file(str(token_path))
        assert not token_path.exists()
        assert target.read_text() == "b" * 64
    finally:
        reset_openamer_home_override(override)


def test_token_file_rejects_parent_escape(tmp_path, monkeypatch):
    home = tmp_path / "home"
    token_root = home / ".openamer" / "desktop-ssh"
    token_root.mkdir(parents=True, mode=0o700)
    escaped = token_root.parent / "0123456789abcdef.token"
    escaped.write_text("b" * 64)
    _harden_token_file(escaped)
    override = set_openamer_home_override(home / ".openamer")
    try:
        with pytest.raises(SystemExit, match="invalid runtime path"):
            _read_ssh_session_token_file(str(token_root / ".." / escaped.name))
        assert escaped.exists()
    finally:
        reset_openamer_home_override(override)
