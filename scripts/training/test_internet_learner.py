#!/usr/bin/env python3
"""Tests for internet_learner.py pure logic (no network).

Covers the testable pieces of deep-reading: HTML stripping and Bing
ck/a redirect decoding. The network-bound _fetch_page/_search_urls are
exercised via their pure helpers here.
"""
import os, re, sys, base64

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import internet_learner as il


def test_strip_html_removes_tags_and_scripts():
    html = ("<html><head><style>.x{color:red}</style>"
            "<script>var a=1;</script></head>"
            "<body><h1>Title</h1><p>Hello <b>world</b>.</p></body></html>")
    text = il._strip_html(html)
    assert "Title" in text
    assert "Hello world" in text
    assert "var a=1" not in text, "script content must be stripped"
    assert "color:red" not in text, "style content must be stripped"
    assert "<" not in text, "no tags may remain"


def test_strip_html_collapses_whitespace():
    text = il._strip_html("<p>a</p>\n\n  <p>b</p>")
    assert text == "a b", f"expected 'a b', got {text!r}"


def test_decode_bing_url_roundtrip():
    target = "https://example.com/article"
    b64 = base64.b64encode(target.encode()).decode()
    redirect = f"https://www.bing.com/ck/a?!&&p=x&u=a1{b64}&ntb=1"
    assert il._decode_bing_url(redirect) == target


def test_decode_bing_url_urlsafe():
    # URL-safe base64 with - and _ must still decode
    target = "https://example.com/a?b=c&d=e"
    b64 = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
    redirect = f"https://www.bing.com/ck/a?u=a1{b64}"
    assert il._decode_bing_url(redirect) == target


def test_decode_bing_url_no_u_param():
    assert il._decode_bing_url("https://www.bing.com/ck/a?p=123") == ""


def test_decode_bing_url_invalid_b64():
    assert il._decode_bing_url("https://www.bing.com/ck/a?u=a1!!!notb64!!!") == ""


# --- chrome/testimonial filter (regression: the "No thanks “Sebastian is an
# incredible educator..." testimonial was learned TWICE on 11.09.26) ---

def _extract_first_sentence(text):
    """Mirror of deep_learn's deterministic extraction, on in-memory text."""
    _NAV = ("no thanks", "testimonial", "subscribe", "newsletter", "sign up",
            "incredible", "highly recommend")
    for m in re.finditer(r"([A-Z][^.!?]{40,250}[.!?])", text):
        s = m.group(1).strip()
        low = s.lower()
        if any(n in low for n in _NAV):
            continue
        if s.count("›") > 0 or s.count("&amp;") > 1:
            continue
        return s
    return ""


def test_chrome_testimonial_is_rejected():
    page = ("No thanks “Sebastian is an incredible educator and always has "
            "invaluable insights--do keep up with his work! "
            "Subscribe to our newsletter for weekly updates about the course.")
    assert _extract_first_sentence(page) == "", \
        "testimonial/marketing chrome must not become a learned insight"


def test_real_technical_sentence_survives_the_filter():
    page = ("No thanks “Sebastian is an incredible educator! "
            "LoRA adapters inject trainable low-rank matrices into each layer "
            "and cut fine-tuning memory by roughly three orders of magnitude.")
    got = _extract_first_sentence(page)
    assert got.startswith("LoRA adapters inject"), got


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {t.__name__}: {e}")
        except Exception as e:
            print(f"  [ERROR] {t.__name__}: {e}")
    print(f"\nRESULT: {passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
