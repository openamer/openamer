#!/usr/bin/env python3
"""Tests for internet_learner.py pure logic (no network).

Covers the testable pieces of deep-reading: HTML stripping and Bing
ck/a redirect decoding. The network-bound _fetch_page/_search_urls are
exercised via their pure helpers here.
"""
import os, sys, base64

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
