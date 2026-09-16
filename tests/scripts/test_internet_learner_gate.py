"""Tests for the internet learner's learning-quality gates (scripts/training).

Hermetic: no network, no LLM, no real training buffer. We pin the contract that
keeps page furniture out of the LoRA training set — the failure mode is
concrete and was observed live (all four rows below really were "learned"):

  docs cycle       -> "Jetzt spenden Benutzerkonto erstellen Anmelden ..."  (DE wiki chrome)
  competitor cycle -> "Unsere Werbepartner Einkaufen Ferienwohnungen ..."  (DE ad chrome)
  competitor cycle -> "Pomysly na rodzinne spotkania ... Przepisy Porady"  (PL ad chrome)
  github cycle     -> "With GitHub, developers, agents, and code come together ..."

A cycle that finds nothing must report "rejected, not trained" rather than
store chrome, so `store()` returns False and the caller can be honest.
"""
import importlib.util
import sys
from pathlib import Path
import json
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent.parent
TRAINING = REPO / "scripts" / "training"
sys.path.insert(0, str(TRAINING))

_spec = importlib.util.spec_from_file_location(
    "internet_learner", TRAINING / "internet_learner.py"
)
IL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(IL)

# The exact bytes the papers cycle logged as "paper-learn: ..." (15.09.26):
# deep_learn() fetched an arxiv PDF and decoded it as text.
_PDF_NOISE = "".join(chr(c) for c in (
    0x54, 0xef, 0x70, 0xef, 0x25, 0x92, 0x92, 0x3b, 0x94, 0x22, 0x94, 0x94, 0x13,
    0x4a, 0x94, 0x38, 0x00, 0x94, 0x94, 0x6a, 0x9d, 0x73, 0x9d, 0x59, 0x9d, 0x6b,
    0x94, 0x94, 0x94, 0x94, 0x40, 0x72, 0x5c, 0x94, 0x94, 0x11, 0xd7, 0x34, 0x37,
    0x9d, 0x04, 0x60, 0x20, 0x94, 0x3a, 0x94, 0x47, 0x94, 0x74, 0x31, 0x94, 0x38,
    0x37, 0x35, 0x94, 0x20, 0x94, 0x54, 0x07, 0x94, 0x65, 0x94, 0x94, 0x13, 0x31,
    0x94, 0x94, 0x53, 0x35, 0x94, 0x5b, 0x94, 0x41, 0x94, 0x12,
))

# Writer-gate leaks found live 16.09.26 (both had passed BOTH gates and
# were sitting in the 300-row buffer):
#   cycle_d_docs   -> MediaWiki wikitext from a film infobox, no prose at all
#   cycle_c_github -> GitHub pricing-table copy, no sentence shape
# Writer-gate leaks found live 16.09.26 (both had passed BOTH gates and
# were sitting in the 300-row buffer):
#   cycle_g_security    -> AI-chat feature list, no prose
#   cycle_f_multi_domain -> review-site header + nav, no prose
_CHATUI_LEAK = (
    "Agent mode Let Chat calculate, work with files, and create downloads "
    "Create Image Concierge Let Chat hand off real-world tasks until you "
    "turn it off Memory Memory settings Voice Chat Standard AI Chat can "
    "make mistakes."
)
_REVIEWSITE_LEAK = (
    "Home Product categories AI Agents The best AI agents in 2026 Last "
    "updated Sep 15, 2026 Based on 4,014 reviews Products considered 726 "
    "AI Agents are software systems that act as digital teammates."
)

_WIKITEXT_LEAK = (
    'Sum|143|150|154|165|149|114|127|}} minutes (7 films)"},'
    '"distributor":{"wt":"{{Plainlist|* [[Paramount Pictures]] (2007-present)}}'
)
_PRICING_LEAK = (
    "BILLED ANNUALLY $119 /yr Select First 7 days FREE then $119 billed "
    "annually, cancel anytime Gaia+ $24 ."
)

