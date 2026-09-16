"""Measure how many usable URLs each search path yields for k=2 and k=6.

Hypothesis: the CDP (PRIMARY) path loses most result URLs to Bing's display
truncation ('…' paths are skipped), so deep_learn's k=6 retry cannot help.
"""
import importlib.util, sys, re, urllib.request, urllib.parse
import html as _html

T = "C:/Users/damir/AppData/Local/openamer-laptop/scripts/training"
spec = importlib.util.spec_from_file_location("il", T + "/internet_learner.py")
m = importlib.util.module_from_spec(spec)
sys.path.insert(0, T)
spec.loader.exec_module(m)

QUERIES = [
    "AI coding agent news",
    "AI agent news",
    "LLM agent research",
    "OWASP AI security testing guide",
    "quantization LLM inference efficiency",
    "Devin AI agent new features 2026",
]


def http_urls(q, k=6):
    raw = urllib.request.urlopen(urllib.request.Request(
        "https://www.bing.com/search?q=" + urllib.parse.quote(q),
        headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read().decode("utf-8", "replace")
    raw = _html.unescape(raw)
    out = []
    for mm in re.finditer(r'href="(https://www\.bing\.com/ck/a\?[^"]+)"', raw):
        d = m._decode_bing_url(mm.group(1))
        if d.startswith("http") and "microsoft" not in d and d not in out:
            out.append(d)
    return out[:k]


print(f"{'query':38} {'CDPk2':>6} {'CDPk6':>6} {'HTTPk6':>7}")
tot = [0, 0, 0]
for q in QUERIES:
    try:
        c2 = len(m._search_urls(q, k=2))
    except Exception as e:
        c2 = -1
    try:
        c6 = len(m._search_urls(q, k=6))
    except Exception as e:
        c6 = -1
    try:
        h6 = len(http_urls(q, k=6))
    except Exception as e:
        h6 = -1
    tot[0] += c2
    tot[1] += c6
    tot[2] += h6
    print(f"{q[:37]:38} {c2:>6} {c6:>6} {h6:>7}")
print(f"{'TOTAL':38} {tot[0]:>6} {tot[1]:>6} {tot[2]:>7}")

print("\n=== does _search_urls ever return fewer than k? ===")
for q in QUERIES:
    u = m._search_urls(q, k=6)
    print(f"  asked k=6 got {len(u)}: {q[:40]}")
    for x in u:
        print("       ", x[:90])
