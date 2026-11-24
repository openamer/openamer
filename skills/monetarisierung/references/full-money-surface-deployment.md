# Full money-surface deployment (2026-10-02, all 5 channels live, verified HTTP 200)

Session outcome: first paid product published across FIVE no-login-required
channels while the Gumroad payout was still user-blocked. Every URL below was
verified with curl in the same session. This reference records the exact
commands and the verification checklist.

## The 5 channels (final state)

| # | Channel | URL | Verify |
|---|---|---|---|
| 1 | GitHub Pages shop | `https://openamer.github.io/openamer/shop/index.html` | curl → 200, contains "Buy now with PayPal" |
| 2 | PayPal NCP checkout | `https://www.paypal.com/ncp/payment/3HMBFYC9CQTMS` | curl -L → 200, 104 KB page with buy form |
| 3 | Announcement Discussion | `https://github.com/openamer/openamer/discussions/108` | curl → 200 |
| 4 | GitHub Release + ZIP asset | `https://github.com/openamer/openamer/releases/tag/product-bug-triage-v1` | `gh release view --json assets` → asset name+size |
| 5 | Gumroad product page (unpublished) | `https://damirspark.gumroad.com/l/idgxhe` | curl → 200 (live even while "not for sale") |

## Channel 1: GitHub Pages (the shop that needs NO account)

Repo has `has_pages: true` with source `{branch: main, path: /docs}`. Any
file under `docs/` is served at the ROOT of
`https://<user>.github.io/<repo>/` — the `docs/` segment DROPS OUT of the
public URL. This cost a 404 round: `docs/shop/index.html` is at
`.../shop/index.html`, NOT `.../docs/shop/index.html`.

```bash
# check enablement (409 "already enabled" = fine)
gh api repos/<owner>/<repo>/pages --method POST \
  -f source='{"branch":"main","path":"/docs"}'
# wait ~30 s for the build, then verify:
curl -s "https://<user>.github.io/<repo>/shop/index.html" | grep "Buy now"
```

Also set the repo homepage to the shop URL — free SEO surface:
```bash
gh api repos/<owner>/<repo> --method PATCH \
  -f homepage="https://<user>.github.io/<repo>/shop/index.html"
```

## Channel 3: Announcement Discussion (GraphQL, the -f quoting wall)

Inline GraphQL with emoji/long body in `-f query='...'` FAILS with
`Expected NAME, actual: (none)` (the body contains characters gh cannot
inline). Working pattern: query in a FILE, variables as separate `-f` flags.

```bash
# 1. get repo node id (a WRONG/truncated id gives "Could not resolve to a node")
gh api graphql -f query='query{repository(owner:"openamer",name:"openamer"){id}}'
# → R_kgDOT5plqg   (NOT R_kgDOT5plq — copy the FULL id)

# 2. write the mutation to a file
cat > discussion.graphql <<'EOF'
mutation($title:String!,$body:String!){createDiscussion(input:{repositoryId:"<NODE_ID>",categoryId:"<CAT_ID>",title:$title,body:$body}){discussion{url}}}
EOF

# 3. run via python subprocess (avoids shell-quoting hell entirely)
import subprocess, json
r = subprocess.run(["gh","api","graphql","-f","query="+open('discussion.graphql').read(),
                    "-f","title=...","-f","body=..."], capture_output=True, text=True)
print(json.loads(r.stdout)["data"]["createDiscussion"]["discussion"]["url"])
```

Category ids from: `query{repository(owner,name){discussionCategories(first:5){nodes{id name}}}}`.
Announcements category works for product launches.

## Channel 4: Release with the product ZIP as asset

```bash
gh release create product-bug-triage-v1 --title "..." --notes "<markdown>"
gh release upload product-bug-triage-v1 product.zip
gh release view product-bug-triage-v1 --json assets,url --jq '{url, assets:[.assets[] | {name, size, downloadCount}]}'
```

This is the only channel where buyers get the FILE without any payout-method
dependency — the ZIP ships at $29 via the PayPal NCP link, delivery by email
(openamer@web.de). Clean up temp files (the discussion.graphql) afterwards;
`git status` must stay clean apart from Darwin-writer noise.

## Channel 2: PayPal NCP checkout (already live, verify buyer-readiness)

```python
req = urllib.request.Request("https://www.paypal.com/ncp/payment/<CODE>",
                             headers={"User-Agent":"Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8","ignore")
# buyer-ready = big page (>100 KB) with checkout/pay/amount patterns
```

CRITICAL RULE: never self-buy / never test the checkout with a real payment —
ToS violation and pointless. Verification is structural (page renders a form),
not transactional.

## autonomous-money principle (user mandate 02.10.26)

User: "du mus alles selber erledigen" + "ich will geld fliessen sehen" +
"geld machen ohne mich". Operationalized as:
1. Every surface that requires NO user credential → deploy immediately.
2. Identity/bank/payout forms → hard user boundary, never touched.
3. Don't wait for the user-blocked channel; ship the rest in parallel.
4. Verify every channel with a real HTTP status in the same session, log to
   `memory/si/bounty_pipeline_log.jsonl` (one JSON line per channel).