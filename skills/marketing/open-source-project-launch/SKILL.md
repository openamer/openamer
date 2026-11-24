---
name: open-source-project-launch
description: Launch OSS on Product Hunt, HN, Reddit, and Twitter.
---

# Open-Source Project Launch

Use when the user asks you to launch or promote an open-source project publicly. Covers the full sequence from content creation through platform submission.

## When to Use

- The user says "mach alles" about launching on Product Hunt / Reddit / HN
- The user wants to promote an open-source project on social media
- You need to create submission content for multiple platforms
- The user asks "wie kommen wir an User" or "Sichtbarkeit"

## When NOT to Use

- The user just wants to build features (no launch phase) → use `competitive-overtake`
- The user wants a single platform post, not a full launch → just do it directly

## The Full Launch Sequence

### Phase 0 — Funding/Payment Infrastructure (before launch)

Before promoting your project publicly, set up payment infrastructure so interested supporters can contribute immediately.

### 0.1 Create a PayPal Hosted Button

1. User navigates to **paypal.com/buttons/saved** (logged in)
2. Clicks **"Neu" / "Erstellen"** and selects **"Zahlungsbuttons"** (for website) or **"Zahlungslink & QR-Code"** (for social media/chat)
3. Fills in:
   - **Name & description** — product/service name + optional description
   - **Price** — fixed price OR "Vom Kunden festgelegter Preis" (customer decides)
   - **Currency** — EUR, USD, etc.
   - **Quantity** — optional, lets customers buy multiple
   - **Bilder** — up to 5 photos (optional)
   - **Lieferadresse erfassen** — optional
4. Clicks save → gets a **Hosted Button ID** (e.g. `3HMBFYC9CQTMS`)
5. The **Payment Link** is always at:
   ```
   https://www.paypal.com/ncp/payment/{hostedButtonId}
   ```

### 0.2 Embed in Website (HTML)

**Step 1 — SDK in `<head>`:**
```html
<script src="https://www.paypal.com/sdk/js?client-id=YOUR_CLIENT_ID&components=hosted-buttons&disable-funding=venmo&currency=EUR">
</script>
```

**Step 2 — Container + Render in `<body>` (async-safe pattern):**
```html
<div id="paypal-container-YOUR_BUTTON_ID"></div>
<script>
  function renderPayPalButton() {
    if (typeof paypal !== 'undefined' && paypal.HostedButtons) {
      paypal.HostedButtons({
        hostedButtonId: "YOUR_BUTTON_ID",
      }).render("#paypal-container-YOUR_BUTTON_ID");
    }
  }
  if (document.readyState === 'complete') {
    renderPayPalButton();
  } else {
    window.addEventListener('load', renderPayPalButton);
  }
</script>
```
**You MUST use `.render()` and the `window.addEventListener('load', ...)` guard** — the SDK loads asynchronously and the inline `<script>` runs before it finishes. Without this, the button silently fails (no error, no DOM insertion).

### 0.3 Update Repo Assets

- **README.md** — add/update PayPal badge pointing to payment link:
  ```markdown
  <a href="https://www.paypal.com/ncp/payment/YOUR_BUTTON_ID"><img src="https://img.shields.io/badge/PayPal-ProjectName-00457C?style=for-the-badge&logo=paypal" alt="Donate via PayPal"></a>
  ```
- **SPONSORS.md** — add PayPal section under "How to support":
  ```markdown
  ### 💳 PayPal (One-time / Custom Amount)
  Support directly via PayPal. Choose your own amount.
  [→ Pay via PayPal](https://www.paypal.com/ncp/payment/YOUR_BUTTON_ID)
  ```
- **Dedicated landing/donation pages** — add the payment button section after features/before footer

### 0.4 Fiverr Gigs (alternative monetization channel)

For selling services (consulting, custom builds, templates) rather than accepting donations, **Fiverr** is more effective than PayPal alone because it provides marketplace visibility, buyer protection, and review systems.

1. User signs up on **fiverr.com** (real browser — Fiverr also blocks headless)
2. Creates gigs under **"Programming & Tech → AI / Automation"**
3. Gig templates for OSS project monetization:
   - **Quick Audit** (€499) — business opportunity assessment
   - **Pipeline Build** (€1.999) — custom agent pipeline, 48h delivery
   - **Full Stack** (€4.999) — enterprise multi-agent infrastructure
   - **Small digital products** (€29-€149) — skill packs, templates, plugins
4. Message buyers before order to discuss requirements
5. Link to the main open-source project in gig description for cross-promotion

**Note:** Fiverr DataDome blocks headless browsers just like PayPal — create gigs through real browser.

