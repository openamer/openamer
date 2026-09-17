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
# arXiv abstract-page label chain (live 16.09.26, class 10): the papers cycle
# logged `paper-learn: Xiv-issued DOI via DataCite Submission history ...` —
# 243 chars of pure page labels, zero prose, accepted because the submission
# timestamp fed the technical-signal gate and the length cleared the >=90
# "long prose" trust. Verbatim from the stored buffer row.
_ARXIV_CHROME_LEAK = (
    "Xiv-issued DOI via DataCite Submission history From: Shuming Ma "
    "[ view email ] [v1] Tue, 27 Feb 2024 18:56:19 UTC (201 KB) Full-text "
    "links: Access Paper: View a PDF of the paper titled The Era of 1-bit LLMs: "
    "All Large Language Models are in 1."
)


# Chinese Q&A / answer-portal chrome (live 16.09.26, class 12): the efficacy
# cycle stored a Baidu-Zhidao answer-portal scrape as a learning. Verbatim
# from the stored buffer row; CJK kept as ASCII escapes so the file stays
# diff-stable. Both gates passed it: the badge dates fed the
# technical-signal gate and the length cleared the >=90 long-prose trust.
_QA_PORTAL_LEAK = (
    "CAD\u770b\u56fe\u738b \u63d0\u4f9b \u55e8\u683c\u5f0f 2019-02-19 \u00b7 \u767e\u5ea6\u8ba4\u8bc1:\u82cf\u5dde\u821c\u5fc3\u79d1\u6280\u6709\u9650\u516c\u53f8 \u55e8\u683c\u5f0f \u55e8\u683c\u5f0f\u662f\u82cf\u5dde\u5f00\u5fc3\u76d2\u5b50\u8f6f\u4ef6\u6709\u9650\u516c\u53f8\u65d7"
    "\u4e0b\u7684\u72ec\u7acb\u54c1\u724c\u3002\u82cf\u5dde\u5f00\u5fc3\u76d2\u5b50\u8f6f\u4ef6\u6709\u9650\u516c\u53f8\u662f\u4e00\u5bb6\u4e13\u6ce8\u8f6f\u4ef6\u7814\u53d1\u7684\u4e92\u8054\u7f51\u79d1\u6280\u516c\u53f8\u3002 \u5411TA\u63d0\u95ee \u5173\u6ce8 \u5c55\u5f00\u5168\u90e8 \u5728Word\u6587\u6863\u4e2d\uff0c\u5982\u4f55\u8f93"
    "\u5165\u50cf\u8fd9\u6837\u53ef\u4ee5\u6253\u52fe\u6253\u53c9\u7684\u65b9\u6846\u5462\uff1f\u6709\u4e0d\u6b62\u4e00\u79cd\u65b9\u6cd5\u80fd\u591f\u8f93\u5165\u8fd9\u6837\u7684\u65b9\u6846\uff0c\u4e00\u8d77\u6765\u5b66\u4e60\u4e00\u4e0b\u3002 \u5df2\u8d5e\u8fc7 \u5df2\u8e29\u8fc7 \u4f60\u5bf9\u8fd9\u4e2a\u56de\u7b54\u7684\u8bc4\u4ef7\u662f\uff1f \u8bc4\u8bba "
    "\u6536\u8d77 \u8bfb\u4e66\u5c0f\u660e\u767d \u9ad8\u7c89\u7b54\u4e3b 2020-02-14 \u00b7 \u9189\u5fc3\u7b54\u9898\uff0c\u6b22\u8fce\u5173\u6ce8 \u77e5\u9053\u7b54\u4e3b \u56de\u7b54\u91cf\uff1a 12."
)
# Counter-cases. A LANGUAGE-based rule ("reject CJK") would have eaten the
# first one, which is real knowledge; the gate therefore keys on the portal's
# label CHAIN and needs TWO independent markers. The second case carries
# exactly ONE marker inside genuine prose, and is kept at >=90 chars on
# purpose: below that the PRE-EXISTING short-candidate rule (which wants an
# ENGLISH technical keyword) fires first and would look like this gate
# misfiring. Measured: 69 chars -> gated by the short rule; 102 -> survives.
_CJK_REAL = (
    "LLM Agent \u7684\u8bb0\u5fc6\u7cfb\u7edf\u901a\u5e38\u5206\u4e3a\u77ed\u671f\u4e0a\u4e0b\u6587\u548c\u957f\u671f\u5411\u91cf\u5b58\u50a8\u4e24\u5c42\uff0c\u5411\u91cf\u68c0\u7d22\u7684\u53ec\u56de\u7387\u76f4\u63a5\u51b3\u5b9a\u4e86\u957f\u671f\u8bb0\u5fc6\u5728\u5b9e\u9645\u4efb\u52a1\u4e2d\u7684\u53ef\u7528\u6027\uff0c\u800c\u77ed"
    "\u671f\u4e0a\u4e0b\u6587\u5219\u53d7\u5230\u7a97\u53e3\u957f\u5ea6\u7684\u786c\u6027\u9650\u5236\u3002"
)
_CJK_ONE_MARKER = (
    "\u8bba\u6587\u4f5c\u8005\u58f0\u660e\u8be5\u6a21\u578b\u6743\u91cd\u7684\u8bad\u7ec3\u6570\u636e\u672a\u516c\u5f00\uff0c\u56e0\u6b64 INT4 \u91cf\u5316\u540e\u7684\u7cbe\u5ea6\u590d\u73b0\u6027\u65e0\u6cd5\u7531\u7b2c\u4e09\u65b9\u72ec\u7acb\u9a8c\u8bc1\uff0c\u800c fp16 \u57fa\u51c6\u5728\u516c\u5f00\u6570\u636e\u96c6\u4e0a"
    "\u53ef\u4ee5\u590d\u73b0\u3002\u6a21\u578b\u5728 2 \u4f4d\u91cf\u5316\u4e0b\u53c2\u6570\u5360\u7528\u7ea6\u51cf\u5c11\u5230\u56db\u5206\u4e4b\u4e00\uff0c\u63a8\u7406\u5ef6\u8fdf\u4e5f\u968f\u4e4b\u4e0b\u964d\u3002"
)
# German SaaS pricing/checkout chrome (live 16.09.26, class 13): the github
# cycle stored this exact plan-table copy as a learning. Verbatim from the
# stored buffer row. Both gates passed it: the prices fed the
# technical-signal gate and the 133 chars cleared the >=90 long-prose trust.
_DE_PRICING_LEAK = (
    "Bleib flexibel: Monatlich k\u00fcndbar Lastschrift Kreditkarte Auf Re"
    "chnung Jahrespaket 49,50 \u20ac / Jahr ~ 4,12 \u20ac pro Nutzer und Monat "
    "inkl."
)
# Counter-cases: real prose that merely cites a price, and prose carrying
# exactly ONE billing marker. The English twin of this class ('billed
# annually') already lives in buffer_store._NAV_CHROME.
_DE_PRICING_REAL = (
    "Serving that model costs about 0,002 \u20ac per 1k tokens; annualised"
    " that is roughly 12 \u20ac per agent per month including the vector s"
    "tore overhead."
)
_DE_PRICING_ONE_MARKER = (
    "Die Rechnung wird monatlich k\u00fcndbar abgerechnet, und die Quantis"
    "ierung senkt den Speicherbedarf des 7B-Modells auf etwa vier Gig"
    "abyte bei INT4, was die Inferenzlatenz deutlich reduziert."
)
# A mid-sentence snippet echo welded to the front of a real sentence
# (live 16.09.26, class 14): the multi-domain cycle stored this exact row.
# Verbatim from the buffer; the extractor got Bing's mid-sentence snippet
# opening and prepended it to the article's real first sentence. STRIP, not
# reject - the sentence behind the fragment is the knowledge.
_CLOCK_ECHO = (
        "at 11:44 am we asked four ai coding agents to In a recent experi"
        "ment, four AI coding agents were tasked with recreating the clas"
        "sic game Minesweeper, revealing both the potential and limitatio"
        "ns of modern AI in programming."
)
_CLOCK_ECHO_BODY = (
        "In a recent experiment, four AI coding agents were tasked with r"
        "ecreating the classic game Minesweeper, revealing both the poten"
        "tial and limitations of modern AI in programming."
)
# Counter-cases: prose that merely mentions a time of day must be untouched
# (the rule needs a LOWERCASE start plus a clock with am/pm). Both are >=90
# chars on purpose: below that the PRE-EXISTING short-candidate rule (which
# wants an ENGLISH technical keyword) fires first and would look like this
# gate misfiring.
_CLOCK_PROSE = [
    (
        "At 11:44 am the retriever returned a stale embedding, and the qu"
        "antization step then masked the drift for three consecutive batc"
        "hes."
    ),
    (
        "The job starts at 11:44 and finishes before the peak; the quanti"
        "zed model keeps peak VRAM under 6 GB while continuous batching h"
        "olds throughput steady."
    ),
]
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
    # arXiv abstract-page label chain (live 16.09.26) — see _ARXIV_CHROME_LEAK.
    _ARXIV_CHROME_LEAK,
    # Chinese Q&A/answer-portal label chain (live 16.09.26) - see
    # _QA_PORTAL_LEAK and its dedicated test below.
    _QA_PORTAL_LEAK,
    # German pricing/checkout label chain (live 16.09.26) - see
    # _DE_PRICING_LEAK and its dedicated test below.
    _DE_PRICING_LEAK,
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
    # Counter-case for the arXiv-chrome rule: real prose may legitimately
    # mention a submission history or a revision, and one page label alone is
    # NOT chrome — the rule needs TWO independent label fragments.
    "The paper's submission history shows v1 to v3 in four months; INT4 "
    "quantization recovers 97% of fp16 accuracy on the reasoning benchmark.",
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


def test_german_dictionary_serp_chrome_is_gated_on_both_paths():
    """cycle_c_github stored two dictionary SERP snippets joined by ";".

    Live 16.09.26: the row was German dictionary chrome (Duden + Wikipedia)
    with zero technical prose, and it cleared BOTH gates. A structural
    "\u2026;" gate was REJECTED because 7 of the 16 such buffer rows (vLLM,
    quantization) carry genuine technical prose; the marker is the
    dictionary's own call to action instead.
    """
    sys.path.insert(0, str(TRAINING))
    import buffer_store
    leak = (
        "Agent Rechtschreibung, Bedeutung, Definition, Herkunft Duden \u2014 "
        "Definition, Rechtschreibung, Synonyme und Grammatik von 'Agent' "
        "Auf Duden online nachschlagen W\u00f6rterbuch der deutschen \u2026; "
        "Agent (Nachrichtendienst) \u2013 Wikipedia \u2014 Agent ist im "
        "deutschen Sprachraum ein allgemeinsprachlich uneinheitlich"
    )
    assert buffer_store.is_junk(leak), leak
    assert IL._is_junk(leak), leak
    # the \u2265\u2026\u003b shape alone must stay clean (real prose uses it too)
    for prose in (
        "Parallelism and Scaling - vLLM \u2014 It's often advantageous to "
        "exploit the inherent parallelism of experts \u2026; Optimization and "
        "Tuning - vLLM \u2014 Data parallelism can be combined with the other "
        "parallelism strategies.",
        "Quantization Format Comparison 2026 \u2014 GGUF, AWQ, GPTQ, EXL2, "
        "MLX, FP8, NF4, INT4, INT8. Quality degradation, throughput \u2026; 4.8",
    ):
        assert not buffer_store.is_junk(prose), prose
        assert not IL._is_junk(prose), prose


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


