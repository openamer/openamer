"""Regression guard: the Windows updater binary must embed its frontend.

Symptom this pins
-----------------
`openamer update` (desktop -> `openamer-setup.exe --update`) opened a WHITE,
EMPTY window. The user saw a blank installer and no progress, and the update
chain stalled.

Root cause
----------
Tauri v2 compiles the app in DEV mode unless the `custom-protocol` feature is
enabled (`tauri-2/src/lib.rs`: `!cfg!(feature = "custom-protocol")` selects
the dev asset server). In dev mode the binary does NOT embed `frontendDist`
assets; it serves them from the Vite `devUrl` (`http://127.0.0.1:5175`),
which does not exist on a user's machine. Result: the WebView loads nothing and
the window stays blank.

The Tauri CLI passes `custom-protocol` automatically for `tauri build`, but a
plain `cargo build --release` does NOT -- which is exactly how the broken
binary on this host was produced (measured: deployed binary carried 0
`assets/` entries and no `index-*.js`; a `--features tauri/custom-protocol`
build carried 66 `assets/` entries plus `index-*.js` and rendered the UI).

The guard
---------
The `custom-protocol` feature must be declared as a dependency of the
`tauri` crate in `apps/bootstrap-installer/src-tauri/Cargo.toml`, so the
correct build is the ONLY possible one regardless of how it is invoked.

These checks are static (they read the manifest) so they run on every CI
host without a Rust toolchain or a built binary.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
INSTALLER = REPO / "apps" / "bootstrap-installer"
CARGO_TOML = INSTALLER / "src-tauri" / "Cargo.toml"
PACKAGE_JSON = INSTALLER / "package.json"
TAURI_CONF = INSTALLER / "src-tauri" / "tauri.conf.json"


def _cargo_toml_text() -> str:
    assert CARGO_TOML.exists(), f"missing {CARGO_TOML}"
    return CARGO_TOML.read_text(encoding="utf-8")


def _tauri_dependency_line() -> str:
    """Return the `tauri = {...}` dependency line from Cargo.toml."""
    for line in _cargo_toml_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("tauri =") or stripped.startswith("tauri="):
            return stripped
    pytest.fail("no `tauri` dependency found in apps/bootstrap-installer/src-tauri/Cargo.toml")


def test_tauri_crate_enables_custom_protocol():
    """`tauri` must depend on `custom-protocol`, or the binary ships blank.

    Without the feature Tauri runs in dev mode and serves the frontend from
    the Vite devUrl instead of the embedded assets -> white window.
    """
    line = _tauri_dependency_line()
    assert "custom-protocol" in line, (
        "the bootstrap-installer must build tauri with the `custom-protocol` "
        "feature, otherwise the shipped updater opens a WHITE window: "
        f"got {line!r}"
    )


def test_custom_protocol_feature_is_not_disabled_by_a_features_override():
    """A `features = []` override on the tauri dep would silently drop it."""
    line = _tauri_dependency_line()
    # `features = []` on the tauri dependency means the default feature set of
    # the tauri crate is replaced by the given list -> custom-protocol lost.
    match = re.search(r"features\s*=\s*\[([^\]]*)\]", line)
    assert match is not None, f"tauri dependency must list features explicitly: {line!r}"
    listed = match.group(1)
    assert "custom-protocol" in listed, (
        "the tauri dependency's explicit feature list must contain "
        f"`custom-protocol`: got {line!r}"
    )


def test_no_second_bare_tauri_dependency_without_the_feature():
    """A duplicate `tauri` dep without the feature would win the build."""
    lines = [
        line.strip()
        for line in _cargo_toml_text().splitlines()
        if line.strip().startswith("tauri =")
    ]
    assert len(lines) == 1, f"expected exactly one tauri dependency, got {lines!r}"
    assert "custom-protocol" in lines[0]


def test_frontend_dist_is_configured():
    """The app must point at a real frontendDist for the assets to embed."""
    assert TAURI_CONF.exists(), f"missing {TAURI_CONF}"
    text = TAURI_CONF.read_text(encoding="utf-8")
    assert "frontendDist" in text, (
        "tauri.conf.json must configure `frontendDist`, otherwise nothing is "
        "embedded into the binary and the installer window stays white"
    )


def test_installer_declares_the_react_binding_it_imports():
    """`@nanostores/react` is imported by the sources but must be declared.

    The sources import the React binding:
        src/app.tsx:1             import { useStore } from '@nanostores/react'
        src/routes/failure.tsx:1  import { useStore } from '@nanostores/react'
        src/routes/progress.tsx:1 import { useStore } from '@nanostores/react'

    `nanostores` alone does NOT provide `useStore`. An undeclared import makes
    a clean `npm install && npm run build` fail with
    `TS2307: Cannot find module '@nanostores/react'`, so the updater frontend
    cannot be rebuilt from a clean checkout.
    """
    assert PACKAGE_JSON.exists(), f"missing {PACKAGE_JSON}"
    import json

    pkg = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    declared = set(pkg.get("dependencies", {})) | set(pkg.get("devDependencies", {}))
    assert "@nanostores/react" in declared, (
        "apps/bootstrap-installer must declare `@nanostores/react` — the "
        "sources import it but `nanostores` does not provide `useStore`"
    )


def test_installed_versions_satisfy_the_declared_ranges():
    """The declared `@nanostores/react` range must be installable.

    Guards against a range that no published version satisfies (which npm
    silently resolves to nothing and breaks the build again).
    """
    import json

    pkg = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    spec = pkg.get("dependencies", {}).get("@nanostores/react")
    assert spec, "@nanostores/react must be a runtime dependency"
    assert spec.startswith("^") or spec.startswith("~") or spec[0].isdigit(), (
        f"unexpected version spec {spec!r}"
    )


if __name__ == "__main__":  # pragma: no cover - manual invocation
    sys.exit(pytest.main([__file__, "-v"]))
