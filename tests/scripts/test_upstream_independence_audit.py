"""Contract: the upstream-independence audits classify correctly.

The audit scripts are the evidence behind the claim "OpenAmer is its own
architecture", so their classification logic is pinned here rather than
trusted. A synthetic upstream tree stands in for the real checkout, so the
test runs everywhere.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]


def _load(name: str):
    path = REPO / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


desktop = _load("audit_upstream_independence_desktop")
core = _load("audit_upstream_independence")


def test_rebrand_rewrites_upstream_names():
    assert desktop.rebrand("hermes_cli/foo") == "openamer_cli/foo"
    assert desktop.rebrand("HermesAgent") == "OpenAmerAgent"
    assert desktop.rebrand("HERMES_HOME") == "OPENAMER_HOME"


def test_rebrand_keeps_the_js_toolchain_names():
    """The npm scope ``@hermes/`` and ``hermes-parser`` must survive the rename.

    They are real package names on npm, not OpenAmer branding, so rewriting
    them would point the code at a package that does not exist.
    """
    assert desktop.rebrand("hermes-parser") == "hermes-parser"
    assert desktop.rebrand("@hermes/plugin-sdk") == "@hermes/plugin-sdk"
    assert desktop.rebrand("@hermes/ink") == "@hermes/ink"
    assert desktop.rebrand("hermes-estimator") == "hermes-estimator"


def test_port_script_rebrand_keeps_the_js_toolchain_names():
    port = _load("port_from_upstream")
    assert port.rebrand("hermes-parser") == "hermes-parser"
    assert port.rebrand("@hermes/plugin-sdk") == "@hermes/plugin-sdk"
    assert port.rebrand("hermes_cli/main.py") == "openamer_cli/main.py"


def test_port_script_guard_still_catches_real_leaks():
    """The branding guard must fire on a genuine upstream leak."""
    port = _load("port_from_upstream")
    leaks = port.leftover_hermes("import hermes_state\n", "x.py")
    assert leaks, "a real hermes import must be reported as a leak"
    # a kept npm scope alone is not a leak
    assert port.leftover_hermes("import '@hermes/plugin-sdk'\n", "x.py") == []


def test_check_only_reports_zero_unattributed_leaks():
    """The shipped tree must carry no upstream name outside a known
    attribution site or the audit tooling itself."""
    port = _load("port_from_upstream")
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "port_from_upstream.py"), "--check-only"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=600,
    )
    assert "leftover hermes tokens: 0" in result.stdout, result.stdout
    assert result.returncode == 0, result.stdout


def test_core_rebrand_matches_desktop_rebrand():
    for token in ("hermes_cli/foo", "HermesAgent", "HERMES_HOME", "hermes-agent"):
        assert core.rebrand(token) == desktop.rebrand(token), token


def test_classify_detects_identical():
    text = "const a = 1;\nconst b = 2;\n"
    assert desktop.classify(text, text)[0] == "IDENTICAL"
    assert core.classify(text, text)[0] == "IDENTICAL"


def test_classify_detects_cosmetic():
    src = "const a = 1;\nconst b = 2;\n"
    dst = "// a comment\nconst a = 1;\nconst b = 2;\n"
    assert desktop.classify(src, dst)[0] == "COSMETIC"


def test_classify_detects_minor_and_substantive():
    src = "\n".join(f"const v{i} = {i};" for i in range(100))
    minor = "\n".join(
        f"const v{i} = {i};" if i >= 5 else f"const v{i} = {i} + 1;" for i in range(100)
    )
    assert desktop.classify(src, minor)[0] == "MINOR"

    subst = "\n".join(f"const w{i} = {i * 2};" for i in range(100))
    assert desktop.classify(src, subst)[0] == "SUBSTANTIVE"


def test_classify_ignores_blank_and_tiny_changes():
    src = "const a = 1;\n"
    dst = "const a = 1;\n\n"
    assert desktop.classify(src, dst)[0] == "IDENTICAL"


def test_changed_lines_counts_each_change_once():
    """A modified line is one change, not two (unified_diff emits - and +)."""
    src = "\n".join(f"const v{i} = {i};" for i in range(100))
    dst = "\n".join(f"const v{i} = {i};" for i in range(100))
    dst = dst.replace("const v50 = 50;", "const v50 = 999;")
    changed, added = desktop._changed_lines(src.splitlines(), dst.splitlines(), desktop.NOISE)
    assert changed == 1
    assert added == 1
    changed, added = core._changed_lines(src.splitlines(), dst.splitlines(), core.NOISE)
    assert changed == 1
    assert added == 1


def test_walk_skips_node_modules(tmp_path):
    (tmp_path / "keep.ts").write_text("x", encoding="utf-8")
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "skip.ts").write_text("x", encoding="utf-8")
    found = [p.name for p in desktop.walk(tmp_path, {".ts"})]
    assert found == ["keep.ts"]


def test_desktop_audit_runs_on_a_synthetic_tree(tmp_path):
    """End-to-end: a synthetic upstream checkout yields a sane report."""
    up = tmp_path / "up"
    oa = tmp_path / "oa"
    for tree in (up, oa):
        (tree / "apps" / "desktop" / "src" / "lib").mkdir(parents=True)

    (up / "apps" / "desktop" / "src" / "lib" / "same.ts").write_text(
        "export const a = 1;\n", encoding="utf-8"
    )
    (oa / "apps" / "desktop" / "src" / "lib" / "same.ts").write_text(
        "export const a = 1;\n", encoding="utf-8"
    )
    (up / "apps" / "desktop" / "src" / "lib" / "diff.ts").write_text(
        "\n".join(f"export const v{i} = {i};" for i in range(50)), encoding="utf-8"
    )
    (oa / "apps" / "desktop" / "src" / "lib" / "diff.ts").write_text(
        "\n".join(f"export const w{i} = {i * 3};" for i in range(50)), encoding="utf-8"
    )
    (up / "apps" / "desktop" / "src" / "lib" / "only-up.ts").write_text(
        "export const gone = 1;\n", encoding="utf-8"
    )
    (oa / "apps" / "desktop" / "src" / "lib" / "only-oa.ts").write_text(
        "export const mine = 1;\n", encoding="utf-8"
    )

    # Point both the upstream tree and the OpenAmer tree at the fixture, so
    # the report lands in the fixture's reports/ directory, not the real one.
    assert desktop.audit(up, oa) == 0

    import json

    report = json.loads(
        (oa / "reports" / "upstream-independence-audit-desktop.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["upstream_files"] == 3
    assert report["openamer_files"] == 3
    assert report["compared"] == 2
    assert report["upstream_only_dropped"] == 1
    assert report["classes"]["IDENTICAL"] == 1
    assert report["classes"]["SUBSTANTIVE"] == 1
    assert report["identical_files"] == ["lib/same.ts"]


def test_scripts_are_executable_and_self_contained():
    for name in (
        "audit_upstream_independence",
        "audit_upstream_independence_desktop",
        "audit_upstream_coupling",
        "port_from_upstream",
    ):
        path = REPO / "scripts" / f"{name}.py"
        assert path.is_file(), name
        src = path.read_text(encoding="utf-8")
        assert 'if __name__ == "__main__":' in src, name
        compile(src, str(path), "exec")


def test_the_shared_rebrand_module_is_importable():
    """The shared map is a library, not a CLI -- it must still compile."""
    path = REPO / "scripts" / "upstream_rebrand.py"
    assert path.is_file()
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_all_three_scripts_share_one_rebrand_map():
    """One source of truth: the porting tool and both audits must apply the
    same rename, or they disagree about what "rebranded upstream" means."""
    canonical = _load("upstream_rebrand")
    port = _load("port_from_upstream")
    for module in (port, core, desktop):
        assert module.rebrand("hermes_cli/x") == canonical.rebrand("hermes_cli/x")
        assert module.rebrand("@hermes/plugin-sdk") == "@hermes/plugin-sdk"
    assert port.RENAMES == canonical.RENAMES