def test_arxiv_abstract_chrome_is_rejected():
    """An arXiv abstract page's LABEL CHAIN is not knowledge (live 16.09.26).

    cycle_b_papers logged, verbatim from the stored buffer row:
      "Xiv-issued DOI via DataCite Submission history From: Shuming Ma
       [ view email ] [v1] Tue, 27 Feb 2024 18:56:19 UTC (201 KB) Full-text
       links: Access Paper: View a PDF of the paper titled The Era of 1-bit
       LLMs: All Large Language Models are in 1."
    243 chars of page labels welded together, zero prose: the submission
    timestamp satisfied the technical-signal gate and the length cleared the
    >=90 "long prose" trust.

    The rule is structural (TWO independent page labels), never topical — a
    genuine insight ABOUT an arXiv paper must stay learnable, and one label
    alone (real prose can mention a submission history) is left alone.
    """
    assert IL._is_arxiv_abstract_chrome(_ARXIV_CHROME_LEAK)
    assert IL._is_junk(_ARXIV_CHROME_LEAK)
    assert IL._clean_insight(_ARXIV_CHROME_LEAK) == ""

    import buffer_store
    assert buffer_store.is_junk(_ARXIV_CHROME_LEAK)

    # counter-cases: a REAL paper insight, and prose carrying exactly ONE
    # page label, must both survive
    for text in (
        "BitNet stores its weights in ternary form, so a 7B model fits in "
        "about 2 GB at int4 with no measurable accuracy loss.",
        "The submission history shows v1 to v3 landed within four months; "
        "INT4 quantization recovers 97% of fp16 accuracy on all three "
        "reasoning benchmarks.",
        "Full-text links aside, the paper's key result is that 1.58-bit "
        "weights match fp16 on most downstream tasks.",
    ):
        assert not IL._is_arxiv_abstract_chrome(text), text
        assert not IL._is_junk(text), text
        assert buffer_store.is_junk(text) is False, text
        assert IL._clean_insight(text), text


def test_blog_header_stack_is_stripped_not_stored():
    """Header stacks + share widgets must not ride along, but the article text
    must survive (live 16.09.26 — three verbatim rows of one family).

    Learned, verbatim from the buffer:
      1. "Team / JUN 1, 2026 / 0 comments AI Coding Agents: The Complete Guide
          to Autonomous Software Development (2026) 32 min read Share on
          Twitter , LinkedIn Software development is undergoing ..."
      2. "3 min read Illustration The Agent Times // Share X LinkedIn HN Copy
          link The specific article at the center of the storm remains ..."
      3. "AI agents Home News MIT News Published On: Nov 22 2024 Published on:
          May 21, 2026 Share Facebook Twitter Bluesky Fields ranging from
          robotics to medicine ..."
    Three structural rules: a `<name> / <DATE> / <N> comments` dateline, a share
    widget ANCHORED to a date/read-time/`//` header marker, and the `copy link`
    button label. Each measured over the live 277-row buffer: 3 hits total (the
    leaking rows), 0 real-prose rows.

    The voice-only variant ("share on <platform>" anywhere) was measured and
    REJECTED — it ate a real sentence, so that counter-case is pinned below.
    """
    cases = [
        # (verbatim leak, chrome that must be gone)
        (
            "Team / JUN 1, 2026 / 0 comments AI Coding Agents: The Complete "
            "Guide to Autonomous Software Development (2026) 32 min read Share "
            "on Twitter , LinkedIn Software development is undergoing its "
            "biggest transformation since the invention of version control.",
            ("/ JUN 1, 2026 /", "0 comments", "Share on Twitter"),
        ),
        (
            "3 min read Illustration The Agent Times // Share X LinkedIn HN "
            "Copy link The specific article at the center of the storm remains "
            "somewhat obscured in human terms.",
            ("Share X LinkedIn", "Copy link", "The Agent Times //"),
        ),
        (
            "AI agents Home News MIT News Published On: Nov 22 2024 Published "
            "on: May 21, 2026 Share Facebook Twitter Bluesky Fields ranging "
            "from robotics to medicine to political science are attempting to "
            "train AI systems.",
            ("Share Facebook Twitter",),
        ),
    ]
    for leak, gone in cases:
        out = IL._strip_blog_header_stack(leak)
        assert len(out.split()) >= 5, leak
        for chrome in gone:
            assert chrome not in out, (chrome, out)
        # the surviving text is a trimmed SLICE of the original, never invented
        for word in out.split():
            assert word in leak, (word, out)

    # the full chain must leave NO residue of the header (read-time rule also
    # terminates on a `//` separator, so row 2's "3 min read … //" is consumed)
    for leak, _ in cases:
        for helper in (IL._strip_read_time_header, lambda t: IL._clean_insight(t, 300)):
            cleaned = helper(leak)
            assert "min read" not in cleaned or "Illustration" not in cleaned

    # counter-cases: prose that merely MENTIONS a share, a read time, or uses
    # slashes must survive byte-identical. The first needs a real technical
    # keyword because a <90-char candidate must carry one — that is the
    # pre-existing length rule, not this one.
    for text in (
        "The write-up is a 6 min read; we share on Twitter the INT4 quantization table.",
        "We share on Twitter the benchmark results for the quantized 7B model today.",
        "We share X posts about quantization every week on our internal channel.",
        "Share on Twitter is not a strategy; accuracy comes from quantization at int4.",
        "Training took 3 days / 2 GPUs / 400 GB of tokens per epoch overall.",
        "A 32 min read of the vLLM docs shows the attention backend is auto-selected.",
        "The team copied the link between latency and batch size in the report.",
    ):
        assert IL._strip_blog_header_stack(text) == text, text
        assert IL._clean_insight(text), text


def test_read_time_header_is_stripped_not_stored():
    """A leading "<N> min read <category nav>" header must not ride into the
    buffer, but the article BEHIND it must survive (live 16.09.26, two cycles).

    Learned, verbatim:
      "11 min read China Semiconductors AI Infrastructure Geopolitics China AI
       Chip Boom: CAICT 417% Demand vs 128% Supply 2026 Caixin Sept 15, 2026:
       CAICT says China AI compute demand jumped 417% YoY in Q1 vs 128% supply."
    The category nav repeats a word the headline re-uses ("China ... China"),
    so the second occurrence is where the article starts. The body must come
    out BYTE-IDENTICAL to the original minus the prefix — a strip-gate is a
    third verdict beside accept/reject, so a plain delta cannot prove it.
    """
    body = (
        "China AI Chip Boom: CAICT 417% Demand vs 128% Supply 2026 Caixin "
        "Sept 15, 2026: CAICT says China AI compute demand jumped 417% YoY in Q1."
    )
    header = ("11 min read China Semiconductors AI Infrastructure Geopolitics " + body)
    assert IL._strip_read_time_header(header) == body          # body byte-identical
    assert IL._clean_insight(header) == body
    assert "min read" not in IL._clean_insight(header)

    nvidia = (
        "12 min read Nvidia AI Infrastructure GPUs FinOps Wall Street Nvidia "
        "$500B AI Compute Fund: What Developers Need to Know Nvidia and six "
        "Wall Street firms unveiled $500B in AI compute financing on August 10, 2026."
    )
    assert IL._clean_insight(nvidia).startswith("Nvidia $500B AI Compute Fund")

    # No repeated nav word -> no structural marker -> UNTOUCHED. This is what
    # keeps real prose that merely mentions a read time safe, and it is why the
    # rule does not need a "strip N words" guess.
    for text in (
        "The 11 min read time on that post is misleading; the quantization "
        "section is only 200 words.",
        "Benchmarks show 40% latency reduction at int4; the write-up is a 6 min read.",
        "vLLM PagedAttention raises serving throughput about 24x over naive HF generation.",
    ):
        assert IL._strip_read_time_header(text) == text, text
        assert IL._clean_insight(text), text


def test_arrow_nav_prefix_is_stripped_not_stored():
    """Leading nav terminated by an HTML-comment arrow must not ride in
    (live 16.09.26, third shape of the byline/header-strip family).

    Learned, verbatim:
      "Studies Blogs Contact Arsha --> Posted on May 2, 2025 by admin --> Prompt
       Engineering Is Dead in 2025 Introduction Prompt engineering, once hailed
       as the essential skill for interacting with large language models (LLMs),
       has become obsolete by 2025."
    `-->` is leaked HTML comment markup -- real prose never contains it, which
    is exactly what makes it a safe boundary. The body must survive BYTE-INTACT.
    """
    leak = (
        "Studies Blogs Contact Arsha --> Posted on May 2, 2025 by admin --> "
        "Prompt Engineering Is Dead in 2025 Introduction Prompt engineering, once "
        "hailed as the essential skill for interacting with large language models "
        "(LLMs), has become obsolete by 2025."
    )
    body = (
        "Prompt Engineering Is Dead in 2025 Introduction Prompt engineering, once "
        "hailed as the essential skill for interacting with large language models "
        "(LLMs), has become obsolete by 2025."
    )
    assert IL._strip_arrow_nav_prefix(leak) == body
    assert IL._clean_insight(leak) == body
    assert "-->" not in IL._clean_insight(leak)

    # a run of empty arrows from a stripped template must also be consumed.
    # (Verbatim live row 154 — the closing clause carries the comma that keeps
    # it out of the nav-list rule; a shortened fixture would trip THAT gate,
    # which is a different rule and not what this test is about.)
    multi = (
        "March 27, 2026 2 min read --> --> --> --> --> Uncomfortable Truths "
        "About AI Coding Agents: What the Industry Needs to Know Artificial "
        "intelligence is reshaping software development, but the rise of AI "
        "coding agents brings both promise and pitfalls."
    )
    assert IL._clean_insight(multi).startswith("Uncomfortable Truths About AI Coding Agents")
    assert "-->" not in IL._clean_insight(multi)

    # counter-cases: real prose with no arrow, and an arrow deep inside a text
    for text in (
        "OpenCode | The open source AI coding agent — What is OpenCode? OpenCode is "
        "an open source agent that runs in the terminal and bills per token.",
        "Retrieval beats fine-tuning for facts; retrieval also costs less per query.",
        "vLLM PagedAttention raises serving throughput about 24x over naive HF generation.",
    ):
        assert IL._strip_arrow_nav_prefix(text) == text, text
        assert IL._clean_insight(text), text


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


def test_qa_portal_chrome_is_rejected_but_chinese_prose_survives():
    """A Chinese Q&A-portal scrape is chrome; real Chinese prose is knowledge
    (live 16.09.26, class 12).

    cycle_h_efficiency learned, verbatim from the stored buffer row, a
    Baidu-Zhidao answer-portal scrape (verified badge, vote widget, fan
    badge, ask-me button, answer counter) with zero technical prose. Both
    gates passed it: the badge dates fed the technical-signal gate and the
    length cleared the >=90 long-prose trust.

    The rule is structural (TWO independent portal markers), never topical
    or language-based, so a genuine insight written in Chinese still
    passes. Measured over the live 5013-row corpus (buffer + junk log):
    5 hits, every one chrome, 0 real-prose rows, and no row carrying
    exactly one marker.
    """
    sys.path.insert(0, str(TRAINING))
    import buffer_store

    assert IL._is_qa_portal_chrome(_QA_PORTAL_LEAK)
    assert IL._is_junk(_QA_PORTAL_LEAK)
    assert IL._clean_insight(_QA_PORTAL_LEAK) == ""
    assert buffer_store.is_junk(_QA_PORTAL_LEAK)
    assert buffer_store._is_nav_chrome(_QA_PORTAL_LEAK)

    # counter-case 1: genuine Chinese technical prose, zero portal markers
    assert not IL._is_qa_portal_chrome(_CJK_REAL)
    assert not IL._is_junk(_CJK_REAL)
    assert buffer_store.is_junk(_CJK_REAL) is False
    assert IL._clean_insight(_CJK_REAL)

    # counter-case 2: exactly ONE marker inside real prose is NOT chrome
    assert not IL._is_qa_portal_chrome(_CJK_ONE_MARKER)
    assert not IL._is_junk(_CJK_ONE_MARKER)
    assert buffer_store.is_junk(_CJK_ONE_MARKER) is False
    assert IL._clean_insight(_CJK_ONE_MARKER)


