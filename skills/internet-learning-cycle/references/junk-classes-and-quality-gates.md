# Junk classes & learning-quality gates (internet_learner, 13.09.26)

Session detail behind the "Verify the cycle actually learned something" section.
Every string below was **actually stored as an insight** by a learning cycle —
they are not hypotheticals. Use them as the regression corpus when you extend
the gate.

## The class of failure

The learner's job is `collect → filter → extract insight → buffer (→ LoRA)`.
The weak link is *extract*: it takes a search-result **title** or the first
sentence of an arbitrary page, so whatever the page renders first can become
"knowledge". Symptom in the log — the cycle reports success while the payload is
page furniture:

```
[internet-learn] cycle_d_docs:        doc-learn: Jetzt spenden Benutzerkonto erstellen Anmelden Meine Werkzeuge
[internet-learn] cycle_e_competitors: competitor-learn: Pomysły na rodzinne spotkania Dania na grilla ... Przepisy Porady
[internet-learn] cycle_c_github:      github-learn: With GitHub, developers, agents, and code come together on one platform.
[internet-learn] cycle_f_multi_domain: domain-learn: Download PDF Download PDF Review Article Open access Publish
[internet-learn] cycle_h_efficiency:  efficiency-learn: Which%20Programming%20Language%20used%20behind%20Microsoft%20Edge%20Browser%20.
```

## Junk classes to expect (with the real strings)

| Class | Real specimen | Caught by |
|---|---|---|
| Wiki/de nav chrome | `Jetzt spenden Benutzerkonto erstellen Anmelden Meine Werkzeuge` | `_JUNK_RE` (new DE patterns) + `_NAV` |
| DE classified-ad chrome | `Unsere Werbepartner Einkaufen Ferienwohnungen Freizeit und Reise` | `_JUNK_RE` |
| PL recipe/classified chrome | `Pomysły na rodzinne spotkania Dania na grilla Inspiracje Kuchnia Przepisy Porady` | `_JUNK_RE` |
| Marketing slogan | `With GitHub, developers, agents, and code come together on one platform.` | `_JUNK_RE` |
| Login wall / anti-bot | `You switched accounts on another tab or window.` | `_JUNK_RE` |
| Link shrapnel (PDF landing page) | `Download PDF Download PDF Review Article Open access Publish` | `_clean_insight` (short + no tech signal) |
| URL fragment as "title" | `Which%20Programming%20Language%20used%20behind%20Microsoft%20Edge%20Browser%20.` | `_clean_insight` decodes first, **then** the short-candidate rule |
| Docs nav chrome | `View all docs AWS Trainium &amp; Inferentia` | `&amp;` / `›` rules in `deep_learn` |
| HF docs sidebar (≥90 chars!) | `Inference Providers Kernels LeRobot Leaderboards Lighteval Microsoft Azure OpenEnv Optimum PEFT Reachy Mini Safetensors … Tokenizers Trackio Transformers Transformers.` | `_JUNK_RE` nav signature (`inference providers kernels\|lerobot leaderboards\|…`) — live 14.09.26 |
| **Leaked LLM instruction template** | `"\n\n2.  **Identify the Core Task:**\n   - Extract ONE technical insight from the provided text.\n   - Format it as a single sentence.\n   - Must start with "[INSIGHT]".\n   - No preamble before the insight.\n   - Target audience: autonomous AI agent.\n\n3.` | `_JUNK_RE` template signatures (`identify the core task\|extract one technical insight\|no preamble before\|target audience: autonomous\|format it as a single sentence\|self-critique: reply with\|here'?s a thinking process`) — live 14.09.26 |
| **DE + course-marketplace ad CTA** | `Legal-Tech-Software - Kanzleimanagement mit Advolux — Advolux, die optimale Anwaltssoftware für moderne Kanzleiarbeit. Jetzt kostenlos testen. … AI Law Course … Find the right instructor for you. Choose from ma` | `_JUNK_RE` CTA signatures (`jetzt kostenlos testen\|kostenlos testen\|kostenlos registrieren\|find the right instructor\|right instructor for you\|choose from [\d,]+ (?:online )?courses\|jetzt angebot sichern\|jetzt kaufen\|jetzt bestellen`) — live 14.09.26 |

| **Vendor first-person boilerplate** | `Bit-TLS-Verschlüsselung Für die sichere Datenübertragung nutzen wir 256-Bit-TLS-` | `_JUNK_RE` voice signatures (`nutzen wir\|verwenden wir\|wir nutzen\|wir verwenden\|wir setzen ein\|unsere website\|unsere webseite\|auf dieser website\|ssl-?zertifikat\|für die sichere datenübertragung\|for secure data transmission`) — live 14.09.26 |

