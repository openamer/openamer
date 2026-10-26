"""The s6-overlay service definitions must be LF and declare a valid type.

s6-rc-compile does not execute `type`; it compares the *entire* file contents
against the three literals ``oneshot``, ``longrun`` and ``bundle``. A file that
reads ``longrun`` plus a carriage return is none of them, and compilation
aborts container init::

    s6-rc-compile: fatal: invalid /etc/s6-overlay/s6-rc.d/main-openamer/type

s6-overlay then never reaches the point where it execs anything, so every
container started from the image hangs until the test's 180 s readiness
deadline — which is exactly how the whole docker lane went red: 20+ tests
reporting ``TimeoutError: container ... did not finish cont-init`` while the
real cause sat one byte per line away, in a file no test looked at.

A Windows checkout/commit rewrites these extensionless files as CRLF because
nothing in .gitattributes covered them. These assertions are the measurement
that was missing: they run in the ordinary unit suite (no Docker, no image) so
a CRLF regression fails in seconds, on the commit that introduces it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_S6_ROOT = _REPO_ROOT / "docker" / "s6-rc.d"
_VALID_TYPES = {"oneshot", "longrun", "bundle"}


def _service_type_files() -> list[Path]:
    return sorted(_S6_ROOT.rglob("type"))


def _all_s6_files() -> list[Path]:
    return sorted(p for p in _S6_ROOT.rglob("*") if p.is_file())


def test_the_tree_is_actually_present() -> None:
    """Guard against the assertions below silently matching nothing."""
    assert _S6_ROOT.is_dir(), f"missing s6 service tree: {_S6_ROOT}"
    assert _service_type_files(), "no `type` files found under docker/s6-rc.d"


@pytest.mark.parametrize("path", _service_type_files(), ids=lambda p: p.parent.name)
def test_type_file_declares_a_valid_service_type(path: Path) -> None:
    raw = path.read_bytes()
    assert b"\r" not in raw, (
        f"{path.relative_to(_REPO_ROOT).as_posix()} contains a carriage return; "
        "s6-rc-compile compares the file contents against oneshot/longrun/bundle "
        "byte-for-byte, so 'longrun\\r' is an invalid type and aborts container init"
    )
    value = raw.decode("utf-8").strip()
    assert value in _VALID_TYPES, (
        f"{path.relative_to(_REPO_ROOT).as_posix()} declares {value!r}; "
        f"only {sorted(_VALID_TYPES)} are accepted by s6-rc-compile"
    )


@pytest.mark.parametrize("path", _all_s6_files(), ids=lambda p: p.relative_to(_S6_ROOT).as_posix())
def test_no_s6_service_file_contains_cr(path: Path) -> None:
    raw = path.read_bytes()
    assert b"\r" not in raw, (
        f"{path.relative_to(_REPO_ROOT).as_posix()} contains a carriage return. "
        "These files are copied into the image verbatim: a CRLF shebang resolves to "
        "an interpreter named 'sh\\r', and a CRLF `type` breaks s6-rc-compile outright"
    )


def test_gitattributes_pins_the_s6_tree_to_lf() -> None:
    """The guard that keeps a Windows checkout from reintroducing the CRLF."""
    attributes = (_REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    rules = [line.strip() for line in attributes.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert "docker/s6-rc.d/** text eol=lf" in rules, (
        "docker/s6-rc.d/** must be pinned to LF: the service files have no "
        "extension, so a bare `*.sh` rule does not cover `type`, `run` or `finish`"
    )
