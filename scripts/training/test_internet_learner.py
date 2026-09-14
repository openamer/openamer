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
            "incredible", "highly recommend", "view all docs")
    for m in re.finditer(r"([A-Z][^.!?]{40,250}[.!?])", text):
        s = m.group(1).strip()
        low = s.lower()
        if any(n in low for n in _NAV):
            continue
        if s.count("›") > 0 or "&amp;" in s or "&#" in s:
            continue
        if not il._looks_like_content(s):
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


# --- junk gate (regression: 13.09.26 the github cycle "learned" GitHub's
# anti-bot page — "You switched accounts on another tab or window." — and the
# technews cycle learned a newsletter footer. Page chrome is not knowledge.) ---

def test_login_wall_is_junk():
    assert il._is_junk("You switched accounts on another tab or window.")
    assert il._is_junk("Please sign in to continue")
    assert il._is_junk("Verify you are human")
    assert il._is_junk("404 Not Found")


def test_real_technical_insight_is_not_junk():
    real = ("Speculative decoding with a small draft model cuts decode latency "
            "by ~40% at equal output quality.")
    assert not il._is_junk(real)


# --- corporate first-person boilerplate (regression: 14.09.26 the efficiency
# cycle stored "Bit-TLS-Verschlüsselung Für die sichere Datenübertragung nutzen
# wir 256-Bit-TLS-…" — site chrome whose bare digit 256 satisfied the
# technical-signal gate, so the junk gate has to catch it on the vendor voice).
def test_vendor_tls_boilerplate_is_junk():
    chrome = ("Bit-TLS-Verschlüsselung Für die sichere Datenübertragung "
              "nutzen wir 256-Bit-TLS-")
    assert il._is_junk(chrome)


def test_real_tls_encryption_insight_is_not_junk():
    # A genuine security insight must survive the new pattern — the gate keys on
    # the vendor's first-person voice, never on the topic (TLS/encryption).
    real = ("TLS 1.3 removes a round trip from the handshake; session "
            "resumption cuts per-connection CPU cost.")
    assert not il._is_junk(real)


def test_filter_junk_drops_the_login_result_but_keeps_nothing_invented():
    raw = ("You switched accounts on another tab or window. :: Please sign in to continue. "
           "|| Methods to reduce inference cost in production :: "
           "We reduce cost by 40 percent with speculative decoding and caching.")
    kept = il._filter_junk(raw)
    assert "switched accounts" not in kept
    assert "reduce cost by 40 percent" in kept


def test_extract_insight_rejects_login_wall():
    raw = "You switched accounts on another tab or window. :: Please sign in to continue."
    assert il.extract_insight("github trending agents", raw) == "", \
        "an anti-bot page must not become a learned insight"


def test_extract_insight_keeps_a_real_title():
    raw = ("State space models reach transformer quality at half the decode cost :: "
           "The paper reports equal benchmark scores with a 2x faster decode path.")
    got = il.extract_insight("arxiv ssm", raw)
    assert "State space models" in got, got


def test_add_to_buffer_refuses_junk():
    """The write gate must reject page chrome before it reaches the buffer."""
    before = il.add_to_buffer("q", "You switched accounts on another tab or window.")
    assert before is False, "junk must never enter the training buffer"


# --- docs-site chrome in the deterministic extractor (13.09.26: the docs cycle
# returned "LoRA PEFT 🏡 View all docs AWS Trainium &amp; Inferentia ...") ---

def test_docs_nav_line_is_classified_junk():
    assert il._is_junk("LoRA PEFT View all docs AWS Trainium &amp; Inferentia")


def test_docs_nav_is_skipped_and_the_next_real_sentence_wins():
    page = ("LoRA PEFT View all docs AWS Trainium &amp; Inferentia Accelerate "
            "Argilla AutoTrain. "
            "LoRA adapters inject trainable low-rank matrices into each layer "
            "of a frozen model and cut fine-tuning memory by roughly 3 orders "
            "of magnitude.")
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