# Extraction-gate leaks found live 16.09.26 (all three passed BOTH gates and
# were sitting in the 300-row buffer). Two shapes, one root cause: the short
# (<90) candidate rule accepted ANY `_TECH_HINT_RE` match, and that alternation
# also matches a bare digit — a section numeral counts as "technical signal".
#   cycle_e_competitors  -> App-Store blurb for a to-do app, buffered as
#                           competitor intelligence (>=90, so length-trusted)
#   cycle_f_multi_domain -> a bare document heading, accepted on the numeral "2"
#   connection cycles    -> the extractor's OWN task instructions, echoed back
_APPMARKETING_LEAK = (
    "Things - To-Do List App for Mac & iOS - Cultured Code — Things is the "
    "award-winning personal task"
)
_HEADING_NUMERAL_LEAK = "Distinction between classical and modern physics 2."
_PROMPT_ECHO_LEAK = "Need find shared underlying pattern."
_CONTACT_LEAK = "You can also reach us at +1 (123) 456-7890."

CHROME = [
    "Jetzt spenden Benutzerkonto erstellen Anmelden Meine Werkzeuge",
    "Unsere Werbepartner Einkaufen Ferienwohnungen Freizeit und Reise",
    "Pomysły na rodzinne spotkania Dania na grilla Inspiracje Kuchnia Przepisy Porady",
    "With GitHub, developers, agents, and code come together on one platform.",
    "You switched accounts on another tab or window.",
    "View all docs AWS Trainium &amp; Inferentia",
    # HuggingFace docs sidebar (live 14.09.26): 200 chars of product labels, so
    # it passed the >=90 "long prose" trust until the nav signature was added.
    "Inference Providers Kernels LeRobot Leaderboards Lighteval Microsoft Azure "
    "OpenEnv Optimum PEFT Reachy Mini Safetensors Sentence Transformers TRL Tasks "
    "Text Embeddings Inference Text Generation Inference Tokenizers Trackio "
    "Transformers Transformers.",
    # Leaked LLM instruction template (live 14.09.26): the multi-domain cycle
    # stored the 2B model's own extraction scaffolding verbatim.
    "\"\n\n2.  **Identify the Core Task:**\n   - Extract ONE technical insight "
    "from the provided text.\n   - Format it as a single sentence.\n   - Must "
    "start with \"[INSIGHT]\".\n   - No preamble before the insight.\n   - "
    "Target audience: autonomous AI agent.\n\n3.",
    # German/marketplace ad CTA (live 14.09.26): the multi-domain cycle stored
    # this exact CTA copy (Advolux + a Udemy-style course ad), 300 chars long so
    # it cleared the >=90 "long prose" trust.
    "Legal-Tech-Software - Kanzleimanagement mit Advolux — Advolux, die optimale "
    "Anwaltssoftware für moderne Kanzleiarbeit. Jetzt kostenlos testen. Mit Advolux "
    "arbeiten Sie besser, schneller und entspannter in; AI Law Course - AI for Legal "
    "Professionals — Find the right instructor for you. Choose from ma",
    # vendor first-person boilerplate (live 14.09.26): the efficiency cycle
    # stored this exact SSL-compliance chrome — the bare digit 256 satisfied the
    # technical-signal gate, so the junk gate keys on the vendor voice instead.
    "Bit-TLS-Verschlüsselung Für die sichere Datenübertragung nutzen wir 256-Bit-TLS-",
    # blog pagination + newsletter footer (live 15.09.26): the papers cycle
    # stored this exact text — the pagination digits ("1 2 3 … 11") satisfied
    # the technical-signal gate and the footer CTA cleared the >=90 length trust.
    "Onboarding Code Comprehension AI Coding Jishu Labs August 6, 2026 1 2 3 4 5 "
    "6 7 8 9 10 11 Next Stay Updated Get the latest insights on software "
    "development delivered to your inbox.",
    # raw PDF bytes as an "insight" (live 15.09.26): the digits in the
    # blob satisfied the technical-signal gate, so length + signal both
    # passed a byte dump into the training buffer.
    _PDF_NOISE,
    # GitHub releases-page chrome (live 15.09.26): the multi-domain cycle
    # stored this exact page meta — "released this <date>" satisfied the
    # technical-signal gate and it cleared the >=25 length floor.
    "No results found View all tags openai-sdks released this 14 Sep 23:28 v3.",
    # Social share/follow widget (live 16.09.26): the technews cycle learned
    # this exact string; the timestamps' digits satisfied the technical-signal
    # gate. See test_social_share_widget_chrome_is_rejected for the counter-cases.
    "March 17, 2026 (UPDATED Sep 8, 2026) 2026-09-08T13:12:23-04:00 "
    "Reddit Post Share Threads Support my work.",
]

