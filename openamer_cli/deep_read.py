"""Deep reading: fetch a source and actually read all of it.

The internet learner's problem, measured 2026-11-01 on 4,085 cycles:

    chars per "learned" record: median 154, mean 185, 88% under 300

because ``extract_insight()`` returns a *search-result snippet*
(``snippet[:150]``, ``insights[:2][:300]``) — never the page. Calling that
"learning" is page-visiting, not reading.

This module does the reading part:

    fetch -> strip boilerplate -> isolate main content -> keep structure
          (headings, paragraphs, code blocks, lists, tables)
          -> extract metadata (title, author, date, language)
          -> check (thin content, paywall, boilerplate ratio, missing date)
          -> test what is testable (code-block syntax, numeric sanity)
          -> return the whole thing, not a 150-char tail

Nothing here executes code from a page. "Testing" a code block means checking
that it parses, never running it.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin, urlparse

MIN_USEFUL_CHARS = 800
INSTALL_HINT = "pip install -e .[read]   (or: pip install lxml pypdf)"
BOILERPLATE_TAGS = (
    "script", "style", "noscript", "nav", "header", "footer", "aside",
    "form", "iframe", "svg", "button", "select", "template",
)
BOILERPLATE_HINTS = (
    "cookie", "consent", "newsletter", "subscribe", "paywall", "advert",
    "breadcrumb", "sidebar", "related", "share", "social", "comment",
    "navbar", "menu", "banner", "promo",
)
PAYWALL_MARKERS = (
    "subscribe to continue", "subscribers only", "sign in to continue",
    "create a free account to read", "this article is for subscribers",
    "already a subscriber", "log in to read",
)
CODE_LANG_HINTS = {
    "python": "python", "py": "python", "python3": "python",
    "javascript": "javascript", "js": "javascript", "ts": "typescript",
    "typescript": "typescript", "json": "json", "bash": "bash",
    "sh": "bash", "shell": "bash", "sql": "sql", "yaml": "yaml", "yml": "yaml",
}


@dataclass
class CodeCheck:
    lang: str
    chars: int
    ok: bool
    detail: str = ""


@dataclass
class ReadResult:
    url: str
    final_url: str = ""
    status: int = 0
    content_type: str = ""
    title: str = ""
    byline: str = ""
    published: str = ""
    lang: str = ""
    text: str = ""
    headings: list[tuple[int, str]] = field(default_factory=list)
    code_blocks: list[tuple[str, str]] = field(default_factory=list)
    tables: int = 0
    list_items: int = 0
    links: list[tuple[str, str]] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)
    html_chars: int = 0
    html_text_chars: int = 0
    pdf_chars: int = 0
    boilerplate_chars: int = 0
    checks: list[str] = field(default_factory=list)
    code_checks: list[CodeCheck] = field(default_factory=list)
    verdict: str = "unknown"
    error: str = ""

    @property
    def text_chars(self) -> int:
        return len(self.text)

    @property
    def article_ratio(self) -> float:
        """Share of the fetched HTML that is article text (PDF excluded)."""
        base = self.html_text_chars or self.text_chars
        return base / self.html_chars if self.html_chars else 0.0

    @property
    def words(self) -> int:
        return len(self.text.split())

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status": self.status,
            "content_type": self.content_type,
            "title": self.title,
            "byline": self.byline,
            "published": self.published,
            "lang": self.lang,
            "text_chars": self.text_chars,
            "html_text_chars": self.html_text_chars,
            "pdf_chars": self.pdf_chars,
            "words": self.words,
            "headings": len(self.headings),
            "code_blocks": len(self.code_blocks),
            "tables": self.tables,
            "list_items": self.list_items,
            "links": len(self.links),
            "html_chars": self.html_chars,
            "article_ratio": round(self.article_ratio, 4),
            "checks": self.checks,
            "code_checks": [c.__dict__ for c in self.code_checks],
            "verdict": self.verdict,
            "error": self.error,
            "text": self.text,
        }


def _clean_ws(s: str) -> str:
    return re.sub(r"[ \t\u00a0]+", " ", s.replace("\r", "")).strip()


def _drop_boilerplate(doc) -> int:
    """Remove chrome nodes; return how many characters were dropped."""
    dropped = 0
    for tag in BOILERPLATE_TAGS:
        for node in doc.xpath(f"//{tag}"):
            dropped += len("".join(node.itertext()))
            node.drop_tree()
    # class/id hints (cookie banners, sidebars, share widgets, ...)
    for node in doc.xpath("//*[@class or @id]"):
        ident = f"{node.get('class','')} {node.get('id','')}".lower()
        if any(h in ident for h in BOILERPLATE_HINTS):
            dropped += len("".join(node.itertext()))
            node.drop_tree()
    return dropped


def _main_node(doc):
    """Prefer <article>/<main>; else the densest <div>/<section>."""
    for xp in ("//article", "//main", "//*[@role='main']"):
        nodes = doc.xpath(xp)
        if nodes:
            best = max(nodes, key=lambda n: len("".join(n.itertext())))
            if len("".join(best.itertext())) > 400:
                return best
    best, best_len = None, 0
    for node in doc.xpath("//div | //section"):
        n = len(_clean_ws(" ".join(node.itertext())))
        if n > best_len:
            best, best_len = node, n
    # `best or doc` triggers lxml's FutureWarning (element truth-testing)
    return doc if best is None else best


def _block_text(node, base_url: str, out: dict) -> str:
    """Render one element as structured text (headings, lists, code, tables)."""
    tag = node.tag if isinstance(node.tag, str) else ""
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        text = _clean_ws(" ".join(node.itertext()))
        if text:
            level = int(tag[1])
            out["headings"].append((level, text))
            return f"{'#' * level} {text}"
        return ""
    if tag == "pre":
        code = node.text_content() if hasattr(node, "text_content") else "".join(node.itertext())
        code = code.strip("\n")
        if code.strip():
            lang = ""
            cls = " ".join(
                c for n in node.iter() for c in (n.get("class") or "").split()
            ).lower()
            for hint, name in CODE_LANG_HINTS.items():
                if hint in cls:
                    lang = name
                    break
            out["code_blocks"].append((lang, code))
            return f"```{lang}\n{code}\n```"
        return ""
    if tag == "table":
        out["tables"] += 1
        rows = []
        for tr in node.xpath(".//tr"):
            cells = [
                _clean_ws(" ".join(c.itertext()))
                for c in tr.xpath("./th | ./td")
            ]
            if any(cells):
                rows.append(" | ".join(cells))
        return "\n".join(rows)
    if tag in ("ul", "ol"):
        items = [_clean_ws(" ".join(li.itertext())) for li in node.xpath("./li")]
        items = [i for i in items if i]
        out["list_items"] += len(items)
        return "\n".join(f"- {i}" for i in items)
    if tag == "a":
        href = node.get("href") or ""
        text = _clean_ws(" ".join(node.itertext()))
        if href and text and not href.startswith("#"):
            out["links"].append((text[:120], urljoin(base_url, href)))
        return text
    # Any block can contain links — collect them before flattening to text,
    # otherwise a page reports "0 links" and its sources are lost.
    for anchor in node.xpath(".//a[@href]"):
        href = anchor.get("href") or ""
        text = _clean_ws(" ".join(anchor.itertext()))
        if href and text and not href.startswith("#") and len(out["links"]) < 2000:
            out["links"].append((text[:120], urljoin(base_url, href)))
    text = _clean_ws(" ".join(node.itertext()))
    return text


def _extract_metadata(doc, result: ReadResult) -> None:
    def first(xpaths: Iterable[str]) -> str:
        for xp in xpaths:
            nodes = doc.xpath(xp)
            if nodes:
                val = nodes[0]
                val = val if isinstance(val, str) else val.get("content") or val.get("value") or ""
                if val and str(val).strip():
                    return _clean_ws(str(val))
        return ""

    def many(xpath: str) -> str:
        vals = []
        for node in doc.xpath(xpath):
            v = node if isinstance(node, str) else (node.get("content") or "")
            v = _clean_ws(str(v))
            if v and v not in vals:
                vals.append(v)
        return ", ".join(vals[:12])

    result.title = first([
        "//meta[@name='citation_title']/@content",
        "//meta[@property='og:title']/@content",
        "//meta[@name='twitter:title']/@content",
        "//title/text()",
        "//h1//text()",
    ])
    # citation_author repeats per author (arXiv, PubMed, most publishers)
    result.byline = many("//meta[@name='citation_author']") or first([
        "//meta[@name='author']/@content",
        "//meta[@property='article:author']/@content",
        "//*[@rel='author']//text()",
        "//*[contains(@class,'author')]//text()",
    ])
    result.published = first([
        "//meta[@name='citation_publication_date']/@content",
        "//meta[@name='citation_date']/@content",
        "//meta[@property='article:published_time']/@content",
        "//meta[@name='date']/@content",
        "//time/@datetime",
        "//meta[@name='pubdate']/@content",
    ])
    html = doc.getroottree().getroot()
    result.lang = (html.get("lang") or "")[:12]


def _extract_numbers(text: str) -> list[str]:
    """Sentences carrying a quantitative claim worth checking later."""
    claims = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        s = sentence.strip()
        if len(s) < 25 or len(s) > 300:
            continue
        if re.search(r"\d", s) and re.search(
            r"%|\bpercent\b|\d+\s?(ms|s|GB|MB|tok|tokens|x)\b|\b\d{4}\b", s
        ):
            claims.append(s)
        if len(claims) >= 12:
            break
    return claims


def check_code_block(lang: str, code: str) -> CodeCheck:
    """Syntax-check a code block. Never executes it."""
    if lang in ("python", "") and re.search(r"^\s*(def |class |import |from |print\()", code, re.M):
        try:
            ast.parse(code)
            return CodeCheck("python", len(code), True, "parses")
        except SyntaxError as exc:
            return CodeCheck("python", len(code), False, f"SyntaxError line {exc.lineno}: {exc.msg}")
    if lang == "json" or code.lstrip().startswith(("{", "[")):
        try:
            json.loads(code)
            return CodeCheck("json", len(code), True, "valid JSON")
        except Exception as exc:
            return CodeCheck("json", len(code), False, str(exc)[:120])
    opens = code.count("{") + code.count("(") + code.count("[")
    closes = code.count("}") + code.count(")") + code.count("]")
    ok = abs(opens - closes) <= 1
    return CodeCheck(lang or "unknown", len(code), ok,
                     "brackets balanced" if ok else f"unbalanced brackets {opens}/{closes}")


def _analyze_document(doc, result: ReadResult, follow_pdf: bool = True) -> ReadResult:
    """Turn a parsed HTML document into text + structure + checks.

    Split out of read_url so it can be tested against local fixtures with no
    network involved.
    """
    _extract_metadata(doc, result)
    result.boilerplate_chars = _drop_boilerplate(doc)
    node = _main_node(doc)

    collected: dict = {"headings": result.headings, "code_blocks": result.code_blocks,
                       "tables": 0, "list_items": 0, "links": result.links}
    blocks: list[str] = []
    for child in node.iter():
        if not isinstance(child.tag, str):
            continue
        if child.tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "pre",
                         "ul", "ol", "table", "blockquote"):
            piece = _block_text(child, result.final_url, collected)
            if piece:
                blocks.append(piece)
    result.tables = collected["tables"]
    result.list_items = collected["list_items"]

    # de-duplicate consecutive identical blocks (nested containers repeat text)
    deduped: list[str] = []
    for b in blocks:
        if not deduped or deduped[-1] != b:
            deduped.append(b)
    result.text = "\n\n".join(deduped)
    result.numbers = _extract_numbers(result.text)

    for lang, code in result.code_blocks:
        result.code_checks.append(check_code_block(lang, code))

    lowered = result.text.lower()
    if any(m in lowered for m in PAYWALL_MARKERS) and result.text_chars < 4000:
        result.verdict = "paywall"
        result.checks.append("paywall marker found and text is short")
    elif result.text_chars < MIN_USEFUL_CHARS:
        result.verdict = "thin"
        result.checks.append(f"only {result.text_chars} chars (<{MIN_USEFUL_CHARS})")
    else:
        result.verdict = "ok"

    if result.article_ratio < 0.02:
        result.checks.append(f"low article ratio {result.article_ratio:.3f}")
    if not result.published:
        result.checks.append("no published date found")
    failed = [c for c in result.code_checks if not c.ok]
    if failed:
        result.checks.append(f"{len(failed)}/{len(result.code_checks)} code blocks failed syntax check")

    # A landing page for a paper is not the paper. If the page advertises a
    # PDF (citation_pdf_url / <link rel=alternate type=pdf>), read that too.
    if follow_pdf:
        pdf_url = ""
        for xp in ("//meta[@name='citation_pdf_url']/@content",
                   "//link[@type='application/pdf']/@href"):
            nodes = doc.xpath(xp)
            if nodes:
                pdf_url = urljoin(result.final_url, nodes[0] if isinstance(nodes[0], str)
                                  else nodes[0].get("href", ""))
                break
        if pdf_url:
            pdf_text, pages, err = read_pdf(pdf_url, max_pages=60)
            if pdf_text and len(pdf_text) > result.text_chars:
                result.html_text_chars = result.text_chars
                result.pdf_chars = len(pdf_text)
                result.text = f"{result.text}\n\n## Full document (PDF, {pages} pages)\n\n{pdf_text}"
                result.checks.append(f"pdf appended: {pages} pages, {len(pdf_text):,} chars")
                result.numbers = _extract_numbers(result.text)
                if result.verdict == "thin":
                    result.verdict = "ok"
            elif err:
                result.checks.append(f"pdf not read: {err}")
    return result


def read_pdf(source: bytes | str, max_pages: int = 80) -> tuple[str, int, str]:
    """Extract text from a PDF. ``source`` is bytes or a URL path (http/https).

    Returns (text, page_count, error).
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", 0, "pypdf not installed (pip install pypdf)"
    import io

    try:
        if isinstance(source, str):
            import requests

            resp = requests.get(source, timeout=30, headers={"User-Agent": "OpenAmerReader/1.0"})
            resp.raise_for_status()
            stream = io.BytesIO(resp.content)
        else:
            stream = io.BytesIO(source)
        reader = PdfReader(stream)
        pages = min(len(reader.pages), max_pages)
        chunks = []
        for i in range(pages):
            try:
                chunks.append(reader.pages[i].extract_text() or "")
            except Exception:
                chunks.append("")
        text = "\n\n".join(c.strip() for c in chunks if c.strip())
        return text, len(reader.pages), ""
    except Exception as exc:
        return "", 0, f"pdf read failed: {exc}"


