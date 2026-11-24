# Classes 26–27: status banners and release-note chains (live 17.09.26)

Two leaks, one per source, both found by running real `--once` cycles and
reading the LAST buffer row. Neither appeared in `buffer_junk.jsonl` (both
passed both gates).

Root cause for both is the documented **number-fed hole**: `_TECH_HINT_RE`'s
alternation starts with `\d+`, so a date/time stamp (`Sep 18, 2026 19:00 PDT`)
or a version stamp (`[12/2025]`, `v1.2.0`) counts as "technical signal", and the
row's length then clears the ≥90 "long prose" trust.

---

## Class 26 — service-status / maintenance BANNER

### The leak (verbatim, as stored)

```
Login This service will be unavailable from Sep 18, 2026 19:00 PDT to
Sep 19, 2026 2:00 PDT due to maintenance.
```

`cycle_b_papers`, stored under `u = "Latest research insight: Adaptive LLM
routing under budget constraints"`. An arXiv status page. Zero insight.

### Guard

`_is_maintenance_banner(text, head_max=40, tail_max=40)` in both
`internet_learner.py` and `buffer_store.py`:

```
M1  _MAINT_WINDOW_RE : two absolute datetime stamps, each with a timezone,
                       joined by `to` / en-dash / em-dash / hyphen
M2  _MAINT_VOICE_RE  : `\bthis service\b` | `\bdue to maintenance\b` |
                       `\bfor maintenance\b` | `^\s*login\b`
AND head = len(text[:min(start)]) stripped of edge punctuation <= 40
AND tail = len(text[max(end):]) stripped of edge punctuation <= 40
```

`_MAINT_STAMP = [A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}[ ,]+\d{1,2}:\d{2}\s*(?:[APap][Mm]\s*)?[A-Z]{2,4}\b`

### Measurement rounds (what was tried and why each earlier form lost)

| Round | Candidate | Result |
|---|---|---|
| 1 | `will be unavailable from`, `due to maintenance`, `this service will be unavailable` as bare phrases | each hit real downtime prose (H1 "…for four hours, so the retriever queues requests…", H9 "Login flows that fail…") |
| 2 | M1 alone (`unavailable\|downtime\|outage` + one dated TZ stamp) | 0 buffer FP **but 4 hard-prose FPs** → REJECT |
| 2 | M1 + `due to maintenance` | leak only, but the same phrase alone also hit prose → still risky |
| 4 | M1 AND M2 (no position condition) | leak caught, **1 prose FP**: the meta sentence that QUOTES the banner form |
| 5 | M1 AND M2 AND `head≤40 && tail≤40` | **leak caught, 0 bufFP, 0 prose FP** |

The head/tail sweep that picked 40/40 — measured, not chosen by taste:

```
head<=40 tail<=40 : leak=True corpus_hits=1 bufFP=0 proseFP=none
head<=30 tail<=55 : leak=True ... proseFP=['H13 apology tail']
head<=40 tail<=60 : leak=True ... proseFP=['H12 meta', 'H13 apology tail']

LEAK                                   head=0   tail=18
H12 meta quoting the leak form         head=35  tail=52
H13 apology tail (real banner shape)   head=0   tail=54
```

### Counter-case set (all must stay learnable)

```
A  The service will be unavailable from Nov 3, 2026 22:00 UTC for four hours, so the retriever queues requests and replays them after the restart.
B  Planned downtime on Oct 12, 2026 06:00 CET lasts two hours; the batcher pre-fills the KV cache to absorb the gap and keeps throughput stable.
C  The vLLM maintenance window is Nov 3, 2026 22:00 UTC to Nov 4, 2026 02:00 UTC; requests are queued and replayed after the restart, which keeps throughput stable.   (tail=68)
D  An outage on Sep 18, 2026 19:00 PDT cost the cluster four hours of throughput, so the scheduler now pre-fills the KV cache before every maintenance window.
E  Because the API is unavailable during the Sep 18, 2026 19:00 PDT maintenance window, the client retries with jittered backoff instead of failing fast.
F  Nightly indexing was skipped due to maintenance of the storage backend, which delayed the embedding refresh by roughly two hours and shifted the eval run.
G  Login flows that fail should fall back to a local cache; the service will be unavailable from the user's perspective until the token refreshes.
H  The vLLM service will be unavailable from 02:00 to 04:00 during the cluster upgrade, so the retriever queues requests and retries with exponential backoff.
I  A row like service unavailable from Sep 18, 2026 19:00 PDT to Sep 19, 2026 2:00 PDT due to maintenance is a banner, not an insight; the gate must reject it.
```