# Link-shrapnel with no junk keyword and no sentence shape: caught by the
# "short candidate needs a technical signal" rule in _clean_insight (the
# multi-domain cycle distilled exactly this string from a PDF landing page).
SHORT_FURNITURE = [
    "Download PDF Download PDF Review Article Open access Publish",
    # a search "title" that is really a URL: the bare digits of %20 satisfied the
    # technical-signal gate until the candidate was decoded first
    "Which%20Programming%20Language%20used%20behind%20Microsoft%20Edge%20Browser%20.",
    # live 16.09.26: a bare document heading cleared the short-candidate rule on
    # the strength of its section numeral ("2"). A bare digit is not knowledge.
    _HEADING_NUMERAL_LEAK,
    _PROMPT_ECHO_LEAK,
    _CONTACT_LEAK,
]

REAL = [
    "vLLM PagedAttention raises serving throughput about 24x over naive HF generation.",
    "PEFT LoRA reduces trainable parameters to under 1% of the base model at int4.",
    "Continuous batching lets a serving engine process many prompts per GPU step, "
    "which cuts cost per token substantially for high-traffic agent workloads.",
    # the vendor-voice pattern must key on first-person boilerplate, never on the
    # topic — a genuine TLS/encryption insight still has to survive
    "TLS 1.3 removes a round trip from the handshake; session resumption cuts "
    "per-connection CPU cost.",
    # the pagination signature needs 6+ run-together short numbers + "Next"; a
    # genuine metrics sentence with scattered numbers must still pass
    "GPT-4 scores 89.1 on MMLU, 92.0 on HumanEval, and 3 of 4 agents pass the "
    "tool-call eval.",
    # Counter-cases for the 16.09.26 short-candidate tightening: a real insight
    # on each blocked topic must still pass. The new rule requires an ALPHABETIC
    # technical keyword below 90 chars, so none of these may be lost.
    "Speculative decoding cuts decode latency by 40% with a draft model.",
    "GGUF Q4_K_M quantization shrinks a 7B model to about 4 GB.",
]


def test_chrome_is_rejected_as_junk():
    for text in CHROME:
        assert IL._is_junk(text), text


def test_binary_blobs_are_rejected_and_prose_is_not():
    """A mis-decoded PDF must not reach the training buffer."""
    assert IL._looks_binary(_PDF_NOISE)
    assert IL._is_junk(_PDF_NOISE)
    for text in REAL:
        assert not IL._looks_binary(text), text


def test_writer_gate_agrees_on_the_new_chrome_and_binary_shapes():
    """buffer_store.is_junk is the WRITER gate (the one every writer hits).

    A shape the extraction gate drops but the writer accepts still lands in
    the buffer through any other writer path, so both must reject it.
    Measured live 15.09.26: the binary row scored 0.576 non-printable
    ratio, the highest-scoring real row 0.000.
    """
    sys.path.insert(0, str(TRAINING))
    import buffer_store
    new_shapes = [
        "No results found View all tags openai-sdks released this 14 Sep 23:28 v3.",
        # social share/follow widget (live 16.09.26) — the writer gate must
        # refuse it too, or any other writer path lands it in the buffer
        "March 17, 2026 (UPDATED Sep 8, 2026) 2026-09-08T13:12:23-04:00 "
        "Reddit Post Share Threads Support my work.",
        "K followers 59-year-old woman found dead in Bay Ridge apartment; "
        "death deemed suspicious Authorities say a 59-year-old woman was found",
        _PDF_NOISE,
        _WIKITEXT_LEAK,
        _PRICING_LEAK,
        _CHATUI_LEAK,
        _REVIEWSITE_LEAK,
    ]
    for text in new_shapes:
        assert buffer_store.is_junk(text), text
        assert IL._is_junk(text), text
    for text in REAL:
        assert not buffer_store.is_junk(text), text
    assert not buffer_store.is_junk(
        "Continuous Learning Loop: Fehler-Capture + Kategorisierung + Memory."
    )