def test_wikipedia_section_edit_prefix_is_stripped_not_stored():
    """A LEADING MediaWiki "<Section> [ edit ]" control must not ride into the
    buffer, but the paragraph BEHIND it must survive (live 16.09.26, class 12).

    Learned, verbatim:
      "Publications [ edit ] OWASP Top Ten The \"Top Ten\", first published in
       2003 and updated periodically (subsequent editions appeared in 2004, 2007,
       2010, 2013, 2017, 2021 and 2025), is a listing of the most critical
       application security risks."
    The bracket control is page furniture the extractor welded to a genuine
    paragraph, so this is a STRIP (a third verdict beside accept/reject) — the
    plain old-vs-new delta cannot prove it. Assert the surviving body is the
    ORIGINAL MINUS THE PREFIX, and keep the counter-cases below alive: a strip
    rule that eats a real sentence about an edit button is worse than the leak.
    """
    body = (
        'OWASP Top Ten The "Top Ten", first published in 2003 and updated '
        "periodically (subsequent editions appeared in 2004, 2007, 2010, 2013, "
        "2017, 2021 and 2025), is a listing of the most critical application "
        "security risks."
    )
    leak = "Publications [ edit ] " + body
    assert IL._strip_wiki_section_prefix(leak) == body       # body pristine
    assert IL._clean_insight(leak) == body
    assert "[ edit ]" not in IL._clean_insight(leak)

    # --- counter-cases: real prose that MENTIONS an edit control must be
    # returned byte-identical. The possessive in case 1 is the load-bearing
    # one: the leading-name guard is sentence-case, so `Wikipedia's` cannot
    # match — a looser first version gutted this sentence to `button is a
    # MediaWiki control ...`, which is exactly what this case exists to catch.
    for text in (
        "Wikipedia's [ edit ] button is a MediaWiki control, not content; the "
        "RAG pipeline should strip it before chunking documents for retrieval.",
        "The paper's edit history shows v1 to v3 in four months; INT4 "
        "quantization recovers 97% of fp16 accuracy on the reasoning benchmark.",
        "You can edit the config.yaml to pin a model, but cron job pins always "
        "win over the global default in OpenAmer.",
    ):
        assert IL._strip_wiki_section_prefix(text) == text, text   # untouched
        assert IL._clean_insight(text), text                       # learnable

    # --- the writer gate must agree with the reader gate -------------------
    import sys
    sys.path.insert(0, str(TRAINING))
    import buffer_store
    assert buffer_store._WIKI_EDIT_WORD_RE.match('Publications [ edit ] OWASP')
    assert not buffer_store._WIKI_EDIT_WORD_RE.match(
        "Wikipedia's [ edit ] button is a MediaWiki control")
    assert buffer_store.is_junk("Publications [ edit ] " + body)
    assert buffer_store.is_junk(
        "Wikipedia's [ edit ] button is a MediaWiki control, not content; the "
        "RAG pipeline should strip it before chunking documents for retrieval."
    ) is False


def test_de_pricing_chrome_is_rejected_but_priced_prose_survives():
    """A German pricing/checkout table is chrome, priced prose is knowledge
    (live 16.09.26, class 13).

    cycle_c_github learned, verbatim from the stored buffer row, a plan
    comparison/checkout table (monthly-cancel wording, direct-debit and
    invoice payment options, annual package, per-seat per-month price) with
    zero technical prose. The rule is
    structural (TWO independent billing markers), never topical, so a
    genuine insight that merely cites a price still passes. Measured over
    the live 4855-row corpus (buffer + junk log): 6 marker hits, all in
    ONE row (the leaking row), 0 real-prose rows.
    """
    sys.path.insert(0, str(TRAINING))
    import buffer_store

    assert IL._is_de_pricing_chrome(_DE_PRICING_LEAK)
    assert IL._is_junk(_DE_PRICING_LEAK)
    assert IL._clean_insight(_DE_PRICING_LEAK) == ""
    assert buffer_store.is_junk(_DE_PRICING_LEAK)
    assert buffer_store._is_nav_chrome(_DE_PRICING_LEAK)

    # counter-case 1: real prose citing a price, zero billing markers
    assert not IL._is_de_pricing_chrome(_DE_PRICING_REAL)
    assert not IL._is_junk(_DE_PRICING_REAL)
    assert buffer_store.is_junk(_DE_PRICING_REAL) is False
    assert IL._clean_insight(_DE_PRICING_REAL)

    # counter-case 2: exactly ONE billing marker inside real prose
    assert not IL._is_de_pricing_chrome(_DE_PRICING_ONE_MARKER)
    assert not buffer_store.is_junk(_DE_PRICING_ONE_MARKER)
    assert IL._clean_insight(_DE_PRICING_ONE_MARKER)


def test_leading_clock_dateline_fragment_is_stripped_not_stored():
    """A leading lowercase clock-dateline fragment must not ride into the
    buffer, but the article body behind it must survive (live 16.09.26, class 13).

    Learned, verbatim:
      "at 11:44 am we asked four ai coding agents to In a recent experiment, four
       AI coding agents were tasked with recreating the classic game Minesweeper,"
    The extractor cut the byline mid-sentence, so a LOWERCASE fragment prefixed a
    real paragraph -> STRIP. Assert the surviving body is the ORIGINAL MINUS the
    fragment, and keep the counter-cases below alive: a capitalized clock time at
    the start of a real sentence must stay learnable.
    """
    body = (
        "In a recent experiment, four AI coding agents were tasked with "
        "recreating the classic game Minesweeper, revealing both the potential "
        "and limitations of modern AI in programming."
    )
    leak = "at 11:44 am we asked four ai coding agents to " + body
    assert IL._strip_dateline_fragment(leak) == body          # body pristine
    assert IL._clean_insight(leak) == body
    assert not IL._clean_insight(leak).startswith("at ")

    # --- counter-cases: real prose that merely MENTIONS a clock time, or opens
    # with the CAPITALIZED form, must be returned byte-identical. Guard 1 is the
    # lowercase requirement -- a sentence never starts 'at 11:44 am ...'.
    for text in (
        "At 12:30 pm the batch job starts, so schedule the quantization sweep "
        "before noon.",
        "The run finished at 11:44 am and the quantized model had lower latency.",
        "at 11:44 we measured 40% lower decode latency, but the sentence has no "
        "am/pm marker.",
    ):
        assert IL._strip_dateline_fragment(text) == text, text   # untouched
        assert IL._clean_insight(text), text                     # learnable


def test_clock_snippet_echo_is_stripped_not_stored():
    """A leading mid-sentence snippet echo is stripped; the body survives
    (live 16.09.26, class 14).

    cycle_f_multi_domain learned, verbatim from the stored buffer row:
      "at 11:44 am we asked four ai coding agents to In a recent experiment,"
       four AI coding agents were tasked with recreating the classic game
       Minesweeper, ..."
    The extractor received Bing's snippet opening MID-SENTENCE and prepended
    it to the article's real first sentence. Both gates passed it: the clock
    digits fed the technical-signal gate and the length cleared the >=90
    long-prose trust.

    The rule is structural: lowercase start, a clock-with-meridiem marker,
    and a capitalised real sentence after the fragment. Measured over the
    live 4870-row corpus: exactly 1 row touched, the body a clean suffix,
    and 4/4 counter-cases unmodified.
    """
    stripped = IL._strip_clock_fragment(_CLOCK_ECHO)
    assert stripped == _CLOCK_ECHO_BODY
    assert _CLOCK_ECHO.endswith(stripped)   # a clean suffix, not a truncation
    assert IL._clean_insight(_CLOCK_ECHO) == _CLOCK_ECHO_BODY[:250]

    # counter-cases: prose that merely mentions a time of day survives
    for text in _CLOCK_PROSE:
        assert IL._strip_clock_fragment(text) == text, text
        assert not IL._is_junk(text), text
        assert IL._clean_insight(text), text


def test_leading_nav_label_stack_is_stripped_not_stored():
    """A leading LABEL-ONLY nav stack ending at a dateline must not ride in,
    but the sentence behind it must survive (live 16.09.26, class 14).

    Learned, verbatim:
      "SECURITY resources Whitepapers/Guides OWASP GenAI LLM Top 10 2026
       August 3, 2026 About OWASP Top 10 for LLM Applications 2026 is the latest
       community-driven guide to the most critical security risks facing
       applications powered by large language models."

    A GENERIC `<nav-run> <date> <body>` rule was MEASURED and REJECTED: it ate
    four GitHub-advisory rows (the GHSA case below) plus two counter-cases.
    The surviving rule adds the structural fact that separates a MENU from a
    sentence: a slash-joined Capitalized pair must be present AND the head may
    carry no function word and at most one lowercase word.
    """
    body = (
        "About OWASP Top 10 for LLM Applications 2026 is the latest "
        "community-driven guide to the most critical security risks facing "
        "applications powered by large language models."
    )
    leak = ("SECURITY resources Whitepapers/Guides OWASP GenAI LLM Top 10 "
            "2026 August 3, 2026 " + body)
    assert IL._strip_nav_label_stack(leak) == body        # body pristine
    # The STRIP contract -- "the sentence behind the nav survives" -- is
    # asserted with a GENUINE insight. The verbatim logged body above is
    # this page's own META blurb, which class 31 (_is_page_meta_blurb,
    # 17.09.26) correctly refuses; asserting IT learnable would test the
    # wrong contract. See test_page_meta_blurb_is_rejected.
    genuine = (
        "Prompt injection is the first of ten categories in the 2026 "
        "guide, and the new agent-tooling class covers tool-call abuse "
        "directly."
    )
    assert IL._strip_nav_label_stack(leak.replace(body, genuine)) == genuine
    assert IL._clean_insight(leak.replace(body, genuine)) == genuine

    # --- counter-cases: prose heads, which is exactly what the function-word
    # guard protects. Each must come back byte-identical AND stay learnable.
    for text in (
        "The paper compares German/English tokenizers on a March 3, 2026 "
        "benchmark of 12 models.",
        "Whitepapers/Guides are listed on the site; the August 3, 2026 "
        "revision adds three sections.",
    ):
        assert IL._strip_nav_label_stack(text) == text, text   # untouched
        assert IL._clean_insight(text), text                   # learnable

    # the GitHub-advisory shape the generic candidate rule WRONGLY ate: the
    # strip must leave it byte-identical. Not asserted learnable — the
    # PRE-EXISTING _is_nav_list rule rejects it (a different gate).
    GHSA = (
        "Critical Authenticated Arbitrary Data Export Theft via Mass "
        "Assignment in sendFileMessage GHSA-fhc2-x8cp-c5ch by julio-rocketchat "
        "High Previous 1 2 3 Next Learn more about advisories."
    )
    assert IL._strip_nav_label_stack(GHSA) == GHSA
    assert IL._is_nav_list(GHSA)