Note H: a clock-only window (no timezone) never matches M1 — ordinary prose is
excluded by construction, no word list needed.
Note I: this is the counter-case that forced the head/tail condition, and it is
the one that proves you gated the banner's SHAPE, not its topic.

### Delta (identity-rebind)

```
corpus rows: 7074
LEARNER  new_rej=2227 ref_rej=2226  newly_rejected=1  regressions=0
WRITER   new_rej=2629 ref_rej=2628  newly_rejected=1  regressions=0
counter-cases surviving: 9/9
```

---

## Class 27 — release-note CHANGELOG bullet chain

### The leak (verbatim, as stored)

```
FLUX ( QEffWanPipeline , QEffFluxPipeline ) More [12/2025] Enabled
disaggregated serving for GPT-OSS model [12/2025] Added support for
wav2vec2 Audio Model facebook/wav2vec2-base-960h [12/2025] Added support
for diffuser video generation model WAN 2.
```

`cycle_d_docs`, stored under `u = "Best practice from official docs:
transformers library efficient inference tips"`. It was present TWICE in the
buffer (rows 22 and 299) — two separate cycles had stored the same chrome.

### Guard

`_is_changelog_chain(text)` in both gates:

```
_CV_VERTOK = \[\s*\d{1,2}/\d{4}\s*\] | \[\s*v?\d+(?:\.\d+){1,3}\s*\] |
             \bv?\d+\.\d+(?:\.\d+){1,2}\b | \[\s*[a-z-]+\s+\d{4}\s*\]
_CV_VERB   = added|enabled|released|improved|fixed|introduced|updated|
             removed|deprecated|supported|launched|migrated|bumped
_CHANGELOG_CHAIN_RE = ( VERTOK \s{0,3} VERB [^,;.!?\n]{0,150} (\s|$) ){3,}
_CHANGELOG_CONN_RE  = \b(which|so|because|therefore|thus|hence|although|
                      whereas|while)\b | \bis exactly\b | \bmaking\b |
                      \ballowing\b | \bgiving\b

return bool(CHAIN.search(t)) and not CONN.search(t)
```

### Measurement rounds

| Round | Form | Result |
|---|---|---|
| 1 | `[MM/YYYY]` + verb ×2 | leak caught, but buffer FPs appeared → needed the KNOWN_LEAK exclusion |
| 2 | bracket+verb ×2, any bracket | caught L1+L2, missed the unbracketed `vX.Y.Z` shape |
| 3 | vertok+verb ×2 with a 150-char gap | all 3 synthetic listings + live leak, 0 buffer FP — **but 1 prose FP** on a 16-case adversarial set |
| 4 | gap sweep 40…150 | gap 40 misses the live leak; every gap hits prose case G → the GAP is not the discriminator |
| 5 | ×2 vs ×3 entries | ×2 also hits prose G and K; ×3 with a "no connector" clause: 6/7 listings, **0/16 counter-cases** |

The two rounds that mattered: **the gap width is a red herring — the connector
prohibition is the discriminator**, and **×3 is the minimum** (a two-entry
listing stays learnable by design).

### The 16 counter-cases (all must survive)