def test_real_insights_survive_the_junk_gate():
    for text in REAL:
        assert not IL._is_junk(text), text


def test_clean_insight_drops_short_chrome_and_keeps_prose():
    for text in CHROME + SHORT_FURNITURE:
        assert IL._clean_insight(text) == "", text
    assert IL._clean_insight(REAL[0])
    assert IL._clean_insight(REAL[2])


def test_bare_digit_is_not_technical_signal():
    """A section numeral must not buy a fragment into the buffer (live 16.09.26).

    `_clean_insight` trusted any short candidate matching `_TECH_HINT_RE`, whose
    alternation also matches a bare number — so the document heading
    "Distinction between classical and modern physics 2." was buffered as
    multi-domain knowledge. The check is structural (alphabetic keyword
    required), never topical, so a real short insight on the same subject still
    passes. Measured over the live 300-row buffer: 42 verbless fragments
    rejected, all 13 rows with a real technical keyword kept.
    """
    assert IL._TECH_HINT_RE.search(_HEADING_NUMERAL_LEAK)  # old gate's signal
    assert IL._TECH_HINT_RE.search(_HEADING_NUMERAL_LEAK).group(0) == "2"
    assert not IL._has_alpha_signal(_HEADING_NUMERAL_LEAK)
    assert IL._clean_insight(_HEADING_NUMERAL_LEAK) == ""
    # a genuine short insight on the SAME topic must survive the tightening
    assert IL._has_alpha_signal("Mamba-3 decodes faster than a transformer.")
    assert IL._clean_insight("Mamba-3 decodes faster than a transformer.")


def test_alpha_signal_scans_past_a_leading_digit():
    """The keyword scan must not stop at the first match (live 16.09.26).

    `_has_alpha_signal` inspected only `_TECH_HINT_RE.search(...)` — the FIRST
    match. Real prose whose opening technical-ish token is a bare number was
    therefore rejected even though it carries a genuine keyword:
    "By contrast, the 2024 study found quantization recovers 97% of fp16
    accuracy at INT4." matched "2024", never saw "quantization", and scored as
    signal-less. Scanning every match keeps that insight while still rejecting
    a fragment whose ONLY signal is a numeral.
    """
    real = ("By contrast, the 2024 study found quantization recovers 97% of "
            "fp16 accuracy at INT4.")
    assert IL._TECH_HINT_RE.search(real).group(0) == "2024"  # the trap
    assert IL._has_alpha_signal(real)
    assert not IL._has_alpha_signal(_HEADING_NUMERAL_LEAK)   # numeral only -> still out


