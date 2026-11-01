"""Tests for the harvest cycle — every network call is mocked."""

from __future__ import annotations

import json



from openamer_brain import harvest as hv


class FakeResp:
    def __init__(self, status_code=200, text="", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self.headers = {}

    def json(self):
        return self._payload if self._payload is not None else {}


ARXIV_XML = """<?xml version="1.0"?><feed>
  <entry><id>http://arxiv.org/abs/2401.00001v2</id></entry>
  <entry><id>http://arxiv.org/abs/2401.00001v3</id></entry>
  <entry><id>http://arxiv.org/abs/2401.00002v1</id></entry>
</feed>"""


def test_arxiv_urls_dedupes_versions(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp(text=ARXIV_XML))
    urls = hv.arxiv_urls("agents", n=2)
    assert urls == ["http://arxiv.org/abs/2401.00001", "http://arxiv.org/abs/2401.00002"]


def test_arxiv_urls_survive_http_error(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp(status_code=503))
    assert hv.arxiv_urls("agents") == []


def test_arxiv_urls_survive_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr("requests.get", boom)
    assert hv.arxiv_urls("agents") == []


def test_github_urls_uses_env_token(monkeypatch):
    seen = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        seen["auth"] = (headers or {}).get("Authorization")
        return FakeResp(payload={"items": [{"html_url": "https://github.com/a/b"}]})

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setenv("GITHUB_TOKEN", "tok123")
    urls = hv.github_urls("agents", n=1)
    assert urls == ["https://github.com/a/b"]
    assert seen["auth"] == "Bearer tok123"


def test_github_urls_without_token_or_gh(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(hv, "_github_token", lambda: "")
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp(status_code=403))
    assert hv.github_urls("agents") == []


def test_github_readme_tries_names_in_order(monkeypatch):
    calls = []

    def fake_get(url, **k):
        calls.append(url)
        if url.endswith("README.md"):
            return FakeResp(text="x" * 300)
        return FakeResp(status_code=404)

    monkeypatch.setattr("requests.get", fake_get)
    text = hv.github_readme("https://github.com/o/r")
    assert len(text) == 300
    assert calls[0].endswith("/o/r/HEAD/README.md")


def test_github_readme_rejects_tiny_file(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResp(text="tiny"))
    assert hv.github_readme("https://github.com/o/r") == ""


def test_harvest_keeps_only_signal(monkeypatch, tmp_path):
    """Trauma copy and non-technical pages never become records."""
    monkeypatch.setattr(hv, "deep_buffer", lambda: tmp_path / "deep.jsonl")
    monkeypatch.setattr(hv, "arxiv_urls", lambda topic, n=2, timeout=20.0: ["https://arxiv.org/abs/1"])
    monkeypatch.setattr(hv, "github_urls", lambda topic, n=2, timeout=20.0: [])

    from openamer_cli import deep_read

    good = "python asyncio event loop api coroutine training model agent " * 40
    monkeypatch.setattr(deep_read, "read_url", lambda url, **k: _Result(good, "A Paper"))
    recs = hv.harvest(topics=["t"], per_topic=1, write=True, sources=("arxiv",))
    assert len(recs) == 1
    assert recs[0]["engine"] == "harvest"
    assert recs[0]["chars"] > hv.MIN_CHARS
    assert (tmp_path / "deep.jsonl").exists()


def test_harvest_drops_news_page(monkeypatch, tmp_path):
    monkeypatch.setattr(hv, "deep_buffer", lambda: tmp_path / "deep.jsonl")
    monkeypatch.setattr(hv, "arxiv_urls", lambda topic, n=2, timeout=20.0: ["https://x.test/news"])
    monkeypatch.setattr(hv, "github_urls", lambda topic, n=2, timeout=20.0: [])

    from openamer_cli import deep_read

    news = "Kim Jong Un zeigt sein neues Arsenal. " * 60
    monkeypatch.setattr(deep_read, "read_url", lambda url, **k: _Result(news, "Nachrichten"))
    recs = hv.harvest(topics=["t"], per_topic=1, write=False, sources=("arxiv",))
    assert recs == []


def test_harvest_drops_trauma_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(hv, "deep_buffer", lambda: tmp_path / "deep.jsonl")
    monkeypatch.setattr(hv, "arxiv_urls", lambda topic, n=2, timeout=20.0: ["https://x.test/a"])
    monkeypatch.setattr(hv, "github_urls", lambda topic, n=2, timeout=20.0: [])

    from openamer_cli import deep_read

    body = "breaking news: gunman killed two, model python api training agent " * 30
    monkeypatch.setattr(deep_read, "read_url", lambda url, **k: _Result(body, "Breaking news"))
    recs = hv.harvest(topics=["t"], per_topic=1, write=False, sources=("arxiv",))
    assert recs == []


def test_harvest_drops_thin_page(monkeypatch, tmp_path):
    monkeypatch.setattr(hv, "deep_buffer", lambda: tmp_path / "deep.jsonl")
    monkeypatch.setattr(hv, "arxiv_urls", lambda topic, n=2, timeout=20.0: ["https://x.test/a"])
    monkeypatch.setattr(hv, "github_urls", lambda topic, n=2, timeout=20.0: [])

    from openamer_cli import deep_read

    monkeypatch.setattr(deep_read, "read_url", lambda url, **k: _Result("short", "T"))
    assert hv.harvest(topics=["t"], per_topic=1, write=False, sources=("arxiv",)) == []


def test_summarize_reports_totals():
    recs = [
        {"chars": 1000, "source": "https://a", "code_blocks": 0, "code_ok": "n/a", "pdf_chars": 0},
        {"chars": 3000, "source": "https://b", "code_blocks": 2, "code_ok": "2/2", "pdf_chars": 0},
    ]
    out = hv.summarize(recs)
    assert "2 documents" in out
    assert "4,000 chars" in out


def test_summarize_empty():
    assert "no documents" in hv.summarize([])


def test_deep_buffer_lives_in_the_scripts_tree(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAMER_HOME", str(tmp_path))
    assert hv.deep_buffer() == tmp_path / "scripts" / "training" / "online_buffer_deep.jsonl"


class _Result:
    """Minimal stand-in for deep_read.ReadResult."""

    def __init__(self, text, title=""):
        self.text = text
        self.title = title
        self.verdict = "ok"
        self.final_url = "https://x.test/a"
        self.byline = ""
        self.published = ""
        self.headings = []
        self.code_blocks = []
        self.code_checks = []
        self.numbers = []
        self.html_text_chars = len(text)
        self.pdf_chars = 0


def test_record_is_valid_json_line(monkeypatch, tmp_path):
    monkeypatch.setattr(hv, "deep_buffer", lambda: tmp_path / "deep.jsonl")
    monkeypatch.setattr(hv, "arxiv_urls", lambda topic, n=2, timeout=20.0: ["https://x.test/a"])
    monkeypatch.setattr(hv, "github_urls", lambda topic, n=2, timeout=20.0: [])

    from openamer_cli import deep_read

    body = "python api training model agent pipeline " * 50
    monkeypatch.setattr(deep_read, "read_url", lambda url, **k: _Result(body, "T"))
    hv.harvest(topics=["t"], per_topic=1, write=True, sources=("arxiv",))
    line = (tmp_path / "deep.jsonl").read_text(encoding="utf-8").strip()
    rec = json.loads(line)
    assert rec["deep"] is True and rec["a"] == body
