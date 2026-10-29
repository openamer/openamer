"""Everything under docker/ must reach the image with LF line endings.

These files are copied into the image with a bare ``COPY`` and read
byte-for-byte, not through a shell:

``docker/s6-rc.d/<svc>/type``
    s6-rc-compile does not execute it; it compares the entire contents against
    the three literals ``oneshot``, ``longrun`` and ``bundle``. A file that
    reads ``longrun`` plus a carriage return is none of them, and compilation
    aborts container init::

        s6-rc-compile: fatal: invalid /etc/s6-overlay/s6-rc.d/main-openamer/type

    s6-overlay never reaches the point where it execs anything, so every
    container started from the image hangs until the test's 180 s readiness
    deadline — which is exactly how the whole docker lane went red: 20+ tests
    reporting ``TimeoutError: container ... did not finish cont-init`` while
    the cause sat one byte per line away, in a file no test looked at.

``docker/cont-init.d/*``
    The same class of bug one stage later: a CRLF shebang resolves to an
    interpreter named ``sh`` plus a carriage return.

A Windows checkout/commit rewrites these files as CRLF because the earlier
``*.sh`` rule covered neither the extensionless ``type``/``run``/``finish`` nor
the hook scripts. These assertions are the measurement that was missing: they
run in the ordinary unit suite — no Docker, no image — so a CRLF regression
fails in about a second, on the commit that introduces it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCKER_ROOT = _REPO_ROOT / "docker"
_S6_ROOT = _DOCKER_ROOT / "s6-rc.d"
_VALID_TYPES = {"oneshot", "longrun", "bundle"}


def _docker_files() -> list[Path]:
    return sorted(p for p in _DOCKER_ROOT.rglob("*") if p.is_file())


def _service_type_files() -> list[Path]:
    return sorted(_S6_ROOT.rglob("type"))


def test_the_tree_is_actually_present() -> None:
    """Guard against the assertions below silently matching nothing."""
    assert _S6_ROOT.is_dir(), f"missing s6 service tree: {_S6_ROOT}"
    assert _service_type_files(), "no `type` files found under docker/s6-rc.d"
    assert len(_docker_files()) > 5, "docker/ looks empty; scope of this test is wrong"


@pytest.mark.parametrize("path", _service_type_files(), ids=lambda p: p.parent.name)
def test_type_file_declares_a_valid_service_type(path: Path) -> None:
    raw = path.read_bytes()
    assert b"\r" not in raw, (
        f"{path.relative_to(_REPO_ROOT).as_posix()} contains a carriage return; "
        "s6-rc-compile compares the file contents against oneshot/longrun/bundle "
        "byte-for-byte, so 'longrun' plus a CR is an invalid type and aborts container init"
    )
    value = raw.decode("utf-8").strip()
    assert value in _VALID_TYPES, (
        f"{path.relative_to(_REPO_ROOT).as_posix()} declares {value!r}; "
        f"only {sorted(_VALID_TYPES)} are accepted by s6-rc-compile"
    )


@pytest.mark.parametrize("path", _docker_files(), ids=lambda p: p.relative_to(_DOCKER_ROOT).as_posix())
def test_no_docker_file_contains_cr(path: Path) -> None:
    raw = path.read_bytes()
    assert b"\x00" not in raw, (
        f"{path.relative_to(_REPO_ROOT).as_posix()} looks binary, but "
        "`.gitattributes` pins docker/** to `text eol=lf`; add an explicit `-text` "
        "rule for it before committing a binary here"
    )
    assert b"\r" not in raw, (
        f"{path.relative_to(_REPO_ROOT).as_posix()} contains a carriage return. "
        "These files are copied into the image verbatim: a CRLF `type` breaks "
        "s6-rc-compile outright and a CRLF shebang resolves to 'sh' plus a CR"
    )


def test_gitattributes_pins_docker_to_lf() -> None:
    """The guard that keeps a Windows checkout from reintroducing the CRLF."""
    attributes = (_REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    rules = [line.strip() for line in attributes.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert "docker/** text eol=lf" in rules, (
        "docker/** must be pinned to LF: the service files have no extension and the "
        "cont-init hooks are not *.sh, so a per-extension rule does not cover them"
    )