def test_byline_prefix_is_stripped_not_stored():
    """Page bylines must not ride into the buffer on the length trust (live 16.09.26).

    cycle_f_multi_domain stored, verbatim:
      "Written by Christian Gleitze \u00b7 Published June 11, 2026 \u00b7 Last
       reviewed July 23, 2026 AI Consciousness asks whether an Artificial
       Intelligence system could have subjective experience, ..."
    The extractor had legitimately pulled the article's opening sentence; the
    page's byline merely prefixed it. At >90 chars the "long prose is trusted"
    rule in `_clean_insight` never looked closer. The fix STRIPS the leading
    byline so the knowledge behind it survives — rejecting instead would throw
    away a real insight, so the counter-cases below are the point of this test.
    """
    body = ("AI Consciousness asks whether an Artificial Intelligence system "
            "could have subjective experience, whether there could be "
            "something it is like to be that system.")
    bylined = ("Written by Christian Gleitze \u00b7 Published June 11, 2026 "
               "\u00b7 Last reviewed July 23, 2026 " + body)
    assert IL._strip_byline_prefix(bylined) == body
    assert IL._clean_insight(bylined) == body          # body kept, byline gone
    # a bare byline with no body left is still chrome, not knowledge
    assert IL._clean_insight(
        "Written by Christian Gleitze \u00b7 Published June 11, 2026 "
        "\u00b7 Last reviewed July 23, 2026") == ""
    assert IL._strip_byline_prefix("By Mark Coates Published 14 September 26") == ""

    # --- 2nd shape, same run (live 16.09.26): publisher dateline welded to the
    # article title. cycle_a_technews stored this verbatim, cleared both gates
    # because "August 6, 2026" supplied the digits and the body had no byline
    # verb of its own, so the segment rule never matched the leading date.
    datelined = (
        "This article was published on August 6, 2026 Artificial Intelligence "
        "OpenAI and four rivals just agreed on one standard for AI agents "
        "OpenAI, Amazon, Microsoft, Cursor, and Vercel have agreed on a shared "
        "format for agent add-ons."
    )
    assert IL._strip_byline_prefix(datelined).startswith("Artificial Intelligence")
    assert IL._clean_insight(datelined).startswith("Artificial Intelligence")
    assert "This article was published" not in IL._clean_insight(datelined)
    # dateline with no body behind it is still chrome
    assert IL._clean_insight("This article was published on August 6, 2026") == ""
    assert IL._strip_byline_prefix("This article was published on August 6, 2026") == ""

    # --- the bare 4-digit year must stay CONFINED to the dateline voice:
    # "Published 2026 benchmarks show ..." is real prose, not a dateline, so
    # widening _DATE_ALT with a free-standing \d{4} would have eaten it.
    for text in (
        "Published 2026 benchmarks show vLLM serves twice the throughput of the "
        "naive pipeline at equal accuracy on a single A100.",
        "Updated 2026 results confirm quantization recovers 97% of fp16 accuracy.",
        "The 2026 study found Mamba-3 decodes faster than a transformer.",
    ):
        assert IL._strip_byline_prefix(text) == text, text

    # --- counter-cases: real prose that merely LOOKS like attribution ---
    for text in (
        "Published research from Stanford in 2024 shows transformers scale "
        "predictably with compute.",
        "By contrast, the 2024 study found quantization recovers 97% of fp16 "
        "accuracy at INT4.",
        "Updated benchmarks show vLLM serves 2x the throughput of the naive "
        "pipeline at equal accuracy.",
    ):
        assert IL._strip_byline_prefix(text) == text, text   # untouched
        assert IL._clean_insight(text), text                 # still learnable



def test_consumer_app_blurb_is_rejected():
    """An App-Store product blurb is not competitor intelligence (live 16.09.26).

    The row cleared the >=90 length trust on the strength of its marketing copy.
    The pattern keys on the blurb voice, never on the app or its category.
    """
    assert IL._is_junk(_APPMARKETING_LEAK)
    assert IL._clean_insight(_APPMARKETING_LEAK) == ""
    # counter-case: a real competitor/product analysis insight still passes
    real = ("Cursor's agent mode runs up to 8 parallel tool calls and bills per "
            "token, which makes long refactors costlier than a batch CLI run.")
    assert not IL._is_junk(real)
    assert IL._clean_insight(real)


def test_social_share_widget_chrome_is_rejected():
    """A share/follow widget is not knowledge (live 16.09.26).

    cycle_a_technews learned, verbatim:
      "March 17, 2026 (UPDATED Sep 8, 2026) 2026-09-08T13:12:23-04:00 Reddit
       Post Share Threads Support my work."
    and (a second, already-writer-gated row) a truncated counter
      "K followers 59-year-old woman found dead in Bay Ridge apartment; ..."
    Both cleared BOTH gates: the timestamps supplied the digits for the
    technical-signal gate and the rows exceeded the >=90 "long prose" trust.
    The rules key on the widget VOICE and on a counter whose own number is
    MISSING — never on a clock time or a topic word, so real numeric/temporal
    prose must survive (counter-cases below are the point of this test).
    """
    share_widget = (
        "March 17, 2026 (UPDATED Sep 8, 2026) 2026-09-08T13:12:23-04:00 "
        "Reddit Post Share Threads Support my work."
    )
    truncated_counter = (
        "K followers 59-year-old woman found dead in Bay Ridge apartment; "
        "death deemed suspicious Authorities say a 59-year-old woman was found"
    )
    assert IL._is_junk(share_widget)
    assert IL._is_junk(truncated_counter)
    assert IL._clean_insight(share_widget) == ""
    assert IL._clean_insight(truncated_counter) == ""

    # counter-cases: a real sentence that reports a follower count, and real
    # prose carrying a clock time or a batch duration, must all stay learnable.
    # (The clock-time counter-case carries a technical keyword because a SHORT
    # candidate already has to — that is the pre-existing length rule, not this
    # one; what this test pins is that the ticker rule does not add to it.)
    for text in (
        "Mistral has 30k followers on GitHub and ships its weights under Apache 2.0.",
        "The batch job starts at 03:15 CET and the inference latency peaks before "
        "the morning traffic.",
        "Training the 7B adapter took 2:40 on 4 A100s at an effective batch of 16.",
        "A 12K-follower account posted the benchmark; quantization recovered 97% of fp16.",
    ):
        assert not IL._is_junk(text), text
        assert IL._clean_insight(text), text


