"""`openamer re` must be a real subcommand, and its evidence must fit the bridge.

Two failure modes are worth a test each: the parser registering the command but
the dispatch falling through to help text, and an evidence envelope whose field
names the memory bridge silently ignores, which produces an episode reading
"unknown target" while still reporting success.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import struct
from pathlib import Path

import pytest

from openamer_cli.main import _BUILTIN_SUBCOMMANDS
from openamer_cli.subcommands.re import _evidence, build_re_parser


# --------------------------------------------------------------------------- #
# parser wiring
# --------------------------------------------------------------------------- #
def _re_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    build_re_parser(subparsers)
    return subparsers.choices["re"]


def test_re_is_a_builtin_subcommand() -> None:
    # Missing from the set does not crash, it only pays plugin discovery on
    # every invocation (~600 ms), so nothing else would catch it.
    assert "re" in _BUILTIN_SUBCOMMANDS


def test_re_actions_are_registered() -> None:
    parser = _re_parser()
    actions = parser._subparsers._group_actions[0].choices
    assert set(actions) == {"doctor", "scan", "recall"}
    # Bare `openamer re` explains the engines instead of printing usage.
    assert parser.get_default("func") is not None


def test_scan_requires_remember_for_memory_writes() -> None:
    parser = _re_parser()
    scan = parser._subparsers._group_actions[0].choices["scan"]
    defaults = scan.parse_args(["some-target"])
    assert defaults.remember is False


# --------------------------------------------------------------------------- #
# evidence envelope
# --------------------------------------------------------------------------- #
def test_evidence_matches_the_bridge_field_names(tmp_path: Path) -> None:
    archive = tmp_path / "app.asar"
    archive.write_bytes(b"placeholder bytes for digesting")
    report = {
        "kind": "electron-asar",
        "ipc_channels_literal": 4,
        "limitations": ["one", "two"],
    }

    evidence = _evidence(report, archive)

    # The bridge reads subject.name / subject.format / subject.digest.sha256 and
    # provider.id; a string where it expects an object raises AttributeError, and
    # a missing name produces "unknown target" without any error at all.
    assert evidence["subject"]["name"] == str(archive)
    assert evidence["subject"]["format"] == "electron-asar"
    assert len(evidence["subject"]["digest"]["sha256"]) == 64
    assert evidence["provider"]["id"] == "helix"
    assert evidence["operation"] == "scan_javascript_surface"
    assert evidence["confidence"] == "observed"
    assert evidence["authority"] == "derived-from-artifact"
    assert evidence["limitations"] == ["one", "two"]
    assert evidence["evidence_id"].startswith("helix:")
    json.dumps(evidence)  # must stay serializable for the temp-file handoff


# --------------------------------------------------------------------------- #
# end to end on a synthetic archive
# --------------------------------------------------------------------------- #
def _write_asar(target: Path, source: bytes) -> None:
    header = {"files": {"main.js": {"size": len(source), "offset": "0"}}}
    raw = json.dumps(header).encode()
    padding = (-len(raw)) % 4
    header_size = 8 + len(raw) + padding
    target.write_bytes(
        struct.pack("<IIII", 4, header_size, header_size - 4, len(raw))
        + raw
        + b"\x00" * padding
        + source
    )


def test_scan_reports_and_stays_out_of_memory(tmp_path: Path, capsys) -> None:
    from openamer_cli.subcommands.re import cmd_scan

    archive = tmp_path / "app.asar"
    _write_asar(
        archive,
        b'ipcMain.handle("demo:ping", () => 1);',
    )

    exit_code = cmd_scan(argparse.Namespace(target=str(archive), json=False, remember=False))
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ipc channels" in output
    # A handler with no renderer counterpart is one-sided; reporting it is the
    # point of the scanner, so the channel name must appear, not be swallowed.
    assert "one-sided" in output
    assert "demo:ping" in output
    assert "not recorded" in output
