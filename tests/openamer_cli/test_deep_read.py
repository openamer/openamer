"""Tests for the deep reader — local fixtures, no network."""

from __future__ import annotations

from lxml import html as lxml_html

from openamer_cli.deep_read import (
    MIN_USEFUL_CHARS,
    _analyze_document,
    check_code_block,
    read_pdf,
    summarize,
    to_training_record,
)
from openamer_cli.deep_read import ReadResult

ARTICLE = "<p>" + ("This paragraph carries real article content about agent design. " * 40) + "</p>"


def _analyze(markup: str, follow_pdf: bool = False) -> ReadResult:
    doc = lxml_html.fromstring(markup)
    return _analyze_document(doc, ReadResult(url="https://example.test/x", final_url="https://example.test/x"),
                             follow_pdf=follow_pdf)


def test_boilerplate_is_removed():
    result = _analyze(f"""
    <html lang="en"><head><title>Real Title</title></head><body>
      <nav>Home | About | Impressum</nav>
      <header>Site masthead advertising the newsletter</header>
      <article>
        <h2>Section heading</h2>
        {ARTICLE}
      </article>
      <div class="cookie-banner">We use cookies to improve your experience</div>
      <footer>Copyright 2026 Example Inc</footer>
    </body></html>
    """)
    assert "Impressum" not in result.text
    assert "cookies to improve" not in result.text
    assert "Copyright 2026" not in result.text
    assert "real article content" in result.text
    assert result.title == "Real Title"
    assert result.lang == "en"


def test_structure_is_preserved():
    result = _analyze(f"""
    <html><body><article>
      <h1>Main</h1><h3>Deeper</h3>
      {ARTICLE}
      <ul><li>first item</li><li>second item</li></ul>
      <table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>
    </article></body></html>
    """)
    levels = [lvl for lvl, _ in result.headings]
    assert 1 in levels and 3 in levels
    assert result.list_items == 2
    assert result.tables == 1
    assert "- first item" in result.text
    assert "a | b" in result.text


def test_code_blocks_are_detected_and_syntax_checked():
    good = "def add(a, b):\n    return a + b\n"
    bad = "def broken(:\n    return 1\n"
    result = _analyze(f"""
    <html><body><article>{ARTICLE}
      <pre><code class="language-python">{good}</code></pre>
      <pre><code class="language-python">{bad}</code></pre>
    </article></body></html>
    """)
    assert len(result.code_blocks) == 2
    assert len(result.code_checks) == 2
    assert result.code_checks[0].ok is True
    assert result.code_checks[1].ok is False
    assert "SyntaxError" in result.code_checks[1].detail
    assert any("failed syntax check" in c for c in result.checks)


def test_links_inside_paragraphs_are_collected():
    result = _analyze(f"""
    <html><body><article>{ARTICLE}
      <p>See <a href="/docs/one">the first source</a> and
         <a href="https://other.test/two">the second</a>.</p>
    </article></body></html>
    """)
    hrefs = [h for _, h in result.links]
    assert "https://example.test/docs/one" in hrefs
    assert "https://other.test/two" in hrefs


def test_quantitative_claims_are_extracted():
    result = _analyze(f"""
    <html><body><article>{ARTICLE}
      <p>The model reaches 28.4 BLEU on the WMT 2014 task, improving by 2.0 points.</p>
    </article></body></html>
    """)
    assert any("28.4 BLEU" in c for c in result.numbers)


def test_thin_page_is_flagged():
    result = _analyze("<html><body><article><p>Too short.</p></article></body></html>")
    assert result.verdict == "thin"
    assert result.text_chars < MIN_USEFUL_CHARS
    assert any("only" in c for c in result.checks)


def test_paywall_is_detected():
    result = _analyze("""
    <html><body><article>
      <h1>Premium piece</h1>
      <p>This article is for subscribers. Subscribe to continue reading.</p>
    </article></body></html>
    """)
    assert result.verdict == "paywall"


def test_published_date_and_byline_from_citation_meta():
    result = _analyze("""
    <html><head>
      <meta name="citation_title" content="A Paper">
      <meta name="citation_author" content="Vaswani, Ashish">
      <meta name="citation_author" content="Shazeer, Noam">
      <meta name="citation_publication_date" content="2017/06/12">
    </head><body><article>""" + ARTICLE + """</article></body></html>
    """)
    assert result.title == "A Paper"
    assert "Vaswani" in result.byline and "Shazeer" in result.byline
    assert result.published == "2017/06/12"


def test_check_code_block_python_valid_and_invalid():
    ok = check_code_block("python", "def f(x):\n    return x * 2\n")
    assert ok.ok and ok.detail == "parses"
    bad = check_code_block("python", "def f(x)\n    return x\n")
    assert not bad.ok and "SyntaxError" in bad.detail


def test_check_code_block_json():
    assert check_code_block("json", '{"a": 1}').ok
    assert not check_code_block("json", '{"a": }').ok


def test_check_code_block_brackets():
    assert check_code_block("bash", "if [ -f x ]; then echo y; fi").ok
    # tolerance is 1 (brackets inside strings), so the case must be clearly off
    unbalanced = check_code_block("unknown", "call(a, b, [c, d")
    assert not unbalanced.ok
    assert "unbalanced" in unbalanced.detail


def test_read_pdf_rejects_garbage():
    text, pages, err = read_pdf(b"not a pdf at all")
    assert text == ""
    assert pages == 0
    assert "failed" in err.lower() or err


def test_training_record_keeps_full_text():
    result = _analyze(f"<html><body><article><h1>T</h1>{ARTICLE}</article></body></html>")
    rec = to_training_record(result)
    assert rec["a"] == result.text
    assert rec["chars"] == result.text_chars
    assert rec["chars"] > 1000, "a learning record must not be a 150-char snippet"
    assert rec["source"].startswith("https://")


def test_summarize_mentions_content_and_verdict():
    result = _analyze(f"<html><body><article>{ARTICLE}</article></body></html>")
    out = summarize(result)
    assert "Content" in out and "Verdict" in out
    assert "OK" in out or "THIN" in out