def test_news_ticker_loop_is_rejected():
    """A re-rendered ticker headline is not knowledge (live 16.09.26).

    cycle_a_technews learned, verbatim:
      "Trump praised Bezos for reversal 03:15 White House blasted Amazon for
       tariffs explainer, Trump praised Bezos for reversal (03:15) OpenAI backs
       measure that would require independent audits of AI models The AI bubble
       is leaking air, some economists say."
    A ticker re-renders the same headline with a fresh clock, so several
    unrelated headlines arrive glued together with one phrase twice. The rule
    keys on that STRUCTURE (time code + self-repeated >=15-char phrase), never
    on a topic or on a bare clock time — prose that legitimately mentions one
    or two times, or repeats a short word, must survive (counter-cases below).
    """
    ticker = (
        "Trump praised Bezos for reversal 03:15 White House blasted Amazon for "
        "tariffs explainer, Trump praised Bezos for reversal (03:15) OpenAI backs "
        "measure that would require independent audits of AI models The AI bubble "
        "is leaking air, some economists say."
    )
    assert IL._is_ticker_loop(ticker)
    assert IL._is_junk(ticker)
    assert IL._clean_insight(ticker) == ""

    import buffer_store
    assert buffer_store.is_junk(ticker)

    # counter-cases: real prose with one or two clock times, and a sentence
    # that repeats a SHORT word — none may be gated.
    for text in (
        "The batch job starts at 03:15 CET and the inference latency peaks before "
        "the morning traffic.",
        "Two runs measure 03:15 and 04:20 wall clock; the quantized model has "
        "lower inference latency in both.",
        "Training the 7B adapter took 2:40 on 4 A100s at an effective batch of 16.",
        "Retrieval beats fine-tuning for facts; retrieval also costs less per query.",
    ):
        assert not IL._is_ticker_loop(text), text
        assert IL._clean_insight(text), text
        assert not buffer_store.is_junk(text), text