### 0.5 Social Media Support Posts

Create `LAUNCH/support_posts.md` with posts for:
- **X/Twitter** — short, use @handle, include the payment link
- **Reddit** — r/opensource cross-post (link + repo)
- **Dev.to / Indie Hackers** — longer devlog-style post explaining why funding matters

### 0.6 Discord Community Server (recommended)

Create a Discord server as the community hub — it has no bot-detection and works with any browser:
1. User creates server on **discord.com** (name matches the project, e.g. `openamer`)
2. Set up channels: `#welcome`, `#general`, `#showcase`, `#support`, `#plugins-dev`
3. Post welcome message with links to: payment link, consulting page, GitHub repo
4. Share invite link across all social media posts and embed on the project website
5. The Discord server becomes the **lowest-friction entry point** — no bot blocks, real-time interaction
6. Post invite link also in the website footer/nav alongside GitHub/X links

**Invite URL format:** `https://discord.gg/{code}` — obtain by clicking "Invite People" in the server dropdown. Embed in HTML as `<a href="https://discord.gg/CODE">Discord</a>`. Commit format: `🔗 Discord Server Link auf allen Seiten`.

### Phase 1 — Launch Content (prep before posting)

1. **Product Hunt Launch** (`producthunt-launch.md`):
   - Listing Text (max 600 chars)
   - Tagline (max 60 chars)
   - First Comment (~200 words explaining the project)
   - 5 Screenshot descriptions
   - Hunter Pitch
   - Launch-Day Checklist
   - User Acquisition Plan

2. **Submission Content** (`submission-content.md`):
   - Awesome AI Agents Form values
   - Reddit r/selfhosted post (title + body)
   - HackerNews Show HN (title + first comment)
   - Twitter/X Launch Thread (4 tweets)

### Phase 1b — Rewrite outward copy around ONE wedge sentence

Before any post ships, there must be a **single agreed wedge**: one falsifiable
sentence that no competitor can truthfully copy. Twenty USPs is not a
positioning — it is a feature dump that reads as noise to the exact person you
need (a developer scrolling a feed). This phase turns the feature list into one
idea repeated.

**The rule:** every outward post (HN, Reddit, PH, Dev.to) opens with the *same
wedge sentence, verbatim*. The brand becomes one idea repeated, not twenty
scattered. Everything else is depth under the wedge, never a second pitch.

**Do:**
1. Read the positioning doc (e.g. `docs/positioning.md`) and take the wedge line
   exactly as written — do not paraphrase it per platform. Only the *title* and
   *surrounding body* adapt to the platform's tone.
2. **Verify every technical claim against the repo before writing it.** Search
   for the actual module/mechanism (`cua_backend.py`, `win_sandbox.py`, …) and
   quote the real file path. Do not repeat a claim you did not confirm exists.
3. **No fabricated numbers.** Cite only verified figures (e.g. marketplace
   placement with a date). If a number would strengthen the post but you can't
   verify it, mark it `[VERIFY: ...]` inline or omit it — never guess. Stars and
   traction are stated honestly low, not inflated.
4. **State the honest edge, not just the strength.** Where the product does *not*
   deliver (e.g. network egress not OS-isolated on native Windows; filesystem
   boundary is policy, not ACL), say so plainly. A boundary is only useful if its
   edge is honest, and HN/Reddit punish overclaiming hard.
5. **Tailor per platform, keep the wedge identical:**
   - **HN** — no marketing adjectives, no emoji; mechanism + honest limits;
     title ≤ 80 chars; a first comment that invites the two questions you know
     you'll get.
   - **Reddit** — separate post per sub, matched to its rules/tone
     (r/LocalLLaMA = local models/hardware/cost; r/selfhosted = what you run,
     where data lives, no phone-home). Never post the same text to two subs.
   - **Product Hunt** — tagline ≤ 60 chars *derived directly from the wedge*;
     short + long description; maker first comment.
   - **Dev.to** — a technical article on *how the wedge is implemented*, not a
     pitch.
6. **Canonical location:** put all four under `docs/launch/` and leave any
   superseded draft as a one-line pointer to the new file (do-not-post warning)
   rather than deleting it.
7. **Commit only the launch files** — the repo is usually full of unrelated
   dirty/untracked files; `git add docs/launch/ …` explicitly, never `git add -A`.

See `references/wedge-first-launch-copy.md` for the concrete file layout, the
verification checklist, and a worked example.

### Phase 2 — Platform Submission (in order)

