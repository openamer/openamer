"""The OS boot job is the only thing that proves DIR-04's "it boots".

That makes the workflow itself load-bearing, so it gets the same treatment as
the code it verifies: a red run must mean the kernel broke, not that the job
drifted (an unpinned action, a stale image path, a toolchain component dropped
from the contract). Everything here is checked without QEMU and without a
network, so it runs in the normal suite.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "os-boot.yml"
TOOLCHAIN = REPO / "os" / "rust-toolchain.toml"
VERIFY = REPO / "os" / "scripts" / "verify_boot.py"
MARKER = "OpenAmer OS kernel is running."


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def steps(workflow: dict) -> list[dict]:
    return workflow["jobs"]["boot"]["steps"]


def test_workflow_shape(workflow: dict) -> None:
    assert workflow["name"] == "OS boot"
    assert set(workflow["jobs"]) == {"boot"}
    triggers = workflow[True]  # `on:` parses as a boolean key
    assert {"pull_request", "push", "workflow_dispatch"} <= set(triggers)
    # Only the kernel's own tree should trigger a boot.
    for trigger in ("pull_request", "push"):
        assert "os/**" in triggers[trigger]["paths"]


def test_job_is_bounded(workflow: dict) -> None:
    assert workflow["jobs"]["boot"]["timeout-minutes"] >= 20
    assert workflow["concurrency"]["cancel-in-progress"] is True


def test_remote_actions_are_pinned_to_commits(steps: list[dict]) -> None:
    unpinned = [
        step["uses"]
        for step in steps
        if "uses" in step and not re.search(r"@[0-9a-f]{40}\b", step["uses"])
    ]
    assert not unpinned, unpinned


def test_rust_src_is_declared_where_the_contract_lives() -> None:
    # bootloader 0.11 builds its BIOS/UEFI stage binaries against the standard
    # library. Without rust-src a fresh clone fails with "unable to build with
    # the standard library" — the failure that made the first run red.
    toolchain = TOOLCHAIN.read_text(encoding="utf-8")
    assert "rust-src" in toolchain
    assert "x86_64-unknown-none" in toolchain and "x86_64-unknown-uefi" in toolchain


def test_workflow_installs_the_same_components_as_the_contract(steps: list[dict]) -> None:
    install = next(step for step in steps if step.get("name", "").startswith("Install the pinned Rust"))
    run = install["run"]
    assert "rust-src" in run
    for target in ("x86_64-unknown-none", "x86_64-unknown-uefi"):
        assert target in run


def test_boots_the_image_the_builder_reported(steps: list[dict]) -> None:
    # A hardcoded path would pass while the builder wrote somewhere else.
    joined = "\n".join(step.get("run", "") for step in steps)
    assert "run --release -- paths" in joined
    assert "the BIOS image:  " in joined
    assert "scripts/verify_boot.py" in joined
    assert VERIFY.is_file()


def test_verifier_checks_the_marker_and_liveness() -> None:
    source = VERIFY.read_text(encoding="utf-8")
    assert MARKER in source
    # A kernel that panics after printing the marker must not count as booted.
    assert "alive" in source and "-snapshot" in source


def test_every_run_block_is_valid_shell(steps: list[dict]) -> None:
    for step in steps:
        if "run" not in step:
            continue
        completed = subprocess.run(
            ["bash", "-n"], input=step["run"], text=True, capture_output=True, timeout=60
        )
        assert completed.returncode == 0, (step.get("name"), completed.stderr)
