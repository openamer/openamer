"""Harvest: fill the brain's corpus with whole documents, not snippets.

The internet learner depends on a search engine, and the engines rate-limit
(measured 2026-11-01: DuckDuckGo answered HTTP 202 with a bot-anomaly page
after a handful of queries; the Bing fallback returned msn.com portal links).
This module does not search at all — it asks the two APIs that answer
reliably and return real identifiers:

    arXiv  -> /abs/<id> landing page, then the PDF (full paper)
    GitHub -> repository page, then the README

Every hit goes through the deep reader (full text, structure, checks, code
syntax) and the shared gates (no trauma news, real technical signal), then
lands in online_buffer_deep.jsonl where the trainer picks it up.

    openamer brain harvest                  # default topic list
    openamer brain harvest --topics 3        # first N topics
    openamer brain harvest --json
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

DEFAULT_TOPICS = (
    "autonomous llm agent architecture",
    "tool use function calling llm",
    "retrieval augmented generation",
    "agent memory long context",
    "lora fine-tuning",
    "model quantization benchmark",
    "prompt caching inference latency",
    "mixture of experts training",
    "state space model sequence",
    "reinforcement learning human feedback",
    "code generation evaluation",
    "multi-agent orchestration",
)

ARXIV_API = "http://export.arxiv.org/api/query"
GITHUB_API = "https://api.github.com/search/repositories"
MIN_CHARS = 800
MIN_TECH_TERMS = 3


def home() -> Path:
    return Path(os.environ.get("OPENAMER_HOME") or Path.home() / ".openamer")


def deep_buffer() -> Path:
    return home() / "scripts" / "training" / "online_buffer_deep.jsonl"


def arxiv_urls(topic: str, n: int = 2, timeout: float = 20.0) -> list[str]:
    """arXiv abs pages for a topic. Empty on any failure (never raises)."""
    try:
        import requests

        resp = requests.get(
            ARXIV_API,
            params={"search_query": f"all:{topic}", "max_results": max(1, n),
                    "sortBy": "relevance"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return []
        ids = re.findall(r"<id>(http://arxiv\.org/abs/[^<]+)</id>", resp.text)
        seen, out = set(), []
        for url in ids:
            url = re.sub(r"v\d+$", "", url.strip())  # one entry per paper
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out[:n]
    except Exception:
        return []


def _github_token() -> str:
    """A GitHub token for API calls, without storing one here.

    Unauthenticated search allows only 10 requests/hour (measured 2026-11-01:
    HTTP 403, X-RateLimit-Remaining: 0). An explicit env token wins; otherwise
    we ask the gh CLI, which already holds the credential in its keyring.
    """
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        tok = os.environ.get(var)
        if tok:
            return tok.strip()
    try:
        import subprocess

        proc = subprocess.run(["gh", "auth", "token"], capture_output=True,
                              text=True, timeout=10, shell=False)
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return ""


def github_urls(topic: str, n: int = 2, timeout: float = 20.0) -> list[str]:
    """GitHub repository pages for a topic, most-starred first."""
    try:
        import requests

        token = _github_token()
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = requests.get(
            GITHUB_API,
            params={"q": topic, "sort": "stars", "order": "desc", "per_page": max(1, n)},
            timeout=timeout,
            headers=headers,
        )
        if resp.status_code != 200:
            return []
        return [item["html_url"] for item in resp.json().get("items", [])[:n]
                if item.get("html_url")]
    except Exception:
        return []


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def github_readme(url: str, timeout: float = 20.0) -> str:
    """The repository's README as plain markdown.

    A repo page is a JS shell: measured 2026-11-01, 13 repo pages yielded
    16,398 chars total (~1.2k each) while the READMEs behind them are tens of
    kilobytes of real documentation. raw.githubusercontent.com serves the file
    directly, so we ask for that instead of scraping the page.
    """
    try:
        import requests

        parts = [p for p in url.rstrip("/").split("/") if p]
        if len(parts) < 2:
            return ""
        owner, repo = parts[-2], parts[-1]
        for name in ("README.md", "README.rst", "readme.md", "README"):
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{name}"
            resp = requests.get(raw_url, timeout=timeout,
                                headers={"User-Agent": "OpenAmerReader/1.0"})
            if resp.status_code == 200 and len(resp.text) > 200:
                return resp.text
        return ""
    except Exception:
        return ""


def harvest(topics=None, per_topic: int = 2, write: bool = True,
            sources=("arxiv", "github"), max_records: int = 40) -> list[dict]:
    """Read whole documents for each topic. Returns the records it built."""
    from openamer_cli.deep_read import (
        is_trauma_news,
        read_url,
        technical_signal_count,
    )

    topics = list(topics or DEFAULT_TOPICS)
    records: list[dict] = []
    store = deep_buffer()

    for topic in topics:
        if len(records) >= max_records:
            break
        urls: list[str] = []
        if "arxiv" in sources:
            urls += arxiv_urls(topic, n=per_topic)
        if "github" in sources:
            urls += github_urls(topic, n=per_topic)

        for url in urls:
            if len(records) >= max_records:
                break
            # A repo page is a JS shell — read its README instead of the page.
            if "github.com" in url and "/" in url.split("github.com", 1)[1]:
                readme = github_readme(url)
                if len(readme) >= MIN_CHARS:  # noqa: SIM102 - keep the shape simple
                    title = f"README: {url.rstrip('/').split('/')[-1]}"
                    if technical_signal_count(readme) < MIN_TECH_TERMS:
                        continue
                    rec = {
                        "u": f"Read and analyse: {title}",
                        "a": readme,
                        "source": url,
                        "title": title,
                        "byline": "",
                        "published": "",
                        "chars": len(readme),
                        "html_text_chars": len(readme),
                        "pdf_chars": 0,
                        "headings": [ln.lstrip("#").strip() for ln in readme.splitlines()
                                     if ln.startswith("#")][:60],
                        "code_blocks": readme.count("```") // 2,
                        "code_ok": "n/a",
                        "claims": [],
                        "verdict": "ok",
                        "engine": "harvest-readme",
                        "deep": True,
                        "query": topic,
                        "read_at": datetime.now().isoformat(timespec="seconds"),
                    }
                    records.append(rec)
                    if write:
                        store.parent.mkdir(parents=True, exist_ok=True)
                        with open(store, "a", encoding="utf-8", newline="\n") as f:
                            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    continue
            result = read_url(url)
            if result.verdict not in ("ok", "thin") or not result.text:
                continue
            text = result.text
            if len(text) < MIN_CHARS:
                continue
            head = f"{result.title} {text[:2000]}"
            if is_trauma_news(head):
                continue
            if technical_signal_count(f"{result.title} {text}") < MIN_TECH_TERMS:
                continue
            rec = {
                "u": f"Read and analyse: {result.title or url}",
                "a": text,
                "source": result.final_url or url,
                "title": result.title,
                "byline": result.byline,
                "published": result.published,
                "chars": len(text),
                "html_text_chars": result.html_text_chars,
                "pdf_chars": result.pdf_chars,
                "headings": [h[1] for h in result.headings][:60],
                "code_blocks": len(result.code_blocks),
                "code_ok": f"{sum(1 for c in result.code_checks if c.ok)}/{len(result.code_checks)}",
                "claims": result.numbers[:12],
                "verdict": result.verdict,
                "engine": "harvest",
                "deep": True,
                "query": topic,
                "read_at": datetime.now().isoformat(timespec="seconds"),
            }
            records.append(rec)
            if write:
                store.parent.mkdir(parents=True, exist_ok=True)
                with open(store, "a", encoding="utf-8", newline="\n") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return records


def summarize(records: list[dict]) -> str:
    """One-line-per-record digest with the totals that matter."""
    if not records:
        return "no documents harvested"
    lines = [
        f"harvested {len(records)} documents, "
        f"{sum(r['chars'] for r in records):,} chars total, "
        f"median {sorted(r['chars'] for r in records)[len(records)//2]:,} chars"
    ]
    for r in records:
        blocks = f" code={r['code_ok']}" if r.get("code_blocks") else ""
        pdf = f" pdf={r['pdf_chars']:,}" if r.get("pdf_chars") else ""
        lines.append(f"  {r['chars']:>7,} chars{blocks}{pdf}  {r['source'][:78]}")
    return "\n".join(lines)


if __name__ == "__main__":
    t0 = time.time()
    recs = harvest()
    print(summarize(recs))
    print(f"({time.time() - t0:.0f}s)")
