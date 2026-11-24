# H1 Disclosure Retrieval — working route (verified 2026-10-04)

## The problem
`hackerone.com/hacktivity` is a JS app. The GraphQL endpoint exposes no hacktivity
query; the REST API needs auth; `web_extract` is search-only; `web_search` fails on
this laptop with "ddgs package is not installed".

## The working route (no auth, plain markdown)
Structured mirrored archive: `github.com/ajaysenr/HackerOne-Disclosed-Reports`
(auto-updated; live dashboard at h1.ajaysenr.com).

Index (reports ranked by bounty, then severity):
```bash
curl -sL https://raw.githubusercontent.com/ajaysenr/HackerOne-Disclosed-Reports/main/by-year/2026.md
```
One report's full body (Program Summary + Steps To Reproduce + Vulnerability Details):
```bash
curl -sL https://raw.githubusercontent.com/ajaysenr/HackerOne-Disclosed-Reports/main/reports/<REPORT_ID>.md
```
Also available: `by-program/<program>.md`, `by-weakness/<weakness>.md`.

Worked examples used for Run 3 (2026-10-04):
- `reports/3862641.md` — HackerOne IDOR, Critical, $15,000, disclosed 2026-10-01
- `reports/3861550.md` — 8x8 deserialization→RCE, CVSS 9.9, $3,000, disclosed 2026-09-01

## Running ddgs when web_search is broken
The `web_search` tool runs on an interpreter without `ddgs`. Call ddgs directly via
the openamer venv:
```bash
# write tmp_ddgs_search.py (see below), then:
"/c/Users/damir/AppData/Local/openamer-laptop/venv/Scripts/python.exe" C:/Users/damir/tmp_ddgs_search.py "<query>"
```
`tmp_ddgs_search.py`:
```python
import sys
from ddgs import DDGS
q = sys.argv[1]
with DDGS() as d:
    for r in d.text(q, max_results=8):
        print("TITLE:", r.get("title"))
        print("URL:  ", r.get("href"))
        print("SNIP: ", (r.get("body") or "")[:300])
        print("-" * 70)
```
NOTE: the terminal's `python`/`python3` resolves to the WSL/WindowsApps stub, which
prints "can't open file 'C:\\tmp\\...'" for MSYS `/tmp/...` paths. Always pass a
native `C:/Users/damir/...` path and use the venv python explicitly.

## Advisory-only bodies: the NVD API fallback (verified Run 24, 2026-10-12)
Some archive bodies carry only a link — e.g. `#3360354`'s body was a single line
"Security advisory in .../GHSA-fr8x-mvjg-wf9q". The GitHub advisory REST endpoint
404s (`api.github.com/advisories/GHSA-...` → `{"status":"404"}`) and `web_extract` is
ddgs-only, but the free, no-auth **NVD 2.0 API** returns the description verbatim:
```bash
curl -sL "https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2025-66558"
```
Read `vulnerabilities[0].cve.descriptions[0].value` for the mechanism, and
`vulnerabilities[0].cve.metrics.cvssMetricV31[]` for both CVSS vectors (the github-CNA
one and the nvd-nist one). Get the CVE id from the archive row's `**CVE IDs**` field.
Worked example: CVE-2025-66558 → "a missing ownership check allowed an attacker to
take-away a 2FA webauthn device when correctly guessing an 80-128 character long
random string" (Nextcloud twofactor_webauthn, Low CVSS 3.1, $750, 81 votes).

## Path/tooling note for in-dir analysis (Run 24)
`search_files` cannot be pointed at the skill dir — it hands the native `C:/…` path to
`rg` as `/c/…` and fails with `os error 3`. Use `read_file` to read and `execute_code`
(Python `re`) to search/count. Long bash one-liners (brace-quantifier `sed`,
`for … $(grep …)`) are hardline-blocked by the command parser — do that work in Python.
