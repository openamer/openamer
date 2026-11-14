"""Contract: the verification decision is reproducible and forgiving only of orthography.

The verifier is the only thing standing between "a model answered" and "a
language is supported". Its comparison must therefore:

* ignore case, accents and punctuation (those are orthographic variance, and a
  false alarm here would flag every language with diacritics);
* treat clitic/article drift as agreement when one string contains the other;
* treat genuinely different words as disagreement — measured: Afar "Save" came
  back as `Dhaagi` and `Kay` from two models, and that must not count as a match.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def verify():
    spec = importlib.util.spec_from_file_location(
        "verify_quality", REPO / "scripts" / "verify_locale_quality.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("left,right", [
    ("Sətt", "sətt"),            # case only
    ("Café", "Cafe"),             # combining accent is stripped by NFKD
    ("Geri!", "geri"),           # punctuation
])
def test_orthographic_variance_counts_as_agreement(verify, left, right):
    assert verify.similar(left, right) is True


@pytest.mark.parametrize("left,right", [
    ("Dhaagi", "Kay"),                    # measured Afar disagreement
    ("mā", "pərəz-dā"),                   # measured "Avestan" invention
    ("Seting", "Konfigurasiya"),          # different word, same meaning slot
])
def test_different_words_do_not_count_as_agreement(verify, left, right):
    assert verify.similar(left, right) is False


def test_clitic_drift_is_agreement_but_only_for_real_words(verify):
    assert verify.similar("bir kez", "birkez") is True
    assert verify.similar("i", "iz") is False   # too short to trust containment


def test_ratio_is_plain_agreement_share(verify):
    pairs = [("a", "a"), ("b", "b"), ("Dhaagi", "Kay"), ("Seting", "Seting")]
    assert verify.ratio(pairs) == 0.75
    assert verify.ratio([]) == 0.0


def test_supported_threshold_is_meaningful(verify):
    """A 0.7 threshold must not be reachable by two agreeing of five."""
    assert 0.5 < verify.SUPPORTED <= 0.9
    pairs = [("x", "x"), ("y", "y"), ("Dhaagi", "Kay"), ("mā", "pərəz-dā"), ("Seting", "Konf")]
    assert verify.ratio(pairs) < verify.SUPPORTED