def test_leading_byline_stack_is_stripped_not_stored():
    """A leading author/date/counters/Share byline row must not ride in, but
    the article body behind it must survive (live 16.09.26, class 15).

    Learned, verbatim:
      "Simon Lermen Feb 24, 2026 54 5 8 Share TL;DR: We show that LLM agents
       can figure out who you are from your anonymous online posts."
    The byline row prefixed the paper's own TL;DR -> STRIP. The signature is the
    welded ORDER (Name, date, bare counters, "Share"); each element alone is
    prose-safe. Both guards below are measured over the live 5074-row corpus.
    """
    body = (
        "TL;DR: We show that LLM agents can figure out who you are from your "
        "anonymous online posts."
    )
    leak = "Simon Lermen Feb 24, 2026 54 5 8 Share " + body
    assert IL._strip_byline_stack(leak) == body          # body pristine
    assert IL._clean_insight(leak) == body

    # --- counter-cases. The counters must be BARE numbers AND directly followed
    # by "Share": a real sentence that reports its date and metrics cannot match.
    for text in (
        "Alice Smith Jan 5, 2026 reported 40% lower decode latency in the "
        "quantized model.",
        "The Feb 24, 2026 release of vLLM adds 3 new quantized kernels and 2 "
        "fixes.",
        "We show that LLM agents can figure out who you are from your "
        "anonymous online posts.",
        "Simon Lermen Feb 24, 2026 54 5 8 TL;DR: We show that LLM agents can "
        "figure out who you are.",       # no Share control -> untouched
    ):
        assert IL._strip_byline_stack(text) == text, text   # untouched

    # the three prose cases must still be learnable (the fourth is a fragment
    # shape, asserted only for the strip)
    for text in (
        "Alice Smith Jan 5, 2026 reported 40% lower decode latency in the "
        "quantized model.",
        "The Feb 24, 2026 release of vLLM adds 3 new quantized kernels and 2 "
        "fixes.",
        "We show that LLM agents can figure out who you are from your "
        "anonymous online posts.",
    ):
        assert IL._clean_insight(text), text
def test_hn_listing_and_wikipedia_infobox_chrome_is_gated_on_both_paths():
    """cycle_f/cycle_g stored HN front-page listing chrome and a Wikipedia
    infobox label chain (live 16.09.26). Both cleared the writer AND the
    extraction gate: the HN row is >90 chars with digits (so the length trust
    and the technical-signal gate both fired) and the infobox row is a bare
    label chain with no comma, so `_is_nav_list` never matched.

    Measured on the live buffer: 1-2 hits each, 0 real-prose false positives
    on a 12-sentence hand-written prose set. Bank T&C rows were deliberately
    left UNGATED: `consumer account` / `checking account` / `savings account`
    each hit real hand-written prose, i.e. they are topic words, not chrome.
    """
    sys.path.insert(0, str(TRAINING))
    import buffer_store
    leaks = (
        # HN front-page listing chrome: "by <user> visit website #N Launch HN..."
        "by alepeak visit website #14 Launch HN: April (YC S25) - Voice AI to "
        "manage your email and calendar 98 points \u00b7 95 comments \u00b7 "
        "Aug 25, 2025 \u00b7 by nehasuresh1904 visit website #15 Launch HN: Twill.",
        # Wikipedia infobox label chain (" ; 21 months ago ( ... ) Industry ... ")
        "Model Context Protocol Developed by Anthropic Introduced November 25, "
        "2024 ; 21 months ago ( 2024-11-25 ) Industry Artificial intelligence "
        "Connector type TypeScript Python Java Kotlin C# Go PHP Perl Ruby Rust Swift",
        # HN story listing counters mid-row
        "Remix new past ask show jobs submit login AI Regex Scientist: A "
        "self-improving regex solver 9 points by PranoyP 7 months ago | 2 " "comments",
    )
    for leak in leaks:
        assert buffer_store.is_junk(leak), leak
        assert IL._is_junk(leak), leak

    # counter-cases: every marker is also a shape real prose can contain.
    for prose in (
        "Model Context Protocol was introduced by Anthropic in November 2024 "
        "to standardize tool access for LLM applications across vendors.",
        "You can visit our website to read the full benchmark methodology and "
        "the raw latency numbers behind the comparison.",
        "A consumer account typically earns interest while a checking account "
        "does not, which is why fintechs push both products together.",
        "The paper reports 98 points on MMLU after 21 months of iterative "
        "pretraining and reinforcement learning on synthetic data.",
    ):
        assert not buffer_store.is_junk(prose), prose
        assert not IL._is_junk(prose), prose


def test_selfcritique_echo_and_fixture_list_chrome_is_gated_on_both_paths():
    """cycle_d_docs stored a 2B self-critique echo and cycle_c_github stored a
    sports results-page fixture list (live 16.09.26). Both cleared the writer
    AND the extraction gate: each is >90 chars with digits, so the long-prose
    length trust and the technical-signal gate both fired, and no existing
    marker matched.

    Measured on the live buffer's 280-row NON-JUNK corpus (the leaking rows
    excluded -- they pass `is_junk`, so counting them as "real" contaminates
    the FP corpus): 1 hit each, 0 real-prose false positives. A bare "A vs B"
    is deliberately NOT gated -- measured 6 hits, all real prose
    ("CUDA vs ROCm vs Vulkan vs Metal").
    """
    sys.path.insert(0, str(TRAINING))
    import buffer_store
    leaks = (
        # 2B self-critique echo: the extractor reviews its own scaffold
        '"\n   - **Context:** The user pasted a long documentation page from '
        'vLLM, but the actual content is just the table of contents and '
        'section headings.',
        # sports results-page fixture list: scoreline ++ pipe ++ fixture date
        "Napoli vs Lazio 0-2 | 12/04/2026 Parma vs Napoli 1-1 | 12/04/2026 "
        "Parma vs Napoli 1-1 SSC NAPOLI OFFICIAL APP Disponibile ora",
    )
    for leak in leaks:
        assert buffer_store.is_junk(leak), leak
        assert IL._is_junk(leak), leak

    # counter-cases: the same shapes as they appear in genuine prose.
    for prose in (
        "CUDA vs ROCm vs Vulkan vs Metal: GPU Compute in 2026 A deep "
        "technical comparison of the three compute stacks.",
        "vLLM's PagedAttention treats KV cache as paged memory, enabling "
        "chunked prefill and dynamic batching.",
        "Prompt injection defenses include input sanitization, instruction "
        "hierarchy, and output validation layers.",
        "The paper compares Qwen3-4B vs Llama-3.1-8B on 12.04.2026 released "
        "benchmarks and reports a 3.1 point gap after quantization.",
    ):
        assert not buffer_store.is_junk(prose), prose
        assert not IL._is_junk(prose), prose


def test_contact_block_chrome_is_gated_on_both_paths():
    """A legal-imprint / "Transparenzliste" contact block is not an insight.

    Live 16.09.26: cycle_c_github stored the 106-char row
    `Transparenzliste GAIA AG Hans-Henny-Jahnn-Weg 53 22085 Hamburg
    Deutschland +49 40 3510520 info@gaia-group.` -- pure company-address
    chrome. It cleared BOTH gates because the length trust (>=90 chars)
    waved it through and its house number / postcode satisfied the
    technical-signal gate. `_is_nav_list` wants >=6 TitleCase tokens AND no
    comma, so the mixed-case address chain never matched it.

    The rule is STRUCTURAL (postcode AND international phone AND e-mail),
    never topical: `Transparenzliste` alone is a topic word -- it appears in
    a genuine sentence about media-regulation disclosure duties, so a
    marker on it would drop real prose. Measured over the live 300-row
    buffer: exactly 1 hit and that hit IS the leaking row.
    """
    sys.path.insert(0, str(TRAINING))
    import buffer_store

    leaks = (
        "Transparenzliste GAIA AG Hans-Henny-Jahnn-Weg 53 22085 Hamburg "
        "Deutschland +49 40 3510520 info@gaia-group.",
        "Impressum: Muster GmbH, Beispielweg 12, 10115 Berlin, "
        "Tel. +49 30 1234567, kontakt@muster-gmbh.de",
    )
    for leak in leaks:
        assert buffer_store.is_junk(leak), leak
        assert IL._is_junk(leak), leak

    # counter-cases: a technical insight routinely cites numbers, a phone
    # number, a postcode or an e-mail. Each below has AT MOST two of the
    # three signals, so every one must survive BOTH gates.
    for prose in (
        "Deutschland 2026: the BSI reported 412 new CVEs affecting German "
        "public-sector systems, up 18 percent year over year.",
        "The Transparenzliste of the state media authority lists providers "
        "that must disclose their algorithmic recommendation systems.",
        "Kontakt: Universitaet Hamburg, Mittelweg 177, 20148 Hamburg, "
        "Tel. +49 40 42838-0.",
        "Reach the team at info@example.org for a security disclosure and "
        "include a proof of concept with the affected version.",
        "The 10115 Berlin pilot deployed 40 GPUs and cut inference latency "
        "from 900 ms to 120 ms per request.",
    ):
        assert not buffer_store.is_junk(prose), prose
        assert not IL._is_junk(prose), prose

def test_cross_connect_prompt_echo_fourth_shape_is_gated_on_both_paths():
    """cross_connect buffering its OWN prompt fragments is not an insight.

    Live 16.09.26: active_learn.cross_connect wrote three of its own prompt
    fragments into online_buffer.jsonl as "structural connection" answers:

      A) `User asks: "Find the structural connection between these two
         situations:  1.`
      B) `Shared underlying pattern?`  (26 chars -- just clears the producer's
         25-char floor)
      C) `Continuous Learning Loop: Fehler-Capture + Kategorisierung + Memory +
         Auto-Skill-Generierung + Trend\n\nWhat is the shared underlying
         pattern?`

    `_ECHO_SITUATION_RE` is anchored on the numbered `situation N` marker and
    cannot see any of them, and `_ECHO_OPENER_RE` only anchors at the START --
    which is exactly why (B) and (C), whose marker sits at the END, escaped.

    The rule is a TAIL anchor plus a colon-terminated FRAGMENT, never a topic
    phrase: the genuine declarative answer on the same topic and an ordinary
    sentence that merely uses the words must both survive. Measured over the
    live 300-row buffer: 3 hits and all 3 ARE the leaking rows -> 0 real-prose
    false positives on a 12-sentence set; 0 hits over 3,169 longterm_episodes
    rows.
    """
    sys.path.insert(0, str(TRAINING))
    import buffer_store

    leaks = (
        'User asks: "Find the structural connection between these two '
        "situations:  1.",
        "Shared underlying pattern?",
        "Continuous Learning Loop: Fehler-Capture + Kategorisierung + "
        "Memory + Auto-Skill-Generierung + Trend\n\n"
        "What is the shared underlying pattern?",
    )
    for leak in leaks:
        assert buffer_store.is_junk(leak), leak
        assert buffer_store.is_prompt_echo(leak), leak
        assert IL._is_junk(leak), leak

    # counter-cases: the SAME words inside a genuine answer or an ordinary
    # sentence. A topic-phrase marker would kill every one of these.
    for prose in (
        "The shared underlying pattern is a closed-loop feedback system "
        "that monitors and self-optimizes based on captured error data.",
        "Situation 1 and situation 2 share a common failure mode: unbounded "
        "retries without backoff.",
        "A user asks the agent to summarize a document, and the agent must "
        "decide whether to call a tool first.",
        "The structural connection between energy efficiency and learning "
        "rate is a trade-off curve.",
        "Both systems use a feedback loop: the error signal drives the next "
        "action selection.",
        "Continuous learning loops capture errors, categorize them, and "
        "generate skills over time.",
    ):
        assert not buffer_store.is_junk(prose), prose
        assert not buffer_store.is_prompt_echo(prose), prose

def test_extractor_template_echo_fifth_shape_is_gated_on_both_paths():
    """The 2B extractor echoing its OWN numbered template is not an insight.

    Live 16.09.26: cycle_h_efficiency buffered

        '"\n\n2.  **Identify the Goal:**\n   - I need to look at the provided
        list of papers, understand the themes, and extract a single, high-value
        technical insight that would be most relevant/valuable for an autonomous
        AI agent.\n   - The insight should be ge...'

    The pre-existing template markers ("identify the core task", "extract one
    technical insight", "no preamble before", "format it as a single sentence")
    all key on OTHER phrasings of the same prompt, so this numbered
    "the goal" / "high-value" variant cleared both gates.

    Markers are colon-terminated ("identify the goal:") or phrase-complete
    ("the insight should be"), never bare keywords: measured 1 buffer hit and
    that hit IS the leaking row -> 0 real-prose FPs on an 8-sentence set;
    0 hits over 3,169 longterm_episodes + 9,906 buffer_junk rows.
    """
    sys.path.insert(0, str(TRAINING))
    import buffer_store

    leaks = (
        '"\n\n2.  **Identify the Goal:**\n   - I need to look at the '
        "provided list of papers, understand the themes, and extract a single, "
        "high-value technical insight that would be most relevant/valuable for "
        "an autonomous AI agent.",
        "Identify the Goal: pull one high-value technical insight out of the "
        "supplied document and state it in a single sentence.",
    )
    for leak in leaks:
        assert buffer_store.is_junk(leak), leak
        assert buffer_store.is_prompt_echo(leak), leak

    # counter-cases: the bare words in genuine technical prose must survive.
    for prose in (
        "The first step of the pipeline is to identify the goal function and "
        "its gradient before backpropagation.",
        "To improve a benchmark you must identify the goal metric before "
        "optimizing throughput.",
        "Retrieval systems should extract a single high-value technical "
        "insight per document and cite it.",
    ):
        assert not buffer_store.is_junk(prose), prose
        assert not buffer_store.is_prompt_echo(prose), prose