1. **Awesome AI Agents Form** — fill via browser at https://forms.gle/UXQFCogLYrPFvfoUA
2. **GitHub Topics** — set via API: 14 topics including ai-agent, open-source, self-improving, windows
3. **Repo Description** — update via API to 160 chars with all key features
4. **Product Hunt** — user must submit (Cloudflare). Navigate them through it.
5. **Reddit r/selfhosted** — user must post (login required). Provide copy-paste content.
6. **HackerNews Show HN** — user must post (login required). Provide copy-paste content.
7. **Twitter/X Thread** — user must post. Provide copy-paste content.

### Phase 3 — Follow-Up

- Day 1: Monitor Product Hunt, respond to comments
- Day 2: Post to additional subreddits (r/AI_Agents, r/opensource)
- Day 3: Share on LinkedIn, Dev.to, Medium
- Day 7: Post progress update

## Pitfalls

1. **Product Hunt has Cloudflare** — the `posts/new` page and login are behind Cloudflare
   JS challenges. Two paths:
   - **Cloudflare blocks automation** (browser tools, headless) — CANNOT automate login.
   - **BUT: if user is already logged in** with an active browser tab, Background
     Computer-Use can drive the entire form autonomously. Find the open tab via
     `capture(app="msedge")`, click it, then use foreground `type`/`key` for all
     input fields and background `click` for buttons/links.
   - **Real example (Aug 2026):** User logged into PH 2 days prior. Agent found
     the "Launch Day dashboard" tab, clicked "Edit Launch", changed name from
     "GitHub" to "OpenAmer", wrote tagline (60 chars), description (328/500 chars),
     and clicked Save — all via Background Computer-Use. Result: "All changes saved
     successfully."
   
   **Checklist for PH via computer-use:**
   - [ ] User is logged in (browser tab exists)
   - [ ] Capture and find the relevant tab
   - [ ] Click tab to switch to it
   - [ ] Click "Edit Launch" (Admin badge visible)
   - [ ] Type new name (foreground)
   - [ ] Type new tagline, max 60 chars (foreground)
   - [ ] Type description, max 500 chars (foreground)
   - [ ] Click "Save changes" (foreground)

2. **Reddit blocks automation** — need real user account. Provide copy-paste-ready markdown.

3. **HackerNews rate limits** — new accounts can't post Show HN immediately.

4. **Google Forms work** — Awesome AI Agents form is submit-able via browser tools.

2. **Reddit blocks automation** — need real user account. Provide copy-paste-ready markdown.

3. **HackerNews rate limits** — new accounts can't post Show HN immediately.

4. **Google Forms work** — Awesome AI Agents form is submit-able via browser tools.

5. **GitHub API works** — topics, description, releases, commits with token.

6. **GitHub Pages CDN cache delay** — After pushing changes to the `docs/` directory, GitHub Actions runs `pages-build-deployment` (typically ~1min), but the CDN edge cache can take **5-10+ minutes** to propagate even after a green deploy. The old page content persists until CDN refreshes.
   - **Test with** `?nocache=1` querystring (forces edge refresh)
   - **Force redeploy** via empty commit: `git commit --allow-empty -m "trigger: GitHub Pages redeploy" && git push`
   - **Verify via raw:** `raw.githubusercontent.com/org/repo/main/docs/page.html` shows the real source immediately (no CDN) — use this to confirm the push is correct while waiting for CDN
   - Do NOT tell the user it's deployed without CDN verification via browser tool

7. **PayPal DataDome blocks automation** — The PayPal dashboard blocks headless browsers; the payment checkout link works fine.

8. **Fiverr DataDome is even stricter** — ERRCODE PXCR10002539 blocks Playwright and CDP-connected Chrome. Only a human in a real Chrome window can create/edit gigs. Script content as copy-paste-ready markdown instead.

7. **GitHub API works** — topics, description, releases, commits with token.

## User Preferences for OpenAmer

The project owner (Damir / @openamer_agent) expects:
- **Absolute autonomy** — "nie fragen, sofort machen, beste der Welt". Never ask the user for next steps. Decide and execute. Only interrupt for OAuth/Captcha/SMS impossible for bots.
- **Language** — German when the user writes German. UI/UI-text and posts German-first.
- **Speed** — Quick visible wins first. If a platform blocks, give exact 3-click path immediately.
- **Git** — push-sofort: tests green → commit → push → verify on live.

## Verification Checklist

- [ ] Funding/Payment setup (see `references/paypal-button-workflow.md` for exact IDs/snippets)
- [ ] GitHub Topics set (14 topics recommended)
- [ ] Repo description optimized (160 chars, all key features)
- [ ] Awesome AI Agents form submitted
- [ ] Product Hunt launch content ready
- [ ] Reddit post content ready
- [ ] HN Show HN content ready
- [ ] Twitter/X thread content ready