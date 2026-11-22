"""Integration coverage for profile-local MCP discovery in slash workers."""

from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import textwrap
import threading

import pytest
import yaml

pytest.importorskip("mcp.server.fastmcp")


def test_profile_local_mcp_tool_is_visible_in_slash_worker(tmp_path):
    profile_home = tmp_path / "profile-home"
    profile_home.mkdir()
    marker = "profile-local-61922"
    server = tmp_path / "fastmcp_probe.py"
    server.write_text(
        textwrap.dedent(
            f"""
            from mcp.server.fastmcp import FastMCP

            mcp = FastMCP("profileprobe")

            @mcp.tool()
            def openamer_61922_profile_probe() -> str:
                return {marker!r}

            if __name__ == "__main__":
                mcp.run(transport="stdio")
            """
        ),
        encoding="utf-8",
    )
    (profile_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                # The worker caps its wait for MCP discovery at
                # ``mcp_discovery_timeout`` (default 1.5s) so a dead server
                # cannot block startup. A real fastmcp server needs longer than
                # that on a loaded machine (measured: ~16s to the first /tools
                # reply here), so pin a generous cap: this test asserts that the
                # profile-local tool becomes VISIBLE, not that startup is quick.
                "mcp_discovery_timeout": 30,
                "mcp_servers": {
                    "profileprobe": {
                        "enabled": True,
                        "command": sys.executable,
                        "args": [str(server)],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    for key in list(env):
        if key.endswith("_API_KEY") or key.endswith("_TOKEN"):
            env.pop(key)
    env["OPENAMER_HOME"] = str(profile_home)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    env["OPENAMER_SLASH_WATCHDOG_GRACE_S"] = "0"
    env["OPENAMER_SLASH_WATCHDOG_POLL_S"] = "0.05"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-m",
            "tui_gateway.slash_worker",
            "--session-key",
            "agent:main:tui:dm:mcp-profile-test",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=tmp_path,
    )
    output: queue.Queue[str] = queue.Queue()
    try:
        assert proc.stdin is not None
        assert proc.stdout is not None
        stdout = proc.stdout
        threading.Thread(
            target=lambda: output.put(stdout.readline()),
            daemon=True,
        ).start()
        proc.stdin.write(json.dumps({"id": 1, "command": "/tools"}) + "\n")
        proc.stdin.flush()
        try:
            # Budget covers interpreter start + plugin discovery + MCP
            # handshake. Measured 2026-11-21 on this host: 16.3s for the
            # first reply with a single stdio server, i.e. the old 10s
            # window failed for a worker that worked. The assertion is about
            # tool visibility, so give the process room and fail only when
            # it is genuinely silent.
            line = output.get(timeout=60)
        except queue.Empty:
            pytest.fail("slash worker produced no /tools response within 60 seconds")
        response = json.loads(line)
        assert response["ok"] is True
        assert "mcp__profileprobe__openamer_61922_profile_probe" in response["output"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
