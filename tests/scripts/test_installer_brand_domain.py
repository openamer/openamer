"""The setup window must name the site that actually exists.

`openamer.dev` shipped in the footer of three screens — a domain that does not
resolve (measured 2026-11-18: `openamer.com` -> HTTP 200, `openamer.dev` ->
no contact). Nothing failed, because nothing checked. This is the check.
"""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
ROUTES = REPO / "apps" / "bootstrap-installer" / "src" / "routes"

CANONICAL = "openamer.com"


def test_no_dead_domain_in_the_installer() -> None:
    offenders = [
        f"{path.name}:{number}"
        for path in ROUTES.glob("*.tsx")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "openamer.dev" in line
    ]

    assert not offenders, f"openamer.dev does not resolve; found in {offenders}"


def test_every_terminal_screen_names_the_site() -> None:
    for name in ("welcome.tsx", "success.tsx", "failure.tsx"):
        source = (ROUTES / name).read_text(encoding="utf-8")

        assert CANONICAL in source, f"{name} must show {CANONICAL} in its footer"