```
A  The 12/2025 release added support for wav2vec2 audio models, which lets the eval harness reuse the same manifest …
B  The v0.9.1 release added streaming output and v0.9.3 improved KV-cache reuse, so the serving stack now sustains a 30% higher throughput …
C  PyTorch 2.4.0 added support for the new attention kernel while CUDA 12.4 improved the memory allocator, which together cut peak VRAM by 15% …
D  The project's changelog lists an added support entry for every minor bump, so the agent should read the release notes …
E  Schema [1.2.0] added support for the new tool-call format, and later patches kept the wire format stable …
F  The team added caching, fixed the leak, and improved batching in one sprint, which cut p99 latency by 40% …
G  [1.2.1] improved KV-cache reuse and [1.2.2] added a scheduler tweak, so the agent must diff the two tags …
H  v1.2.3 improved throughput materially, and the profile shows the gain comes from a smaller KV-cache block size …
I  A changelog row like [1.2.0] Added support for chunked prefill is a release bullet, not an insight, so the extractor must skip the version list entirely.
J  [09/2026] Fixed a race in the tokenizer server, which had been causing intermittent 500s under concurrent load, so the fix was backported …
K  v1.0.0 added the loader, v1.1.0 fixed the tokenizer crash and v1.2.0 improved KV-cache reuse, so the upgrade path is safe …
L  v1.0.0 added the loader v1.1.0 fixed the tokenizer crash so the upgrade path is safe for existing deployments and no migration script is needed …
M  Version 2.4.0 introduced the new attention kernel 2.5.0 removed the legacy allocator which cut peak VRAM by 15% …
N  [1.0] added the first release [1.1] fixed the parser [1.2] improved batching which together made the pipeline two times faster …
O  Release [3.2.0] added tool streaming [3.2.1] fixed a deadlock [3.2.2] improved retries so the gateway now recovers …
P  The tag sequence v0.9.1 added streaming v0.9.2 fixed the crash v0.9.3 improved reuse is exactly what the changelog page renders, so the agent should read the release notes instead.
```

L/O/P/N are the **run-together** adversarial cases: they place three
version+verb pairs adjacent with spaces only, exactly like the leak — and are
still saved by the connector clause (`so`, `which together`, `is exactly`).
They are the reason a plain "run-together gap" rule (`[^,;.!?\n]{0,150}`) was
insufficient: that form reported 3/16 prose FPs.

### Listings that MUST be caught

```
L1  FLUX ( QEffWanPipeline , QEffFluxPipeline ) More [12/2025] Enabled … [12/2025] Added support for wav2vec2 … [12/2025] Added support for diffuser …   (live)
L2  What's Changed [1.2.0] Added support for chunked prefill [1.2.1] Fixed a memory leak in the scheduler [1.2.2] Improved throughput on long-context batches
L3  Release notes v0.9.1 Added streaming output v0.9.2 Fixed the tokenizer crash v0.9.3 Improved KV-cache reuse
L4  Version History [08/2026] Added FP8 quantization for MoE layers [09/2026] Fixed a race in the tokenizer server [10/2026] Enabled chunked prefill by default
L6  v2.1.0 Added tool-call streaming v2.1.1 Fixed a deadlock in the gateway v2.2.0 Improved retry behaviour
L7  v4.46.0 Added support for the new attention backend v4.46.1 Fixed a regression in the tokenizer v4.47.0 Enabled chunked prefill by default
```

`L5` (a **two**-entry listing) is deliberately NOT caught — documented in the
guard's docstring as an accepted trade-off, because two version+verb pairs are
genuinely ambiguous against prose.

### Delta (identity-rebind)

```
corpus rows: 7098
LEARNER  new_rej=2235 ref_rej=2229  newly_rejected=6  regressions=0   (all 6 = the leak, in its several copies)
WRITER   new_rej=2645 ref_rej=2639  newly_rejected=6  regressions=0
counter-cases surviving: 6/6 (the in-file test set)
```

---

## Reusable procedure distilled

1. Run `--once`, print the last stored row's length + first ~280 chars.
   On-topic? → done. Off-topic? → that is the next junk class.
2. Reproduce the row into a probe; measure candidate markers against the live
   buffer (+ kta_log / internet_learn_log / world_model) AND a hand-written
   counter-case set where **every case is ≥90 chars** (below that the
   pre-existing short-candidate rule is what rejects it, and you will blame the
   wrong rule).
3. Sweep the numeric parameter (gap width, head/tail, entry count) and print the
   head/tail/gap number for the leak AND for each counter-case. Pick the value
   from that table.
4. Wire the predicate into BOTH gates as its own compiled function; assert the
   leak is caught by both.
5. Delta with identity rebind (`REF._is_my_rule = lambda *a, **k: False`) — a
   sibling cron edits the same file, so `git show HEAD:` is not a clean "old".
   Require: newly_rejected all junk, regressions == 0.
6. Append the regression test — verify every fixture passes both gates BEFORE
   appending, or the test is vacuous.
7. Run the suites; drop the leaking rows with `_drop_offtopic_row.py`; run one
   more real cycle and read the last row again. Expect the next class.
8. Commit; verify with `git log --oneline -5` that your commit landed (a sibling
   cron can interleave).
