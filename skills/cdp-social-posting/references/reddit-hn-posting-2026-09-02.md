# Session detail: Reddit r/LocalLLaMA posting attempt (02.09.2026)

Full transcript of the attempt, for reference when retrying or debugging.

## What worked
- HN login verified: `user: openamer` via `.hnuser` selector.
- Reddit login verified: `Realistic_Kitchen_65` via `api/me.json` fetch with credentials.
- Reddit composer fields filled visually: title 76 chars in `post-composer-title` shadow textarea; body 566 chars in light-DOM `div[contenteditable=true][aria-label="Post body text field"]` via `Input.insertText` after focusing.
- Community preselected via URL `https://www.reddit.com/r/LocalLLaMA/submit` (bypasses `reddit-search-large` triple-nested shadow).
- Flair modal `r-post-flairs-modal`: "View all flairs" expands; options found by recursively walking shadowRoots looking for leaf divs matching /Question|Help|Resources|Discussion|News/; "Discussion" clicked, "Add" clicked.

## What failed and why
- `shreddit-composer.getValueAs("json")` returned `{}` throughout — the composer never registered the filled fields into its form state. Submit button click (`r-post-form-submit-button` shadow button, `btn_disabled: false`) produced ZERO network requests (confirmed via CDP Network.enable monitoring). Both `element.click()` and real `Input.dispatchMouseEvent` at button coordinates were tried.
- Direct API POSTs from page JS: `https://oauth.reddit.com/api/submit` → TypeError Failed to fetch (CORS); `https://www.reddit.com/api/submit` → returns HTML not JSON (login-wall for that endpoint); `https://old.reddit.com/api/submit` from old.reddit origin → `BAD_CAPTCHA` error even with valid modhash. The captcha error is Reddit's correct anti-bot response for this account tier — not fixable by retrying.
- old.reddit classic form exists at `/r/<sub>/submit?kind=self` (light DOM: `textarea[name=title]`, `textarea[name=text]`, hidden `flair_id`/`flair_text`, enabled `submit` button) but clicking it also did not navigate; likely the same captcha gate.

## Verdict
Reddit posting for this account tier requires human interaction (captcha) or account maturation. The UI form path is broken for programmatic state registration; the API path requires captcha. Honest stop, keep post text in `reports/post-dream-cycle-hn-reddit.md`, retry via cron when the account is older or after a manual human posting warms the account.

## Working examples (copy-paste ready)

### Verify Reddit login (from any reddit.com tab)
```js
(async function(){
  const r = await fetch("https://www.reddit.com/api/me.json", {credentials:"include"});
  const d = await r.json();
  return d.data ? d.data.name : "not-logged-in";
})()
```

### Fill old.reddit classic form (light DOM, works reliably)
```js
document.querySelector("textarea[name=title]").value = "...";
document.querySelector("textarea[name=text]").value = "...";
// submit button: [...document.querySelectorAll("button")].find(b=>b.textContent.trim()==="submit")
```
Note: even with the classic form filled and clicked, the post may not go through due to captcha — verify via `user/<name>/submitted.json`.

### HN Algolia search for fresh comment targets
```python
import json, urllib.request, time, urllib.parse
url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(q)}&tags=story&numericFilters=created_at_i>{int(time.time()-86400*7)},points>2"
```