def available() -> tuple[bool, str]:
    """Whether the reader can run, plus what is missing if it cannot.

    lxml is an optional extra (`.[read]`), so the reader must degrade with an
    explicit install line instead of an ImportError traceback.
    """
    missing = []
    for mod in ("lxml", "requests"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return False, f"missing {', '.join(missing)} — {INSTALL_HINT}"
    try:
        __import__("pypdf")
    except ImportError:
        pass  # PDF support only; HTML reading still works
    return True, ""


def read_url(url: str, timeout: float = 20.0, max_bytes: int = 4_000_000,
             user_agent: str | None = None, follow_pdf: bool = True) -> ReadResult:
    """Fetch and fully read one source."""
    import requests

    result = ReadResult(url=url)
    try:
        from lxml import html as lxml_html
    except ImportError:
        result.error = INSTALL_HINT
        result.verdict = "error"
        return result

    ua = user_agent or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 OpenAmerReader/1.0"
    )
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": ua,
                                                          "Accept-Language": "en,de;q=0.8"})
    except Exception as exc:
        result.error = f"fetch failed: {exc}"
        result.verdict = "error"
        return result

    result.status = resp.status_code
    result.final_url = resp.url
    result.content_type = resp.headers.get("Content-Type", "").split(";")[0]
    raw = resp.content[:max_bytes]
    result.html_chars = len(raw)

    if result.status >= 400:
        result.error = f"HTTP {result.status}"
        result.verdict = "error"
        return result

    ctype = result.content_type.lower()
    if ctype == "application/pdf" or (url.lower().endswith(".pdf") and "html" not in ctype):
        text, pages, err = read_pdf(raw)
        result.text = text
        result.checks.append(f"pdf: {pages} pages") if pages else None
        if err:
            result.checks.append(err)
        result.verdict = "ok" if result.text_chars >= MIN_USEFUL_CHARS else "thin"
        return result
    if ctype in ("text/plain", "application/json") or ctype.endswith("+json"):
        text = raw.decode(resp.encoding or "utf-8", errors="replace")
        result.text = text if ctype == "text/plain" else json.dumps(
            json.loads(text), indent=2, ensure_ascii=False)[:200_000]
        result.verdict = "ok" if result.text_chars >= MIN_USEFUL_CHARS else "thin"
        return result

    try:
        doc = lxml_html.fromstring(raw)
    except Exception as exc:
        result.error = f"parse failed: {exc}"
        result.verdict = "error"
        return result

    return _analyze_document(doc, result, follow_pdf=follow_pdf)


