# Disclosed-Report Patterns (condensed bank)

Extracted from real, publicly disclosed HackerOne reports via the archive route
(`github.com/ajaysenr/HackerOne-Disclosed-Reports`). Read this before drafting new
lessons so you extend the bank rather than re-derive it. Each entry: the durable
rule + the case that established it. Full prose lives in `bounty-factory/lessons.md`.

## Report discipline (applies to every class)

1. **60-Second Rule.** Triage decides in 60s. Answer in order: bug type (title),
   exact endpoint+parameter, numbered copy-pasteable repro, visible impact proof,
   one-sentence business impact, CVSS + justification. #1 rejection reason is
   "cannot reproduce / insufficient PoC".
2. **Impact chaining beats raw severity.** Chain low-sev findings into one attack
   path (enumeration → info-leak → ATO) as an explicit step diagram.
3. **Corrected title/severity ≠ rejection.** Cloudflare #3622877 ("smuggling" →
   "request-inspection bypass") still paid $1,500. Describe the mechanism you
   *proved*, scope blast-radius precisely, name the fix in the vendor's own terms.
4. **Redact real secrets; offer SHA-256 fingerprints instead** (Mozilla Taskcluster
   #3782701, $12k). Showing you *can* read a secret is enough; publishing it is
   amateur and triggers a rotation fire-drill.
5. **Harmless-proof-first.** Prove a primitive with an output that changes no data
   (a computed marker like `RCE_42_object`), and state explicit stop-conditions.

## By vulnerability class

- **Code injection / RCE.** Prove by DIFFERENTIAL probing, not by claiming a class
  (H1 #3694007 Painless, $7k): (a) show the parameter reaches a real engine;
  (b) malformed-vs-valid probes locate the compiler as the discriminating layer;
  (c) two requests differing only in the payload produce output inexplicable
  unless it ran. Trace untrusted input into THIRD-PARTY sinks — `sift $where` /
  `new Function` / template engines, not just first-party code (#3782701).
  Weaponise the app's own error/format channel as the blind oracle (#3782701).
  For deserialization, write every hop of the gadget chain to the sink, not the
  class name (#3861550 8x8, CVSS 9.9). **An OPEN SCALAR argument that reaches a
  downstream INTERPRETER is code injection**: a free-form `: String` / `JSON` /
  `Any` argument (or any typed field carrying raw text) forwarded verbatim into a
  tool with its own evaluator — Elasticsearch `painless`/`_script` sort, MongoDB/
  sift `$where`, Jinja/`eval`, JMESPath. The GraphQL type system advertises a
  *value* while the backend treats it as a *program* (#3694007: `Query.search
  (sort_query: String)` → ES `_script` sort compiled+executed per document,
  BEFORE any resolver-layer authz filter — confidentiality is the sharpest claim,
  not "RCE"). You do NOT need to prove RCE to prove execution ran: the differential
  COMPILE probe (malformed source → 500, valid `"1"`/`"1+1"` → 200, identical JSON
  structure) localises the interpreter behind the wire, and a per-document proof
  reads an INTERNAL metadata field (`doc["_seq_no"].value`) inside your OWN
  filtered result set.
- **IDOR / authz.** Read the WHOLE error body, never stop at the status code
  (H1 #3862641, $15k: HTTP 422 "access denied" still carried private detail in
  `context.subject`). Recovery/reset flows taking another user's identifier and
  emitting a token are IDOR goldmines → ATO.
- **A NONCE on a page anonymous users can load is NOT a per-user secret** (WordPress
  Secure Custom Fields #3893632, CVSS 5.3, 5 votes, Resolved): WordPress issues
  logged-out nonces to uid 0 with an EMPTY session token, so every anonymous visitor
  gets the SAME nonce — a nonce gates request INTEGRITY for a session, it does not
  authorize a stranger. SCF 6.9.2 registered `wp_ajax_nopriv_acf/fields/{post_object,
  relationship,page_link}/query`; the shared helper `acf_get_grouped_posts()` ran a
  `WP_Query` with `post_status='any'` and no `perm` arg / no `current_user_can()` →
  draft, pending, private, future posts and non-public CPTs all returned. The ONLY
  gate was a per-field nonce emitted into any public page rendering the field via
  `acf_form()`. So: scrape the nonce from public HTML
  (`curl -s https://SITE/pubform/ | grep -o 'data-nonce="[a-f0-9]*"'`) and replay it —
  `POST /wp-admin/admin-ajax.php --data 'action=acf/fields/post_object/query&
  field_key=\<k>&nonce=\<scraped>&paged=1'` → HTTP 200 JSON listing
  `"PRIVATE-POST (private)"`, `"SECRET-DRAFT (draft)"`; the `s=` param turns it into a
  targeted keyword search over non-public content. Rule: grep every `wp_ajax_nopriv_`
  handler and ask (a) does its query filter by capability AND `post_status`, (b) is
  its only gate a nonce? `nopriv` + `post_status=any` + nonce-only = an
  unauthenticated disclosure primitive dressed as a protected endpoint. Evidence that
  landed it: file:line root-cause map (`class-acf-field-post_object.php:34/148`,
  `api-helpers.php:1299`), the exact scrape→replay curl pair using a REAL scraped
  nonce ("no simulation"), and the 200 response carrying the draft/private titles —
  reproducible with no credentials at all.
- **Missing control on a SIBLING path = the bug (the "guarded-vs-unguarded" tell).**
  When a security control exists on one code path but not its sibling, the ABSENCE
  is the finding. Fastest conversion from "looks wrong" to "finding": grep every
  file/socket/exec sink for the guard the engine uses elsewhere
  (`check_global_access(thd, FILE_ACL)`, `is_secure_file_path`, an authz helper) —
  if the same codebase treats a control as mandatory on one path and omits it on
  the sibling, it is not a design choice (MariaDB CONNECT #3836021, CVSS 8.8:
  file-backed TABLES enforce `FILE`+`secure_file_priv` at `ha_connect.cc:4538/
  4557/4559`, but the `json_file/bson_file/jfile_make/bfile_make/jbin_file` UDFs
  call neither → a `SELECT`-only user reads `/etc/passwd` and writes outside
  `secure_file_priv`; `grep -niE 'FILE_ACL|is_secure_file_path' jsonudf.cpp
  bsonudf.cpp` → **zero hits** is the proof). Canonicalise the path
  (`my_realpath`) BEFORE the `secure_file_priv` check so `../` can't slip past.
  When a sibling CVE was DISPUTED/closed, pre-empt the dispute by naming the
  boundary YOUR case crosses that it did not (here: bypasses `FILE` entirely;
  defeats a `secure_file_priv` the engine itself enforces elsewhere). This is the
  same tell as auth-route (#3869124) and JWT-verify (Nextcloud OIDC): whenever you
  find one unguarded sink, grep every sibling function and DIFF the guards.
- **Integer underflow / arithmetic on untrusted length — read the DIRECTION.** A
  length computed as `len - 1` on an attacker-controllable length is an underflow;
  unsigned `0 - 1` → `SIZE_MAX` → any `malloc(SIZE_MAX)`/`alloca` — then read/write
  "len" bytes is an OOB. MariaDB #3781201 (CVSS 5.7): `caching_sha2_password`
  RSA-OAEP-decrypts an EMPTY password reply → `plain_text_len == 0` →
  `pkt_len - 1 == SIZE_MAX` → `my_sha256_multi` reads `SIZE_MAX` bytes → SIGSEGV
  (`Exited(139)`), crashing the server BEFORE any credential comparison, so NO
  valid password is needed. PoC is ~30 lines of raw protocol + `pub.encrypt(b"",
  OAEP(...))`; the proof is "does the connection die after the ciphertext?".
  CRITICAL: determine the DIRECTION before writing up — OVER-READ (memory-unsafe →
  exploitable) vs CLAMP (memory-safe → usually Informative; see the curl `(size_t)
  size` case below). Same "integer bug" headline, opposite outcome; the direction
  IS the severity. State preconditions (plugin in use, plaintext TCP, RSA keys
  present) — over-stating them is how a real crash gets downgraded. Fix: a one-line
  `if (pkt_len < 1) return CR_ERROR;` plus a defensive `key_len == 0` guard in the
  hash routine.
- **SSRF.** Prove internal reach, don't name the class. **Allowlist bypass lives
  in URL PARSING ambiguity** (DuckDuckGo #3522157, $500): the trusted host sat in
  the *userinfo* section (`.../audio.wordnik.com@raw.githubusercontent.com/...`)
  and the fetched host was the part AFTER `@`. Test `trusted@evil`, `evil#trusted`,
  `evil?x=trusted`, redirect chains, decimal/IPv6/`%2f` encodings — substring
  allowlisting is the bug. Chain to a second primitive (reflection → XSS).
  **STORED / DEFERRED SSRF: prove the SINK FIRING, not the value being accepted**
  (Nextcloud #3623149, CVSS 5.4, Resolved): `POST /ocs/v2.php/apps/notifications/
  api/v2/push` is a `NoAdminRequired` route that STORES a user-controlled
  `proxyServer`; the outbound `POST {proxyServer}/notifications` fires LATER from
  `Push::sendNotificationsToProxies()` when a notification event occurs — so the
  registration returning `201 Created` is NOT the vuln. Name BOTH ends (the
  controller/method that STORES the value vs the method that CONSUMES it), then
  TRIGGER the deferred sink (e.g. `occ notification:test-push <user> --files`) and
  prove internal reach from the TARGET'S OWN log line (`127.0.0.1 … "POST
  /notifications" … "Nextcloud Server Crawler"`) — the inbound request in the
  victim's logs is the evidence, not the 201. Generalises Lesson 4 to every
  stored-then-fetched URL/host: webhooks, scheduled imports, avatar/URL fetchers,
  push proxies. "The server accepted my URL" alone is a blind finding and gets
  downgraded.
- **DoS / resource abuse.** The cheapest DoS is ONE request the server expands
  into N expensive ops (H1 #3287208 GraphQL alias, $12,500). Any costly side
  effect (OTP/email/SMS, hash, external call, file scan) is a candidate when the
  format allows repetition (aliases, duplicate JSON keys, array elements).
  Prove the linear slope harmlessly, single-user/single-IP; fix is an operation
  budget, not "rate limiting". Read the current DoS policy first — the POLICY
  VERSION determines pay-or-ban (HackerOne retroactively tightened DoS rules:
  testing windows, single-request/single-user/single-IP; #3287208 was paid under
  the older rules). REPORT THE MEASURED MARGINAL COST per repetition ("≈8 s added
  per alias, ~20 s measured at three"), because that number is what lets triage
  scope the fix. A `Severity: None` / unrated report can still be a five-figure
  bounty ($12,500, 141 votes) — when your own shows "None", re-read whether the
  IMPACT argument, not the bug, failed.
- **Secret exfil via analytics/telemetry.** A secret in an AUTOMATIC page-load
  event is a live exfil channel (HackerOne Code #4000185, $200): `analytics.page()`
  fired on reset-link load and shipped the 64-char token in `context.page.search`,
  `context.page.url`, `properties.search`, `properties.url` — four places. Audit
  every `page()/track()` on URLs carrying reset/invite/magic-link secrets. The
  winning proof is a CONTROL request (queryless page still fires, no token) plus
  an identity JOIN (same `anonymousId` as an earlier identify event carrying
  email/UID). Rate honestly Low if telemetry access is required.
- **Untrusted NAME / reserved-key collisions.** A user-supplied *field name* the
  engine already trusts can overwrite critical state, separately from supplying a
  value (8x8 #3858504, CVSS 7.7, $1,337: workflow step output field names weren't
  validated against reserved context variables). Test `__proto__`, `constructor`,
  `$ctx`, framework-reserved keys anywhere a user names a key (JSON keys, form
  fields, template/workflow variables). Proof = before/after of engine state
  changing under attacker control; fix is a name allow/denylist at creation.
- **The hunter's own tool is attack surface.** A scanner/crawler fetching hostile
  pages must treat every page-controlled attribute as hostile input
  (PortSwigger #3712279, $5k: file-input `accept` attr → Path Traversal → Windows
  Startup folder write). Sink pattern: derive a filename/path from untrusted
  metadata + `Path.resolve/join` with no separator check.
- **Non-browser render sink / template injection.** Any place user input lands in a
  TEMPLATE the victim reads — transactional email, push, PDF, SMS, receipt — is a
  first-class injection surface, not just the web page (Essity #3802451, CVSS 5.3:
  unauthenticated `POST /contacts/email` interpolated `firstName` raw into a
  `text/html` confirmation mail sent via SendGrid, DKIM/SPF/DMARC-valid from the
  brand's own infra → weaponised phishing). Test an HTML sanitizer with a TAG
  MATRIX, never one payload — tabulate what survives (`<img>` stripped but
  `<a style=…>` survived = a PARTIAL filter, i.e. the bug). Impact framing that
  moves severity: "phishing via the vendor's own authenticated mail infrastructure
  through their real branded template". Fix = context-correct output encoding.
- **Memory-safe narrowing cast / Informative triage bar.** 64→32-bit integer
  truncation only pays when you SHOW the impact chain; if you can't build the
  primitive, downgrade your OWN severity (curl #4059104, Resolution: Informative —
  `chunk=(size_t)size` clamped a 4 GiB IMAP literal to 10 bytes on 32-bit builds;
  the reporter self-falsified the memory-corruption angle: "the truncation only
  ever makes the copied length SMALLER … so there is no out-of-bounds read", and
  admitted "response injection is plausible but I have not built a working E2E").
  Two flavours: OVER-READ (memory-unsafe → exploitable) vs CLAMP (memory-safe →
  usually not); prove WHICH before writing up. Contrast the SAME program/week's
  PAID siblings (#4064040 curl use-after-free, #4085412 curl Rustls OOB heap read)
  — memory-UNSAFE out-of-bounds reads: what pays is the proven over-read this bug
  lacked. Voluntary under-claiming reads as credibility; unbuilt impact claims are
  the #1 reason legit bugs get closed.

- **Reference-count / double-free via a REUSABLE lookup key** (PlayStation #3320669,
  $10k, 90 votes). When a teardown path matches its target by a *recyclable* number
  (fd, index, port, inode, PID, slot id) instead of the object, an identifier reuse
  between set and clear makes the release hit the WRONG object. Pattern: add(ref A
  under key K) → A closes, K reassigned to B → remove(key K) releases B and leaks A.
  Here `kern_netevent_clear_queue` compared `ne->socket_fd == socket_fd`, so closing
  `s1` and reopening `s2` (same fd) got `s2` double-`fdrop`ed (refcount 1→0 → UAF,
  freed while still in the fdtable) while `s1`'s ref leaked. Rules: the invariant
  "K ⇒ A" is broken by identifier recycling — store/compare the OBJECT (or a
  generation counter), never the recycled key; grep teardown for `== fd/index/slot`
  vs a user value. Classify by imbalance DIRECTION: DOUBLE-PUT (extra release →
  frees live memory → exploitable) vs LEAK (only resource exhaustion). Exploit fd
  predictability (close then immediate `socket()` → same fd); name the
  platform-specific fault trigger (PS5 `fget()` hangs on refcount 0; PS4
  `fcntl(F_SETFL)` drives another free). High when the reachable primitive is a
  UAF; not Critical until code execution is shown.
- **Privilege retention / escalation: a DROP (or revoke) that clears SOME but not
  all of an object's grant rows** (MariaDB #3908943, High CVSS 8.0, no bounty on the
  VDP). `DROP PACKAGE` cascaded correctly in `mysql.proc` but removed only the
  `PACKAGE` row from `mysql.procs_priv`, orphaning the `PACKAGE BODY` EXECUTE grant
  — and `PACKAGE BODY` is the type that gates execution. A user once granted
  `EXECUTE ON PACKAGE BODY appdb.kvchk` later executes an UNRELATED recreated
  `kvchk` (created by root) with root's definer privileges, holding no grant on it.
  Rules: whenever teardown touches a thing carrying grants/ACLs/memberships,
  enumerate every row it must clear and **diff its sibling drops** — run a batch
  with one object of every type, grant each, drop each, diff survivors;
  `DROP PROCEDURE/FUNCTION/PACKAGE BODY` clean their row while `DROP PACKAGE` did
  not, and the one-type-lags result IS the bug (the guarded-vs-unguarded tell applied
  to CLEANUP). The escalation needs NAME REUSE — the orphaned row is keyed by name,
  so drop-then-recreate-under-the-same-name (the ordinary deploy pattern, not
  attacker-triggered) re-attaches it. Check ROLE propagation (a grant to a role
  orphans for all current/future members). Grade the CONSEQUENTIAL grant type. VDP
  writeup craft worth copying: plant a MARKER in the protected data
  (`HUNT-VAULT-9f3a2c71`) and read it back so the leak is a fact not an inference;
  show BOTH control halves (direct SELECT → error 1142, versus via the recreated
  package → marker); print grant snapshots before/after as a table; state LIMITATIONS
  honestly ("not attacker-triggered; needs an admin drop + later same-name create",
  "SHOW GRANTS can reveal it"); add a self-referential sibling exclusion ("DROP
  DATABASE also leaves grants, but that is documented behaviour and I am not
  claiming it"); disclose AI tooling use while affirming every output was executed.
 - **Two consumers, two normalisations: the CHECK canonicalises the path, the
 LOADER uses it LITERALLY** (PlayStation #3452696, Medium, $2,500, 43 votes — PS4
 BD-J nested JAR). One string,
 `file:/dsm/00000.jar/../../app0/bdjstack/lib/ext/00000.jar`, is resolved by the
 security policy (`new File(url.getFile()).getCanonicalPath()` → collapses `..` →
 `/app0/bdjstack/lib/ext/00000.jar` → `startsWith(javaHome+"lib/ext")` → grants
 **AllPermission**) while the class loader splits it at the FIRST `.jar/`, opens
 `/VP/BDMV/JAR/00000.jar` off the disc, and looks up `../../app0/...` as a
 **literal archive entry NAME** where `..` are just characters → untrusted content
 runs with AllPermission. Rules: (a) the tell is a path/URL consumed by two
 components with different normalisation — grep
 `getCanonicalPath`/`realpath`/`normpath`/`normalize()`/`resolve()`/URL-decoding on
 ONE side and a raw string compare/open/split on the other; every form the other
 side does not normalise bypasses the check (`..`, `%2e%2e`, `..%2f`, backslash,
 `//`, trailing dot/space, symlink, NTFS ADS); (b) a `startsWith` prefix test is
 ALSO a sibling-directory bypass (`/app0/bdjstack/lib/ext_evil` passes
 `startsWith(".../lib/ext")`) — require the separator boundary; (c) whenever the
 format is `container/subpath` (`outer.jar/entry`, `zip:`, `tar:`,
 `docker image:tag`, `file:`, `s3://`, `#fragment`) ask SEPARATELY whether the
 subpath is normalised — nothing in an archive-entry namespace normalises `..`,
 and that asymmetry IS the bug; (d) the compound bypass: `isSigned()` was a pure
 RANGE test on the application id (`0x4000 <= aid <= 0x7FFFF`), so an
 attacker-chosen out-of-range `aid` in the BDJO makes `needsToVerify()` false and
 certificate verification is skipped entirely — **any security boolean computed
 from an attacker-influenced numeric range is an OFF-switch**; grep the verifier
 for the value it decides on and who supplies it; (e) the writeup that carries it
 is the two-column transformation table (check path step-by-step vs load path
 step-by-step → "AllPermission granted / untrusted disc content loaded") with
 FILE:function citations; (f) grade honestly — Medium, not Critical, because it
 needs physical disc media + a non-premium application id.
 - **DOM sink on an attacker-controlled FILENAME = authenticated REQUEST GADGET, not
 a cosmetic DOM bug** (Basecamp/Fizzy #3608199, High CVSS 8.0, $500, 60 votes). The
 account-import page rendered the selected local filename with `innerHTML`
 (`app/javascript/controllers/upload_preview_controller.js`) instead of
 `textContent`, so a crafted `.zip` NAME is parsed as live HTML *inside the real
 authenticated form*: naming the file `\<button formaction=/40002/users/\<victim-id>
 /email_addresses formmethod=post name=email_address value=attacker@example.com>
 Take over.zip` makes ONE click submit the victim's authenticated POST with the
 form's real `authenticity_token` → email change to the attacker's mailbox →
 redeem the confirmation link → fresh victim `session_token` → `200 OK` on the
 victim's account/edit pages = full ATO (also: write-scoped PAT creation, account
 deletion). Rules: (a) filenames/upload names/titles/query echoes are
 attacker-controlled text re-rendered CLIENT-side long after the server
 "sanitised" the upload path — the download/upload path is hardened, the PREVIEW
 path usually is not; audit every `innerHTML`/`outerHTML`/`insertAdjacentHTML`/
 `document.write`/`dangerouslySetInnerHTML`/jQuery `.html()` that receives one;
 (b) escalate with a FORM CONTROL, not script — `\<button formaction= formmethod=
 post name= value=>`, `\<input type=image formaction=>`, a nested `\<form>`, `\<a
 ping=>`: no `\<script>` needed (CSP/sanitizer-proof, the browser's own submit does
 the work), the enclosing authenticated form supplies the CSRF token for free, and
 the victim cookie rides along — **same-origin DOM XSS voids CSRF-token
 protection**; grade DOM sinks on authenticated pages as request forgery, never as
 UI manipulation; (c) enumerate EVERY impact reachable from the one sink and lead
 with the strongest DEMONSTRATED one; (d) evidence standard that made it land: pin
 the exact upstream commit, build/run the real app in Docker, capture outbound
 mail in MailHog, log HTTP checkpoints end-to-end (victim POST with `[FILTERED]`
 authenticity_token → confirmation mail to attacker mailbox → confirmation POST →
 new `session_token` → `200` on victim pages → identity now `attacker@example.com`)
 and ship seed+replay scripts; "validated on current upstream in a real
 deployment", never "potentially"; (e) 60 votes on a small $500 High = a fully
 built, plainly written chain beats a scary class label on an unbuilt impact.

 - **Inherited visibility: a per-object status check that skips the ANCESTOR walk leaks the child**
  (WordPress bbPress/BuddyPress #4053546, Medium, no bounty, Resolved, disclosed
  2026-10-10). bbPress's BuddyPress bridge builds the Activity `hide_sitewide` flag
  with `bbp_is_forum_public( $forum_id, false )` (`includes/extend/buddypress/
  activity.php`, topic_create/reply_create) — the explicit `false` disables the
  helper's own ancestor recursion, so only the immediate forum's `publish` status
  is read, not the parent's `private`/`hidden`. A publish subforum under a private
  parent broadcasts every topic (title, forum, permalink, RAW BODY) to the PUBLIC
  `/wp-json/buddypress/v1/activity` stream while the topic's own permalink 404s for
  the same anonymous viewer. Rules: (a) inherited state is the bug surface — the
  check must walk the same parent chain the viewer-facing page walks; the tell is an
  extra boolean/`depth=0`/`shallow` argument that turns the ancestor walk off for
  ONE caller — grep the helper's call sites and diff the argument; (b) the strongest
  evidence is a **contradiction between two read paths for the same object** (404 on
  the canonical permalink vs 200 on the feed) — self-contained broken-authz proof
  that triage cannot wave off with "the content was public anyway"; enumerate the
  secondary surfaces (ActivityPub/RSS, `/wp-json/*` collections, search, sitemaps,
  notification mail, previews/embeds); (c) the fix is one argument — drop the `false`
  — and naming it in the maintainer's own terms is what converts a no-bounty VDP
  report into Resolved-and-merged rather than Informative.
- **A code/token that is never CONSUMED + an expiry check reading the WRONG column =
  two bugs in one handler; the repeat at a SIBLING handler is the guarded-vs-unguarded
  tell applied to DATA** (Mozilla Taskcluster #3734676, Medium, $2,000).
  `services/web-server/src/servers/oauth2.js:165-199` validates `redirect_uri`+code,
  mints a bridge access token and returns WITHOUT deleting the `authorization_codes`
  row (RFC 6749 §4.1.2 single-use violated); the expiry check at line 66 reads
  `entry.client_details.expires` (lifetime of the RESULTING credentials, e.g. "1
  year") instead of `entry.expires` (the code's 10-minute lifetime, set line 33), so
  expired codes stay redeemable until a daily `cleanup-expire-auth-codes` cron — and
  the same wrong-column read repeats at `oauth2.js:318-375`. Rules: (a) for any
  code/token/nonce ask **"what consumes it?"** — if the answer is a scheduled cleanup
  job, replay is open for the whole cron interval; prove it by exchanging the same
  code twice and diffing (`token A != token B`); (b) two rows with similarly-named
  columns is a bug generator — trace which ROW an `expires` field belongs to, then
  hunt the same mistake at every sibling handler; (c) the paid craft: the PoC is an
  extension of upstream's OWN test suite (Mocha `TC-002` in `test/third_party_test.js`,
  pinned commit, `docker compose up -d postgres`, assert 200→200 with different
  tokens), RFC clause cited BY NUMBER, one-line pass log printed.

- **A pointer taken INTO a growable container is invalidated by a REALLOCATION
  during a nested call; "not fixed by \<prior fix>" is a FIX-SCOPE AUDIT order.**
  MariaDB #3915935 (High CVSS 8.8, Resolved, 2 votes, disclosed 2026-10-07):
  `sp_cursor::open()` (`sql/sp_rcontext.cc:845`) passes `&result` /
  `&server_side_cursor` — members of `this`, an `sp_cursor` inside the
  `m_statement_cursors` Dynamic_array — into `mysql_open_cursor()`; the nested
  `mysql_execute_command()` runs the cursor's SELECT, which calls a function that
  opens further SYS_REFCURSORs, so once the count crosses the array's DEFAULT
  capacity (17 > 16) the backing buffer is reallocated and freed; on return
  `materialized_cursor->open(result, 0)` is a virtual call through the dangling
  `result` (`sql/sql_cursor.cc:250`) and `*pcursor = materialized_cursor` writes 8
  bytes into freed memory (line 255) — ASan heap-use-after-free. Rules: (a) an
  address of a member/out-param handed to a callee that can run NESTED
  attacker-influenced code (stored-proc statement, trigger, callback, signal
  handler, event loop) dangles if a container grows during that execution — grep
  call sites passing `&this->member` / `&array[i]` into an `execute`-style call and
  re-derive AFTER the call, `reserve` capacity, or use a non-movable allocation;
  (b) the CAPACITY BOUNDARY is the trigger (17 > 16) — read the container's growth
  policy to size the PoC; (c) a prior fix that removed a stale STORED MEMBER did
  not touch the CALL-SITE PARAMETERS that also dangle — when a title says "still
  vulnerable after MDEV-X / PR #X", diff what the prior fix CHANGED (the
  declaration) against what it MUST have changed (every consumer of the moved
  data) and test the untouched half: the guarded-vs-unguarded tell applied to a
  PATCH; (d) CREATE FUNCTION suffices (any user with a database) → low-priv →
  claimed RCE; (e) the SIGSEGV/ASan UAF is PROVEN, IP control + heap corruption
  are CLAIMED — write them as claimed-not-shown.
- **When the object id lives INSIDE a synthetic config KEY, the API validates the
  key's SHAPE and forgets to authorize the object it NAMES.** Nextcloud Deck
  #3599383 (Medium CVSS 4.3, CVE-2026-77170, $200, 28 votes, Resolved, disclosed
  2026-09-17): `POST /ocs/v2.php/apps/deck/api/v1.0/config/board:28:notify-due`
  `{"value":"all"}` — an authenticated low-priv user (`test100_1`) writes a
  board-scoped preference for board 28 owned by `admin`; the key is
  `board:<boardId>:<key>`, parsed and written to `oc_preferences` with NO
  ownership check on the id it names. Rules: (a) NAMESPACE-ENCODED IDENTIFIERS —
  any id embedded in a STRING route/key/param (`board:28:notify-due`,
  `s3://bucket/key`, `user/<id>/file`, `tenant:<id>:setting`) is an implicit
  parameter needing the SAME per-object authz as an explicit one — find the
  parse/split step and ask "where is the ownership check on the parsed id?"; (b)
  config/preference WRITERS are authorization-poor by design (built for "the
  current user's own settings") and become cross-object the moment the key carries
  a foreign id — enumerate every `set_config`/`setPreference`/`update_setting`
  route with a COMPOSITE key; (c) this is the KEYED sibling of the settings-blob
  class (Lesson 46): Lesson 46 abused an allowlist-less VALUE blob against the
  caller's OWN account, here the abuse is a FOREIGN OBJECT addressed by the key —
  same family, different axis (object scope vs key set); (d) evidence = TWO
  independent read paths: the exact curl (cookie jar + `OCS-APIRequest: true`)
  THEN a DB check (`SELECT ... FROM oc_preferences WHERE
  configkey='board:28:notify-due'`) proving the foreign row EXISTS — "the server
  said OK" is not "it was written" (same discipline as stored-SSRF, Lesson 42);
  (e) grade CVSS 4.3 Medium for an integrity-only write and add the
  forward-looking note instead of inflating — 28 votes on $200 (cleanly reproduced
  access-control gap on a CVE'd product) beats a scary-but-unbuilt class label.

- **ALLOCATE-BEFORE-VALIDATE: a client-supplied COUNT sizes a buffer the next lines
  write into, and the bound check fires only LATER** (MariaDB HandlerSocket #3867363,
  Medium/CWE-400, reporter CVSS 7.5, Resolved, 1 vote, disclosed 2026-10-07).
  MariaDB's optional HandlerSocket plugin (a SECOND listener port giving direct
  key/value index access, bypassing the SQL parser) does
  `fldnum = read_field_count_from_request(); flds = alloca(fldnum * sizeof(string_ref));`
  then loops `flds[i] = string_ref(field_pointer, field_length);` — the check
  `fldnum <= index->field_count` runs only AFTERWARDS, so `fldnum=1000000000` sizes a
  ~16 GB stack frame and `mariadbd` SIGSEGVs on the first write (container exit 139).
  Rules: (a) the bug is the ORDER, not a missing check — grep every
  `alloca(<client> * sizeof(...))` / `malloc(count*size)` / `new T[client_count]` /
  `memcpy(dst, src, client_len)` where the count/len comes straight from the request
  and ask "does the bound check appear BEFORE the allocation on the same path?" (the
  check EXISTS, just too late — that is why review misses it); (b) `alloca`/VLA sized
  by input cannot fail gracefully (stack guard page → SIGSEGV, no NULL to test) —
  treat any input-sized stack allocation as unconditional severity; (c) an optional
  plugin's OWN listener/protocol (binary protocol, KV layer, admin port) is a SEPARATE
  attack surface from the main service — "the normal SQL port is not affected" means
  you must fuzz each plugin's request parser independently; (d) auth precondition
  shapes the score honestly (no `handlersocket_plain_secret` → unauthenticated, PR:N,
  CVSS 7.5), and the reporter BOUNDED the claim ("only proves DoS, not code execution
  or data theft") which is why it closed Resolved — a crash report that resists
  inflating itself to RCE survives triage; (e) evidence kit = from-source container
  pinned to an exact commit, container exit 139 as the crash, the port UNREACHABLE
  after the trigger as the observable, `date -R` for the timeline.
- **ESCAPE-THEN-DECODE IS NOT A BARRIER: a producer `escape()`s a value and the very
  next step `decode()`s the same string — IDENTITY for every character the escape set
  preserves** (curl FTP wildcard #4057637, High-titled / Resolution: Informative,
  0 votes, disclosed 2026-09-26). In `lib/ftp.c:4079-4095` each server LIST filename is
  `curl_easy_escape(NULL, finfo->filename, 0)`-ed and appended to the wildcard path;
  `curl_easy_escape()` keeps RFC-3986 unreserved `A-Za-z0-9-._~`, so `.` survives
  literally — `../etc/passwd` → `..%2Fetc%2Fpasswd` (only `/` encoded) — and the
  immediately-following `Curl_urldecode(ftp->path, …)` reverses it straight back to
  `../etc/passwd`, with `REJECT_CTRL` filtering CONTROL characters only (no `..`
  filtering, no normalisation) before the decoded path drives CWD/RETR. Rules: (a)
  follow every encode/escape call to its consumer — an `escape`/`urlencode`/
  `htmlspecialchars`/`quote` immediately followed by a `decode`/`unescape`/`base64_decode`
  on the SAME value is a no-op wrapper; the only question is which characters the encode
  set PRESERVES (`%2F` decodes back to `/`, so an encoder leaving `.` literal cannot stop
  `../`); (b) a CHARACTER-CLASS filter is not a SEMANTIC check — `REJECT_CTRL` answers
  "is this byte a control char?", never "does this path escape its root?"; boundary
  validation for paths must be semantic and applied to the DECODED value (reject `..`
  components, reject absolute leading `/`, canonicalise then confirm still under the
  intended root); (c) sibling of the delimiter/re-serializer class (Lesson 45): there the
  re-serializer SHORTENED a fence, here it UNDID an escape — whenever safety rests on a
  transformation, the bug is in whatever reverses or rewrites it; (d) grade the trust
  boundary + opt-in honestly — attacker is a hostile/MITM'd FTP *server* AND the victim
  app must set `CURLOPT_WILDCARDMATCH` (default paths unaffected), so a High-titled
  traversal closes Informative: attacker preconditions and opt-in features cap severity;
  (e) fix at BOTH ends (reject `/`, `..`, absolute leading `/` before escaping; validate
  the decoded path after).

## Corroborating cases (severity/blast-radius calibration)

- #3489490 Nextcloud User OIDC, ID4me missing JWT signature verification — High,
  CVSS 8.1, $2,500, CVE-2026-45156.
- #3800870 8x8 JWT algorithm confusion — paid despite honestly read-only impact;
  the write-up scoped blast-radius explicitly rather than over-claiming.
- #3622877 Cloudflare h2c upgrade tunneling — corrected class, still paid.
- #3320669 PlayStation "Double fdrop on a socket through sys_netcontrol" — High,
  $10,000, 90 votes, disclosed 2026-05-01. Double-free via recycled-fd lookup key.
- #3908943 MariaDB "DROP PACKAGE leaves PACKAGE BODY grant in mysql.procs_priv"
  — High CVSS 8.0, no bounty (VDP), disclosed 2026-10-07. Orphaned-grant privilege
  retention; model VDP writeup craft.
- #3452696 PlayStation "PS4 BD-J privilege escalation using nested JAR" — Medium,
  $2,500, 43 votes, disclosed 2026-04-29. Canonicalize-vs-literal path differential
  + `isSigned()` range as an attacker-controlled verification off-switch; Medium
  despite AllPermission because it needs physical disc media.
- #3608199 Basecamp "DOM XSS in fizzy.do import filename preview enables one-click
  victim account takeover" — High CVSS 8.0, $500, 60 votes, disclosed 2026-04-14.
  Filename→`innerHTML` sink inside an authenticated form = request gadget; 60 votes
  on a $500 High (built chain beats scary label).
- #3893632 WordPress Secure Custom Fields — unauthenticated disclosure of draft/
  private/pending post titles+IDs via nopriv AJAX query handlers; Medium CVSS 5.3,
  5 votes, Resolved, disclosed 2026-09-28. Nonce-on-an-anonymous-page is not an
  authz control (logged-out WP nonces are shared across all anon visitors, uid 0).
- #3623149 Nextcloud — SSRF via user-controlled Push `proxyServer`; Medium CVSS 5.4,
  3 votes, Resolved, disclosed 2026-09-30. Stored/deferred SSRF: registration 201 is
  not the vuln — trigger the sink and show the internal request in the target's log.
- #4053546 WordPress "Information Disclosure - Unauthen Leak Private Content"
  (bbPress ↔ BuddyPress) — Medium, no bounty, 1 vote, Resolution: Resolved,
  disclosed 2026-10-10 (freshest row on the archive; +1 advance since Run 17).
  Ancestor-status blindness: `bbp_is_forum_public($forum_id, false)` skips the parent
  walk, so a private parent's public subforum leaks topics into the public Activity
  stream while the permalink 404s.
- #3734676 Mozilla Taskcluster "OAuth2 authorization codes are reusable and the
  exchange handler checks the wrong expiry column" — Medium, $2,000, 12 votes,
  disclosed 2026-06-23. Two bugs in one handler (no single-use consumption; wrong
  `expires` column) recurring at a sibling handler; PoC as an upstream Mocha test.
- #4063328 curl "`--hsts` is ignored for a schemeless URL starting with a scheme-
  like token" — Low, no bounty, disclosed 2026-10-08. Freshest row on the archive
  when Run 16 executed; held over (thin, Low) — listed for completeness, NOT yet
  mined.
- #3915935 MariaDB "Heap Use-After-Free in Materialized_cursor::open via
  SYS_REFCURSOR Array Reallocation" — High CVSS 8.8, no bounty, 2 votes, Resolved,
  disclosed 2026-10-07. Dangling member address into a growable Dynamic_array
  reallocated during a nested procedure call; "NOT fixed by MDEV-40396" = fix-scope
  audit (that fix removed a stale member, not the call-site parameters).
- #3599383 Nextcloud Deck "Arbitrary Board Preference Injection via Deck Config
  API" — Medium CVSS 4.3, CVE-2026-77170, $200, 28 votes, Resolved, disclosed
  2026-09-17. Object id embedded in a config KEY (`board:<id>:<key>`) written with
  no per-object authz; evidence = curl + a `SELECT` on `oc_preferences`.
- #3867363 MariaDB "HandlerSocket Improper Request Field-Count Validation Causes
  Server Crash" — Medium per archive / CWE-400, reporter CVSS 7.5, Resolved, 1 vote,
  disclosed 2026-10-07. MINED Run 21: allocate-before-validate order (see class entry
  above). Unauth when no HandlerSocket secret; claim bounded to DoS.
- #4057637 curl "[HIGH] CWE-22 Path Traversal in FTP Wildcard Download via Unencoded
  `.` in Escaped Filenames" — High title but Resolution: Informative, 0 votes,
  disclosed 2026-09-26. MINED Run 21: escape-then-decode round trip is not a barrier
  (see class entry above); opt-in `CURLOPT_WILDCARDMATCH` + hostile server caps severity.
- HELD OVER, not yet mined (verified un-mined, Run 21 — re-fetch the archive before
  Run 22 to check for advancement): #3867358 MariaDB "Low-Privilege User Can Exhaust
  Memory Through a Formatting…" (Medium, 1 vote, 2026-10-07) = next crisp
  resource-exhaustion row; the MariaDB cluster #3880451 "Privilege escalation via user
  controlled usernames / roles…" (2 votes, 2026-10-07) and #3849025 "DATA / INDEX
  DIRECTORY Abuse" (2 votes, 2026-10-07); fix-scope-audit candidates #2814774 Rails
  "Possible DoS in NumberHelpers" (Medium, 1 vote, 2026-10-06) and #4071872 curl
  "Secure=1 cookie flag bypasses the 8.22.0 fix…" (Low, 1 vote, 2026-10-06).


## Classes added — Run 22 (2026-10-11)

- **Uncontrolled recursion / stack-exhaustion DoS: a PROJECT-WIDE guard used everywhere EXCEPT one parser** *(Run 22)* — the canonical recursion guard (`check_stack_overrun`) is called throughout the codebase (`item.cc`, `item_func.cc`, `item_cmpfunc.cc`, `item_subselect.cc`, `item_jsonfunc.cc`, `json_table.cc`, `json_schema.cc`, …) but `grep -rn check_stack_overrun sql/spatial.cc sql/spatial.h sql/item_geofunc.cc` returns **ZERO hits**; the asymmetric ABSENCE of a control the codebase itself treats as mandatory IS the finding, and the negative grep is the proof. A recursive descent over attacker-controlled nesting (`Gis_geometry_collection::init_from_wkb`, spatial.cc:4414 recursing :4447; `::get_data_size`, :4284) with no depth cap consumes one stack frame per level → SIGSEGV that kills the whole server (default `thread_stack` ~292 KB → a few thousand levels). One missing guard sits behind MULTIPLE sibling front-ends — enumerate all: WKB (`create_from_wkb` / `ST_GeomFromWKB`), WKT text (`create_from_wkt` spatial.cc:4342 / `ST_GeomFromText`), GeoJSON (`init_from_json` spatial.cc:767 / `ST_GeomFromGeoJSON`), and the STORED-VALUE path (`Field_geom::store` → `is_binary_valid()` → `get_data_size()`, i.e. INSERT/UPDATE of a crafted value into a GEOMETRY column). Evidence = a DEPTH DIFFERENTIAL (K=50 alive vs K=120000 → sig 139, two independent runs) not a malformed byte; and ASan prints NOTHING on a stack-exhaustion crash (the stack is gone before the handler runs) — the bare `sig=139` IS the signature, do not read "no ASan output" as "no bug". Corroborated by **#3896507** MariaDB WKB GEOMETRYCOLLECTION parser (Medium, Resolved, 2 votes, disclosed 2026-10-11 — freshest row on the archive; low-priv, CVSS 3.1 ≈ 6.5, RCE=No). This is the guarded-vs-unguarded tell (L33 / L47c) applied to a RECURSION guard.
- **A "safe" markdown renderer is an injection sink: the sanitizer guards the TEXT and forgets the link/image TARGET** *(Run 22)* — a renderer that escapes the visible text still emits `<a href>` / `<img src>` from the TARGET, so `![alt](javascript:…)` (or a link target with a `javascript:` URL) survives unless the URL SCHEME is allow-listed (`http`/`https`/`mailto`); `data:`, `vbscript:`, `file:` likewise. And a "reflected" XSS can be a STORED delivery when a token-less cross-site POST writes the content (a `greeting`/banner/welcome/message field) that the NEXT page load renders. Audit every markdown→HTML sink (chat bots, receipts, e-mail/PDF templates, comment/README renderers) for scheme validation on the TARGET, and treat an AI/chatbot greeting surface as a first-class injection surface. Grade by the IMPACT CHAIN, not the user gesture — a `target=_blank` link that needs a click still paid. Corroborated by **#2509022** Shopify Help-Center AI assistant (Medium CVSS 4.2, $1,600, 24 votes, Resolved, disclosed 2026-06-18): a token-less CSRF `POST /en/search` stores a markdown-image greeting whose target is `javascript:eval(atob(...))`; the victim's click executes JS in the authenticated origin, exfiltrating `window.__remixContext.state.loaderData.root.userInfo` (PII) and issuing a GraphQL `subscriberCreate` mutation that injects the attacker's e-mail into the victim's last support conversation.
- HELD OVER, not yet mined (archive advanced **708 → 711**, newest 2026-10-11; verified un-mined Run 22): **#3423013** LY Corporation "page.line.me Open Redirect Leading to OAuth Authorization Code Exposure and Access Token Compromise" (High CVSS 7.1, $1,000, 4 votes, 2026-06-02; archive body thin — "No vulnerability information available", only the program summary — queue as an open-redirect→OAuth-code class stub), **#3400140** Discourse drafts-creation DoS (High CVSS 7.5, $1,024, 14 votes, 2026-06-30), **#3837634** 8x8 JaaS SIP Gateway authz bypass (Medium CVSS 5.8, $500, 2026-08-12), **#3878586** Liberapay unauth income/payments export (Medium CVSS 5.3, $100, 2026-08-01); plus the Run-21 carry-over **#3867358** MariaDB memory-exhaustion-via-formatting (Medium, 1 vote, 2026-10-07), MariaDB **#3880451** (priv-esc via user-controlled usernames/roles, 2 votes) and **#3849025** (DATA/INDEX DIRECTORY abuse, 2 votes), and fix-scope-audit candidates **#2814774** Rails NumberHelpers DoS (Medium, 1 vote) and **#4071872** curl Secure=1 cookie-flag bypass (Low, 1 vote).
- _Path note (Run 22): the CANONICAL bank lives here — `<skill_dir>/references/disclosed-report-patterns.md` (skill-scoped, NOT under `openamer-product/`). The `bounty-factory/references/disclosed-report-patterns.md` created in Run 21 is a STRAY DUPLICATE; it now holds only a pointer to this file._


## Classes added — Run 23 (2026-10-12)

- **A privacy/consent gate re-implemented per SURFACE drifts; the endpoint that reads a FROZEN snapshot column ignores later revocation** *(Run 23)* — find the ONE place the app applies the whole privacy predicate (Liberapay's profile page `index.html.spt`: recipient opt-in `patron_visibilities & 4`, `tip.visibility = 3`, `NOT tipper_p.hide_giving`, `tipper_p.hide_from_lists = 0`, all read from `current_tips`), list every conjunct, then diff every OTHER surface emitting the same rows. The export `income/payments.spt` omitted `hide_giving` + `hide_from_lists` + the recipient gate and read the FROZEN `payin_transfers.visibility` (set once at `payin/common.py:752` `abs(visibility)`, never updated — no `UPDATE` touches that column) instead of the live `current_tips.visibility`, so the unauthenticated `.json`/`.csv` disclose donor name + amount + date for opted-out and since-revoked donations. This is the L33/L51 guarded-vs-unguarded tell applied to a PRIVACY predicate. Rules: snapshot-vs-live consent (a copied visibility flag read by an immutable ledger row silently ignores the later change); public exports (`.json`/`.csv`) emit raw rows the UI filters so any template-only gate is absent there, and CSV often has no pagination cap; lead the impact with the DOWNGRADE (donation explicitly marked secret, still shown) over the opt-out; evidence = a no-Cookie request + a response showing both the disclosed AND the `null` fields (proving the sole gate is `pt.visibility = 3`) + the profile-page differential. Corroborated by **#3878586** Liberapay unauth income/payments export (Medium CVSS 5.3, $100, 12 votes, Resolved, disclosed 2026-08-01).
- **A size check enforced on the MESSAGE path but not its DRAFT sibling, plus a 5xx that still COMMITS, is a one-endpoint resource-exhaustion primitive** *(Run 23)* — a size/`max_length` limit on `create_post` is worthless if `create_draft` (or preview/autosave/import/template) writes the same content field without it. Prove the asymmetry with a two-path differential ("payload rejected as a message, accepted as a draft"), not by asserting the limit is missing. And a 5xx that persists a row is a write-bypass signal: the error comes from a DIFFERENT component (gateway/proxy/timeout) than the one that commits, so verify persistence with an independent GET and never equate "returned an error" with "did nothing". Grade honestly: authenticated resource-consumption (CWE-400), C:N/I:N -> CVSS 3.1 `AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H` = 7.5; High is earned by the AMPLIFICATION (a few cheap requests -> 32 s cross-user latency) + the automation caveat, not a single request. Corroborated by **#3400140** Discourse `POST /drafts.json` (~800k-char drafts, 502-but-saved, 32.108 s latency, High CVSS 7.5, $1,024, 14 votes, Resolved, disclosed 2026-06-30).
- HELD OVER, not yet mined (archive static at **711 rows**, newest 2026-10-11; verified un-mined Run 23): **#3423013** LY Corporation page.line.me open-redirect->OAuth-code (High CVSS 7.1, $1,000, 4 votes, 2026-06-02; archive body thin — "No vulnerability information available"), **#3837634** 8x8 JaaS SIP Gateway authz bypass (Medium CVSS 5.8, $500, 2026-08-12); plus Run-21 carry-over **#3867358** MariaDB memory-exhaustion-via-formatting (Medium, 1 vote, 2026-10-07), MariaDB **#3880451** (priv-esc via user-controlled usernames/roles, 2 votes) and **#3849025** (DATA/INDEX DIRECTORY abuse, 2 votes), and fix-scope-audit candidates **#2814774** Rails NumberHelpers DoS (Medium, 1 vote) and **#4071872** curl Secure=1 cookie-flag bypass (Low, 1 vote).
- **Covered-set caveat (Run 23):** the `#?[0-9]{6,8}` grep over `lessons.md` + this bank returns an UPPER bound on mined ids, because QUEUED/held-over mentions land in the same set (e.g. #3400140 and #3878586 were named in Run 22's queue prose yet were un-mined until Run 23). When the top of the index looks fully mined, read each id hit's sentence — "mined" and "mentioned as queued" are indistinguishable to the grep and mean opposite things.

_Last extended: Run 23, 2026-10-12._

## Classes added — Run 24 (2026-10-12)

- **An "unguessable" identifier is NOT an authorization control: a destructive endpoint gated only on possession of a long random id is an IDOR whose sole barrier is the id's ENTROPY** *(Run 24)* — grep every state-changing verb (`remove`/`delete`/`revoke`/`unlink`/`disable`) for its object-lookup predicate: `WHERE id = ?` with no `AND user_id = ?` (or owner join) means the *id* is the control. A "long random string" is a bearer-capability, not an authz check — say so, because the entropy is what caps the grade. Grade honestly and lead with the LIMIT (here the attacker cannot authenticate as the victim, so it is a 2FA DOWNGRADE, integrity-only: CVSS 3.1 `AV:N/AC:H/PR:L/UI:N/S:U/C:N/I:L/A:N` = 3.1; NVD 4.3 with `UI:R`) — *not* account takeover. Prove the missing owner check by a DIFFERENTIAL (same device id deletes from a DIFFERENT user's session) — no payload, only a second account; the absence of the cross-user guard IS the finding. Fix = bind the object to the CALLER, not to lengthen the id. Also: when an H1 body links only a GHSA/advisory, recover the mechanism from the **NVD API** (`services.nvd.nist.gov/rest/json/cves/2.0?cveId=<CVE>`). Corroborated by **#3360354** Nextcloud `twofactor_webauthn` (CVE-2025-66558, fixed 1.4.2/2.4.1, Low CVSS 3.1, $750, 81 votes, disclosed 2026-02-06).
- **A credential injector ON BY DEFAULT turns every server-controlled URL into a credential sink; the guard is an explicit per-call OPT-OUT, so the bug is the SET of call sites that omit it** *(Run 24)* — find the guard that is an opt-out flag/attribute/overload the caller must remember (its default state is "insecure"), grep the injector for that check, then grep which call sites SET it: the set-difference is the attack surface. Trace provenance — is the URL/method/host attacker-controlled? In a sync/download client the SERVER (and any mirror/CDN) is untrusted for URL *origin*. A same-origin / subdomain / external LADDER ("same path = acceptable, CDN subdomain = questionable, external = dangerous") converts "no validation" into a precise severity argument, and the fix is an origin comparison using the mechanism the code ALREADY has but never applies on this path. PoC = a two-process local harness (fake sync server advertising a malicious `<oc:downloadURL>` + a stealer listener printing the decoded `Authorization`), no live target needed. Same family as the guarded-vs-unguarded-sibling tell, with the twist that the guard EXISTS in the API but is unapplied. Corroborated by **#3400143** Nextcloud Desktop Client `directDownloadUrl` (`propagatedownload.cpp:727-738` omits `DontAddCredentialsAttribute`; Medium CVSS 4.2, $250, 36 votes, disclosed 2026-04-13).
- HELD OVER, not yet mined (archive static at **711 rows**, newest 2026-10-11; verified un-mined Run 24): **#3581911** Basecamp Trix-Editor v2.1.16 stored XSS "Sanitizer Bypass" (Low CVSS 3.0, $337, 6 votes, 2026-07-14 — RICH body, a *sanitizer↔serializer round-trip* class: a DOMPurify hook retains every `data-trix-*` attribute and the serializer `JSON.parse`s `data-trix-serialized-attributes` then `el.setAttribute(name, value)` with NO re-sanitize = a second, unsanitized parse of data the first pass allowed); **#3764217** Basecamp Android `StartActivity` exported with no `android:permission` (Medium CVSS 4.0, $287, 8 votes, 2026-07-04 — RICH body, *mobile exported-component* class: any co-installed zero-permission app forces logout + persistent DoS; `MainActivity.y()` `finish()`es the authenticated task; chained secondary via the unvalidated `launchDataUri` extra). Both are classes this bank LACKS (0 hits for `android`/`exported`/`manifest`/`DOMPurify`/`DontAddCredentials`). Also held: **#3423013** LY page.line.me open-redirect→OAuth-code (High CVSS 7.1, $1,000, 4 votes; body thin), **#3837634** 8x8 JaaS SIP Gateway authz bypass (Medium CVSS 5.8, $500, 10 votes; body thin — client-supplied JWT `sip-outbound-call` feature flag trusted without a server-side entitlement check), MariaDB **#3867358**/**#3880451**/**#3849025**, and fix-scope-audit candidates **#2814774** Rails NumberHelpers DoS and **#4071872** curl `Secure=1` cookie-flag bypass.

## Classes added  -  Run 25 (2026-10-12)

- **A visibility control enforced inside a QUERY filter is NOT inherited by a framework's auto-generated DIRECT-LOOKUP route; when the lock is on the parent and `publish` is on the child, the single-item fetch by primary key skips the filter** *(Run 25)*  -  when authorization lives in a query layer (`pre_get_posts`/scope/row-filter hook), enumerate every OTHER read path that fetches by ID directly (`get_post`/`find`/`get_by_pk`)  -  especially FRAMEWORK-GENERATED routes (`show_in_rest`, GraphQL node lookup, oEmbed, feeds). A permission callback keying on STATUS ALONE is blind when the restricted child inherits a public status while only its container is restricted. Prove members-only data with a FOUR-PATH CONTROL DIFFERENTIAL on the SAME anonymous client (single-item 200 vs collection filtered/empty vs front-end 404 vs own-endpoint 401)  -  three denials + one allow localize the gap to exactly that route. Sequential integer IDs make it a scalable harvest. A `show_in_rest`-style opt-in flip is a REGRESSION: diff released vs trunk and report pre-release. Fix = re-impose visibility via `rest_{post_type}_item_permissions_check` calling the plugin's own visibility check (or scope `show_in_rest` to capability), covering both collection and single-item. Corroborated by **#3801107** WordPress bbPress 2.7.0-trunk: `WP_REST_Posts_Controller::get_item()` resolves via `get_post($id)` (no `WP_Query`) so it never fires `bbp_pre_get_posts_normalize_forum_visibility()` (`src/includes/forums/functions.php:2329`); topics/replies are stored `publish` (`src/includes/topics/functions.php:33`) while only the forum is private/hidden; `check_read_permission()` returns true for `publish`, and `src/bbpress.php:548,578,608` set `show_in_rest => true` (2.6.x did not, so the released line is unaffected). Critical CVSS 9.3, no bounty, 3 votes, disclosed 2026-10-12.
- **A buffer sized from one server-declared value and read to a different server-reported value is an out-of-bounds read; the `MIN(reported, allocated)` clamp is the missing control, and an incomplete fix (`== 0` hardened, `> capacity` not) is the sibling-boundary omission that leaves the exploitable case open** *(Run 25)*  -  grep the sink for a server-controlled length used as the readable extent (`length_value`/`len`/`size`) without a clamp against the allocation size. Prove it by a DIFFERENTIAL with an honest-server NEGATIVE CONTROL differing in exactly one field: declared-length 4 + field-len 40000 â†’ ASAN `heap-buffer-overflow â€¦ READ of size 40000`; declared = field = 40000 â†’ `no crash, exit 0, zero ASAN errors`. Read the FIX BOUNDARY for the omitted case (`length_value == 0` hardened but not `length_value > buffer_length`). State the impact SPLIT honestly: info-leak (adjacent process heap copied into an app-visible column; on a connection-POOLED client that heap holds other requests'/users' data/credentials/pointers â†’ ASLR defeat) vs DoS (`length_value` up to 4 GB â†’ crash exit 134). A database CONNECTOR is a trust boundary  -  "requires a malicious or MITM server" is a real precondition to state, not a dismissal. Corroborated by **#3872248** MariaDB Connector/C++ 1.0.8-dev (`BinRowProtocolCapi.cpp:69` `new uint8_t[buffer_length]` sized from the declared column length vs `:107-108`/`:1716` reading `length_value`; libmariadb `ma_stmt_codec.c:599` copies `MIN(len, buffer_length)` but reports the uncapped `len`; reachable via `useServerPrepStmts=true` or any `prepareCall(...)`  -  `MariaDbProcedureStatement.cpp:59,83`), Medium CVSS 4.6, 1 vote, disclosed 2026-10-12; same connector-trust family: **#3871977** Connector/ODBC malicious-server version-string size wrap (CVSS 4.6) and **#3871740** r2dbc-mariadb Parsec `1024 << iterations` server-controlled PBKDF2 CPU-exhaustion DoS (CVSS 5.7, regression `b7766de` loosened the cap `> 3` â†’ `> 20`).

## Classes added - Run 26 (2026-10-12)

- **A work-factor taken from the PEER and guarded only FROM ABOVE is unbounded when the cost is EXPONENTIAL in it: one attacker-chosen byte becomes ~10^9 rounds (CPU-exhaustion DoS)** *(Run 26)* - grep every client-side value sourced from the peer (server reply / URL / header) that becomes a loop count, an iteration count, or the EXPONENT of one; an `x > N` check is not a bound when the operation is `BASE << x` (`1024 << 20` = 1.07e9 PBKDF2 rounds ~ 25 CPU-min). This is the EXPONENTIAL-growth sibling of the integer/arithmetic class (Lessons 34/60): the direction AND the growth curve are the severity. A PRE-AUTH exchange is the sweet spot - the work runs before auth completes, so no credentials/prerogatives are needed, and defaults (plaintext, no plugin allow-list) widen the threat model from "rogue server" to "any MITM on the path". Prove by a DIFFERENTIAL SCALING MEASUREMENT, not one point: a rogue server that differs in exactly ONE byte (the work-factor) plus an old-cap negative control plus a table across exponents (`3/10/13/15` -> `231/1518/11745/45113 ms`) confirms the 2x-per-increment law and lets you extrapolate the cap - label the extrapolation as such. Check the cap's git HISTORY: a cap that WAS tight and was loosened is a REGRESSION (name the commit). Fix = restore the tight cap on the SMALL value. Corroborated by **#3871740** MariaDB r2dbc-mariadb 1.4.1: `iterations` is one byte read from the server's ext-salt reply, guarded only by `iterations > 20` (`ParsecPasswordPlugin.java:66,69`), then `1024 << iterations` in `PBEKeySpec` (`:104`); regression commit `b7766de` moved `> 3` -> `> 20`; Medium CVSS 5.7, 1 vote, disclosed 2026-10-12.

- **A printf-family truncation return is SIGNED and goes NEGATIVE; accumulated into a `size_t` it wraps to ~2^64 and moves a write offset BACKWARD by an attacker-chosen distance** *(Run 26)* - grep every `printf`/`snprintf`/`_snprintf`-family return value that is ACCUMULATED into a length/size/offset (`+=`, `len = fn(...)`); those returns are signed and go negative on truncation (and on output error), so adding one to an unsigned wraps to a huge value - use the ACTUAL written length or only add when `result > 0`. This is the signed/unsigned BOUNDARY flavour of the integer class (Lesson 34 was `len - 1` on a length; here the wrap source is a format helper's RETURN) and the INVERSE of the memory-safe narrowing cast (curl #4059104, Informative: the truncated length only got SMALLER): here it gets astronomically LARGER and the offset is WRITABLE. The attacker chooses the wrap DISTANCE via an INPUT'S LENGTH (`L > ~500` -> wrap to `2^64 - (L - 510)`), so the OOB offset is attacker-controlled and points BACKWARD - adjacent-heap corruption is plausible, not merely a crash; grade the DEMONSTRATED effect (crash = DoS) and name the potential separately. One unguarded accumulator -> grep every SIBLING caller of the truncating helper (Lessons 33/36). Proof craft: prove the input is reachable + UNCAPPED first, then an ASAN differential with an honest-length negative control differing in exactly ONE field, firing at statement allocation with no query. Corroborated by **#3871977** MariaDB Connector/ODBC: `_snprintf` returns `count - result - 1` (negative) on truncation (`driver/ma_platform_posix.cpp:41`) and is added to `size_t PrefixLen` (`driver/ma_c_stuff.h:70`) together with the server's uncapped handshake `server_version` (`driver/ma_error.cpp:165`); sinks `MA_ClearError` (`driver/ma_api_internal.cpp:58`) and `MADB_SetNativeError` (`driver/ma_error.cpp:231,235`); Medium CVSS 4.6, 1 vote, disclosed 2026-10-12.

## Classes added - Run 27 (2026-10-12)

- **A visibility/authorization filter hooked into the LISTING-QUERY path does NOT protect a READ-BY-PRIMARY-KEY endpoint** *(Run 27)* - when a plugin enforces access with a QUERY filter (`pre_get_posts` / `posts_where` / a `WP_Query` hook), the guard runs only when a QUERY builds the result set. A SINGLE-OBJECT read that resolves by primary key (core REST `get_item()` -> `get_post($id)`, `get_terms`, `/<ns>/v2/<type>/<id>`) never builds a `WP_Query`, so the filter is silently skipped and a generic permission check keyed on the object's OWN status (`publish` -> allow) passes. Object-level visibility in a query filter is NOT authorization. Durable move: grep every SINGLE-OBJECT read path and check whether the same guard runs there; a listing filter is bypassed by direct object access (the "collection is filtered, item is not" split). The tell is a SIBLING-SURFACE DIFF on the SAME request - enumerate every read path for the same object and diff the responses; the one path that returns data the others deny IS the finding (the guard-diff tell of Lessons 33/36 extended to DATA-READ surfaces). Prove the NEGATIVE on the guarded siblings to prove the POSITIVE on the leaking one. Watch STATUS INHERITANCE: children stored `publish` while only the CONTAINER carries the restricted status - the guard must walk UP to the ancestor restricted entity. Distinguish REGRESSION from design choice by diffing versions (a control that WAS absent and got introduced, like a loosened cap - Run 26 - is the same tell). Corroborated by **#3801107** WordPress bbPress 2.7.0: `show_in_rest => true` on forum/topic/reply (`src/bbpress.php:548,578,608`) exposes `/wp-json/wp/v2/topic|reply`; the only guard, `bbp_pre_get_posts_normalize_forum_visibility()` (`src/includes/forums/functions.php:2329`) hooked to `pre_get_posts`, is skipped because `WP_REST_Posts_Controller::get_item()` uses `get_post($id)`; an unauthenticated caller reads full members-only content by sequential-ID enumeration while the front-end (404), the REST collection (excluded) and the forum endpoint (401) all deny it; Critical CVSS 9.3, 3 votes, disclosed 2026-10-12.

- **A bounded copy followed by an UNBOUNDED write with the SAME original length: the clamp was applied to the `memcpy` but not to the terminator** *(Run 27)* - when a function clamps a length for ONE use (`memcpy(buf, p, MY_MIN(n, 31))`), grep EVERY other use of that SAME variable in the function (the terminator write, the index, the loop bound). A HALF-APPLIED guard is the bug: the developer hardened the sink they were thinking about (the copy) and left the adjacent write unclamped - the guard-its-sibling tell (Lessons 33/36) applied WITHIN a single function body. The unclamped length often arrives as a DECLARED WIDTH, not a buffer length - trace it from the user-facing DDL to the C sink (`DOUBLE(255,30)` -> field_length=255, `sql/field.cc` -> `ha_connect.cc` -> `reldef.cpp`/`colblk.cpp`/`tabdos.cpp` -> `DOSCOL::ReadColumn` passing `field` straight into the parser): the C layer treats an SQL column WIDTH as a buffer SIZE, and widths up to 255 are the reachable unclamped range. Grade honestly: a single NUL byte is a 1-byte stack corruption - memory-UNSAFE (contrast the memory-SAFE clamp/narrowing flavours, Lessons 34/36) - but the DEMONSTRATED effect gates the pay; name code-exec as potential-only. Proof craft: ASAN shows a 1-byte stack-buffer-overflow WRITE at the `buf[n] = '\0'` line, without ASAN the server crashes; state the input precondition (attacker supplies the file). Fix: clamp the terminator the same way as the copy. Corroborated by **#3910393** MariaDB CONNECT, CVE-2026-107815: `TYPVAL<double>::SetValue_char()` (`storage/connect/value.cpp`) copies `MY_MIN(n, 31)` into `char buf[64]` but writes `buf[n] = '\0'` with the raw SQL width -> `buf[255]` on a 64-byte buffer, a single-byte 0x00 write up to ~191 bytes past the end; DoS, no bounty listed, 2 votes, disclosed 2026-10-12.



## Classes added - Run 28 (2026-10-13)

- **A sanitizer hook that retains a whole attribute NAMESPACE (wildcard/prefix allowlist) + a serializer that RE-HYDRATES attributes from stored JSON = a two-pass pipeline with only the first pass filtered** *(Run 28)* - a `DOMPurify` hook that keeps every attribute matching a PREFIX regex (`/^data-trix-/`) hands the attacker a retained place to STORE unsanitized data, and a serializer that later rebuilds attributes from a JSON blob (`data-trix-serialized-attributes`) via `el.setAttribute(name, value)` with NO re-sanitization is a SECOND DOM write that never saw the filter. Durable move: (1) grep sanitizer configs for NAMESPACE allowlists (prefix/regex) - a whole retained namespace is writable storage; (2) COUNT THE PASSES whenever markup is sanitized on ingest and later rebuilt on export (serialize/deserialize pair, attribute-JSON restore, template re-render) - the rebuild is a fresh sink, so check whether it re-sanitizes; (3) the payload rides INSIDE a nested element's attribute (a benign-looking outer `data-trix-attachment` whose inner `content` carries the JSON), so a top-level scan misses it; (4) a bypass of TWO prior fixes is the incomplete-fix tell - name the prior reports. This is the sibling-surface tell (Lessons 33/36/57/61) applied to a data TRANSFORM rather than a route. Grade the trigger honestly (paste/DOM interaction = `UI:R`, hence Low) while noting the result is STORED and cross-user. Corroborated by **#3581911** Basecamp Trix 2.1.16: Low CVSS 3.0, $337, 6 votes, disclosed 2026-07-14, bypasses #2521419 (2.1.1) and #2819573 (2.1.8); fix = explicit allowlist, re-sanitize on deserialize, deny `on*`.

- **An exported component with NO permission guard is the mobile equivalent of an unauthenticated endpoint; if it re-runs the app's startup/auth-boot sequence, a zero-permission co-installed app force-logs-out on demand** *(Run 28)* - `android:exported="true"` with no `android:permission` AND no intent-filter means ANY installed app can fire an explicit `Intent` at it (an explicit intent needs no filter to match). If the activity's `onCreate`/`onResume` runs an AUTH-BOOT sequence, an outside caller re-triggers it, and `finish()` on the authenticated task discards the session; `android:launchMode="singleInstance"` makes it worse (owns its own task -> external intent arrives via `onNewIntent()` which re-runs startup regardless of a valid session) AND makes it loopable for a persistent DoS. Durable move: grep the manifest for `exported="true"` and check each for a `android:permission` guard and an intent-filter ("no intent-filter" is NOT a mitigation, it is what makes it trivially addressable); watch the STATE MACHINE, not just the component (a boot activity must be re-entrancy/session aware); follow every extra into navigation for a SECOND potential impact (`launchDataUri` forwarded unvalidated -> forced navigation). Same guarded-vs-unguarded-sibling tell (Lessons 33/36) one platform over. Grade honestly - forced logout + DoS, no read, no ATO = Medium CVSS 4.0; lead with the LIMIT. Proof = an `adb shell am start -n <pkg>/<activity>` one-liner PLUS a minimal manifest with NO `<uses-permission>` (the realism argument in one artifact) + before/after screenshots. Corroborated by **#3764217** Basecamp Android `com.basecamp.bc4.app.main.start.StartActivity`: Medium CVSS 4.0, $287, 8 votes, disclosed 2026-07-04; fix = `exported="false"` or a signature-level permission, plus session-preserving `onNewIntent()`.

## Classes added - Run 29 (2026-10-13)

**Delimiter-carrying value in a raw-text record (field injection into a serialized options blob).** When a multi-field record is stored as RAW TEXT of `key=value` pairs (definer strings / `FILE_OPTIONS_STRING`, ACL and role serializations, option blobs), any field whose VALUE can contain the record's own delimiter (newline, `=`, `;`, `\0`) can inject SIBLING keys at write time. Tell: validate the *field value's* encoding at the SERIALIZATION boundary, not merely the object name's validity. If the object is definer-bearing (VIEW / PROCEDURE / FUNCTION / `DEFINER=CURRENT_ROLE`), the injected `suid`/`definer_host` fields cross a PRIVILEGE boundary - prove it by the denied-vs-allowed differential on the same client (base table `ERROR 1142` vs the definer's rows through the view). Enumerate every definer-bearing object form. Scope honestly: needs control of the provisioned username/role. Corroborated by **#3880451** MariaDB "Privilege escalation via user controlled usernames / roles and views": Severity None, 2 votes, disclosed 2026-10-07; a name `root\ndefiner_host=localhost\nsuid=1` injects `suid=1` into the raw definer string. Fix = encode/escape the name when writing `FILE_OPTIONS_STRING`.

**Guard whose path-canonicaliser FALLS BACK on failure (the degraded return is the bypass).** When a security check decides on a path resolved by `realpath()`/`getCanonicalPath()`/`normpath()`, READ THE FUNCTION'S ERROR BRANCH: a canonicaliser that silently degrades to a weaker normaliser when resolution fails turns "invalid path -> reject" into "invalid path -> allow". Precondition: include a NON-EXISTENT path segment so `realpath()` returns NULL and the fallback runs. Diff the sanitised builder against its UNSANITISED sibling (the guarded-vs-unguarded tell on filename construction); a no-`FILE`-privilege user may still place files outside the data dir if the external-directory path skips the sanitiser. Corroborated by **#3849025** MariaDB "DATA / INDEX DIRECTORY Abuse" (CVE-2026-102523): Severity None, 2 votes, disclosed 2026-10-07; `append_file_to_dir()` appends the RAW table name with no `tablename_to_filename()`, and `my_realpath()`->`my_load_path()` fallback when `realpath()` fails defeats `error_if_data_home_dir()`. Sibling of the canonicalize-vs-literal class above (check the DEGRADED return, not just the happy path).

## Classes added - Run 30 (2026-10-13)

- **A resource guard that bounds the WRONG resource + an input limit whose ACCEPTED BOUNDARY is already fatal + a size-reducer that does not short-circuit the allocation** *(Run 30)* - three tells that together turn a "guarded" formatting parameter into a ~2 GB allocation. (1) Locate the size limit and ask WHICH resource it bounds and WHERE it runs relative to the allocation: `max_allowed_packet` is a WIRE limit checked at result serialisation, long after the server materialised the value in memory - a packet/response cap is not a memory cap. (2) Read the CONSTANT of the range check: a parser that rejects width `> 2147483647` but ACCEPTS `2147483647` sets its cap at INT32_MAX, i.e. at exactly the payload - ~2 GB; a cap must be chosen against the RESOURCE BUDGET, never the integer type's maximum. (3) A reducing wrapper (`LENGTH(f(x))`, `SUBSTR`, `LEFT`, `COUNT`) still EVALUATES `f(x)` in full before inspecting it - evaluation order means a wrapper that only needs the SIZE never avoids building the VALUE; grep the implementation for materialise-then-measure. Sibling of the ALLOCATE-BEFORE-VALIDATE class (HandlerSocket #3867363, "guard after the allocation"); contrast the EXPONENTIAL work-factor sibling (#3871740, L59) - here the amplification is LINEAR in one field. The precondition list is part of the report (low-priv authenticated TCP, no special rights, memory headroom), and the claim is bounded to DoS. Corroborated by **#3867358** MariaDB `SFORMAT()`: `SELECT LENGTH(SFORMAT('{:2147483647}', 'x'));` -> the full ~2 GB string is built before `LENGTH` measures it; Medium CVSS 6.5, CWE-789, no bounty, 1 vote, disclosed 2026-10-07; fix = cap the width against memory, not the type maximum.

- **A permission check that lives ONLY in the client is not a check: the server endpoint behind the hidden control has an AUTHENTICATION gate but no AUTHORIZATION gate** *(Run 30)* - when the frontend contains an explicit role/permission predicate (`canPin`, `isAllowed`, `hasPermission`, `user.role === 'admin'`, `if (!user.isStaff) return null`) it MAPS where the SERVER must have the same check: grep the handler that the button calls and its ABSENCE IS the finding (the guarded-vs-unguarded-sibling tell across the CLIENT/SERVER boundary - the client is guarded, the server is not). Hiding a control is not access control: enumerate the request the hidden control WOULD send and replay it from a low-privilege session. `@login_required` is authentication, not authorization - a handler whose only guard is a login decorator plus a bare object lookup (`get_object_or_404(Comment, id=...)`) with no ownership/role join is the classic broken-access-control shape; prove it by replaying against a FOREIGN object id (success on the foreign id is the proof). Report craft that earns votes on a Low: frontend guard file:line + backend handler file:line showing the missing check + the raw copy-pasteable request (two-account flow) + the `200 OK` and the before/after state. Grade by DEMONSTRATED radius (integrity-only write on another user's object -> Low; do not inflate). Corroborated by **#3025797** Mozilla Pontoon: `canPin` gates the Pin/Unpin button (`translate/src/modules/comments/components/Comment.tsx`) while `pin_comment`/`unpin_comment` (`pontoon/base/views.py`) check nothing but login -> any user pins/unpins any comment on any project or locale; Low, no bounty, 56 votes, disclosed 2026-03-20; fix = enforce the Project-Manager check server-side.

## Classes added - Run 31 (2026-10-13)

- **A hidden control is not a permission check, and when the gate is a PAID TIER the same tell becomes a REVENUE bug: the state-changing endpoint behind the premium-only setting writes it for anyone authenticated** *(Run 31)* - the client-only-permission-check tell (Run 30, #3025797) applied to a SUBSCRIPTION boundary instead of a ROLE boundary. The frontend predicate encodes the privilege (`isPremium`, `user.plan === 'pro'`, `isStaff`), so grep the endpoint the hidden control WOULD call and the ABSENCE of a server-side entitlement check IS the finding; the guarded-vs-unguarded-sibling diff works across the free/paid line exactly as across the user/staff line. Two traps that make this class under-graded: (a) **a SELF-SCOPED write is not automatically harmless** - the attacker mutates only their own setting, so the "is someone else's data exposed?" reflex calls it a non-issue, yet here the setting IS the paid feature (revenue + devaluation of the plan; the honest impact is a counterfactual: non-premium users x lost ad impressions x the plan price they no longer need to pay), grade High on business logic while stating plainly there is NO cross-user data access; (b) **`Content-Type` is not validated** on this endpoint - a server that never modelled its request shape also never modelled the AUTHORIZATION on that shape, so a missing content-type check is a hint to look harder at who may call it. Enumerate every boolean/enum in a user-settings payload and ask of each: does this correspond to a paid tier or a privileged role, and where is that predicate enforced (READ-side gating is common; the WRITE that turns the feature off for free is forgotten)? Watch the LOCALE/SIBLING axis too: a feature can be gated in one site variant and not its sibling (pixiv's `/en` host was fine, the Japanese host was not - scope the asset precisely). Corroborated by **#3183520** pixiv `dic.pixiv.net`: `POST /_api/update_user_setting` `{"setting":{"showAds":false,"showNewUI":true}}` returns `{"success":true}` for any authenticated non-premium user, flipping "Do not display ads" with no premium check; High, $3,000, 72 votes, disclosed 2026-04-27, Resolved. Report craft that earns votes: raw copy-pasteable POST + exact JSON body, the unvalidated-Content-Type note, a UI before/after screenshot, one plain revenue/devaluation impact sentence; add the CVSS vector and the explicit precondition line ("any authenticated user, non-premium, no special rights") that this writeup lacked.

- **A numeric input validator that accepts the LANGUAGE's exponent/compact notation turns a 16-character string into a bignum with hundreds of trillions of digits: the parse is cheap, the FORMAT is the bomb** *(Run 31)* - grep the accepted numeric GRAMMAR of every string-to-number coercion: Ruby `BigDecimal`/`Integer`/`Float` accept `11288E822222`/`1e9`, Python `Decimal`/`float` accept `1e999999` and `int("1"*10**6)` is the classic, some JSON parsers accept exponents. A validator that only rejects non-numeric CHARACTERS still accepts a 16-char exponential literal whose VALUE is astronomically wide. The cost is in the OPERATION AFTER the parse (format / compare / serialise / render), so a parse-boundary guard must bound the RESULT (mantissa digits x exponent magnitude) and never the input LENGTH (the input is 16 bytes) - the "guard bounds the wrong resource" tell (Run 30) with the input itself as the amplifier. The FIX is the tell: switching to a "contains `e`/`d` -> not numeric" WHITELIST rather than a digit-count or magnitude cap confirms the intended grammar was plain decimal and that exponent notation was the smuggled channel. This is the THIRD amplification family the bank now holds, and they must be told apart: LINEAR over-allocation (#3867358 `SFORMAT` width, L68), EXPONENTIAL peer-work-factor (`1024 << iterations`, #3871740, L59), and this one - amplification inherited from the NUMBER SYSTEM's own decimal exponent, no shift the code chose. Reachability: if the helper runs on unauthenticated input (a public currency/percentage formatter) it is a PRE-AUTH DoS. Proof craft: minimal repro (`BigDecimal("11288E822222")` plus the exact helper call plus the observed OOM/timeout), amplification stated as "16 input bytes -> >10^14-digit BigInt", precondition named. Corroborated by **#2814774** Ruby on Rails Active Support number helpers, CVE-2026-33176 (fixed 7.2.3.1 / 8.0.4.1 / 8.1.2.1): `BigDecimal("11288E822220222")` -> a number with hundreds of trillions of digits -> `number_to_currency`/`number_to_percentage` exhausts memory/CPU from a single request; Medium, no bounty, 1 vote, disclosed 2026-10-06, Resolved (the writeup asserted "can be taken down" without a measured time/memory table - measure it).

_Last extended: Run 31, 2026-10-13._
