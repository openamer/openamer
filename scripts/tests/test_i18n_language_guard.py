"""The Avestan catalog must not carry Azerbaijani text.

Regression: a translation run filled `ae.ts` with Azerbaijani — `Söndür`
("turn off"), `Yenidən skan et` ("rescan") — while only ~18% of the values were
in Avestan. Any user selecting Avestan was reading Turkish. A wrong language is
worse than a known English fallback, because it claims to be the user's.

These tests pin the detector and the invariant that the catalog stays clean.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import i18n_language_guard as guard  # noqa: E402


# ------------------------------------------------------------------ detector
@pytest.mark.parametrize("text", [
    "Söndür",
    "Yenidən skan et",
    "Fayl menecerində göstər",
    "Plagin qovluğunu aç",
    "Bu tətbiqə yüklənmiş UI genişləndirmələri",
    "başarısız",
])
def test_detects_azerbaijani(text):
    assert guard.is_foreign(text) is True


@pytest.mark.parametrize("text", [
    "Test sent. If nothing appears, check your OS notification permissions.",
    "Search API keys...",
    "Initial Public Offering",
    "Removed.",
    "",
])
def test_does_not_flag_english(text):
    """ASCII capital `I` must never be a marker — it flagged 'If ...' sentences."""
    assert guard.is_foreign(text) is False


def test_avestan_script_is_not_foreign():
    assert guard.is_foreign("\U00010B00\U00010B01\U00010B02") is False


# -------------------------------------------------------------------- parser
def test_parser_builds_dotted_paths(tmp_path):
    src = tmp_path / "en.ts"
    src.write_text(
        "export const en = defineLocale({\n"
        "  settings: {\n"
        "    plugins: {\n"
        "      title: 'Desktop plugins',\n"
        "      blurb: 'Loaded from disk.',\n"
        "    },\n"
        "    mode: {\n"
        "      light: { label: 'Light' },\n"
        "    },\n"
        "  },\n"
        "});\n",
        encoding="utf-8",
    )
    vals = guard.values_by_path(src)
    assert vals["settings.plugins.title"] == "Desktop plugins"
    assert vals["settings.plugins.blurb"] == "Loaded from disk."
    assert vals["settings.mode.light.label"] == "Light"


# ----------------------------------------------------------------- invariant
def test_avedstan_catalog_has_no_azerbaijani_sentences():
    """The repaired file must not contain the Azerbaijani strings that were found."""
    ae = REPO / "apps" / "desktop" / "src" / "i18n" / "ae.ts"
    if not ae.exists():
        pytest.skip("desktop i18n tree not present")
    text = ae.read_text(encoding="utf-8")
    for marker in ("Söndür", "Yenidən skan et", "Plagin qovluğunu aç",
                   "Fayl menecerində göstər", "tətbiqə yüklənmiş"):
        assert marker not in text, f"Azerbaijani string survived in ae.ts: {marker}"


def test_ae_keeps_its_avestan_values():
    """Repair must not blank the locale — the Avestan content has to survive."""
    ae = REPO / "apps" / "desktop" / "src" / "i18n" / "ae.ts"
    if not ae.exists():
        pytest.skip("desktop i18n tree not present")
    vals = guard.values_by_path(ae)
    native = [v for v in vals.values() if guard.AVESTAN.search(v)]
    assert len(native) > 200, f"only {len(native)} Avestan values left"
