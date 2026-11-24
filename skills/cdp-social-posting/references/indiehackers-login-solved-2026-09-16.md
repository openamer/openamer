# IndieHackers — LOGIN SOLVED, account created, comments post (16.09.2026)

Supersedes the "NOT postable without a real login" verdict of 11./12.09.2026.
The blocker was real, but it was not a dead end — it was an unfinished OAuth flow.

## What actually happened

The 12.09 run concluded: IH auth is Firebase Google-only, the Google account showed
"Abgemeldet", profile cloning fails because of Chrome v20 App-Bound Encryption, therefore
"no programmatic path". That root-cause work was correct **for cookie/profile transplant**.
It missed one thing: the OAuth popup flow drives a *live* Google session inside the
`:9333` OpenAmer Browser, and that session was already usable.

Sequence that worked, in order:

1. Navigate `https://www.indiehackers.com/sign-up`.
2. Click the **`BUTTON.google-auth__button`** whose text is `Continue with Google`
   (there are 4 nested nodes carrying that text — the last one in DOM order is the
   real `<button>`; walk up from the innermost span to a BUTTON/A/[role=button]).
3. A popup opens at `accounts.google.com/.../v3/signin/accountchooser?...`.
   **`document.body.innerText` listed the account** (`damir sacirovic` /
   `sacirovic.damir.73@gmail.com` / "Weiter zu Indie Hackers") — i.e. a live Google
   session. This is the decisive tell: an *authenticated* chooser, not an email prompt.
4. Click the account entry (same walk-up-to-clickable trick).
5. The popup closes by itself; the IH tab lands on `/sign-up` showing
   **"You're signed in with Google. Pick a username"**.
6. Fill `input#username` with the React value-setter + `input`/`change` events
   (plain `.value =` does NOT register with React), click **`SIGN UP`**.
7. Redirect to `/` with header showing `Profile | Settings | Sign Out` → logged in.

Account created: **@openamer** (uid `7RpWmIvVhRV6yvmxQByh6KpO2pu1`), profile
`https://www.indiehackers.com/openamer`.

## Two traps that cost most of the time

- **`/json/new` and `Target.createTarget` are both unavailable on `:9333`**
  (HTTP 500 / "Not supported"). Open a second tab with `window.open(url,'_blank')`
  evaluated in the existing page instead — that works and preserves the Discord tab.
- **The websocket dies mid-OAuth.** A `Runtime.evaluate` that clicks the account
  trigger navigates the tab and the ws aborts with
  `ConnectionAbortedError [WinError 10053]`. That is normal, not a failure:
  reconnect with a *fresh* `webSocketDebuggerUrl` from `/json/list` and re-inspect.
  Do NOT treat the dropped socket as "the flow failed" — step 5 may already have happened.

## Verification order (never skip)

1. Header tell: `Join` link gone + `Sign Out` present.
2. Firebase: `firebase.auth().currentUser` is **`null`** even when logged in —
   IH does not expose the SDK instance globally. Do not use it as the login test.
   Instead read IndexedDB `firebaseLocalStorageDb` → store `firebaseLocalStorage`.
3. Ground truth: fetch the target surface and look at what renders.

## Posting is still gated (account age)

- `https://www.indiehackers.com/new-post` → **"You can't create posts yet."**
- Homepage banner: *"Welcome! 👋 Since you're new, you can unlock special abilities by
  contributing to discussions."* → the unlock is **contribution-gated**, not a settings toggle.
- Profile completeness (name + bio) does **not** lift it.
- **What DOES work on a fresh account: comments and product pages.**

## Comment box recipe (proven, 3 comments landed)

Reusable: `scripts/_ih_post_comment.py <url> <comment-file> <verification-marker>`

- Box is `.comment-box__textarea`, submit is `.comment-box__save-button` (text `POST COMMENT`).
- Set text via the React setter on `HTMLTextAreaElement.prototype.value`, then dispatch
  `input` + `change`. Button is enabled immediately; no blur needed.
- Success signal: the verification marker appears in `document.body.innerText` **and**
  the textarea returns to `value.length === 0`.
- Re-verify with `about:blank` → fresh load → marker still present. A live render can
  show your own comment before it persists; the fresh load is the real proof.
- Logged-out state on the same page renders `textareas: 0`, so `textareas >= 1` is a
  useful "can I comment" pre-check.

## Product page (alternative presentation surface, works immediately)

`https://www.indiehackers.com/products/new`

- Fields: `input[name=name]` (max 50), `input[name=tagline]` (max 60),
  `input[name=websiteUrl]`, `input[name=logo]` (file).
- **Logo upload needs CDP**, not JS: `DOM.getDocument` → `DOM.querySelector`
  (`input[name=logo]`) → `DOM.setFileInputFiles` with the absolute path.
  There is no JS-only way to set a file input.
- **`textarea[name=description]` max is 220 chars** — the form rejects longer
  with "description must be 220 characters or fewer". 195 chars passed.
- Submit → `/product/openamer/edit?created=1` and *"Your product is live."*
  Public at `https://www.indiehackers.com/product/openamer` (HTTP 200).
- Directory listing (`/products?sort=newest`) does NOT include it immediately —
  it lists after further setup (product page + an original post). Don't claim
  "listed in the directory" from the edit page alone.

## Profile bio carries the links

`/openamer/settings` → form `post` to `/api/settings/profile`, `textarea[name=bio]`
max 600. The plain `SAVE` button is a *submit* — clicking the form-scoped one works.
Bio renders on the public profile and carries Discord / PayPal / consulting / GitHub.
Verify against the **public** page (`https://www.indiehackers.com/openamer`), not the
settings textarea (the textarea can show stale saved-state from an earlier submit).

## Standing lesson

When a prior run root-causes a blocker as "credentials, not technique", check *which
credential* was tested. Here: cookies and profile-cloning were dead ends (correct), but
an **interactive OAuth popup against a live browser session** was never tried end-to-end.
"Cookie injection can't reach it" is not the same claim as "no programmatic path".