**Ad/CTA copy is the ≥90-char hole one more time.** Marketing calls to action
(`Jetzt kostenlos testen`, `Find the right instructor for you`, `Choose from
200,000+ online courses`) come with numbers and are long enough to pass every
length-based trust, so they need concrete-phrase signatures in `_JUNK_RE` like
anything else. Keep them as full phrases — `kostenlos` alone would kill a real
insight like `Kostenlose Modelle erreichen 30 tok/s auf CPU`. Scrub after the fix
(186→179 rows; the Advolux row plus 6 stale/empty fragments went to
`buffer_junk.jsonl` as `pre-existing`).

**The URL-fragment class is the subtle one.** `%20` contains digits, and the
technical-signal gate accepts *a number* as signal — so an undecoded URL title
walked straight through. Fix is to `urllib.parse.unquote` **before** judging,
then apply the short-candidate rule to the decoded words.

**Padded nav lists are the current subtle one.** The ≥90-char path *trusts*
length as prose so non-tech domains survive — a 200-char sidebar of product
labels therefore sails through. Signature it narrowly (the sidebar's own label
sequence), never by "many capitalised words" (real headlines look like that too).

**Leaked instruction templates are the same ≥90-char hole, different junk.**
When the LLM fallback (`_extract_insight_2b`) fails to obey, it returns its own
prompt scaffolding verbatim — `Identify the Core Task … Extract ONE technical
insight … No preamble before the insight. Target audience: autonomous AI agent.`
That is 200+ chars, so `_clean_insight` trusts it, and it contains a number
(`2.`/`3.`) so the short-candidate rule would not have saved it either. Signature
the template fragments as concrete phrases (never a bare `insight`/`extract`).
**Guard, not just detect:** the real fix direction is to reject a model output
that is *about the extraction task* rather than *from the source* — until then,
the phrase list is the cheap gate. `_extract_insight_2b` already prefers
`[INSIGHT]`-delimited output; anything else is suspect.

## Gate design (two layers, one write path)

```
cycle → store(user_text, insight, buffer=…)
          ├─ _is_junk(insight)            → audit "junk"          (chrome keywords)
          ├─ not _clean_insight(insight)  → audit "no-tech-signal"
          └─ buffer_store.append(cleaned) (cap enforced there)
```

- `_clean_insight(text, max_len)`: decode percent-escapes → `< 20 chars` or
  `_is_junk` ⇒ `""` → `< 90 chars` must carry a technical signal
  (`_looks_like_content`) → else return cleaned text. ≥ 90 chars pass on their
  own merit so non-tech domains (law, philosophy) survive.
- `_looks_like_content` / `_TECH_HINT_RE` is the cheap "is this prose about
  something technical" probe: a number or a technical noun/verb.
- **All 8 cycles** call `store()` and report honestly on refusal:
  `rejected, not trained (<insight>)`. A cycle that trained nothing says so —
  that is the correct, honest outcome, not a failure to hide.
- Refusals land in `buffer_junk.jsonl` with a reason, so the gate stays
  **observable** (a silent gate is indistinguishable from a broken pipeline).

## Extending the gate

1. Take the offending string **verbatim** from `internet_learner.log` /
   `online_buffer.jsonl` — never invent a pattern from a paraphrase.
2. Choose the right layer: a *keyword* (concrete phrase, never a bare word like
   `login`/`tools`) → `_JUNK_RE`; a *shape* problem (too short, no signal,
   encoded) → `_clean_insight`.
3. Add a case for it in `tests/scripts/test_internet_learner_gate.py` in the same
   change, then `python -m pytest tests/scripts/test_internet_learner_gate.py -q`.
4. Never let the gate grow so broad that it swallows real insight — every added
   pattern gets a counter-case in the `REAL` list of the test.

## Existing pollution is not fixed by a new gate

A tightened gate only stops *future* writes. The rows already in
`online_buffer.jsonl` keep training the LoRA. `scripts/training/scrub_rejected_buffer.py`
re-reads the buffer, moves every row the current gate rejects into
`buffer_junk.jsonl` (`reason: "pre-existing"`), and writes a timestamped backup
first. Live 13.09.26: **136 of 300 rows were chrome** — mostly short fragments
from other writers (`Shared underlying pattern one sentence.`, `These are older
good launches.`, `My terminal tool is also broken …`). After the scrub: 164 rows,
and the next cycles stayed clean (a genuine learn landed immediately:
`LLM Agent Benchmarks (September 2026): 26 Agentic Evals Ranked | BenchLM.`).

Rerun the scrub after any gate change, and read the backup name into the report
(it is the rollback point).
