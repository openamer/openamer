#!/usr/bin/env python3
"""Tests for internet_learner.py pure logic (no network).

Covers the testable pieces of deep-reading: HTML stripping and Bing
ck/a redirect decoding. The network-bound _fetch_page/_search_urls are
exercised via their pure helpers here.
"""
import os, re, sys, base64, json

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


# --- degenerate result URLs that starved deep_learn (14.09.26: the CDP/Bing
# path returned a bare domain and an "arxiv.org/abs" stub; the old
# `if urls: return urls[:k]` handed them on and the HTTP fallback never ran) ---

def test_usable_urls_drops_bare_domains_and_stubs():
    raw = ["https://the-agent-report.com", "https://arxiv.org/abs",  # unfetchable
           "https://arxiv.org/html", "https://example.com/",
           "https://arxiv.org/abs/2601.01743"]                       # the real one
    assert il._usable_urls(raw, 5) == ["https://arxiv.org/abs/2601.01743"]


def test_usable_urls_honours_k_and_empty_input():
    urls = ["https://a.com/p1", "https://b.com/p2", "https://c.com/p3"]
    assert il._usable_urls(urls, 2) == urls[:2]
    assert il._usable_urls([], 3) == []




class _FakeResp:
    """Minimal urlopen() stand-in: .read() returns the bytes we handed in."""
    def __init__(self, text):
        self._b = text.encode()

    def read(self):
        return self._b



def test_fresh_headline_never_returns_a_self_post():
    """Show/Ask HN product pages carry ad copy, so they must be skipped.

    Regression, live 15.09.26: cycle_c_github took "Show HN: A murder mystery
    game built on an open-source gen-AI agent framework", deep-read ad copy and
    was gated — the whole cycle wasted. "" hands over to the LLM query instead.
    """
    hits = [{"title": "Show HN: A murder mystery game built on an open-source gen-AI agent framework"},
            {"title": "Ask HN: who is hiring agents right now"}]
    real = il.urllib.request.urlopen
    il.urllib.request.urlopen = lambda *a, **k: _FakeResp(json.dumps({"hits": hits}))
    try:
        assert il._fresh_headline("AI agent framework", []) == ""
    finally:
        il.urllib.request.urlopen = real


def test_fresh_headline_takes_a_real_article_over_a_self_post():
    hits = [{"title": "Show HN: my agent framework, please star it"},
            {"title": "A practical guide to agent memory architectures with benchmarks"}]
    real = il.urllib.request.urlopen
    il.urllib.request.urlopen = lambda *a, **k: _FakeResp(json.dumps({"hits": hits}))
    try:
        assert il._fresh_headline("AI agent", []).startswith("A practical guide")
    finally:
        il.urllib.request.urlopen = real


def test_store_or_deep_retries_deep_with_wider_k():
    """First deep pass (k=2) empty -> second pass must use k=6 before giving up."""
    ks, good = [], "vLLM 0.9 adds disaggregated prefill and 2x throughput."
    real_store, real_deep = il.store, il.deep_learn
    il.store = lambda user, ins: ins == good
    il.deep_learn = lambda q, k=2: (ks.append(k), good if k == 6 else "")[1]
    try:
        assert il.store_or_deep("u", "q", "") == good
        assert ks == [2, 6], f"expected k=2 then k=6, got {ks}"
    finally:
        il.store, il.deep_learn = real_store, real_deep


def test_store_or_deep_returns_empty_when_both_gates_reject():
    real_store, real_deep = il.store, il.deep_learn
    il.store = lambda user, ins: False
    il.deep_learn = lambda q, k=2: ""
    try:
        assert il.store_or_deep("u", "q", "chrome") == ""
    finally:
        il.store, il.deep_learn = real_store, real_deep

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