def test_2b_plan_scaffold_echo_is_gated_on_both_paths():
    """The 2B extractor echoed its own numbered PLAN back at itself (live
    16.09.26, cycle_h_efficiency): the row cleared the >=90 length trust and
    its digits fed the technical-signal gate, and no existing marker matched
    because the echo opens on the model's own plan, not on the documented
    scaffold phrases. BOTH gates must agree, and real prose that merely USES
    the same topic words must stay learnable."""
    leak = (
        '"\n   - **Content:** I need to browse the provided list of papers, '
        "identify the most relevant/valuable technical insight for an "
        "autonomous AI agent, and output it in the exact format."
    )
    import buffer_store  # the module the learner's store() routes through

    assert buffer_store.is_junk(leak)
    assert IL._is_junk(leak)

    # Counter-cases: the loose alternatives that were measured and REJECTED as
    # markers, plus real prose that uses the same words in a declarative voice.
    for prose in (
        "The agent should browse a provided list of papers only when the "
        "query is genuinely open-ended, otherwise it wastes a full read cycle.",
        "We need to identify the most relevant failure mode when a cron job "
        "dies mid-run, because silent failures accumulate without alerting.",
        "The most valuable technical insight from this paper is that linearity "
        "holds for the quantized weights.",
        "The vLLM scheduler batches prefill requests to keep the GPU "
        "saturated, which raises throughput at the cost of added latency.",
    ):
        assert not IL._is_junk(prose), prose

def test_question_echo_and_ordinal_stub_are_gated_on_both_paths():
    """Sixth prompt-echo shape + chopped-TOC stub must die on BOTH gates.

    Live 16.09.26: active_learn.cross_connect buffered
    `Question: Find structural connection between these two situations. What`
    (the article is dropped and the prompt ends on a period, so the existing
    fragment rule -- which needs "find the structural connection" plus a colon --
    never fired), and cycle_f_multi_domain stored the chopped TOC item
    `Probabilistic methods for uncertain reasoning 2.` because its technical
    keyword ("reasoning") satisfied the alphabetic-signal check.

    One-directional tests pass a broken marker, so both directions are asserted:
    the two leaks must be rejected by the writer gate AND the extraction gate,
    and genuine prose -- including a declarative answer on the very same
    "structural connection" topic -- must stay clean.
    """
    import buffer_store

    leaks = (
        "Question: Find structural connection between these two situations. What",
        "Probabilistic methods for uncertain reasoning 2.",
    )
    for leak in leaks:
        assert buffer_store.is_junk(leak), leak
        assert IL._is_junk(leak), leak

    prose = (
        # a declarative ANSWER on the same topic must survive the echo rule
        "The structural connection between these two situations is a shared "
        "resource bottleneck.",
        "To find the structural connection between these two situations you "
        "have to model both as queues.",
        # real sentences that merely END on a number (the false positives that
        # killed the first version of the ordinal rule)
        "Training the 7B adapter took 2:40 on 4 A100s at an effective batch of 16.",
        "Kontakt: Universitaet Hamburg, Mittelweg 177, 20148 Hamburg, "
        "Tel. +49 40 42838-0.",
        "The 10115 Berlin pilot deployed 40 GPUs and cut inference latency "
        "from 900 ms to 120 ms per request.",
        "LoRA reduces VRAM usage at inference time.",
    )
    for p in prose:
        assert not buffer_store.is_junk(p), p


def test_diagram_markup_source_is_gated_on_both_paths():
    """Diagram DSL source must die on BOTH gates; prose ABOUT it survives.

    Live 16.09.26: cycle_e_competitors stored
    `OKF Agent Memory resolves this dilemma with the Dual-Memory Agent
     Architecture (DMAA) : flowchart TD subgraph PUSH["1.`
    -- an extractor lead-in sentence welded onto Mermaid diagram body. At
    118 chars it cleared the >=90 long-prose trust, so nothing looked
    closer at what the text actually was.

    The rule needs TWO independent markers (a DSL keyword AND diagram
    markup punctuation), so every counter-case below -- a real sentence
    naming a diagram type -- stays learnable.
    """
    import buffer_store

    leak = (
        "OKF Agent Memory resolves this dilemma with the Dual-Memory Agent "
        "Architecture (DMAA) : flowchart TD subgraph PUSH[\"1."
    )
    assert buffer_store.is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak
    assert IL._is_junk(leak), leak
    assert IL._is_diagram_markup(leak), leak

    prose = [
        # names the DSL keyword but carries no node label / arrow syntax
        "A flowchart TD block in the docs renders top-down, so the RAG "
        "chunker must split on the subgraph boundary before embedding the "
        "diagram labels.",
        "Mermaid sequenceDiagram syntax is parsed by the CLI and rendered "
        "as SVG in the browser, which adds about 40 ms per diagram.",
        "Graphviz digraph declarations describe a scheduler dependency "
        "graph, and the renderer lays it out with the dot engine in under "
        "200 ms.",
        "A stateDiagram of the retry policy helps reviewers understand the "
        "backoff, but the shipped code implements jittered exponential "
        "retry in 18 lines.",
        # a single ASCII arrow is ordinary prose and is NOT diagram markup
        "The pipeline writes to a temp file and then renames it, so the "
        "consumer never sees a partial write.",
    ]
    for p in prose:
        assert not IL._is_diagram_markup(p), p
        assert not IL._is_junk(p), p
        assert not buffer_store.is_junk(p), p



