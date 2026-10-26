"""Verification for helix_scan: archive layout, IPC surface, and declared limits.

The numbers this scanner reports are only worth something if they are
reproducible, so the real OpenAmer archive is asserted with the exact figures
published to the user. Synthetic fixtures keep the parser honest without
depending on any installed application.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import helix_scan

REAL_ASAR = Path(
    r"C:/Users/damir/AppData/Local/Programs/OpenAmer/resources/app.asar"
)


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def write_asar(target: Path, members: dict[str, bytes], unpacked: set[str]) -> Path:
    """Write a minimal ASAR using the documented layout.

    packed member  -> stored in the payload, entry carries offset and size
    unpacked member -> stored beside the archive, entry carries `unpacked: true`
    """
    header: dict = {"files": {}}
    payload = bytearray()
    for name, data in members.items():
        node: dict = {"size": len(data)}
        if name in unpacked:
            node["unpacked"] = True
        else:
            node["offset"] = str(len(payload))
            payload.extend(data)
        header["files"][name] = node

    raw_header = json.dumps(header).encode("utf-8")
    padding = (-len(raw_header)) % 4
    # header_size spans offset 8..payload, so it includes the inner length word.
    header_size = 4 + 4 + len(raw_header) + padding
    archive = target
    archive.write_bytes(
        struct.pack("<IIII", 4, header_size, header_size - 4, len(raw_header))
        + raw_header
        + b"\x00" * padding
        + bytes(payload)
    )
    if unpacked:
        unpacked_root = archive.with_name(archive.name + ".unpacked")
        for name in unpacked:
            destination = unpacked_root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(members[name])
    return archive


BRIDGE_SOURCE = b"""
const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("demoApi", {
  load: (id) => ipcRenderer.invoke("demo:load", id),
  save: (payload) => ipcRenderer.invoke("demo:save", payload),
  nested: { inner: true, text: "a } brace in a string" },
  onReady: (handler) => ipcRenderer.on("demo:ready", handler),
});
const dynamicName = "demo:" + suffix;
ipcRenderer.invoke(dynamicName);
"""

MAIN_SOURCE = b"""
const { ipcMain } = require("electron");
ipcMain.handle("demo:load", async (_event, id) => id);
ipcMain.handle("demo:save", async (_event, payload) => payload);
ipcMain.on("demo:shutdown", () => process.exit(0));
"""


# --------------------------------------------------------------------------- #
# archive layout
# --------------------------------------------------------------------------- #
def test_reads_packed_and_unpacked_members(tmp_path: Path) -> None:
    archive = write_asar(
        tmp_path / "app.asar",
        {"main.js": MAIN_SOURCE, "renderer.js": BRIDGE_SOURCE},
        unpacked={"renderer.js"},
    )
    entries, payload = helix_scan.read_asar(archive)
    by_path = {entry.path: entry for entry in entries}
    assert set(by_path) == {"main.js", "renderer.js"}
    assert by_path["main.js"].unpacked is False
    assert by_path["renderer.js"].unpacked is True
    assert by_path["renderer.js"].offset == -1
    assert helix_scan.entry_bytes(by_path["main.js"], payload, archive) == MAIN_SOURCE


def test_rejects_non_asar_file(tmp_path: Path) -> None:
    plain = tmp_path / "app.asar"
    plain.write_bytes(b"not an archive at all, just a misleading name")
    with pytest.raises(ValueError, match="not an ASAR archive"):
        helix_scan.read_asar(plain)


def test_missing_unpacked_member_is_reported_not_swallowed(tmp_path: Path) -> None:
    archive = write_asar(
        tmp_path / "app.asar", {"main.js": MAIN_SOURCE, "gone.js": b"x" * 10},
        unpacked={"gone.js"},
    )
    (archive.with_name(archive.name + ".unpacked") / "gone.js").unlink()
    report = helix_scan.collect_from_asar(archive).as_dict()
    assert report["js_modules"] == 1
    assert "could not be read" in report["limitations"][0]


# --------------------------------------------------------------------------- #
# scanning
# --------------------------------------------------------------------------- #
def test_counts_ipc_and_bridge_surface(tmp_path: Path) -> None:
    archive = write_asar(
        tmp_path / "app.asar",
        {"main.js": MAIN_SOURCE, "renderer.js": BRIDGE_SOURCE},
        unpacked={"renderer.js"},
    )
    report = helix_scan.collect_from_asar(archive).as_dict()
    assert report["ipc_main_handlers"] == 3
    assert report["ipc_renderer_transmissions"] == 2
    assert report["ipc_renderer_listeners"] == 1
    assert report["ipc_channels_literal"] == 4
    assert report["ipc_paired_channels"] == 2
    assert report["ipc_one_sided_channels"] == ["demo:ready", "demo:shutdown"]
    # The computed channel cannot be named, so the scanner must admit it.
    assert report["unresolved_call_sites"] == {"renderer_non_literal": 1}


def test_bridge_members_skip_nested_keys_and_string_braces(tmp_path: Path) -> None:
    archive = write_asar(
        tmp_path / "app.asar", {"renderer.js": BRIDGE_SOURCE}, unpacked={"renderer.js"}
    )
    report = helix_scan.collect_from_asar(archive).as_dict()
    assert report["context_bridge_exposures"] == {"demoApi": 4}
    # a, save, load, onReady on the surface; inner and text one level deeper.
    assert report["context_bridge_members_total"] == 4
    assert report["context_bridge_members_by_depth"] == {"1": 4, "2": 2}


def test_directory_mode_agrees_with_archive_mode(tmp_path: Path) -> None:
    archive = write_asar(
        tmp_path / "app.asar",
        {"main.js": MAIN_SOURCE, "renderer.js": BRIDGE_SOURCE},
        unpacked={"renderer.js"},
    )
    flat = tmp_path / "flat"
    flat.mkdir()
    (flat / "main.js").write_bytes(MAIN_SOURCE)
    (flat / "renderer.js").write_bytes(BRIDGE_SOURCE)

    from_archive = helix_scan.collect_from_asar(archive).as_dict()
    from_directory = helix_scan.collect_from_directory(flat).as_dict()
    for key in (
        "ipc_channels_literal",
        "ipc_paired_channels",
        "ipc_main_handlers",
        "context_bridge_members_total",
        "unresolved_call_sites",
    ):
        assert from_archive[key] == from_directory[key], key


def test_member_extractor_handles_multiline_literal() -> None:
    source = 'expose("api", {\n  a: 1,\n  b: () => x, // , c: nope\n  nested: { d: 2 },\n});'
    start = source.index("{")
    assert helix_scan.top_level_members(source, start) == ["a", "b", "nested"]


# --------------------------------------------------------------------------- #
# the published figures, pinned
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not REAL_ASAR.exists(), reason="OpenAmer desktop archive not installed")
def test_real_openamer_archive_matches_published_figures() -> None:
    report = helix_scan.collect_from_asar(REAL_ASAR).as_dict()

    assert report["kind"] == "electron-asar"
    assert report["ipc_channels_literal"] == 122
    assert report["ipc_paired_channels"] == 108
    assert report["ipc_renderer_transmissions"] == 108
    assert report["ipc_main_handlers"] == 108
    assert report["context_bridge_exposures"] == {"openamerDesktop": 83}
    assert report["context_bridge_members_by_depth"] == {"1": 83, "2": 59, "3": 29}
    assert report["unresolved_call_sites"] == {"renderer_non_literal": 2}
    # Two channels are built at runtime; that is exactly the delta the scanner
    # declares instead of hiding.
    assert len(report["ipc_one_sided_channels"]) == 14


@pytest.mark.skipif(not REAL_ASAR.exists(), reason="OpenAmer desktop archive not installed")
def test_real_archive_scan_is_deterministic() -> None:
    first = helix_scan.collect_from_asar(REAL_ASAR).as_dict()
    second = helix_scan.collect_from_asar(REAL_ASAR).as_dict()
    assert first == second