def test_store_refuses_chrome_and_writes_real_insights(tmp_path):
    buf = tmp_path / "buf.jsonl"
    import buffer_store  # imported lazily by store()

    with patch.object(buffer_store, "_audit", lambda *a, **k: None):
        for text in CHROME:
            assert IL.store("q", text, buffer=buf) is False, text
        assert IL.store("q", REAL[0], buffer=buf) is True
    lines = [ln for ln in buf.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, "only the real insight may reach the training buffer"
    assert REAL[0][:40] in lines[0]


def test_clean_insight_decodes_percent_escapes_before_judging():
    """Percent-escapes must be decoded, not judged raw (digits fake a signal)."""
    assert IL._clean_insight("LoRA%20adapters%20cut%20VRAM%20by%2040%25%20at%20int4.") \
        == "LoRA adapters cut VRAM by 40% at int4."


class _Resp:
    """urlopen() stand-in: .read() hands back the JSON we seeded."""

    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b


def test_headline_prefers_real_articles_and_refuses_self_posts():
    """Show/Ask HN landing pages are ad copy, never a seed for a cycle.

    Live 15.09.26: cycle_c_github took "Show HN: A murder mystery game built on
    an open-source gen-AI agent framework", deep-read the product page and was
    gated — the whole cycle wasted. "" must hand over to the LLM query instead.
    """
    only_self = [{"title": "Show HN: A murder mystery game built on an open-source gen-AI agent framework"},
                 {"title": "Ask HN: who is hiring agent engineers right now"}]
    with patch.object(IL.urllib.request, "urlopen", lambda *a, **k: _Resp({"hits": only_self})):
        assert IL._fresh_headline("AI agent framework", []) == ""

    with_article = [{"title": "Show HN: my agent framework, please star it"},
                    {"title": "A practical guide to agent memory architectures with benchmarks"}]
    with patch.object(IL.urllib.request, "urlopen", lambda *a, **k: _Resp({"hits": with_article})):
        assert IL._fresh_headline("AI agent", []).startswith("A practical guide")


def test_store_or_deep_retries_the_read_with_a_wider_k():
    """A page with no qualifying sentence must not waste the cycle: retry k=6.

    Live 15.09.26: cycle_e/cycle_g logged "rejected, not trained" every other
    run because the first pass (k=2) found nothing storable.
    """
    ks, good = [], "vLLM 0.9 adds disaggregated prefill and 2x throughput."
    with patch.object(IL, "store", lambda u, i: i == good),          patch.object(IL, "deep_learn", lambda q, k=2: (ks.append(k), good if k == 6 else "")[1]):
        assert IL.store_or_deep("u", "q", "") == good
    assert ks == [2, 6], f"expected k=2 then k=6, got {ks}"

def test_every_learning_cycle_gates_its_write_and_reports_honestly():
    """Invariant, not a snapshot: one gate call and one honest rejection path per
    cycle. The gate helper's concrete name is an implementation detail, so key
    the assertion on the number of cycles rather than a literal call shape — a
    change-detector on `if not store(` broke when the cycles switched to
    store_or_deep() (14.09.26)."""
    src = (TRAINING / "internet_learner.py").read_text(encoding="utf-8")
    cycles = src.count("\ndef cycle_")
    assert cycles == 8, f"expected 8 cycles, found {cycles}"
    assert src.count("store_or_deep(") - 1 == cycles, \
        "every cycle must route its write through the gate helper"
    assert src.count('return "rejected, not trained') == cycles, \
        "every cycle must report a rejection honestly when both reads are gated"
def test_serp_pipe_dash_shape_is_gated():
    """SERP shape "<title> | <site> — <snippet>" (no ellipsis) must be junk.

    Observed live 15.09.26: cycle_c_github stored exactly this shape. The
    existing _SERP_ELL_DASH marker never fires without the ellipsis, so this
    needed a marker of its own. The gate lives in buffer_store (the writer's
    gate), not IL._is_junk (the search-result filter). Asserts behaviour, not
    the regex literal."""
    import buffer_store  # the module the learner's store() routes through

    assert buffer_store.is_junk(
        'Fable Studio Review | TheAISelect — Fable Studio\'s "The Simulation" is a groundbreaking platform'
    )
    assert not buffer_store.is_junk(
        "Chunked prefill allows vLLM to process large prefills in smaller chunks and "
        "batch them together with decode requests, which improves throughput."
    )


def test_glued_motif_degeneration_is_gated():
    """A single 4-char motif glued into most tokens must be junk.

    Observed live 15.09.26: cycle_h_efficiency stored the 2B extractor's word
    salad ('ells' inside 14 of ~43 tokens). The periodic-repeat and token-ratio
    gates both missed it because the motif sits INSIDE otherwise-distinct
    words. Measured over the live 300-row buffer: that row scored 14 hits at a
    0.056 char-rate, the highest-scoring real row 8 hits at 0.027, so the
    detector must fire here and stay silent on real prose."""
    import buffer_store

    assert buffer_store.is_junk(
        "Here's a ali with aminoellsかけて subject et recessellsells deep this "
        "urbanellscriptsells around anoells kill fromolt heatells rama fromellsells— "
        "in el ls youngells counts mill cities overtellsells filtersuti rigor-ells "
        "championship bits janitation etce"
    )
    assert not buffer_store.is_junk(
        "Results on quantizing Llama 1 and 2 models, achieving near fp16 "
        "quantization performance at 2 bits with most layers kept at higher precision."
    )
    assert not buffer_store.is_junk(
        "The shared underlying pattern is a dynamic feedback loop where errors "
        "observed in one situation are captured, categorized, and turned into "
        "reusable procedures for the next one."
    )