def summarize(result: ReadResult) -> str:
    """Human-readable digest of what was actually read and checked."""
    lines = [
        f"URL        : {result.final_url or result.url}",
        f"Status     : {result.status} {result.content_type}",
        f"Title      : {result.title or '(none)'}",
        f"Byline     : {result.byline or '(none)'}",
        f"Published  : {result.published or '(none)'}",
        f"Language   : {result.lang or '(none)'}",
        f"Content    : {result.text_chars:,} chars, {result.words:,} words "
        f"({result.article_ratio:.1%} of {result.html_chars:,} HTML chars)",
        f"Structure  : {len(result.headings)} headings, {len(result.code_blocks)} code blocks, "
        f"{result.tables} tables, {result.list_items} list items, {len(result.links)} links",
        f"Claims     : {len(result.numbers)} quantitative sentences",
        f"Verdict    : {result.verdict.upper()}",
    ]
    if result.code_checks:
        passed = sum(1 for c in result.code_checks if c.ok)
        lines.append(f"Code tests : {passed}/{len(result.code_checks)} blocks pass syntax check")
        for c in result.code_checks[:5]:
            if not c.ok:
                lines.append(f"  ✗ {c.lang} ({c.chars} chars): {c.detail}")
    if result.checks:
        lines.append("Warnings   :")
        for c in result.checks:
            lines.append(f"  - {c}")
    if result.error:
        lines.append(f"Error      : {result.error}")
    return "\n".join(lines)


def to_training_record(result: ReadResult) -> dict:
    """A full-content learning record — the opposite of a 150-char snippet."""
    return {
        "u": f"Read and analyse: {result.title or result.url}",
        "a": result.text,
        "source": result.final_url or result.url,
        "title": result.title,
        "byline": result.byline,
        "published": result.published,
        "read_at": datetime.now().isoformat(timespec="seconds"),
        "chars": result.text_chars,
        "headings": result.headings,
        "code_ok": f"{sum(1 for c in result.code_checks if c.ok)}/{len(result.code_checks)}",
        "verdict": result.verdict,
    }
