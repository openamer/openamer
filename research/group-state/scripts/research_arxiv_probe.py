#!/usr/bin/env python3
"""Query arXiv for the real limits of current sequence architectures."""
import re
import urllib.parse
import urllib.request

QUERIES = [
    'all:"illusion of state" AND all:"state space"',
    'all:"state tracking" AND all:transformer',
    'all:parity AND all:"neural network" AND all:expressivity',
    'all:"modular arithmetic" AND all:transformer',
    'all:"state space model" AND all:limitation AND all:tradeoff',
]


def fetch(q, n=4):
    url = ("http://export.arxiv.org/api/query?search_query="
           + urllib.parse.quote(q)
           + f"&max_results={n}&sortBy=relevance")
    try:
        with urllib.request.urlopen(url, timeout=40) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        return f"<error>{e}</error>"


for q in QUERIES:
    xml = fetch(q)
    titles = re.findall(r"<title>(.*?)</title>", xml, re.S)
    dates = re.findall(r"<published>(.*?)</published>", xml)
    print("=" * 72)
    print("QUERY:", q)
    print("=" * 72)
    if "<error>" in xml:
        print("  ", xml[:200])
    entries = list(zip(titles[1:], dates))
    if not entries:
        print("  (no results)")
    for t, d in entries[:4]:
        t = " ".join(t.split())
        print(f"  [{d[:10]}] {t[:105]}")
    print()
