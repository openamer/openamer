"""Regression test: a dead funding link must not come back.

2026-09-14: an audit of every funding URL — read by RENDERED PAGE, not by status
code — found six of seven routes dead. The trap is that a dead page often
answers HTTP 200 with a not-found body (paypalme/openamer, issuehunt). They were
removed from every user-facing surface; this pins that they stay gone, and that
the single verified route is the one that is wired.

Hermetic: pure static file inspection, no network, no clock.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]

LIVE = "www.paypal.com/ncp/payment/3HMBFYC9CQTMS"

# Each of these answered 200/302/404 while being useless to a donor.
DEAD = (
    "paypal.com/paypalme/openamer",
    "github.com/sponsors/openamer",
    "buymeacoffee.com/openamer",
    "ko-fi.com/openamer_agent",
    "oss.issuehunt.io/r/openamer",
)

# Every surface a visitor or donor can actually reach.
SURFACES = (
    "README.md",
    "LICENSE.md",
    "SPONSORS.md",
    ".github/FUNDING.yml",
    "docs/landing.html",
    "docs/index.html",
    "docs/consulting.html",
    "docs/skills-store.html",
    "docs/academy.html",
    "LAUNCH/support_posts.md",
)


def test_no_dead_funding_url_on_any_surface():
    offenders = {}
    for rel in SURFACES:
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = [d for d in DEAD if d in text]
        if hits:
            offenders[rel] = hits
    assert not offenders, f"dead funding links re-appeared: {offenders}"


def test_funding_script_exposes_only_the_live_route():
    import importlib.util

    spec = importlib.util.spec_from_file_location("funding", REPO / "scripts" / "funding.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert "issuehunt" not in mod.PAYMENT_LINKS, "dead issuehunt route still wired"
    assert mod.PAYMENT_LINKS["paypal"].endswith("ncp/payment/3HMBFYC9CQTMS")
    for url in mod.PAYMENT_LINKS.values():
        assert not any(d in url for d in DEAD), f"dead url wired: {url}"


def test_funding_yml_advertises_the_live_route_only():
    data = yaml.safe_load((REPO / ".github" / "FUNDING.yml").read_text(encoding="utf-8"))
    assert "issuehunt" not in data, "dead issuehunt key still advertised to GitHub"
    assert data.get("custom") == [f"https://{LIVE}"]
    # A bare 'github: [openamer]' makes GitHub render a sponsor button that
    # 302s to the plain profile — the exact dead CTA that was removed.
    assert not data.get("github")


def test_the_live_route_is_actually_still_referenced():
    """Removing dead links must not have removed the working one."""
    blob = "\n".join(
        (REPO / rel).read_text(encoding="utf-8", errors="replace")
        for rel in ("README.md", "SPONSORS.md", "docs/landing.html")
    )
    assert LIVE in blob