def test_package_index_file_listing_is_gated_on_both_paths():
    """PyPI files-page label chain must die on BOTH gates; prose survives.

    Live 16.09.26 (found while verifying the diagram gate):
    cycle_f_multi_domain stored
    `B view details ) Uploaded Jun 28, 2024 Python 2 Python 3 File details
     Details for the file openpyxl-3.`
    -- a package files-page label chain with zero prose, accepted because
    the version digits fed the technical-signal gate.

    The guard needs TWO INDEPENDENT label markers, so a real sentence that
    merely cites a release and a date stays learnable.
    """
    import buffer_store

    leak = (
        "B view details ) Uploaded Jun 28, 2024 Python 2 Python 3 "
        "File details Details for the file openpyxl-3."
    )
    assert IL._is_package_index_chrome(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak

    prose = [
        # one marker only: a release + a date, in a real sentence
        "openpyxl 3.1 was uploaded in June 2024 and writes roughly 400k "
        "cells per second, which is 3x faster than the pure-python writer.",
        "The PyPI files page exposes each wheel as a download link with "
        "its upload date, and a scraper should read the JSON API instead "
        "of parsing HTML.",
        "The library still ships a Python 2 compatible shim, but Python 3 "
        "is the supported target and the shim is removed in the 4.0 "
        "release.",
        "Upgrading to openpyxl 3.1.2 fixed the memory blowup on large "
        "sheets, cutting peak RSS from 1.8 GB to 240 MB in our benchmark.",
    ]
    for p in prose:
        assert not IL._is_package_index_chrome(p), p
        assert not IL._is_junk(p), p
        assert not buffer_store.is_junk(p), p



def test_course_landing_cta_is_gated_on_both_paths():
    """Course/certification landing-page CTA must die on BOTH gates.

    Live 16.09.26 (third leak found in one verification run):
    cycle_g_security stored
    `Certified Agentic AI Security Expert (CAASE) Coming Soon Attack,
     poison, & harden AI agents: reasoning loops, memory stores,
     tool-calling, & multi-agent identity.`
    A sales headline plus a feature bundle, zero prose -- and it is
    ON-TOPIC for the security cycle, so relevance cannot be the
    discriminator. The page VOICE is.

    The guard needs a promo CTA AND a course-bundle phrase, so a real
    sentence that mentions a course, a certification, or the words
    attack/poison in their technical sense stays learnable.
    """
    import buffer_store

    leak = (
        "Certified Agentic AI Security Expert (CAASE) Coming Soon "
        "Attack, poison, & harden AI agents: reasoning loops, memory "
        "stores, tool-calling, & multi-agent identity."
    )
    assert IL._is_course_cta_chrome(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak

    prose = [
        # CTA phrase but no course bundle -> one marker only
        "The course on agent security is coming soon, but the threat "
        "model it covers is already documented in the OWASP agentic "
        "top-10 list for 2026.",
        "A certified Kubernetes administrator is expected to understand "
        "admission controllers, and the exam tests etcd backup and "
        "restore under 30 min.",
        "An attacker can poison the retrieval index during ingestion, "
        "so the pipeline must hash documents before indexing and "
        "re-verify the corpus.",
        "The curriculum for the security module covers prompt injection, "
        "tool poisoning and sandbox escapes, which matches the OWASP "
        "agentic top-10.",
    ]
    for p in prose:
        assert not IL._is_course_cta_chrome(p), p
        assert not IL._is_junk(p), p
        assert not buffer_store.is_junk(p), p
def test_market_ticker_chrome_is_gated_on_both_paths():
    """News-site market-ticker widget chrome (live 17.09.26).

    cycle_f_multi_domain stored
    "Walmart investors reject AI workplace report as automation expands in the
    US - The Economic Times Benchmarks CLOSED Nifty 23,118." - a real lede
    plus the ticker widget tail. 129 chars with digits, so the length trust
    and the technical-signal gate both fired.
    """
    import buffer_store

    leak = ("Walmart investors reject AI workplace report as automation expands"
            " in the US - The Economic Times Benchmarks CLOSED Nifty 23,118.")
    assert buffer_store.is_junk(leak), leak
    assert IL._is_junk(leak), leak

    # Second shape: the bare ticker widget with the site label.
    leak2 = "The Economic Times Benchmarks CLOSED Nifty 23,118."
    assert buffer_store.is_junk(leak2), leak2
    assert IL._is_junk(leak2), leak2

    prose = [
        "Benchmarks from the Nifty index showed a 2% gain while the rupee weakened against the dollar.",
        "We utilize a comprehensive dataset encompassing Nifty 100 intraday and daily price data from 2015 to 2024.",
        "Walmart investors reject AI workplace report as automation expands in the US.",
        "Chunked prefill enables dynamic, parallel processing of request prefixes, dramatically improving GPU utilization.",
        "The Economic Times reported that Indian IT firms are adopting AI agents for code review at scale.",
        "The agent benchmarks closed-source and open-weight models on the same harness.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s
def test_readme_changelog_bullet_list_is_gated_on_both_paths():
    """GitHub README changelog/news bullet list (live 17.09.26).

    cycle_h_efficiency stored "Inference: low decode overhead, best
    throughput, and TTFT News [2024-10-14] Add Rocm support [2024-10-6]
    Try it on Google Colab [2024-10-5] Add free Huggingface Demo ..." --
    251 chars with digits, so the length trust and the technical-signal gate
    both fired.
    """
    import buffer_store

    leak = ("Inference: low decode overhead, best throughput, and TTFT News "
            "[2024-10-14] \U0001f680 Add Rocm support [2024-10-6] "
            "\U0001f680 Try it on Google Colab [2024-10-5] "
            "\U0001f680 Add free Huggingface Demo : Huggingface Demo "
            "[2024-10-4] \u270f\ufe0f Updated the VPTQ tech report.")
    assert buffer_store.is_junk(leak), leak
    assert IL._is_junk(leak), leak

    prose = [
        "Add ROCm support for AMD GPUs to the inference backend.",
        "You can try it on Google Colab without installing anything locally.",
        "The benchmark tracks decode overhead, throughput, and TTFT across backends.",
        "Inference: low decode overhead, best throughput, and TTFT across all backends.",
        "Add free Hugging Face demo notebooks to the docs for quick evaluation.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s

def test_blog_archive_listing_is_gated_on_both_paths():
    """Blog ARCHIVE listing: date-stamped post titles, zero prose (live 17.09.26).

    cycle_c_github stored "LM Serving white-paper July 24, 2026 Thinking
    Machines Lab Inkling, Explained: Why Open Weights Change the Enterprise AI
    Math insights July 17, 2026 Top 7 AI Agent Platforms for Citizen
    Developers (2026) insights July 6, 2026 What Is a Good AI Harness?" --
    252 chars, so the >=90 length trust waved it through, and the dates
    satisfied the technical-signal gate.  No existing marker matched.

    The discriminator is STRUCTURAL, not topic-keyed: two or more
    "<label> <Month D, YYYY>" occurrences AND no period anywhere.  A listing
    concatenates entry titles and never ends a sentence; prose that merely
    NAMES two labels always carries a full stop, so it survives by
    construction (asserted below).
    """
    import buffer_store

    leak = ("LM Serving white-paper July 24, 2026 Thinking Machines Lab Inkling, "
            "Explained: Why Open Weights Change the Enterprise AI Math insights "
            "July 17, 2026 Top 7 AI Agent Platforms for Citizen Developers "
            "(2026) insights July 6, 2026 What Is a Good AI Harness?")
    assert buffer_store.is_junk(leak), leak
    assert IL._is_junk(leak), leak

    # Counter-cases: real prose that NAMES the same labels.  All must survive
    # BOTH gates -- a one-directional test would pass a broken marker.
    prose = [
        "The archive page lists posts under headings like Insights July 17, 2026 "
        "and News May 29, 2026, but the agent should parse the article body.",
        "A blog index that renders Insights July 17, 2026 News May 29, 2026 and "
        "Blog July 6, 2026 as separate anchors confuses the crawler, so the "
        "retriever must strip those labels before chunking the page.",
        "The release notes for vLLM 1.2 landed on Insights July 17, 2026, which "
        "the agent should diff against the previous tag.",
        "News May 29, 2026 reported governance failures across autonomous agent "
        "deployments",
        "White-paper July 24, 2026 Thinking Machines Lab published its findings "
        "on open weights",
        "Gartner predicts that by 2027 governance issues will trigger 40% of "
        "enterprises to demote or decommission autonomous AI agents.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s

def test_github_issue_page_chrome_is_gated_on_both_paths():
    """GitHub ISSUE page label chain (live 17.09.26).

    cycle_f_multi_domain stored "Description AnasBenAmor10 opened on Jul 23,
    2024 Issue body actions Confirm this is an issue with the Python library
    and not an underlying OpenAI API This is an issue with the Python library
    Describe the bug Error: You tried to access openai.embeddings ..." -- page
    furniture with zero insight.  The date satisfied the technical-signal gate
    and the length cleared the >=90 trust.

    The guard ANDs TWO independent template markers.  Every marker ALONE hits a
    real-prose counter-case (asserted below), so a single phrase would be a
    topic word rather than chrome.
    """
    import buffer_store

    leak = ("Description AnasBenAmor10 opened on Jul 23, 2024 Issue body actions "
            "Confirm this is an issue with the Python library and not an "
            "underlying OpenAI API This is an issue with the Python library "
            "Describe the bug Error: You tried to access openai.embeddings")
    assert buffer_store.is_junk(leak), leak
    assert IL._is_junk(leak), leak

    # Counter-cases: real prose that NAMES the same template markers.  Each of
    # these hits ONE marker only -- which is exactly why two are required.
    prose = [
        "A maintainer opened on Jul 23, 2024 an issue about the embedding "
        "client, and the agent should triage it automatically.",
        "The issue body actions menu on GitHub renders a confirm-this-is-an-"
        "issue checkbox that the crawler should skip.",
        "Confirm this is an issue with the Python library and not an unrelated "
        "bug in the downstream service.",
        "An issue was opened on the tracker, and the triage agent routed it to "
        "the retrieval component.",
        "The agent should read a GitHub issue body and summarize the "
        "reproduction steps for the maintainer.",
        "Describe the bug in two sentences, then list the exact reproduction "
        "command and the observed error output.",
        "Error: You tried to access openai.embeddings, but the installed "
        "version of the SDK does not expose it.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s

def test_plan_scaffold_bullet_echo_is_gated_on_both_paths():
    """The extractor's OWN plan echoed back as an insight (live 17.09.26).

    cycle_d_docs logged `doc-learn: "\n   - Input text: A very long, fragmented,
    and repetitive list of vLLM documentation topics/headings. It's essentially
    a dump of section titles from a vLLM documentation website.\n   - Goal:
    Extract the "ONE most valuable technical insight" from this` -- the 2B model
    returned its task plan instead of an insight. Same family as the documented
    plan-scaffold class, new paraphrase ("most valuable" where the older note
    recorded "most relevant/valuable").

    Keyed on the plan's BULLET+LABEL form.  The bare phrases are topic words:
    `input text:` and `one most valuable technical insight` each hit a real-prose
    counter-case below; the leading bullet-dash is what separates a plan line
    from a sentence.
    """
    import buffer_store

    leak = ('"\n   - Input text: A very long, fragmented, and repetitive list of '
            "vLLM documentation topics/headings. It's essentially a dump of "
            'section titles from a vLLM documentation website.\n   - Goal: '
            'Extract the "ONE most valuable technical insight" from this')
    assert buffer_store.is_junk(leak), leak
    assert IL._is_junk(leak), leak

    # Counter-cases: the same words inside real sentences (no bullet form).
    prose = [
        "The input text: field of a dataset card points at the original corpus, "
        "so the retriever can trace provenance.",
        "Extract the one most valuable technical insight from each retrieved "
        "document before writing the summary.",
        "The goal: reduce peak KV-cache memory while keeping decode throughput "
        "stable.",
        "Chunked prefill lets vLLM batch prompt tokens, cutting peak KV-cache "
        "memory during long-context inference.",
        "The agent should identify the goal of the task before choosing a tool.",
        "Documentation topics and headings are useful for navigation but carry "
        "no technical insight on their own.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s

    # A task description that legitimately discusses the plan format must live.
    meta = ("The extractor should emit one technical insight and never its own "
            "plan; a bullet like - Goal: extract the insight is a leak.")
    assert not buffer_store.is_junk(meta), meta
    assert not IL._is_junk(meta), meta


def test_financial_infobox_label_chain_is_gated_on_both_paths():
    """A company/Wikipedia infobox financial label chain must not train.

    Live 17.09.26 (cycle_e_competitors): the JetBrains infobox was buffered as
    "competitor intelligence" - 248 chars WITH digits, so the >=90 long-prose
    trust and the technical-signal gate both fired. Every naive literal was
    measured and REJECTED as a topic-word trap; the discriminator is the
    repeated (financial-label, year-in-parens) co-occurrence.
    """
    import buffer_store
    leak = ("CEO [ 1 ] Revenue 15,065,029,000 Czech koruna (2024) Operating income "
            "2,041,654,000 Czech koruna (2024) Net income 2,479,110,000 Czech koruna "
            "(2024) Total assets 17,426,568,000 Czech koruna (2024) Number of "
            "employees 2,800 [ 2 ] Website jetbrains .")
    assert buffer_store.is_junk(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_financial_infobox(leak)

    # Hostile counter-cases: real prose on the SAME topic/numbers must survive.
    prose = [
        "Llama 2 (2023) and Llama 3 (2024) improved long-context reasoning at lower cost.",
        "GPT-4 (2023) scored 91.2% while GPT-5 (2024) reached 95.1% on the same benchmark.",
        "The release (2024) followed the beta (2023) and the first preview (2022).",
        "Revenue 2024 was 15,065,029,000 and operating income 2,041,654 according to the filing.",
        "Operating income rose to 2,041,654 koruna while net profit stayed flat.",
        "The CEO reported revenue of 15 million Czech koruna for the 2024 fiscal year.",
        "The website lists revenue, operating income and net income ( 2024 ) in one table.",
        "Total assets ( 2023 ) were 17,426,568,000 koruna at the end of the year.",
        "Number of employees grew to 2,800 ( 2024 ) across the Czech and German offices.",
        "The agent benchmarked 15,065,029,000 tokens across 4 A100s in 2024.",
        "vLLM (2024) and SGLang (2024) both support chunked prefill for long context.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s

def test_maintenance_banner_is_gated_on_both_paths():
    """A service-status / maintenance BANNER must die on BOTH gates.

    Live 17.09.26 (junk class 26): cycle_b_papers stored

    `Login This service will be unavailable from Sep 18, 2026 19:00 PDT to
     Sep 19, 2026 2:00 PDT due to maintenance.`

    -- an arXiv status-page announcement, zero insight.  Both gates passed
    it: the timestamps fed the technical-signal gate (`_TECH_HINT_RE`'s
    alternation STARTS with a digit, so a date counts) and the length
    cleared the >=90 "long prose" trust.

    The guard needs TWO structural markers ANDed -- a dated timezone window
    (M1) and the announcement voice (M2) -- plus head<=40/tail<=40 around
    the announcement span.  A measured-and-REJECTED candidate was M1 alone
    (`unavailable` + one dated timezone stamp): it hit real prose about a
    downtime window.  Measured over 7,070 live corpus rows: 1 hit (the
    leaking row), 0 real-prose false positives, 0 regressions.
    """
    import buffer_store

    leak = ("Login This service will be unavailable from Sep 18, 2026 19:00 PDT "
            "to Sep 19, 2026 2:00 PDT due to maintenance.")
    assert IL._is_maintenance_banner(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak

    # Counter-cases: real prose that DESCRIBES a downtime window (same
    # markers) must stay learnable on BOTH gates -- a one-directional test
    # would pass a broken marker.
    prose = [
        # M1 present, but a remedy clause follows -> real context after the span
        "The vLLM maintenance window is Nov 3, 2026 22:00 UTC to Nov 4, 2026 "
        "02:00 UTC; requests are queued and replayed after the restart, which "
        "keeps throughput stable.",
        # prose that QUOTES the banner form -> head/tail carry real context
        "A row like service unavailable from Sep 18, 2026 19:00 PDT to Sep 19, "
        "2026 2:00 PDT due to maintenance is a banner, not an insight; the gate "
        "must reject it.",
        # a duration, not a from/to window
        "The service will be unavailable from Nov 3, 2026 22:00 UTC for four "
        "hours, so the retriever queues requests and replays them after the "
        "restart.",
        # M2 present ("due to maintenance"), no window
        "Nightly indexing was skipped due to maintenance of the storage backend, "
        "which delayed the embedding refresh by roughly two hours and shifted "
        "the eval run.",
        # a single stamp is not a window
        "Planned downtime on Oct 12, 2026 06:00 CET lasts two hours; the batcher "
        "pre-fills the KV cache to absorb the gap and keeps throughput stable.",
        # a clock-only window (no timezone) is ordinary prose
        "The vLLM service will be unavailable from 02:00 to 04:00 during the "
        "cluster upgrade, so the retriever queues requests and retries with "
        "exponential backoff.",
    ]
    for s in prose:
        assert not IL._is_maintenance_banner(s), s
        assert not IL._is_junk(s), s
        assert not buffer_store.is_junk(s), s

def test_changelog_bullet_chain_is_gated_on_both_paths():
    """A rendered release-note CHANGELOG chain must die on BOTH gates.

    Live 17.09.26 (junk class 27): cycle_d_docs stored

    `FLUX ( QEffWanPipeline , QEffFluxPipeline ) More [12/2025] Enabled
     disaggregated serving for GPT-OSS model [12/2025] Added support for
     wav2vec2 Audio Model facebook/wav2vec2-base-960h [12/2025] Added
     support for diffuser video generation model WAN 2.`

    -- a release-notes listing, zero prose.  Both gates passed it: the
    version stamps fed the technical-signal gate and the length cleared the
    >=90 "long prose" trust.

    Structural discriminator: three or more (version token, release verb)
    pairs AND no prose connector.  A listing is a CHAIN concatenated with
    spaces only; prose that cites several versions always LINKS them with
    grammar ("... , so ...", "... which together ...").  Same "a menu is a
    LABEL CHAIN, a sentence has grammar" rule as the nav-strip family.

    Measured over the live corpora (buffer + kta/log/world): 0 genuine-prose
    false positives, 0 regressions; 6 realistic listing shapes caught and
    0/16 hand-written counter-cases hit.  A two-entry listing is
    deliberately NOT caught -- two version+verb pairs are ambiguous against
    prose, so the rule stops at three.
    """
    import buffer_store

    leak = ("FLUX ( QEffWanPipeline , QEffFluxPipeline ) More [12/2025] Enabled "
            "disaggregated serving for GPT-OSS model [12/2025] Added support for "
            "wav2vec2 Audio Model facebook/wav2vec2-base-960h [12/2025] Added "
            "support for diffuser video generation model WAN 2.")
    assert IL._is_changelog_chain(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak

    listing = ("Version History [08/2026] Added FP8 quantization for MoE layers "
               "[09/2026] Fixed a race in the tokenizer server [10/2026] Enabled "
               "chunked prefill by default")
    assert IL._is_changelog_chain(listing), listing
    assert buffer_store.is_junk(listing), listing

    # Counter-cases: real prose that cites the same versions/verbs must stay
    # learnable on BOTH gates -- a one-directional test would pass a broken rule.
    prose = [
        # two releases linked by prose
        "The v0.9.1 release added streaming output and v0.9.3 improved KV-cache "
        "reuse, so the serving stack now sustains a 30% higher throughput on the "
        "same hardware.",
        # library versions, linked by grammar
        "PyTorch 2.4.0 added support for the new attention kernel while CUDA 12.4 "
        "improved the memory allocator, which together cut peak VRAM by 15% on "
        "the 70B benchmark.",
        # two bracketed versions with a prose tail
        "[1.2.1] improved KV-cache reuse and [1.2.2] added a scheduler tweak, so "
        "the agent must diff the two tags rather than trust the changelog headline.",
        # run-together pairs, but a prose connector follows
        "v1.0.0 added the loader v1.1.0 fixed the tokenizer crash so the upgrade "
        "path is safe for existing deployments and no migration script is needed.",
        # run-together triples that the row itself discusses as chrome
        "The tag sequence v0.9.1 added streaming v0.9.2 fixed the crash v0.9.3 "
        "improved reuse is exactly what the changelog page renders, so the agent "
        "should read the release notes instead.",
        # a meta sentence about the listing shape
        "A changelog row like [1.2.0] Added support for chunked prefill is a "
        "release bullet, not an insight, so the extractor must skip the version "
        "list entirely.",
    ]
    for s in prose:
        assert not IL._is_changelog_chain(s), s
        assert not IL._is_junk(s), s
        assert not buffer_store.is_junk(s), s


def test_trailing_read_time_header_is_stripped_not_stored():
    """A leading blog header that CLOSES with "<N> min read" is stripped (live 17.09.26).

    `cycle_d_docs` learned, verbatim:
      "Building is my Passion Post Cancel Efficient Fine-tuning with PEFT and
       LoRA Posted Aug 21, 2023 By Niklas Heidloff 3 min read Classic
       fine-tuning of Large Language Models typically changes most weights of
       the models which requires a lot of resources."
    The article's opening sentence IS the knowledge; the page furniture merely
    rode in front of it. This is a STRIP, so the counter-cases below (prose that
    legitimately MENTIONS a read time) are the point of the test -- a
    reject-pattern would have thrown real insights away.

    The guard is structural: the head before the read time must carry a real
    DATE literal and NO sentence terminator once the dates are removed. Page
    furniture is a label chain and never ends a sentence.
    """
    body = ("Classic fine-tuning of Large Language Models typically changes "
            "most weights of the models which requires a lot of resources.")
    leaks = [
        # the live row (author + posted-by + read time welded to the body)
        ("Building is my Passion Post Cancel Efficient Fine-tuning with PEFT "
         "and LoRA Posted Aug 21, 2023 By Niklas Heidloff 3 min read " + body),
        # documented pending shape: "Updated: <date> <N> min read <body>"
        ("Updated: September 7, 2026 15 min read As enterprises rapidly deploy "
         "large language models (LLMs) and AI agents across critical business "
         "functions, protecting sensitive data becomes harder."),
        # documented pending shape: "<category> · <date> · <N> min read <body>"
        ("General Compute · March 18, 2026 · 6 min read Quantization "
         "reduces the memory footprint of large language models without "
         "retraining them and keeps int4 accuracy within one point of fp16."),
    ]
    for leak in leaks:
        out = IL._strip_trailing_read_time_header(leak)
        assert out != leak.strip(), leak
        # the body must survive intact -- a strip, never a truncation
        assert all(w in leak for w in out.split()), out

    # the live row must now be learnable AS THE BODY (not rejected)
    out = IL._clean_insight(leaks[0])
    assert out.startswith("Classic fine-tuning of Large Language Models"), out

    # Counter-cases: prose that MENTIONS a read time must be untouched. All are
    # >=90 chars on purpose -- a shorter fixture would be judged by the
    # pre-existing short-candidate rule and would test a different gate.
    prose = [
        "A 32 min read of the vLLM docs shows that paged attention is the "
        "single biggest throughput lever for long-context serving.",
        "The write-up is a 6 min read; the quantization section alone recovers "
        "97% of fp16 accuracy at int4 on this benchmark, so the rest can be "
        "skipped without losing anything.",
        "Published research from Stanford in 2024 shows transformers scale "
        "predictably with data, compute and parameters when the recipe is stable.",
        "By contrast, the 2024 study found quantization recovers 97% of fp16 "
        "accuracy at INT4 with a negligible latency penalty on consumer GPUs.",
        # a sentence ABOUT the chrome shape -- proves the SHAPE is gated, not the topic
        "Posted Aug 21, 2023 By Niklas Heidloff is a byline, not knowledge, so "
        "the RAG pipeline should strip it before chunking the page for retrieval.",
    ]
    for s in prose:
        assert IL._strip_trailing_read_time_header(s) == s, s
        assert not IL._is_junk(s), s
def test_adwall_notice_is_rejected_and_prose_about_it_is_not():
    """Class 28 (live 17.09.26): an ad-blocker-off / subscribe notice is page
    furniture. `cycle_f_multi_domain` stored, verbatim:

      "Adblocker ausschalten Duden im Abo Nutzen Sie Duden online ohne Werbung
       und Tracking auf allen Endgeräten für nur 2,99 EUR/Monat."

    Both gates passed it: the "2,99" fed the technical-signal gate (whose
    alternation starts with \\d+) and the 104 chars cleared the >=90 "long
    prose" trust. The guard keys on the NOTICE's own CTA shape -- a blocker verb
    followed by an offer signal inside one span -- never on the topic, so prose
    ABOUT ad blockers or paywalls stays learnable.

    The measured verdicts (7177-row sweep over buffer + junk + learn log):
    2 hits, both the same leaking row, 0 real-prose rows.
    """
    leak = ("Adblocker ausschalten Duden im Abo Nutzen Sie Duden online ohne "
            "Werbung und Tracking auf allen Endgeräten für nur 2,99 €/Monat.")
    assert IL._is_adwall_notice(leak)
    assert IL._is_junk(leak)
    assert IL._clean_insight(leak) == ""

    # the writer gate must agree -- a second sink, not a second chance
    import buffer_store
    assert buffer_store._is_nav_chrome(leak)

    # Counter-cases: every one is >=90 chars (a shorter fixture would be judged
    # by the pre-existing short-candidate rule and test a different gate) and
    # every one names the topic while carrying no offer span.
    prose = [
        "The RAG crawler should detect an ad blocker interstitial and treat it "
        "as a paywall, then fall back to the cached copy instead of storing the "
        "notice text as knowledge.",
        "Detecting the ad-blocker-detection script of a news site is a "
        "fingerprinting problem: the page probes a bait element and reads its "
        "computed height before deciding to hide the article body.",
        "A paywall that hides an article behind a subscription costing 4,99 € "
        "per month must be skipped by the learner, since the call to action "
        "carries no technical fact at all.",
        # a meta sentence that discusses the chrome shape -- proves the SHAPE is
        # gated here, never the topic
        "The extractor must never store an ad-wall notice; a row telling the "
        "reader to switch off the ad blocker and subscribe is page furniture, "
        "not an insight.",
    ]
    for s in prose:
        assert not IL._is_adwall_notice(s), s
        assert not IL._is_junk(s), s
        assert IL._clean_insight(s) != "", s
def test_dated_header_slash_stack_is_stripped_not_stored():
    """Class 29 (live 17.09.26): a DATED HEADER STACK closed by a short label,
    welded to the article body. `cycle_g_security` learned, verbatim:

      "OWASP GenAI LLM Top 10 2026 OWASPGenAIProject Editor / August 3, 2026 /
       Resources OWASP Top 10 for LLM Applications 2026 is the latest
       community-driven guide to the most critical security risks facing
       applications powered by large language models."

    Both gates passed it: the date fed the technical-signal gate (whose
    alternation starts with \\d+) and the 247 chars cleared the >=90 "long
    prose" trust. This is the SECOND variant of the same page's header -- the
    class-14 rule already strips its "SECURITY resources Whitepapers/Guides ..."
    form -- so it is the same family, keyed on the same discriminator: a menu is
    a LABEL CHAIN, a sentence has grammar.

    A generic "<nav-run> <date> <body>" rule was measured and REJECTED on
    16.09.26 (it ate GitHub advisories and two prose counter-cases), so the
    counter-cases below are the point of this test: they must stay untouched.
    """
    body = ("OWASP Top 10 for LLM Applications 2026 is the latest "
            "community-driven guide to the most critical security risks facing "
            "applications powered by large language models.")
    leak = ("OWASP GenAI LLM Top 10 2026 OWASPGenAIProject Editor / August 3, "
            "2026 / Resources " + body)

    out = IL._strip_dated_header_slash_stack(leak)
    # a STRIP, never a rejection: the body survives byte-identical
    assert out == body, out
    assert all(w in leak for w in out.split()), out
    assert IL._clean_insight(leak) == body, IL._clean_insight(leak)
    # the WRITER gate must not refuse the cleaned row either
    import buffer_store
    assert not buffer_store._is_nav_chrome(body)

    # Counter-cases. The first two are the exact strings that killed the generic
    # rule on 16.09.26; the third carries the same slash shape in prose; the
    # fourth is the leak's own BODY (must never be re-stripped).
    prose = [
        "The paper compares German/English tokenizers on a March 3, 2026 "
        "benchmark and finds the multilingual vocabulary saves 12% of the "
        "token budget.",
        "Whitepapers/Guides are listed on the site; the August 3, 2026 revision "
        "adds three sections about retrieval evaluation and prompt injection.",
        "The team shipped the fix on March 3, 2026 / Users report the "
        "regression is gone from version 4.2 onwards, so the upgrade path is "
        "safe now.",
        body,
    ]
    assert len(prose) == 4 and prose[0] != prose[1]
    for s in prose:
        assert IL._strip_dated_header_slash_stack(s) == s, s


def test_page_meta_blurb_is_rejected():
    """A page's own `About <Title> ... is the latest ...` blurb is not a fact.

    Live 17.09.26 (class 31): `cycle_g_security` stored the OWASP landing
    page's self-description. The row is ON-TOPIC, so relevance cannot be the
    discriminator (the class-22 lesson) -- the page's own promotional voice is.
    Two markers ANDed, both anchored; each marker ALONE was measured over 8,078
    live rows and REJECTED (5 real prose sentences start `About <word>`, and a
    bare `is the latest` matches 2)."""
    import internet_learner as IL
    import buffer_store

    leak = ("About OWASP Top 10 for LLM Applications 2026 is the latest "
            "community-driven guide to the most critical security risks facing "
            "applications powered by large language models.")

    # the leak is refused on BOTH paths -- extraction gate retries, writer drops
    assert IL._is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak

    # Counter-cases: real prose that talks the same way must stay learnable.
    # `About <word>` alone and `is the latest` alone are ordinary English; only
    # the anchored pair is the page's meta voice. Kept >=90 chars so each one
    # clears the pre-existing short-candidate rule and actually reaches THIS one.
    prose = [
        "About half of the quantized models we benchmarked lose under 1 point "
        "of accuracy, so INT4 stays usable for retrieval in production.",
        "About GDPR compliance, the 2026 rules require a documented data-flow "
        "map for every retrieval index that stores user prompts.",
        "About OpenAI's safety framework, the interesting part is the tool-call "
        "allowlist rather than the wording of the model card itself.",
        "This paper is the latest work on post-training quantization, and it "
        "recovers 97% of fp16 accuracy at INT4 on the same benchmark.",
        "Home page rendering is the latest bottleneck our profiler found, so we "
        "moved the template compile out of the request path entirely.",
        "A leading nav label such as About welded to a meta description is page "
        "furniture, not an insight, so the extractor should strip it first.",
    ]
    assert len(prose) == 6 and prose[0] != prose[1]
    for s in prose:
        assert not IL._is_junk(s), s
        assert not buffer_store._is_nav_chrome(s), s

    # the rule is anchored at the START: a mid-sentence use is prose
    mid = ("The docs page opens with About OWASP Top 10 for LLM Applications "
           "2026 is the latest guide, and the index below lists all ten risks.")
    assert not IL._is_page_meta_blurb(mid), mid



def test_github_listing_row_is_rejected():
    """A GitHub repo-LISTING row is not an insight (live 17.09.26, class 32).

    `cycle_c_github` stored, verbatim:

      "Python 0 MIT 3,612 0 0 Updated Jun 13, 2025 ComfyUI Public Forked from
       Comfy-Org/ComfyUI The most powerful and modular stable diffusion GUI,
       api and backend with a graph/nodes interface."

    Language + counters + license + relative `Updated <date>` + the repo's own
    one-line description: a search-result listing row, zero insight. 186 chars
    cleared the >=90 "long prose" trust and the counters/license fed the
    technical-signal gate, so BOTH gates passed it and it trained.

    Keyed on the anchored LABEL PAIR, never on its parts: `Updated <Mon DD,
    YYYY>` alone is ordinary dates and `Public` alone is ordinary English
    ("Public health agencies ..."). Measured on the live corpora: 2 buffer hits
    (both ARE the leak), 0 of 3,056 longterm episodes, 0 of 323 test-asserted
    clean control literals. A bare `Forked from` was measured and REJECTED --
    it matches a real episode about openclaw being forked from a project.
    """
    import internet_learner as IL
    import buffer_store

    leaks = [
        # the verbatim logged row (counters + license + Updated + Public Forked)
        "Python 0 MIT 3,612 0 0 Updated Jun 13, 2025 ComfyUI Public Forked from "
        "Comfy-Org/ComfyUI The most powerful and modular stable diffusion GUI, "
        "api and backend with a graph/nodes interface.",
        # the sibling shape: a plain repo row (no fork), same listing band
        'Updated Oct 29, 2024 QuIP Public Code for paper: "QuIP: 2-Bit '
        'Quantization of Large Language Models With Guarantees" Uh oh!',
    ]
    for leak in leaks:
        assert IL._is_junk(leak), leak            # extraction gate retries
        assert buffer_store._is_nav_chrome(leak), leak   # writer gate drops
        assert IL._clean_insight(leak) == "", leak

    # Counter-cases: ordinary prose that mentions the same parts must survive.
    prose = [
        "Public health agencies published a joint report on March 3, 2026 about "
        "monitoring LLM outputs in clinical settings, and the guidance is final.",
        "The repository was updated on June 13, 2025 and the maintainers say the "
        "next release will move the renderer to a separate package entirely.",
        "The team open-sourced a new agent framework and the public code for the "
        "scheduler lives in a separate repository with its own benchmark suite.",
    ]
    assert len(prose) == 3 and prose[0] != prose[1]
    for s in prose:
        assert not IL._is_junk(s), s
        assert not buffer_store._is_nav_chrome(s), s

    # the rule needs the ANCHORED pair: a date far from the label is prose
    far = ("The dataset was Updated March 3, 2026 and the licence is MIT, but "
           "the Public sector team maintains a separate mirror for archives.")
    assert not IL._is_gh_listing_row(far), far

def test_news_card_stub_and_relative_time_nav_chain_are_gated_on_both_paths():
    """A news-card stub and a relative-time nav chain must not train.

    Live 17.09.26 (classes 33/34, cycle_e_competitors, found by reading the
    buffer tail -- neither ever appeared in buffer_junk.jsonl):

      `OpenAI introduces framework for reporting model misalignment Sep 17 7.`
      `Game Developer * 4 hours, 34 minutes ago For You Latest Trending Tech
       Updates: Week of Sep 14 4 updates Babylon.`

    The first is a card headline with its relative-date label and truncated
    counter glued on (70 chars, so the >=90 long-prose trust never applied);
    the second is a site widget whose counters read as technical signal.
    Both rules are ANDed with a TAIL/relative anchor because each part alone
    matches real prose (see the counter-cases below).
    """
    import buffer_store
    leaks = [
        "OpenAI introduces framework for reporting model misalignment Sep 17 7.",
        ("Game Developer \u2022 4 hours, 34 minutes ago For You Latest Trending "
         "Tech Updates: Week of Sep 14 4 updates Babylon."),
    ]
    for leak in leaks:
        assert buffer_store.is_junk(leak), leak
        assert IL._is_junk(leak), leak
        assert buffer_store._is_nav_chrome(leak), leak

    # Hostile counter-cases: ordinary dates, relative times, nav words and
    # roundup headers in real prose must ALL stay learnable.
    prose = [
        "The benchmark ran on Sep 17 2026 and produced 7 tokens per second.",
        "Model misalignment was reported in September 2026 by three labs.",
        "The job finished 4 hours, 34 minutes ago and the log is ready.",
        "It was posted 2 days ago. For the latest trending models, see Section 3.",
        "For you, the latest results and the trending models are in Table 2.",
        "Tech Updates: Week of Sep 14 shipped 4 new updates to the Babylon renderer.",
        "GPT-4 (2023) scored 91.2% while GPT-5 (2024) reached 95.1%.",
        "We trained for 7 epochs starting Sep 17 and saw a 12% gain.",
        "The release shipped on Aug 3 7 days after the freeze.",
        "vLLM ships 4 optimization levels (-O0, -O1, -O2, -O3) that trade startup "
        "time for performance.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s

def test_date_stamped_headline_listing_is_gated_on_both_paths():
    """A date-stamped headline listing (blog archive) must not train.

    Live 17.09.26 (class 35, found by reading the buffer tail after the
    class 33/34 fix -- again never in buffer_junk.jsonl):

      `June 27, 2025 Lessons Learned from Major Incident Response Cases June 8,
       2025 Top Cybersecurity Business Solutions You Need To Know February 1,
       2025 Hotel Hackers Using Fake Booking.`
      `July 2023 September 16, 2026 Building Materials/Construction ECMD Expands
       Southeast Presence with New DC in Ocala, FL September 16, 2026 AI
       Fastenal Quietly Acquired an ...`

    A date label glued to a headline, repeated. Measured: 2 buffer hits, both
    ARE the leak -> 0 real-prose FPs; 0/3,056 longterm_episodes. A bare
    `>=2 full dates` was REJECTED (15 live buffer hits + 2 hand FPs -- real
    rows carry a published AND an updated date).
    """
    import buffer_store
    leaks = [
        ("June 27, 2025 Lessons Learned from Major Incident Response Cases June 8, "
         "2025 Top Cybersecurity Business Solutions You Need To Know February 1, "
         "2025 Hotel Hackers Using Fake Booking."),
        ("July 2023 September 16, 2026 Building Materials/Construction ECMD Expands "
         "Southeast Presence with New DC in Ocala, FL September 16, 2026 AI Fastenal "
         "Quietly Acquired an Asset."),
    ]
    for leak in leaks:
        assert buffer_store.is_junk(leak), leak
        assert IL._is_junk(leak), leak
        assert buffer_store._is_nav_chrome(leak), leak
        assert buffer_store._is_date_heading_listing(leak), leak

    # Hostile counter-cases: dates, a slash category and roundup headers in real
    # prose must ALL stay learnable.
    prose = [
        "September 16, 2026 was the release date for the Ocala data center expansion.",
        "The report was published September 16, 2026 and updated September 17, 2026.",
        "Building Materials/Construction was the strongest sector in the 2026 survey.",
        "ECMD expanded its Southeast presence with a new distribution center in Ocala, FL.",
        "On July 2023 the team shipped the first prototype; in September 2026 they shipped v2.",
        "The paper (September 14, 2026) and its rebuttal (September 16, 2026) agree on the claim.",
        "Building Materials/Construction grew 12% between September 2025 and September 2026.",
        "The benchmark ran on Sep 17 2026 and produced 7 tokens per second.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s

def test_repo_page_tab_and_statbar_chrome_is_gated_on_both_paths():
    """A GitHub repo-page tab bar + language/size stat bar must not train.

    Live 17.09.26 (class 36, cycle_e_competitors):

      `Code Issues Releases 91 Packages Activity The glamourous AI coding agent
       for your favourite terminal <emoji> agentic-ai ai llms ravishing 4,181
       commits 161 branches 203 tags 972 MiB Go 98.`

    182 chars carrying counters, so the technical-signal gate fired; the class-AK
    rule keys on `Updated <date>` + `Public ...`, which this row has neither of.
    Measured: 1 buffer hit, IS the leak -> 0 real-prose FPs; 0/3,056
    longterm_episodes. Every part alone was REJECTED (see the counter-cases).
    """
    import buffer_store
    leak = ("Code Issues Releases 91 Packages Activity The glamourous AI coding agent "
            "for your favourite terminal agentic-ai ai llms ravishing 4,181 commits "
            "161 branches 203 tags 972 MiB Go 98.")
    assert buffer_store.is_junk(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak
    assert buffer_store._is_repo_tab_statbar_chrome(leak), leak

    # Hostile counter-cases: the same tab words, counts and language/size bar in
    # real prose must ALL stay learnable.
    prose = [
        "The repo's Code, Issues and Releases tabs all render server-side.",
        "We filed code issues releases were delayed by a week due to the freeze.",
        "GitHub shows commits, branches and tags for every repository.",
        "The project has 4,181 commits, 161 branches and 203 tags in total.",
        "The binary is 972 MiB and written in Go with 98% test coverage.",
        "Go 98% of the repository is written in Go according to GitHub.",
        "The packages tab lists 91 packages and 97 tags in the registry.",
        "We measured 972 MiB of RSS while the Go service handled 98 requests.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s
