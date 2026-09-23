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


def test_repeated_aggregator_feed_listing_is_gated_on_both_paths():
    """A Hacker-News-style feed row (>=2 items) must not be stored as prose.

    Live 17.09.26 (class 37): `cycle_b_papers` stored

        AshleysBrain 3 hours ago | 9 comments 77 Neovim have a ~$800k Bitcoin
        donation sitting untouched since 2023 by jakemanger 1 hour ago |
        6 comments 741 Nvidia announces native GPU programming in Rust
        (developer.

    -- submitter handle + relative time + `| N comments` + points + headline,
    repeated for a second item and cut off mid-word. 209 chars carrying digits
    and real headline prose, so the `>=90` length trust AND the technical-signal
    gate both fired; the class-34 rule needs the `For You / Latest / Trending`
    labels, which this shape does not have.

    The discriminator is REPETITION: a feed row repeats the
    `<relative-time> | N comments` unit, real prose uses it at most once.
    Measured: 1 buffer hit and it IS the leak -> 0 real-prose FPs; 0/3,056
    `longterm_episodes`.
    """
    import buffer_store
    leak = ("AshleysBrain 3 hours ago | 9 comments 77 Neovim have a ~$800k Bitcoin "
            "donation sitting untouched since 2023 by jakemanger 1 hour ago | "
            "6 comments 741 Nvidia announces native GPU programming in Rust (developer.")
    assert buffer_store.is_junk(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak
    assert buffer_store._is_hn_feed_listing_chrome(leak), leak
    assert IL._is_hn_feed_listing_chrome(leak), leak

    # Hostile counter-cases: the same handles, relative times, points and
    # comment counts in real prose must ALL stay learnable. The first one is the
    # single-occurrence form the rule must NOT flag.
    prose = [
        "The review took 2 days ago | 4 comments per reviewer were recorded.",
        "The model was benchmarked 3 hours ago and took 9 comments to converge.",
        "Neovim received a large Bitcoin donation the maintainers left untouched since 2023.",
        "Nvidia announced native GPU programming in Rust for its developer toolchain.",
        "The agent parsed 741 comments and counted 77 unique titles.",
        "A user donated 800k USD worth of Bitcoin to the project in 2023.",
        "Comments are ranked by score; the top item had 741 points and 6 comments.",
        "The pipeline finished 3 hours ago with 9 comments in the changelog.",
        "GPU programming in Rust was announced with 6 example kernels.",
        "Training ran for 3 hours | the loss dropped to 0.77 over 9 epochs.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s
        assert not buffer_store._is_hn_feed_listing_chrome(s), s


def test_marketing_hero_cta_chain_is_gated_on_both_paths():
    """A landing-page hero CTA chain (availability + CTA + [*] + brag) is chrome.

    Live 17.09.26 (class 38): stored three times in one buffer, once in German
    (`cycle_e_competitors`) and twice in English (rows 17 and 87):

        Available as a terminal interface, desktop app, and IDE extension Read
        docs The open source AI coding agent [*] With over 195,000 GitHub
        stars, 950 contributors, and over 13,000 commits, OpenCode is used and
        trusted by over 16M de

    -- availability line + nav CTA + product tagline + `[*]` footnote marker +
    the adoption-brag counter sentence. The counters and the CTA verb made every
    existing gate pass; `_is_nav_list` wants >=6 TitleCase tokens with no comma.

    Marker = `[*]` immediately followed by the brag opener `With over` / `Mit
    ueber`. Measured: 3 live buffer hits, ALL THREE are this leak -> 0 real-prose
    FPs; 0/3,056 `longterm_episodes`. The looser `(Read docs|Doku lesen) ...
    [*]` form was REJECTED on measurement (3 control FPs).
    """
    import buffer_store
    leaks = [
        ("Terminal-Interface, Desktop-App und IDE-Extension Doku lesen Der Open-Source "
         "AI-Coding-Agent [*] Mit \u00fcber 195,000 GitHub-Stars, 950 Contributors und "
         "\u00fcber 13,000 Commits wird OpenCode von \u00fcber 16M Entwickler:innen jeden Monat genut"),
        ("Available as a terminal interface, desktop app, and IDE extension Read docs The open "
         "source AI coding agent [*] With over 195,000 GitHub stars, 950 contributors, and over "
         "13,000 commits, OpenCode is used and trusted by over 16M de"),
    ]
    for leak in leaks:
        assert buffer_store.is_junk(leak), leak
        assert IL._is_junk(leak), leak
        assert buffer_store._is_nav_chrome(leak), leak
        assert buffer_store._is_marketing_hero_cta_chrome(leak), leak

    # Hostile counter-cases: footnote-style `[*]` markers, the CTA verb, the
    # "with over N" brag opener and German nav words in real prose must ALL stay
    # learnable.
    prose = [
        "The terminal interface, desktop app and IDE extension share one config file.",
        "Read docs before installing the open-source AI coding agent.",
        "OpenCode has over 195,000 GitHub stars, 950 contributors and 13,000 commits.",
        "Die Doku lesen ist wichtig, bevor man das Plugin installiert.",
        "We read the doku and installed the extension in the IDE.",
        "Terminal-Interface, Desktop-App und IDE-Extension nutzen dieselbe Config.",
        "Required fields are marked with [*] in the form below.",
        "Read docs to learn how the [*] wildcard expands in glob patterns.",
        "Doku lesen hilft, weil [*] die Pflichtfelder kennzeichnet.",
        "Read docs and [*] will be replaced by the matched text.",
        "With over 5,000 examples the dataset is large enough to train on.",
        "Mit \u00fcber 16M Entwicklern ist das Projekt gewachsen.",
        "The README has a [*] symbol; with over 3,000 forks the project is popular.",
        "Ein Stern [*] markiert Pflichtfelder im Formular.",
        "Use [*] to flag required fields in the config.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s
        assert not buffer_store._is_marketing_hero_cta_chrome(s), s


def test_platform_selector_listing_is_gated_on_both_paths():
    """An OS/arch selector glued to a subreddit feed row is chrome, not prose.

    Live 17.09.26 (class 39): `cycle_b_papers` stored

        OS/iOS: macOS Apple Silicon (arm64) macOS Apple Silicon (arm64,
        KleidiAI enabled) DISABLED macOS Intel (x64)\u2026 25 r/MachineLearning
        community 3h ago ICLR 2027 table font sizes [D] I am preparing an
        ICLR 2027 submission using the official LaTeX style.

    -- a release page's OS/architecture selector (with a DISABLED entry,
    truncated at `\u2026`) followed by a subreddit feed row (upvote count +
    `r/... community` + relative time) and a forum post title. The selector's
    counters and the `ICLR 2027` digits fed the technical-signal gate.

    Marker = a `macOS Apple Silicon (arm64)`-style selector within 200 chars of
    `r/<name> community`. Measured: 1 live buffer hit and it IS the leak -> 0
    real-prose FPs; 0/3,056 `longterm_episodes`. The arm64-paren+relative-time
    form was REJECTED on measurement (3 control FPs).
    """
    import buffer_store
    leak = ("OS/iOS: macOS Apple Silicon (arm64) macOS Apple Silicon (arm64, KleidiAI "
            "enabled) DISABLED macOS Intel (x64)\u2026 25 r/MachineLearning community "
            "3h ago ICLR 2027 table font sizes [D] I am preparing an ICLR 2027 "
            "submission using the official LaTeX style.")
    assert buffer_store.is_junk(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak
    assert buffer_store._is_platform_selector_listing_chrome(leak), leak

    # Hostile counter-cases: platform selectors, subreddit mentions and the
    # relative-time feed tail in real prose must ALL stay learnable.
    prose = [
        "macOS Apple Silicon (arm64) builds are released for every version.",
        "macOS Apple Silicon (arm64, KleidiAI enabled) gave the best throughput.",
        "The installer supports macOS Intel (x64) and Linux x64 targets.",
        "Supported targets: macOS Apple Silicon (arm64) and macOS Apple Silicon (arm64, KleidiAI enabled).",
        "Build matrix covers macOS Apple Silicon (arm64) and macOS Intel (x64).",
        "Install options are macOS Apple Silicon (arm64), Linux x64 and Windows x64.",
        "macOS Apple Silicon (arm64) support landed 2h ago in the nightly release.",
        "Community members on r/LocalLLaMA compared macOS Apple Silicon (arm64) throughput.",
        "The r/MachineLearning community 3h ago posted macOS Intel (x64) benchmarks.",
        "The Reddit thread had 25 comments and 3h ago it was still active.",
        "KleidiAI enabled the arm64 path and the r/MLOps community wrote about it.",
        "The paper was discussed on r/MachineLearning and got 25 comments.",
    ]
    for s in prose:
        assert not buffer_store.is_junk(s), s
        assert not IL._is_junk(s), s
        assert not buffer_store._is_platform_selector_listing_chrome(s), s


def test_byline_published_article_header_is_gated_on_both_paths():
    """Editorial chip + headline + mid-text byline + `Published` dateline (class 40).

    Live 17.09.26: two rows in the 300-row `online_buffer.jsonl` had passed BOTH
    gates and were never in `buffer_junk.jsonl` --

      "Pro Why CIOs are paying closer attention to physical security By Mark
       Coates Published 14 September 26 Connected physical security is
       reshaping how CIOs approach risk, data and resilience."
      "Pro Why every enterprise needs an AI model exit strategy By Ganesh
       Padmanabhan Published 15 September 26 Model flexibility helps
       enterprises protect workflows, institutional knowledge and control as
       AI evolves."

    An article-header byline run glued to the article's own lede. Both are
    >90 chars, so the length trust accepted them, and `14 September 26` /
    `15 September 26` fed the technical-signal gate. `_strip_byline_prefix`
    only removes a LEADING byline, so a byline sitting AFTER the headline
    (mid-text) survived every existing rule.
    """
    import buffer_store

    leaks = (
        "Pro Why CIOs are paying closer attention to physical security By Mark "
        "Coates Published 14 September 26 Connected physical security is "
        "reshaping how CIOs approach risk, data and resilience.",
        "Pro Why every enterprise needs an AI model exit strategy By Ganesh "
        "Padmanabhan Published 15 September 26 Model flexibility helps "
        "enterprises protect workflows, institutional knowledge and control "
        "as AI evolves.",
    )
    for text in leaks:
        assert IL._is_junk(text), text
        assert buffer_store._is_nav_chrome(text), text
        assert buffer_store._is_byline_published_article_header(text), text

    # counter-cases: real prose that merely LOOKS like byline + dateline
    clean = (
        "By Mark Coates Published research shows that connected physical "
        "security is reshaping how CIOs approach risk.",
        "The paper was published in September 2026 by the ACM and describes a "
        "new quantization method.",
        "Ganesh Padmanabhan wrote about AI model exit strategies in a 2024 "
        "enterprise report.",
        "By contrast, the 2024 study found quantization recovers 97% of fp16 "
        "accuracy at INT4.",
        "Published research from Stanford in 2024 shows transformers scale "
        "predictably with compute.",
        "Published 2026 benchmarks show vLLM serves twice the throughput of "
        "the naive pipeline at equal accuracy on a single A100.",
        "vLLM's PagedAttention reduces memory fragmentation by 60% while "
        "serving 2x the requests.",
    )
    for text in clean:
        assert not IL._is_junk(text), text
        assert not buffer_store._is_byline_published_article_header(text), text


def test_midtext_read_time_header_without_dateline_is_stripped():
    """Class 41 (live 17.09.26): the shipped read-time strip required a DATELINE
    in the head and a CAPITALISED body, so two live rows rode into the buffer:

      "AI Agents 11 min read AI Agent Cost Benchmarks: Tokens, Latency, and
       Dollars per Task Original 2026 benchmark: tokens, P95 latency, ..."
      "Start the challenge Blog 18 April 2026 / 24 min read 8 best open-source
       AI agent frameworks on GitHub in 2026 The best open-source AI agent ..."

    Row 1 has no date literal at all (category label only), row 2's body starts
    with a DIGIT ("8 best ..."). Both bodies are the knowledge, so this is a
    STRIP — and real prose that merely mentions a read time must stay intact.
    """
    leak_a = ("AI Agents 11 min read AI Agent Cost Benchmarks: Tokens, Latency, "
              "and Dollars per Task Original 2026 benchmark: tokens, P95 latency.")
    body_a = ("AI Agent Cost Benchmarks: Tokens, Latency, and Dollars per Task "
              "Original 2026 benchmark: tokens, P95 latency.")
    assert IL._strip_trailing_read_time_header(leak_a) == body_a
    assert IL._clean_insight(leak_a, 300) == body_a
    assert "min read" not in IL._clean_insight(leak_a, 300)

    leak_b = ("Start the challenge Blog 18 April 2026 / 24 min read 8 best "
              "open-source AI agent frameworks on GitHub in 2026 The best "
              "open-source AI agent frameworks in 2026: LangGraph, AutoGen.")
    body_b = ("8 best open-source AI agent frameworks on GitHub in 2026 The best "
              "open-source AI agent frameworks in 2026: LangGraph, AutoGen.")
    assert IL._strip_trailing_read_time_header(leak_b) == body_b
    assert IL._clean_insight(leak_b, 300) == body_b

    # Real prose that merely MENTIONS a read time carries lowercase words in the
    # head, so the label-chain guard must leave every one of these alone.
    clean = [
        "The blog post takes 5 min to read and explains ternary quantization at 1.58 bits.",
        "The 24 min read limit was generous for a 6-page report of the survey.",
        "The 11 min read time on that post is misleading; the quantization numbers matter.",
        "Reading time was about 8 min for the 12-page survey, so the model processed it in one pass.",
        "The dataset contains 12 min read windows of EEG signal per subject.",
    ]
    for text in clean:
        assert IL._strip_trailing_read_time_header(text) == text, text

def test_metric_row_fragment_is_gated_on_both_paths():
    """A benchmark TABLE row: column labels + counts, no sentence (class 43).

    Live 17.09.26: `cycle_g_security` stored

      "Attack Success Rate (360 runs — 60 payloads × 2 models × ~3 reps)
       Paradigm gemma4-e2b (local, Ollama) claude-haiku-4-5 ETP 73."

    A benchmark table row welded together -- no verb anywhere. It cleared both
    gates through the number-fed hole (`_TECH_HINT_RE` starts with `\d+`, so the
    counts count as technical signal) plus the >=90 length trust.

    The discriminator is the same "a menu is a LABEL CHAIN, a sentence has
    grammar" rule as the nav-strip family: a parenthesised ratio of counts or a
    tilde-approximated product AND no finite verb. Measured 1 hit over the live
    300-row buffer, 0 real-prose FPs across the counter-cases below (several of
    which reuse the LEAK'S OWN words inside a sentence).
    """
    import buffer_store

    leak = ("Attack Success Rate (360 runs \u2014 60 payloads \u00d7 2 models "
            "\u00d7 ~3 reps) Paradigm gemma4-e2b (local, Ollama) "
            "claude-haiku-4-5 ETP 73.")
    assert IL._is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak
    assert IL._is_metric_row_fragment(leak), leak
    assert buffer_store._is_metric_row_fragment(leak), leak

    # Counter-cases: real prose that carries the SAME counts / the same ratio /
    # the same multiplication sign and must stay learnable. Every one has a verb.
    clean = (
        "The benchmark suite (12 models \u00d7 4 seeds) reports a median attack "
        "success rate of 41% at int4, which is 8 points above the fp16 baseline.",
        "Attack success rate (360 runs \u2014 60 payloads \u00d7 2 models) was "
        "measured on the local Ollama build and landed at 73% for the hosted model.",
        "An attack success rate of 73% (360 runs \u2014 60 payloads \u00d7 2 models "
        "\u00d7 ~3 reps) is alarmingly high for a production agent, so the registry "
        "now validates manifests.",
        "A sweep over 12 seeds \u00d7 4 learning rates took 3 hours on one A100, "
        "and the best run reached 71.2% exact match.",
        "The harness reports 360 runs, 60 payloads and 2 models, yet the aggregate "
        "success rate was never published by the vendor.",
        "Group relative policy optimization assigns credit per turn (3 turns "
        "\u00d7 2 agents) which is what makes a multi-agent rollout trainable.",
        "Quantization stores 32-bit floats as 8-bit integers (4 bytes \u2192 1 byte), "
        "so a 7B model needs about 3.5 GB instead of 28 GB at inference time.",
    )
    for text in clean:
        assert not IL._is_metric_row_fragment(text), text
        assert not IL._is_junk(text), text
        assert not buffer_store._is_metric_row_fragment(text), text



def test_masthead_nav_chain_is_stripped_from_the_insight():
    """class 43 (17.09.26): a site's section menu welded to its own lede.

    Live: cycle_a_technews stored
      "Blog Guides Insights Breaking story Breaking AI News Salesforce Launches
       Koa: CRM Reasoning Model for Agentforce Salesforce unveils Koa at
       Dreamforce 2026, a reasoning model trained on 27 years of CRM data ..."
    The lede behind the menu IS the knowledge, so this is a STRIP, not a
    reject. The discriminator is a CHAIN of masthead labels (>= 2 in the first
    80 chars with no sentence terminator in front of the last one) -- each
    label alone is ordinary English, which is why every single-phrase marker
    was measured and rejected.
    """
    leak = ("Blog Guides Insights Breaking story Breaking AI News Salesforce "
            "Launches Koa: CRM Reasoning Model for Agentforce Salesforce unveils "
            "Koa at Dreamforce 2026, a reasoning model trained on 27 years of CRM "
            "data that delivers 3x fewer errors on sales tasks.")
    stripped = IL._strip_masthead_nav_chain(leak)
    assert "Blog Guides Insights" not in stripped
    assert "Breaking AI News" not in stripped
    assert stripped.startswith("Salesforce Launches Koa:")
    assert IL._strip_masthead_nav_chain(stripped) == stripped      # idempotent
    # the whole pipeline must land on the lede, free of the menu
    cleaned = IL._clean_insight(leak, 300)
    assert cleaned, "the lede is real prose and must survive"
    assert not IL._MASTHEAD_NAV_RE.search(cleaned), cleaned

    # a bare label is a legit headline / sentence -- must stay BYTE-IDENTICAL
    clean = (
        "Blog Guides Insights are three content formats we publish for developers.",
        "The blog post explains how guides and insights differ from tutorials.",
        "Breaking story coverage of model releases dominated the tech news cycle.",
        "Breaking AI news dominated the cycle this week in the agent space.",
        "Breaking AI News: Anthropic ships a new tool-use API for agents.",
        "Our Breaking AI News desk covers model launches every week.",
        "Blog posts, guides, and insights about LLMs are published weekly.",
        "We publish a Blog, Guides and Insights sections. Breaking AI News is our "
        "flagship desk.",
    )
    for text in clean:
        assert IL._strip_masthead_nav_chain(text) == text.strip(), text



def test_source_verdict_about_the_page_is_gated_on_both_paths():
    """class 44 (17.09.26): the distillation LLM's verdict ABOUT the input.

    Live: cycle_h_efficiency learned
      "The provided text is a boilerplate webpage footer containing no
       technical information, only navigation links and legal notices."
    That is a SOURCE ASSESSMENT, not knowledge -- but the word "technical" fed
    the technical-signal gate and 127 chars cleared the short-text check.
    The discriminator is the page-furniture vocabulary welded to the source
    noun, NOT any single word.
    """
    import buffer_store
    leak = ("The provided text is a boilerplate webpage footer containing no "
            "technical information, only navigation links and legal notices.")
    assert IL._is_junk(leak), "learner gate must reject a verdict about the page"
    assert buffer_store._is_nav_chrome(leak), "writer gate must reject it too"
    assert IL._is_source_verdict_chrome(leak)
    # a second live variant of the same verdict family
    assert IL._is_source_verdict_chrome(
        "The given page consists of a cookie banner and legal notices.")
    assert IL._is_source_verdict_chrome(
        "Extracted content contains only navigation links and site furniture.")

    # real prose that merely NAMES the source must stay learnable
    clean = (
        "The provided text is a transcript of the talk and includes the full "
        "speaker notes.",
        "The paper's provided text covers three quantization schemes for LLMs.",
        "Boilerplate license headers should be stripped before parsing the repository.",
        "The provided text is a code snippet implementing flash attention.",
        "Their documentation provides a technical overview of the serving stack.",
        "The agent's provided input had no technical signal, so the cycle rejected it.",
        "The extracted content covers a technical comparison of GPU compute platforms.",
    )
    for text in clean:
        assert not IL._is_source_verdict_chrome(text), text
        assert not IL._is_junk(text), text
        assert not buffer_store._is_nav_chrome(text), text


def test_operator_spotlight_widget_row_is_gated_on_both_paths():
    """Class 45 (live 17.09.26): a widget row whose own label repeats."""
    import buffer_store
    import internet_learner as IL

    leak = (
        "July 24, 2026 cahaseler 016 Operator Spotlight: Scripts Are Cheaper "
        "Than Tokens Operator Spotlight: Brocktree runs ~200 AI agents in "
        "SpaceMolt through one stationary hub bot, and trusts none of them to "
        "plan."
    )
    assert IL._is_operator_spotlight_chain(leak)
    assert IL._is_junk(leak)
    assert buffer_store._is_nav_chrome(leak)

    clean = (
        "Our operator spotlight feature rotates weekly across the hub bots and their scripts.",
        "About the operator spotlight: two scripts cut token cost by 40% in the agent pipeline.",
        "The operator spotlighted three scripts that cut token cost by 40% in the pipeline.",
        "Brocktree runs ~200 AI agents in SpaceMolt through one stationary hub bot.",
    )
    for text in clean:
        assert not IL._is_junk(text), text
        assert not buffer_store._is_nav_chrome(text), text


def test_preprint_header_chain_is_gated_on_both_paths():
    """Class 46 (live 17.09.26): paper title + slash-date + project title."""
    import buffer_store
    import internet_learner as IL

    leak = "Activations for 1-bit LLMs 10/21/2024 1-bit AI Infra: Part 1."
    assert IL._is_preprint_header_chain(leak)
    assert IL._is_junk(leak)
    assert buffer_store._is_nav_chrome(leak)

    clean = (
        "The paper was published on 10/21/2024 and the results show a 3x speedup in inference throughput.",
        "We benchmarked 4-bit vs 8-bit weights on 10/21/2024 Results were 2x faster, but accuracy dropped.",
        "Results from GPT-5 on 10/21/2024 showed gains.",
        "The 10/21/2024 release of the framework added native quantization support.",
        "Native 4-bit Activations with Hadamard Transformation for 1-bit LLMs Published in arXiv , 2025 Abstract : Efficient deployment",
        "The benchmark on 10/21/2024 GPT-4 model showed a 3x throughput gain over the baseline.",
    )
    for text in clean:
        assert not IL._is_preprint_header_chain(text), text
        assert not IL._is_junk(text), text
        assert not buffer_store._is_nav_chrome(text), text


def test_personal_blog_nav_chain_is_gated_on_both_paths():
    """Class 47 (live 17.09.26): `About \u2715 ... Work Writing About ...` header run."""
    import buffer_store
    import internet_learner as IL

    leak = (
        "About \u2715 AAKASH SETHI Work Writing About June 26, 2026 \u00b7 AI "
        "Engineering Haystack: Open-Source AI Framework for Production Ready "
        "Agents, RAG \u25b6 Listen Haystack just hit the front page of HN, and "
        "most engineers building \u201cRAG\u201d still don\u2019t know what it does."
    )
    assert IL._is_personal_blog_nav_chain(leak)
    assert IL._is_junk(leak)
    assert buffer_store._is_nav_chrome(leak)

    clean = (
        "About 200 agents run in the simulation, and none of them plan explicitly.",
        "Work writing about AI frameworks is common, and About pages rarely help the agent.",
        "June 26, 2026 was the release date of the AI engineering blog post about Haystack.",
        "Haystack is an open-source AI framework for production-ready agents with RAG support.",
    )
    for text in clean:
        assert not IL._is_personal_blog_nav_chain(text), text
        assert not IL._is_junk(text), text
        assert not buffer_store._is_nav_chrome(text), text


def test_pricing_hero_chrome_is_gated_on_both_paths():
    """Class 48 (live 17.09.26): a competitor landing-page promo banner."""
    import buffer_store
    import internet_learner as IL

    leak = (
        "Flash 75% OFF base pricing for a limited time Powered by IDEs Proven "
        "in Benchmarks IntelliJ IDEA Engine Top performer on SWE-Rebench 10+ "
        "models supported via BYOK Plan on a powerful model, implement on a "
        "fast one."
    )
    assert IL._is_pricing_hero_chrome(leak)
    assert IL._is_junk(leak)
    assert buffer_store._is_nav_chrome(leak)

    clean = (
        "The discount was 30% off list pricing for a limited time, the vendor said.",
        "Flash pricing dropped 75% off the base rate for a limited time last quarter.",
        "Powered by IDEs, the plugin benchmarks every supported model on SWE-bench.",
        "Plan on a powerful model and implement on a fast one to save cost, the docs say.",
    )
    for text in clean:
        assert not IL._is_pricing_hero_chrome(text), text
        assert not IL._is_junk(text), text
        assert not buffer_store._is_nav_chrome(text), text

def test_nav_widget_run_chrome_is_gated_on_both_paths():
    """Class 50 (live 18.09.26): a document-hosting page's nav-widget run."""
    import buffer_store
    import internet_learner as IL

    leak = (
        "Language , English Upload Sign in Sign in Download free for 30 days "
        "Documents Get started with the community\u2019s uploads Skip carousel Go "
        "to previous items Overview (selected) Categories Go to next items Footer "
        "menu Back to top About About Scribd, Inc."
    )
    assert IL._is_nav_widget_run_chrome(leak)
    assert IL._is_junk(leak)
    assert buffer_store._is_nav_widget_run_chrome(leak)
    assert buffer_store._is_nav_chrome(leak)

    clean = (
        "Skip the carousel and go to the previous items to review the earlier benchmarks.",
        "The footer menu links to the About page and back to the top of the document.",
        "Back to top of the article, the footer menu lists the licence.",
        "The UI has a skip carousel button, a go to next items control, and a footer menu component.",
        "We documented back to top, footer menu, and about scribd as the three nav affordances.",
        "Scribd, Inc. publishes documents uploaded by its community of readers and authors.",
        "Sign in with your account to download the free whitepaper about LLM serving on local GPUs.",
        "Upload the dataset to the repository before signing in to the document store.",
    )
    for text in clean:
        assert not IL._is_nav_widget_run_chrome(text), text
        assert not IL._is_junk(text), text
        assert not buffer_store._is_nav_widget_run_chrome(text), text
        assert not buffer_store._is_nav_chrome(text), text

def test_news_byline_share_header_is_gated_on_both_paths():
    """Class 51 (live 18.09.26): a broadcast-news byline + dateline + Share header."""
    import buffer_store
    import internet_learner as IL

    leak = (
        "ABCNews By Mason Leib Thursday, April 30, 2026 Share A software company "
        "founder went viral this week after sharing a post on social media "
        "describing how an AI agent threw his business into chaos for 30 hours."
    )
    assert IL._is_news_byline_share_header(leak)
    assert IL._is_junk(leak)
    assert buffer_store._is_news_byline_share_header(leak)
    assert buffer_store._is_nav_chrome(leak)

    clean = (
        "ABCNews reported that a software company founder went viral after an AI agent wiped his database.",
        "By Mason Leib, the article described how an AI agent threw the business into chaos for 30 hours.",
        "Share the benchmark results with the team before Thursday, April 30, 2026.",
        "The post was shared on social media describing how an AI agent threw his business into chaos.",
        "Thursday, April 30, 2026 was the release date of the model.",
        "The release was announced on Thursday, April 30, 2026 by the research team.",
        "By Mason Leib and colleagues, the study shows that quantization helps at scale.",
        "By contrast, the 2026 study found that longer training does not always help.",
        "Share a post on social media is not how an engineer should report an incident.",
        "Cursor is a coding agent by Anysphere that lost control and wiped a company database.",
    )
    for text in clean:
        assert not IL._is_news_byline_share_header(text), text
        assert not buffer_store._is_news_byline_share_header(text), text

def test_arxiv_pdf_listing_header_is_gated_on_both_paths():
    """An arXiv LISTING/abstract-modal header is not knowledge (live 18.09.26).

    cycle_h_efficiency stored, verbatim from the buffer row:
      "PDF of the paper titled QuIP: 2-Bit Quantization of Large Language
       Models With Guarantees, by Jerry Chee and 3 other authors View PDF
       HTML (experimental) Abstract: This work studies post-training
       parameter quantization in large language models (LLMs)."
    251 chars: a title (often truncated, with no leading "PDF of the paper
    titled") welded to a byline count and the page's own "View PDF HTML
    (experimental)" controls. The digits fed the technical-signal gate and
    the length cleared the >=90 "long prose" trust, so BOTH gates passed it.

    Sibling of the class-10 ABSTRACT-PAGE chain, not the same row: these
    carry the listing controls with one or zero of the class-10 labels, so
    the old `view a pdf of the paper titled` marker never fired. The control
    pair is unique to the document viewer — real prose that merely mentions
    viewing a PDF or an experimental HTML build carries neither half.
    """
    leaks = (
        "PDF of the paper titled QuIP: 2-Bit Quantization of Large Language "
        "Models With Guarantees, by Jerry Chee and 3 other authors View PDF "
        "HTML (experimental) Abstract: This work studies post-training "
        "parameter quantization in large language models (LLMs).",
        "Enhancing Low-Bit Quantization of LLMs Without GPUs, by Jaewoo Song "
        "and Fangzhen Lin View PDF HTML (experimental) Abstract: The "
        "quantization of large language models (LLMs) is crucial for "
        "deploying them on devices with limited computational resources.",
        "Techniques for Large Language Models, by Yutong Liu and 2 other "
        "authors View PDF HTML (experimental) Abstract: For large language "
        "models (LLMs), post-training quantization (PTQ) can significantly "
        "reduce memory footprint and computational overhead.",
    )
    import buffer_store
    for text in leaks:
        assert IL._is_arxiv_abstract_chrome(text), text
        assert IL._is_junk(text), text
        assert buffer_store._is_arxiv_abstract_chrome(text), text
        assert buffer_store._is_nav_chrome(text), text
        assert IL._clean_insight(text) == "", text

    # counter-cases: real prose about papers, PDFs and bylines must survive
    for text in (
        "The PDF of the paper titled Attention Is All You Need was cited "
        "more than 100,000 times and reframed sequence modelling.",
        "You can view the PDF or the HTML version of the paper on arXiv; "
        "both links ship the same 2-bit quantization tables.",
        "The paper, by Jerry Chee and three other authors, shows that 2-bit "
        "quantization preserves 96% of fp16 accuracy on Qwen3.",
        "The study by Jaewoo Song and Fangzhen Lin reports that low-bit "
        "quantization lets a 7B model run on a CPU-only laptop.",
        "Viewing a PDF is faster than rendering the HTML page when the "
        "document is longer than about fifty pages.",
        "The abstract: This work studies post-training parameter "
        "quantization in large language models and reports a 4x memory cut.",
        "Access Paper: view the full text on the publisher site once the "
        "embargo lifts next quarter.",
        "BitNet stores weights in ternary form, so a 7B model fits in about "
        "2 GB at int4 with no measurable accuracy loss.",
    ):
        assert not IL._is_arxiv_abstract_chrome(text), text
        assert not buffer_store._is_arxiv_abstract_chrome(text), text
        assert not IL._is_junk(text), text
        assert buffer_store.is_junk(text) is False, text
        assert IL._clean_insight(text), text

def test_docs_cta_serp_run_is_gated_on_both_paths():
    """A SERP run welded to a docs site's `Welcome to ...` CTA is not knowledge.

    Live 18.09.26 (class 53), verbatim from the buffer row:
      "Efficient Transformers Library - GitHub — This library provides
       reimplemented blocks of LLMs which are used to make the models
       functional and highly performant on …; Welcome to
       Efficient-Transformers Documentation! — Install
       Efficient-Transformers. 1. Model download and Optimize ..."
    Two search-result titles each with its `Title — snippet` body, welded by
    `…;`, the second carrying the docs site's own page intro.

    A GENERIC `…;` / multi-snippet rule was TRIED and REJECTED — see
    test_german_dictionary_serp_chrome_is_gated_on_both_paths below, which
    records that it was already rejected because real rows (vLLM parallelism
    and quantization) carry genuine technical prose across the same separator.
    The discriminator is therefore the docs site's OWN navigation label
    sitting directly on the welded boundary, not the separator itself.
    """
    leak = (
        "Efficient Transformers Library - GitHub — This library provides "
        "reimplemented blocks of LLMs which are used to make the models "
        "functional and highly performant on …; Welcome to "
        "Efficient-Transformers Documentation! — Install "
        "Efficient-Transformers. 1. Model download and Optimize for Cloud "
        "AIxxx (AI1"
    )
    import buffer_store
    assert IL._is_docs_cta_serp_run(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store._is_docs_cta_serp_run(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak
    assert IL._clean_insight(leak) == "", leak

    # counter-cases: real vLLM rows across the SAME `…;` separator must
    # survive — they are exactly the prose the rejected generic rule ate, and
    # a real sentence that mentions a welcome or a documentation install step
    for text in (
        "Parallelism and Scaling - vLLM — It's often advantageous to "
        "exploit the inherent parallelism of experts …; Optimization and "
        "Tuning - vLLM — Data parallelism can be combined with the other "
        "parallelism strategies.",
        "Quantization Format Comparison 2026 — GGUF, AWQ, GPTQ, EXL2, "
        "MLX, FP8, NF4, INT4, INT8. Quality degradation, throughput …; 4.8",
        "The docs welcome new users to the quantization guide and explain "
        "the install steps for GGUF and AWQ checkpoints.",
        "The docs say: welcome to efficient transformers documentation, then "
        "install it and download a model.",
        "The model runs on …; then it stopped and reported a 3x speedup.",
    ):
        assert not IL._is_docs_cta_serp_run(text), text
        assert not buffer_store._is_docs_cta_serp_run(text), text
        assert not IL._is_junk(text), text
        assert buffer_store.is_junk(text) is False, text

    # Helper-level check only: `_NAV_CHROME` already carries the 
    # PRE-EXISTING marker "welcome to the", so a page-intro sentence is 
    # gated by that older rule and not by this one. Isolate the new helper 
    # here so the test can never report a pre-existing rule as a class-53 
    # regression.
    intro = (
        "Welcome to the quantization documentation — it explains the "
        "install steps for GGUF and AWQ checkpoints."
    )
    assert not IL._is_docs_cta_serp_run(intro), intro
    assert not buffer_store._is_docs_cta_serp_run(intro), intro

def test_marketing_hero_without_star_marker_is_gated_on_both_paths():
    """The SAME landing-page hero WITHOUT the `[*]` marker is not knowledge.

    Live 18.09.26 (class 54), verbatim from the buffer row -- stored TWICE,
    byte-identical (rows 14 and 297):
      "Any Editor Terminal interface, desktop app, and IDE extensions Read the
       docs \u2192 Open Source AI Coding Agent With over 160,000 GitHub Stars,
       900 contributors, and over 13,000 commits, OpenCode is used and trusted
       by over 7."
    The class-38 marker (`[*]` immediately followed by the brag opener) never
    fired because this render uses a `\u2192` bullet instead of the footnote
    marker -- the existing helper's guard was one variant too narrow (the same
    pattern as root cause AO), so the guard was relaxed rather than a fourth
    class added.

    The discriminator is the FULL adoption-brag triple in one sentence (stars
    AND contributors AND commits), which a landing-page hero writes as a list
    and real prose does not.
    """
    leak = (
        "Any Editor Terminal interface, desktop app, and IDE extensions Read "
        "the docs \u2192 Open Source AI Coding Agent With over 160,000 GitHub "
        "Stars, 900 contributors, and over 13,000 commits, OpenCode is used "
        "and trusted by over 7."
    )
    import buffer_store
    assert buffer_store._is_marketing_hero_cta_chrome(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store._is_nav_chrome(leak), leak
    assert IL._clean_insight(leak) == "", leak

    # counter-cases: real prose about the same project's adoption metrics, and
    # the class-38 `[*]` form's own prose controls, must all survive
    for text in (
        "With over 195,000 GitHub stars and 950 contributors, the project "
        "ships a desktop app and an IDE extension.",
        "OpenCode has over 195,000 GitHub stars, 950 contributors and 13,000 "
        "commits.",
        "The repo reports 160,000 GitHub stars, 900 contributors and 13,000 "
        "commits in total.",
        "Read the docs to learn how the quantized model fits on a single A100.",
        "Required fields are marked with [*] in the form below.",
        "Over 13,000 commits landed across the nine contributors this year.",
        "Terminal-Interface, Desktop-App und IDE-Extension nutzen dieselbe "
        "Config.",
    ):
        assert not buffer_store._is_marketing_hero_cta_chrome(text), text
        assert not IL._is_junk(text), text
        assert buffer_store.is_junk(text) is False, text


def test_news_aggregator_listing_run_is_gated_on_both_paths():
    """A press-roundup pipe run (class 55) must be gated on BOTH paths."""
    import buffer_store
    import internet_learner as IL
    leak = (
        "Protocol ACP | Techzine Oct 08, 2025 Zed Code Editor Adds Agent Protocol "
        "for Flexible AI Integration | WebProNews Aug 28, 2025 Google Integrates "
        "Gemini CLI into Zed Code Editor | SD Times Aug 28, 2025 Daily drive with "
        "Zed Code at the speed of thought."
    )
    assert IL._is_news_aggregator_listing_run(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_news_aggregator_listing_run(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True
    for text in (
        "Coverage appeared | Techzine Oct 08, 2025 and again in the roundup.",
        "The news was covered | WebProNews Aug 28, 2025 and others followed.",
        "We compare | Vercel Feb 3, 2026 and | Linear Mar 4, 2026 in the study.",
        "The shared underlying pattern is a closed-loop feedback system with a sensor, controller and actuator.",
        "vLLM uses paged attention; the benchmark ran on a RTX 4090 with 24 GB VRAM (USA).",
    ):
        assert not IL._is_news_aggregator_listing_run(text), text
        assert not buffer_store._is_news_aggregator_listing_run(text), text


def test_devto_card_tail_is_gated_on_both_paths():
    """A dev.to cross-post card counter bar (class 56) must be gated."""
    import buffer_store
    import internet_learner as IL
    leak = "Use `model: inherit` to Keep APC Agents Portable 2 projects | dev."
    assert IL._is_devto_card_tail(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_devto_card_tail(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    for text in (
        "Use model: inherit to keep agents portable across 3 projects for the team.",
        "We shipped 2 projects | dev.to published the writeups afterwards.",
        "The team closed 5 projects | dev. then moved on.",
        "Our team runs 12 projects | dev.to covers them in detail.",
    ):
        assert not IL._is_devto_card_tail(text), text
        assert not buffer_store._is_devto_card_tail(text), text


def test_services_menu_chain_is_gated_on_both_paths():
    """An agency services menu strip (class 57) must be gated on BOTH paths."""
    import buffer_store
    import internet_learner as IL
    leak = (
        "L Development RPA Development Computer Vision INTEGRATION & ENGINEERING "
        "AI Integration AI Product Engineering Youtube 9 Sep, 2026 The Rise of "
        "Enterprise Vertical AI Agents in 2026 The businesses that move now will "
        "be impossible to catch by end of 2026."
    )
    assert IL._is_services_menu_chain(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_services_menu_chain(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True
    for text in (
        "We combine AI & ML research with DevOps Engineering and Data Engineering practice.",
        "Integration & Engineering teams should agree on the interface before the sprint starts.",
        "The RPA Development and Computer Vision teams shipped in 2026.",
        "In 2026, AI Integration and AI Product Engineering grew fast.",
        "Our pipeline blends Data Engineering, DevOps Engineering and Integration Engineering into one stack.",
        "CI & CD pipelines and the SEC & FTC filings are unrelated topics.",
    ):
        assert not IL._is_services_menu_chain(text), text
        assert not buffer_store._is_services_menu_chain(text), text


def test_pagination_newsletter_widget_is_gated_on_both_paths():
    """A blog archive pagination widget + newsletter promo (class 58) must be
    gated on BOTH paths."""
    import buffer_store
    import internet_learner as IL
    leak = (
        "Herv\u00e9 Zwirn Sep 14, 2026 Afshin Khadangi Causal Liability Theory "
        "and the AI Consciousness Fallacy Afshin Khadangi Sep 14, 2026 Previous "
        "Page 1 of 63 Next The Consciousness AI New articles by email One a "
        "week, when there is something worth sending."
    )
    assert IL._is_pagination_newsletter_widget(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_pagination_newsletter_widget(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True
    for text in (
        "The report covers launches from 2022 and 2023 and explains why they aged well.",
        "Previous page 1 of 63 next are ordinary pagination words in a UI description.",
        "The newsletter sends new articles by email once a week when there is something worth sending.",
        "Researchers publish new articles by email every Friday, according to the journal policy.",
        "We compared 1 of 63 configurations and moved to the next page of the manual.",
        "Herv\u00e9 Zwirn and Afshin Khadangi wrote a paper about causal liability theory in September 2026.",
        "The agent parses bylines such as Jane Doe Sep 14, 2026 and stores the dateline with the headline.",
        "Previous Page 2 of 5 Next appears in the docs describing how readers navigate the archive.",
        "The docs show the widget labelled Previous Page 3 of 8 Next on the archive listing.",
        "Sign up to get new articles by email, the blog footer said, and previous page numbers are listed there.",
        "New articles by email are sent weekly, and the archive lists Previous Page 4 of 9 Next in the footer.",
    ):
        assert not IL._is_pagination_newsletter_widget(text), text
        assert not buffer_store._is_pagination_newsletter_widget(text), text


def test_fullscreen_toggle_chrome_is_gated_on_both_paths():
    """A code-block FULLSCREEN toggle widget pair (class 59) must be gated on
    BOTH paths."""
    import buffer_store
    import internet_learner as IL
    leak = (
        "Hugging Face's Transformers: from transformers import pipeline llm = "
        "pipeline ( ' text-generation ' , model = ' gpt-3 ' ) Enter fullscreen "
        "mode Exit fullscreen mode Integrate Z3 : Initialize Z3 and define your "
        "logical constraints."
    )
    assert IL._is_fullscreen_toggle_chrome(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_fullscreen_toggle_chrome(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True
    for text in (
        "The editor lets you enter fullscreen mode and exit fullscreen mode with the same button.",
        "The agent enters fullscreen mode when the display is small and exits it when the user resizes.",
        "Press enter to toggle fullscreen and exit the mode with Escape.",
        "The editor has an enter fullscreen control and a separate exit fullscreen control.",
        "Fullscreen mode hides the toolbar, and exiting fullscreen restores it.",
        "Integrate Z3 : Initialize Z3 and define your logical constraints.",
        "from transformers import pipeline llm = pipeline('text-generation', model='gpt-3')",
        "ProofOfThought translates a question into Z3 constraints and solves them.",
    ):
        assert not IL._is_fullscreen_toggle_chrome(text), text
        assert not buffer_store._is_fullscreen_toggle_chrome(text), text


def test_hashtag_run_after_headline_is_gated_on_both_paths():
    """A post headline welded to its hashtag run (class 60) must be gated on
    BOTH paths."""
    import buffer_store
    import internet_learner as IL
    leak = (
        "AI Coding Agents Must Reduce Maintenance Costs, Not Just Write Code "
        "# ai # webdev # tutorial # productivity A coding agent that drops 800 "
        "lines into your repo in 90 seconds feels productive."
    )
    assert IL._is_hashtag_run_after_headline(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_hashtag_run_after_headline(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True
    for text in (
        "The prompt asked for # ai # ml # data tags, and the agent added them to the post.",
        "The post used the tag run # ai # webdev # tutorial # productivity for reach.",
        "Tags like # ai # ml # data # nlp # llm are common on the platform.",
        "Filter by # ai # ml and exclude # nlp in the query builder.",
        "AI Coding Agents Must Reduce Maintenance Costs, Not Just Write Code for teams that ship weekly.",
        "A coding agent that drops 800 lines into your repo in 90 seconds feels productive.",
    ):
        assert not IL._is_hashtag_run_after_headline(text), text
        assert not buffer_store._is_hashtag_run_after_headline(text), text


def test_dated_tag_strip_chrome_is_gated_on_both_paths():
    """A dated card headline + tag strip (class 61) must be gated on BOTH
    paths."""
    import buffer_store
    import internet_learner as IL
    leak = (
        "LLM Complete Guide \u2014 From Parameters to Optimization, Everything "
        "About Local LLM Serving 2026-02-26 \u00b7 # AI \ud65c\uc6a9 vLLM LLM serving GPU "
        "optimization PagedAttention Qwen3 The first tool engineers encounter "
        "when trying to serve LLMs on local GPUs is vLLM."
    )
    assert IL._is_dated_tag_strip_chrome(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_dated_tag_strip_chrome(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True
    for text in (
        "The guide was updated 2026-02-26 \u00b7 # serving and covers PagedAttention.",
        "Published 2026-02-26 \u00b7 # ai is a tag used on the blog.",
        "The paper (2026-02-26) \u00b7 # quantization explains the method.",
        "See the note 2026-02-26 \u00b7 # notes and the appendix for the derivation.",
        "The report lists 2026-02-26 \u00b7 # ai \u00b7 # ml \u00b7 # data as separate rows.",
        "An update on 2026-02-26 \u00b7 # vLLM and GPU serving were both discussed in the guide.",
        "vLLM uses PagedAttention for KV cache management in serving.",
        "Local LLM Serving: From Parameters to Optimization covers PagedAttention and Qwen3.",
    ):
        assert not IL._is_dated_tag_strip_chrome(text), text
        assert not buffer_store._is_dated_tag_strip_chrome(text), text


def test_model_listing_run_chrome_is_gated_on_both_paths():
    """A model-hub listing row run (class 62) must be gated on BOTH paths."""
    import buffer_store
    import internet_learner as IL
    leak = (
        "13 ChenMnZ/Llama-3-8b-instruct-BlockAP-w2g64 Text Generation \u00b7 2B "
        "\u00b7 Updated Jul 21, 2024 \u00b7 12 ChenMnZ/Llama-3-8b-instruct-BlockAP-w2g128 "
        "Text Generation \u00b7 2B \u00b7 Updated Jul 21, 2024 \u00b7 15 View 4 "
        "collections Papers 8 arxiv: 2505."
    )
    assert IL._is_model_listing_run_chrome(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_model_listing_run_chrome(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True
    for text in (
        "Two releases: Updated Jul 21, 2024 and Updated Aug 2, 2024 are listed in the notes.",
        "The table lists Updated Jul 21, 2024 \u00b7 13 rows and Updated Mar 3, 2025 \u00b7 7 rows.",
        "Updated Jul 21, 2024 \u00b7 13 model variants are compared in the benchmark table.",
        "The repo was updated Jul 21, 2024 and the paper cites 13 baselines.",
        "ChenMnZ released Llama-3-8b-instruct-BlockAP-w2g64 for text generation.",
        "Text Generation is a common task label on model hubs.",
        "The changelog says Updated Jul 21, 2024, and the docs were updated Mar 3, 2025.",
        "We compare repos updated Jul 21, 2024 and Mar 3, 2025 in the appendix.",
    ):
        assert not IL._is_model_listing_run_chrome(text), text
        assert not buffer_store._is_model_listing_run_chrome(text), text


def test_trending_repo_row_chrome_is_gated_on_both_paths():
    """A GitHub trending row (class 63) must be gated on BOTH paths."""
    import buffer_store
    import internet_learner as IL
    leaks = (
        "AI agents and apps\U0001f44d \U0001f44e \u2605 66k +481 100 Python 28 infiniflow/ "
        "ragflow RAGFlow is a leading open-source Retrieval-Augmented Generation "
        "(RAG) engine that fuses\u2026 \U0001f44d \U0001f44e \u2605 91k +439 100 Go 29 "
        "langchain-ai/ langgraph Build resilient agents.",
        "With\u2026 \U0001f44d \U0001f44e \u2605 82k +739 100 Python 21 chaitanyagiri/ "
        "munder-difflin A local multi-agent harness that works with Claude Code.",
    )
    for leak in leaks:
        assert IL._is_trending_repo_row_chrome(leak) is True, leak
        assert IL._is_junk(leak) is True, leak
        assert buffer_store._is_trending_repo_row_chrome(leak) is True, leak
        assert buffer_store._is_nav_chrome(leak) is True, leak
        assert buffer_store.is_junk(leak) is True, leak
    for text in (
        "We compare \u2605 66k +481 and \u2605 91k +439 in the table.",
        "The dashboard shows \u2605 66k stars and +481 weekly in plain prose.",
        "Python 21 is the percentage shown for the repo in the language bar of the report.",
        "The repo gained +481 stars this week and now shows 66k total.",
        "AI agents and apps are trending on GitHub, with Python and Go well represented.",
        "infiniflow/ragflow is a leading open-source RAG engine.",
        "langchain-ai/langgraph lets you build resilient agents.",
        "munder-difflin is a local multi-agent harness that works with Claude Code.",
    ):
        assert not IL._is_trending_repo_row_chrome(text), text
        assert not buffer_store._is_trending_repo_row_chrome(text), text

def test_de_portal_fact_box_is_gated_on_both_paths():
    """Class 64 (18.09.26): a German portal's own byline + summary label pair."""
    import buffer_store

    leak = ("Autor: Patrick Banff Nationalpark in K\u00fcrze: Banff ist Kanadas "
            "\u00e4ltester Nationalpark (gegr\u00fcndet 1885), liegt in Alberta auf 1.")
    assert IL._is_de_portal_fact_box_chrome(leak), leak
    assert buffer_store._is_de_portal_fact_box_chrome(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak

    for text in (
        "In Kurze, das Modell skaliert mit der Datenmenge.",
        "Autor: Jane Doe published the benchmark in 2024.",
        "Autorin: Maria Schmidt analysierte in Kurze den Datensatz.",
        "Der Autor beschreibt in Kurze, wie Quantisierung wirkt.",
        "Die Autoren nennen in Kurze die Ergebnisse des Tests.",
        "Auteurs: the paper lists many contributors and the Kuerze note follows.",
        "Der Artikel wurde von einem Autor verfasst und in Kurze zusammengefasst.",
    ):
        assert not IL._is_de_portal_fact_box_chrome(text), text
        assert not buffer_store._is_de_portal_fact_box_chrome(text), text


def test_prompt_echo_fragment_is_gated_on_both_paths():
    """Class 65 (18.09.26): the learner's own task template echoed back."""
    import buffer_store

    leak = "Shared underlying pattern one sentence."
    assert IL._is_prompt_echo_fragment(leak), leak
    assert buffer_store._is_prompt_echo_fragment(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak

    for text in (
        "The shared underlying pattern is a closed-loop feedback system that couples sensing and actuation.",
        "Both systems share an underlying pattern: a feedback loop.",
        "We asked for one sentence and got a shared underlying pattern description.",
        "The shared underlying pattern, described in one sentence, is a control loop.",
        "The report gives the shared underlying pattern of both systems in one sentence and then explains it.",
    ):
        assert not IL._is_prompt_echo_fragment(text), text
        assert not buffer_store._is_prompt_echo_fragment(text), text


def test_generated_plan_echo_fragment_is_gated_on_both_paths():
    """Class 66 (18.09.26): a generated deliverable plan echoed back, truncated."""
    import buffer_store

    leaks = (
        "KI-Performance-Optimierung: Python-Skript f\u00fcr RAM/Disk/Cron-Monitoring "
        "+ Optimierungsvorschl\u00e4ge + Skill + Cron-Job alle 12h\n2.",
        "KI-Performance-Optimierung: Python-Skript f\u00fcr RAM/Disk/Cron-Monitoring "
        "+ Optimierungsvorschl\u00e4ge + Skill + Cron-Job alle 12h\n\n2.",
        "KI-Performance-Optimierung: Python script for RAM/Disk/Cron-Monitoring "
        "+ optimization suggestions + Skill + Cron job every 12h\n2.",
    )
    for leak in leaks:
        assert IL._is_generated_plan_echo_fragment(leak), leak
        assert buffer_store._is_generated_plan_echo_fragment(leak), leak
        assert IL._is_junk(leak), leak
        assert buffer_store.is_junk(leak), leak

    for text in (
        "The plan is: 1. collect metrics 2. aggregate 3. report.\n2.",
        "Step 1. gather the data\n2. compute the mean",
        "KI-Performance-Optimierung ist ein Praxisbeispiel.",
        "Our toolchain: script + docs + tests + CI.\n2.",
        "The pipeline is: ingest + transform + load + serve.",
        "Deliverables: script + skill + cron job. 3.",
        "The structural connection between the two systems is a feedback loop.",
    ):
        assert not IL._is_generated_plan_echo_fragment(text), text
        assert not buffer_store._is_generated_plan_echo_fragment(text), text


def test_journal_issue_index_chrome_is_gated_on_both_paths():
    """A journal volume/issue index run is not knowledge (class 67, 18.09.26)."""
    import buffer_store
    leak = ("Volume 15 (2025) WRN 15(12) \u2013 December 2025 : Art museums on "
            "Wikidata; comparing three comparisons of Grokipedia and Wikipedia "
            "WRN 15(11) \u2013 November 2025 : At least 80 million inconsistent "
            "facts on Wikipedia \u2013 can AI help find them?")
    assert IL._is_journal_issue_index_chrome(leak), leak
    assert buffer_store._is_journal_issue_index_chrome(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak
    for prose in (
        "WRN 15(12) means the twelfth issue of the fifteenth volume; compare that with the tenth.",
        "The journal published WRN 15(12) in December 2025 and WRN 15(11) in November 2025.",
        "Volume 15 (2025) covers art museums on Wikidata and Wikipedia comparisons.",
        "Issue 15(12) - December 2025 was the last of the year.",
    ):
        assert not IL._is_journal_issue_index_chrome(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_truncated_serp_tail_is_gated_on_both_paths():
    """A site-suffixed SERP snippet cut mid-sentence is not knowledge (class 68)."""
    import buffer_store
    leak = ("Introduction to Haystack - Haystack Documentation \u2014 Haystack is "
            "an open-source AI framework for building production-ready AI Agents, "
            "powerful RAG applications and scalable \u2026")
    assert IL._is_truncated_serp_tail(leak), leak
    assert buffer_store._is_truncated_serp_tail(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak
    for prose in (
        "The model paused\u2026 then continued with the answer.",
        "The article \u2014 a long read \u2014 ended with a trailing ellipsis\u2026",
        "Optimization and Tuning - vLLM explains how to select an attention backend.",
        "The report \u2014 titled Optimization \u2014 covers tuning \u2026",
    ):
        assert not IL._is_truncated_serp_tail(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_docs_feature_label_weld_is_gated_on_both_paths():
    """A docs feature list whose labels were welded together (class 69)."""
    import buffer_store
    leak = ("Tool calling and reasoning parsers OpenAI-compatible API server, plus "
            "Anthropic Messages API and gRPC support Efficient multi-LoRA support "
            "for dense and MoE layers Support for NVIDIA GPUs, AMD GPUs, Intel "
            "GPUs, and x86/ARM/PowerPC CPUs.")
    assert IL._is_docs_feature_label_weld(leak), leak
    assert buffer_store._is_docs_feature_label_weld(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak
    for prose in (
        "Tool calling and reasoning parsers are supported by the server.",
        "The release notes mention reasoning parsers and tool calling support in the API.",
        "Streaming outputs are produced by the model during decoding.",
        "An OpenAI-compatible API server makes integration easier for users.",
        "Efficient multi-LoRA support for dense and MoE layers was added in this release.",
    ):
        assert not IL._is_docs_feature_label_weld(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_label_bullet_chain_is_gated_on_both_paths():
    """A colon-label bullet chain whose newlines were lost (class 70)."""
    import buffer_store
    leak = ("Datasets : ProntoQA, FOLIO, ProofWriter, ConditionalQA, StrategyQA "
            "Model : GPT-5 (Azure deployment) Config : max_attempts=3 , "
            "verify_timeout=10000ms Backend Avg Accuracy Success Rate SMT2 86.")
    assert IL._is_label_bullet_chain(leak), leak
    assert buffer_store._is_label_bullet_chain(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak
    for prose in (
        "Metrics : precision, recall and F1 were reported.",
        "The two categories : classification and regression were compared.",
        "Benchmarks : latency and throughput were measured across models.",
        "Results : the agent improved by 12 percent.",
        "The sources are README and the documentation site.",
    ):
        assert not IL._is_label_bullet_chain(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_repeat_badge_glyph_run_is_gated_on_both_paths():
    """A repeated page badge glyph on list entries is not knowledge (class 71)."""
    import buffer_store
    leak = ("ARTKIT, Meta LlamaFirewall/Llama Guard 4 \U0001f195 New Case Studies "
            "EchoLeak (CVE-2025-32711), DeepSeek R1 vulnerabilities, first "
            "malicious MCP server \U0001f195 AI Regulations EU AI Act 2026 "
            "milestones, NIST AI RMF, ISO/IEC 42001 \U0001f504 Updated LLM Ec")
    assert IL._is_repeat_badge_glyph_run(leak), leak
    assert buffer_store._is_repeat_badge_glyph_run(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak
    for prose in (
        "The agent was updated \U0001f195 to support the new API.",
        "New Case Studies \U0001f195 were added to the docs.",
        "The changelog lists a new feature \U0001f195 and an update \U0001f504 to the parser.",
        "Case studies include EchoLeak (CVE-2025-32711) and the first malicious MCP server.",
        "AI Regulations cover EU AI Act 2026 milestones, NIST AI RMF and ISO/IEC 42001.",
        "The team marked the release \U0001f195 and then documented the fix.",
    ):
        assert not IL._is_repeat_badge_glyph_run(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_repo_stat_footer_run_is_gated_on_both_paths():
    """A repo page's stat footer welded onto its description is not knowledge (class 72).

    Live 19.09.26: cycle_f_multi_domain stored `NeMo: a PyTorch framework for
    physics ML ... methods 3,262 stars 784 forks Python Apache-2.` -- counters
    plus language plus licence at the END of the record. The counters alone are
    ordinary prose, so the discriminator is the welded footer; a record that
    merely QUOTES such a footer (example cue in front) stays learnable.
    """
    import buffer_store
    leaks = (
        "NeMo: a PyTorch framework for physics ML, from install to first surrogate "
        "Open-source deep-learning framework for building, training, and fine-tuning "
        "deep learning models using state-of-the-art Physics-ML methods 3,262 stars "
        "784 forks Python Apache-2.",
        "RAGFlow 91,000 stars 9,400 forks TypeScript MIT.",
        "The repo row reads: an engine for RAG 12 stars 34 forks Go BSD-3.",
    )
    for leak in leaks:
        assert IL._is_repo_stat_footer_run(leak), leak
        assert buffer_store._is_repo_stat_footer_run(leak), leak
        assert IL._is_junk(leak), leak
        assert buffer_store._is_nav_chrome(leak), leak
        assert buffer_store.is_junk(leak), leak
    for prose in (
        "The repository now has 3,262 stars and 784 forks, making it the most popular option for Python users.",
        "The model card reports 12,000 stars, 900 forks and an Apache-2 license issued by the vendor.",
        "We measured 3,262 stars 784 forks in the dataset statistics table for the Python cohort.",
        "Stars and forks grew quickly; the 784 forks came mostly from Python users of the library.",
        "Our crawler stores stars, forks and licence (Apache-2) for each repository row it sees.",
        "The ranking output prints <name> <stars> <forks> <language> <licence>, e.g. repo 12 stars 34 forks Python MIT.",
        "Rows look like this, for example: 12 stars 34 forks Python MIT.",
        "Die Bibliothek hat 3,262 stars 784 forks Python mit Apache-2 Lizenz am Ende.",
        "A typical fixture such as 8,100 stars 620 forks Python Apache-2 appears in the docs.",
        "The dataset has 12 stars, 34 forks, and a BSD licence column per repo.",
    ):
        assert not IL._is_repo_stat_footer_run(prose), prose
        assert not buffer_store._is_repo_stat_footer_run(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_table_header_value_run_is_gated_on_both_paths():
    """A benchmark table's header row with the first value welded on (class 73).

    Live 19.09.26: cycle_f_multi_domain stored `Model Dataset Resolution Acc@1
    ckpt MedViT_small ImageNet-1K 224 83.` -- only 68 chars, so the >=90 length
    trust never applied. The discriminator is >=3 metric column labels AND no
    finite verb AND almost no lowercase words; prose that names the same
    columns always has a verb.
    """
    import buffer_store
    leaks = (
        "Model Dataset Resolution Acc@1 ckpt MedViT_small ImageNet-1K 224 83.",
        "Model Dataset Resolution Acc@1 MedViT ImageNet-1K 224 83.1",
        "Model Params FLOPs Latency Throughput ResNet50 25.6 4.1 3.2 1200",
    )
    for leak in leaks:
        assert IL._is_table_header_value_run(leak), leak
        assert buffer_store._is_table_header_value_run(leak), leak
        assert IL._is_junk(leak), leak
        assert buffer_store._is_nav_chrome(leak), leak
        assert buffer_store.is_junk(leak), leak
    for prose in (
        "Top-1 accuracy and F1 score were reported for each model, dataset and resolution setting.",
        "Backend, avg accuracy and success rate were logged for each of the three runs by the harness.",
        "Precision, recall and F1 were computed per class and then averaged over the dataset splits.",
        "Model A was evaluated on the ImageNet-1K dataset at 224 resolution and reached 83.1% accuracy.",
        "Tokens per second and latency were measured on the same backend for a fair comparison.",
        "We compared model accuracy, dataset size and resolution across the three checkpoints.",
        "A checkpoint trained on ImageNet-1K reached 83% accuracy with 224 input resolution in our test.",
        "The report covers epochs, steps and tokens for each training configuration in the study.",
    ):
        assert not IL._is_table_header_value_run(prose), prose
        assert not buffer_store._is_table_header_value_run(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_decorative_alt_text_chrome_is_gated_on_both_paths():
    """A landing page's welded image alt-text run is not knowledge (class 74).

    Live 19.09.26: cycle_c_github stored a hero section whose alt-texts were
    concatenated -- `GitHub Logo \u2728 Decorative dot pattern background` --
    glued to the marketing slogan. Prose that mentions both always separates
    them with a verb or comma.
    """
    import buffer_store
    leaks = (
        "Agent Launch Week #2 Explore our product launch updates GitHub Logo "
        "\u2728 Decorative dot pattern background The end-to-end AI Agent "
        "Engineering Platform Build enterprise multi-agent systems \u2014 "
        "development , observability , and deployment in one platform.",
        "GitHub Logo \u2728 Decorative dot pattern background",
        "Home GitHub Logo \u2728 Decorative dot pattern background Learn more",
    )
    for leak in leaks:
        assert IL._is_decorative_alt_text_chrome(leak), leak
        assert buffer_store._is_decorative_alt_text_chrome(leak), leak
        assert IL._is_junk(leak), leak
        assert buffer_store._is_nav_chrome(leak), leak
        assert buffer_store.is_junk(leak), leak
    for prose in (
        "GitHub Logo and a decorative dot pattern background are both alt attributes in the hero markup.",
        "The GitHub logo is used under the brand guidelines, and the decorative dot pattern background comes from the theme.",
        "The GitHub logo and the decorative dot pattern background are rendered as separate SVG layers.",
        "Our page uses the GitHub logo plus a decorative dot pattern background for the hero section.",
        "Alt text: GitHub Logo. Decorative pattern background for the hero section of the page.",
        "The header ships the GitHub logo and a decorative pattern background image with empty alt text.",
        "Our design system stores the logo, the decorative pattern, and the background colour tokens.",
        "Agent Launch Week #2 brought product launch updates to the platform according to the blog.",
        "The end-to-end AI Agent Engineering Platform builds enterprise multi-agent systems with observability.",
    ):
        assert not IL._is_decorative_alt_text_chrome(prose), prose
        assert not buffer_store._is_decorative_alt_text_chrome(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_bio_page_furniture_pair_is_gated_on_both_paths():
    """A byline card's furniture pair welded to the lede is not knowledge (class 75).

    Live 19.09.26: cycle_a_technews stored a CBS-style byline card -- Read Full
    Bio + an `Updated on: <date> / <time>` dateline + the publisher label +
    add-on-Google link -- glued to the article's first sentence. Neither half is
    a marker alone; the PAIR is.
    """
    import buffer_store
    leaks = (
        "Read Full Bio Mary Cunningham Updated on: June 17, 2025 / 5:28 PM EDT / "
        "CBS News Add CBS News on Google Amazon's CEO envisions an \"agentic future\" "
        "in which AI robots, or agents, replace humans working in the company's offices.",
        "Read Full Bio Jane Doe Updated on: March 3, 2026 / 9:10 AM PST / The Verge "
        "Add The Verge on Google",
    )
    for leak in leaks:
        assert IL._is_bio_page_furniture_pair(leak), leak
        assert buffer_store._is_bio_page_furniture_pair(leak), leak
        assert IL._is_junk(leak), leak
        assert buffer_store._is_nav_chrome(leak), leak
        assert buffer_store.is_junk(leak), leak
    for prose in (
        "Read Full Bio about the author to learn more about her reporting career.",
        "We read the full bio and the updated on date before citing the article.",
        "Add CBS News on Google to see the publisher's latest coverage.",
        "Read Full Bio of our editors, add us on Google, and follow the blog for updates.",
        "The article was updated on June 17, 2025 / 5:28 PM EDT according to the publisher's changelog.",
        "Published on June 17, 2025 / 5:28 PM EDT and later revised, the piece covers agentic AI.",
        "Our datelines look like June 17, 2025 / 5:28 PM EDT, and each story carries a bio link.",
        "The byline card offers Read Full Bio, Updated on: June 17, 2025 and Add CBS News on Google.",
        "Read the full bio of the author and add the newsroom on Google News from the header.",
    ):
        assert not IL._is_bio_page_furniture_pair(prose), prose
        assert not buffer_store._is_bio_page_furniture_pair(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_tag_counter_run_chrome_is_gated_on_both_paths():
    """A tag-cloud counter run is not knowledge (class 76).

    Live 19.09.26: cycle_b_papers stored a tag strip -- 15 `word (n)` pairs and
    nothing else -- as the answer for a BitNet query. Single-digit counts are the
    discriminator against real prose; one or two pairs are ordinary prose, so the
    discriminator is >=8 pairs in one record.
    """
    import buffer_store
    leak = (
        "AI (2) jackson (2) LangGraph (2) learning (2) mcp (2) NeoCode (2) "
        "production (2) workflow (2) agent-frameworks (1) agents (1) AI framework (1) "
        "angular (1) Anthropic (1) API Comparison (1) architecture patterns (1) CLAUDE."
    )
    assert IL._is_tag_counter_run_chrome(leak)
    assert buffer_store._is_tag_counter_run_chrome(leak)
    assert IL._is_junk(leak)
    assert buffer_store._is_nav_chrome(leak)
    assert buffer_store.is_junk(leak)
    # A sidebar widget that prints the same tag counters is chrome by
    # construction -- asserting it as a leak, NOT as clean prose.
    widget = (
        "Tag counts were AI (2), mcp (2), agents (1), workflow (2), LangGraph (2), "
        "NeoCode (2), production (2), learning (2), routing (1), caching (1) across the sidebar."
    )
    assert IL._is_tag_counter_run_chrome(widget)
    assert IL._is_junk(widget)
    for prose in (
        "We compare LoRA (2), QLoRA (3), PEFT (4), SFT (5) and DPO (6) in the benchmark table.",
        "The evaluation covered agents (12), tools (8), memory (6), routing (5), caching (4), and safety (3).",
        "AI (2) and mcp (2) were the two tags used for the study.",
        "Scores improved: 91.2 (2024), 93.0 (2025), 95.1 (2026), 96.0 (2027), 97.0 (2028).",
        "James Jul 05, 2025 was the day the team shipped the first release.",
        "Share the report with 14 reviewers and 1 manager before Friday.",
    ):
        assert not IL._is_tag_counter_run_chrome(prose), prose
        assert not buffer_store._is_tag_counter_run_chrome(prose), prose
        assert not IL._is_junk(prose), prose


def test_advisory_listing_row_is_gated_on_both_paths():
    """Class 77 (live 19.09.26): a security-advisory LISTING row trained as an answer.

    Vendor/product run welded to an advisory dateline + bare CVE id, and the
    severity badge welded to the tail. 115 chars WITH digits, so the `>=90`
    length trust AND the technical-signal gate both fired.
    """
    import buffer_store

    leak = (
        "Cisco Ios Xe Rockwellautomation Allen Bradley Stratix 5200 Firmware + 5 "
        "-- Oct 16, 2023 CVE-2025-20337 CRITICAL 10."
    )
    assert IL._is_advisory_row(leak)
    assert buffer_store._is_advisory_row(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)
    assert buffer_store._is_nav_chrome(leak)
    for prose in (
        "The Cisco IOS XE firmware update fixes CVE-2025-20337, a critical "
        "remote-code-execution flaw rated 10.0 by NVD.",
        "Rockwell Automation released a Stratix 5200 firmware patch addressing a "
        "critical vulnerability (CVE-2025-20337).",
        "Researchers disclosed 5 CVEs rated CRITICAL in industrial switch "
        "firmware, including Allen-Bradley Stratix 5200.",
        "CVE-2024-12345 was rated CRITICAL 9.8 and patched in the October 16, 2023 "
        "firmware release.",
        "The page lists Cisco IOS XE, Rockwell Automation Allen-Bradley Stratix "
        "5200 firmware and 5 other advisories.",
        "A critical CVE-2025-20337 (CVSS 10.0) affects Stratix 5200 switches "
        "running IOS XE.",
        "CVE-2026-5430 is a critical (CVSS 9.8) auth bypass. Patch now -- Oct 16, "
        "2023 was the disclosure date.",
        "The report lists five CVEs: CVE-2026-5430 CRITICAL 9.8, CVE-2026-5431 "
        "HIGH 8.1 in the appendix table.",
    ):
        assert not IL._is_advisory_row(prose), prose
        assert not buffer_store._is_advisory_row(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_site_branded_headline_stub_is_gated_on_both_paths():
    """Class 78 (live 19.09.26): a site-branded headline STUB stored as knowledge.

    A brand run, a colon, then `<year> Comparison of ...` and nothing else -- the
    SERP card's title line, never a sentence. A bare `20xx Comparison of` is
    ordinary prose (3 control FPs); the brand run before the colon is the
    discriminator.
    """
    import buffer_store

    leak = ("Tech Frontline Low-Code AI Workflow Automation: 2026 Comparison of "
            "Zapier, Make, and Tray.")
    assert IL._is_site_headline_stub(leak)
    assert buffer_store._is_site_headline_stub(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)
    assert buffer_store._is_nav_chrome(leak)
    for prose in (
        "A 2026 Comparison of quantization methods shows 4-bit wins on memory.",
        "The team published a 2026 Comparison of agent frameworks in the appendix.",
        "Our benchmark: 2026 Comparison of vLLM, TensorRT, and llama.cpp throughput.",
        "Tech Frontline published a low-code AI workflow automation guide comparing "
        "Zapier, Make, and Tray in 2026.",
        "NVIDIA Research Blog: 2026 advances in agent architectures and tool use.",
        "The ACM Digital Library: 2025 survey of prompt-injection defenses in "
        "production.",
    ):
        assert not IL._is_site_headline_stub(prose), prose
        assert not buffer_store._is_site_headline_stub(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_fact_box_label_chain_is_gated_on_both_paths():
    """Class 79 (live 19.09.26): an incident/vendor FACT BOX stored as an answer.

    The page's own label pair `Key Points` ... `Affected objects:` welded in one
    run. 191 chars with digits, so both gates fired. `Affected objects` alone is
    ordinary prose, and so is `Key Points` alone -- the WELDED pair is the marker.
    """
    import buffer_store

    leak = (
        "Key Points Event time: 2026-05-10, James Shore published an analysis "
        "article -Affected objects: All developers and technical teams who use "
        "AI coding agents"
    )
    assert IL._is_fact_box_label_chain(leak)
    assert buffer_store._is_fact_box_label_chain(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)
    assert buffer_store._is_nav_chrome(leak)
    for prose in (
        "Key Points from the paper: quantization cuts memory, and pruning cuts "
        "latency.",
        "The affected objects are developers and technical teams who use AI coding "
        "agents.",
        "Event time: 2026-05-10; the analysis article by James Shore discusses AI "
        "coding agents.",
        "Our summary: the report covers Affected objects: developers using coding "
        "agents.",
        "The paper's key points were extracted by the agent and stored as insights.",
        "Affected objects include all developers and technical teams who use AI "
        "coding agents.",
    ):
        assert not IL._is_fact_box_label_chain(prose), prose
        assert not buffer_store._is_fact_box_label_chain(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose


def test_own_plan_plus_run_without_dangling_marker_is_gated_on_both_paths():
    """Class 80 (live 19.09.26): the agent's OWN deliverable plan, minus the `2.`.

    Same own-artifact family as class 66, but it ends in prose instead of a
    dangling list marker, so `_PROMPT_PLAN_ECHO_RE` never fired. The
    discriminator is the own-artifact title AND a 3-way `+`-joined deliverable
    run: `RAM/Disk/Cron` alone hits 5 episodes and `skill + cron` alone hits 3
    episodes plus 1 control FP.
    """
    import buffer_store

    leak = (
        "Energy efficiency: AI performance optimization: Python script for "
        "RAM/Disk/Cron monitoring + optimization suggestions + skill + cron job "
        "every 12h."
    )
    assert IL._is_own_plan_plus_run(leak)
    assert buffer_store._is_own_plan_plus_run(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)
    assert buffer_store._is_nav_chrome(leak)
    for prose in (
        "Energy efficiency: AI performance optimization reduces FLOPs + memory + "
        "latency in inference.",
        "The agent's own artifacts: RAM/Disk monitoring + optimization suggestions "
        "+ skill.",
        "We wrote a Python script for RAM/Disk monitoring, added a skill and a "
        "cron job every 12h.",
        "Energy efficiency: AI performance optimization: the study combines "
        "pruning + distillation to cut cost.",
        "Energy efficiency: the report covers quantization + pruning + "
        "distillation for inference cost.",
        "Efficiency: the pipeline combines caching + batching + sharding across "
        "three services.",
    ):
        assert not IL._is_own_plan_plus_run(prose), prose
        assert not buffer_store._is_own_plan_plus_run(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store.is_junk(prose), prose

        assert not buffer_store.is_junk(prose), prose
def test_institution_abstract_tail_chrome_is_gated_on_both_paths():
    """An affiliation welded to a truncated abstract ORDINAL is not knowledge.

    Live 19.09.26 (class 81), verbatim from the buffer row (cycle_h_efficiency):
      "Language-model groups overstate consensus when replaying human
       deliberation on a reasoning task Waseda University Abstract 9."
    125 chars WITH digits: a paper-listing card cut off mid-tail -- the
    affiliation, then the abstract's ordinal, nothing after it. The >=90
    length trust AND the technical-signal gate both fired and no existing
    marker matched:
      * `_is_arxiv_abstract_chrome` needs the viewer labels (`View PDF` /
        `HTML (experimental)`), which a truncated card does not carry;
      * `_is_nav_list` wants >=6 TitleCase tokens with no comma;
      * the byline helpers are English-keyed on `By <Name>` /
        `Published` / `Share`.
    The discriminator is the PAIR: an institution label AND a bare abstract
    ordinal welded at the TAIL. Prose that merely mentions an institution or
    an `Abstract <n>` reference carries no such tail weld.
    """
    import buffer_store
    leaks = (
        "Language-model groups overstate consensus when replaying human "
        "deliberation on a reasoning task Waseda University Abstract 9.",
        "Quantization of large language models for edge deployment: a survey "
        "of 4-bit methods and their accuracy trade-offs, Kyoto University "
        "Abstract 12.",
    )
    for text in leaks:
        assert IL._is_institution_abstract_tail_chrome(text), text
        assert IL._is_junk(text), text
        assert buffer_store._is_institution_abstract_tail_chrome(text), text
        assert buffer_store._is_nav_chrome(text), text
        assert IL._clean_insight(text) == "", text

    # counter-cases: real prose about institutions, abstracts and ordinals must
    # survive -- the helper ALONE must stay False on every one of them
    clean = (
        "The paper was published by Waseda University. Abstract 9 covers the "
        "method.",
        "Read Abstract 9 for the training details.",
        "In Abstract 9 the authors describe the dataset.",
        "Researchers at the University of Tokyo compared three quantization "
        "schemes.",
        "The abstract states that 9 of the 12 agents improved after the change.",
        "The agent summarized the paper from Tsinghua University in three "
        "sentences.",
        "A survey was presented at Waseda University in 2026.",
        "He earned a degree from Stanford University and then joined the lab.",
        "The conference paper lists affiliation Waseda University and 9 "
        "co-authors.",
        "Waseda University researchers released the model weights under "
        "Apache 2.0.",
        "The team at the Max Planck Institute published Abstract 3 last year.",
        "See the Stanford University page; abstract 4 lists the metrics.",
        "The Laboratory Abstract 5 was rejected by the reviewers.",
        "The university's abstract, 9 pages, covers the protocol.",
        "The paper is summarized in Abstract 9.",
        "Abstract 9 of the supplementary material lists the training "
        "hyperparameters.",
        "Our school abstract 3 is due next week.",
        "The study came out of Waseda University and covered deliberation "
        "replay.",
    )
    for text in clean:
        assert not IL._is_institution_abstract_tail_chrome(text), text
        assert not buffer_store._is_institution_abstract_tail_chrome(text), text
def test_trending_card_header_pair_is_gated_on_both_paths():
    """A trending card's welded header PAIR is not knowledge (class 82).

    Live 19.09.26, verbatim from the buffer row (cycle_c_github, post-fix):
      "This Week Last Update: 2 days ago See Project 2 OpenManus Open-source
       AI agent framework OpenManus is an open-source AI agent framework
       designed to autonomously execute complex, multi-step tasks by
       combining reasoning, planning, and tool use."
    242 chars WITH digits, so the >=90 length trust AND the technical-signal
    gate both fired. Every repo-listing helper returned False: the star
    counter rule wants `\u2605 <N>k +<M>` plus a language stat, the stat-footer
    rule wants a commits/branches/tags footer, and the listing-row rule wants
    `Updated <Mon DD, YYYY>` + `Public Forked`. Here the page's two card labels
    were simply welded onto the description.

    The discriminator is the PAIR in its exact welded form: `This Week Last
    Update: <n> days ago` immediately followed by `See Project <n>` with a
    single space between them. Natural prose about a weekly update or a
    project number carries punctuation between the halves.
    """
    import buffer_store
    leaks = (
        "This Week Last Update: 2 days ago See Project 2 OpenManus Open-source "
        "AI agent framework OpenManus is an open-source AI agent framework "
        "designed to autonomously execute complex, multi-step tasks by "
        "combining reasoning, planning, and tool use.",
        "This Week Last Update: 5 days ago See Project 9 SomeRepo An "
        "open-source tool for reproducible builds across Linux distributions.",
    )
    for text in leaks:
        assert IL._is_trending_card_header_pair(text), text
        assert IL._is_junk(text), text
        assert buffer_store._is_trending_card_header_pair(text), text
        assert buffer_store._is_nav_chrome(text), text
        assert IL._clean_insight(text) == "", text

    # counter-cases: natural prose about updates, projects and trending repos
    clean = (
        "This week's last update to the repo was 2 days ago, so the fix is "
        "fresh.",
        "The dashboard shows the last update per project; see project 2 for "
        "details.",
        "Our team reviewed the last update of each project this week and "
        "shipped 2 patches.",
        "The last update landed 2 days ago, so the API is stable this week.",
        "See the project page for the benchmark numbers and the update history.",
        "Last update: 2 days ago. See the project's changelog for the "
        "migration notes.",
        "Trending repos on GitHub this week include OpenManus and OpenHands.",
        "OpenManus is an open-source AI agent framework for multi-step tasks.",
        "The vendor's site prints a 'this week last update' badge next to each "
        "repo.",
        "The scraped page contains a 'This Week Last Update' label and a See "
        "Project link.",
        "Repos are ranked by stars; the last update was 2 days ago for the top "
        "one.",
        "Each row lists stars, forks, and the last update timestamp.",
    )
    for text in clean:
        assert not IL._is_trending_card_header_pair(text), text
        assert not buffer_store._is_trending_card_header_pair(text), text
def test_aggregator_row_with_year_tail_is_gated_on_both_paths():
    """An aggregator feed row welded to an arXiv `(yyyy)` tail is not knowledge.

    Live 19.09.26 (class 83), verbatim from the buffer row (cycle_b_papers):
      "CameronBanga 5 hours ago | 10 comments 58 Cache-to-Cache: Direct
       Semantic Communication Between LLMs (2025) (arxiv."
    A feed row (`<user> <relative-time> | <n> comments <points> <headline>`)
    welded onto the paper's `(2025) (arxiv` tail. 115 chars WITH digits, so the
    technical-signal gate fired; `_is_hn_item_chrome` and
    `_is_hn_feed_listing_chrome` (classes 37/49) both returned False because
    they require the `<relative-time> | N comments` unit to REPEAT (>=2).

    A single occurrence is deliberately NOT gated: class 37's own test asserts
    the single-unit control `The review took 2 days ago | 4 comments per
    reviewer were recorded.` must stay learnable, and a bare single-unit
    marker measured 4-9 control FPs here. The co-occurrence that works is the
    page's own arXiv `(yyyy)` tail within 80 chars of the feed unit.
    """
    import buffer_store
    leaks = (
        "CameronBanga 5 hours ago | 10 comments 58 Cache-to-Cache: Direct "
        "Semantic Communication Between LLMs (2025) (arxiv.",
        "someuser 3 hours ago | 7 comments 42 Efficient Transformers: A Survey "
        "(2023) (arxiv.",
    )
    for text in leaks:
        assert IL._is_aggregator_row_year_tail(text), text
        assert IL._is_junk(text), text
        assert buffer_store._is_aggregator_row_year_tail(text), text
        assert buffer_store._is_nav_chrome(text), text
        assert IL._clean_insight(text) == "", text

    # counter-cases: a SINGLE `<relative-time> | N comments` unit is ordinary
    # prose (class 37's own clean control) and must stay learnable
    clean = (
        "The review took 2 days ago | 4 comments per reviewer were recorded.",
        "The ticket was closed 3 days ago | 12 comments in the audit log.",
        "Version 2.1 shipped 4 days ago | 6 comments in the changelog.",
        "The PR merged 2 days ago | 8 comments on the review thread.",
        "A post from 3 days ago | 5 comments about quantization was stored.",
        "The commit landed 6 hours ago | 2 comments from the maintainer.",
        "The forum shows 5 hours ago | 10 comments for this paper.",
        "Cameron wrote 5 hours ago that the cache-to-cache paper changed his "
        "view.",
        "The paper (2025) is on arXiv and gathered 58 citations since.",
        "Cache-to-Cache enables direct semantic communication between LLMs.",
        "The arxiv abstract was posted a few hours ago by the authors.",
        "The aggregator row reads: username, relative time, comment count, "
        "points.",
    )
    for text in clean:
        assert not IL._is_aggregator_row_year_tail(text), text
        assert not buffer_store._is_aggregator_row_year_tail(text), text
def test_pipe_byline_shares_header_is_gated_on_both_paths():
    """A pipe-dateline byline welded to the site's `Shares` is not knowledge.

    Live 19.09.26 (class 84), verbatim from the buffer row (cycle_f_multi_domain):
      "Wire How HPC and Simulation Are Powering the Next Wave of Physical AI
       HPC Cluster by Ali Azhar | July 15, 2026 Shares As investment in
       Physical AI accelerates, simulation is taking on a much larger role
       than simply generating synthetic training data."
    A portal article header: section chip, headline, byline, PIPED dateline,
    then the site's own `Shares` affordance glued to the lede. 157 chars WITH
    digits, so both the >=90 length trust and the technical-signal gate fired.

    **The existing helper covers the vocabulary but not the SHAPE** (the
    class-40/51 rule, third occurrence). `_is_news_byline_share_header`
    (class 51) already keys on `By <First> <Last>` + a dateline + `Share` and
    still returned False: it requires a full WEEKDAY dateline, while this page
    ships a PIPE dateline with no weekday. `_strip_byline_prefix` only strips
    a LEADING byline and here the byline sits after a brand chip.

    The discriminator is the three-part weld: byline AND pipe dateline AND the
    bare `Shares` token immediately after the date.
    """
    import buffer_store
    leaks = (
        "Wire How HPC and Simulation Are Powering the Next Wave of Physical "
        "AI HPC Cluster by Ali Azhar | July 15, 2026 Shares As investment in "
        "Physical AI accelerates, simulation is taking on a much larger role "
        "than simply generating synthetic training data.",
        "Quantum computing for logistics: a survey by Jane Doe | March 3, "
        "2026 Shares Enterprises are evaluating annealing hardware for "
        "routing problems at scale.",
    )
    for text in leaks:
        assert IL._is_pipe_byline_shares_header(text), text
        assert IL._is_junk(text), text
        assert buffer_store._is_pipe_byline_shares_header(text), text
        assert buffer_store._is_nav_chrome(text), text
        assert IL._clean_insight(text) == "", text

    # counter-cases: prose that credits an author or reports share counts
    clean = (
        "The article by Ali Azhar was published on July 15, 2026.",
        "Shares of the company rose after the report by the analyst.",
        "Written by Ali Azhar | July 15, 2026 | 5 min read.",
        "The post was shared 12 times on social media.",
        "HPC and simulation are powering the next wave of physical AI.",
        "Simulation is taking a larger role than generating synthetic data.",
        "Shares outstanding grew after the July 15, 2026 announcement.",
        "Ali Azhar wrote the post | July 15, 2026 and it got 5 shares.",
        "Shares in the AI sector rose; the article was by Ali Azhar.",
        "A byline reading 'by Ali Azhar | July 15, 2026' precedes the Shares "
        "button.",
        "The wire story was filed by Ali Azhar on July 15, 2026.",
        "The page header shows the section, headline, byline and dateline.",
    )
    for text in clean:
        assert not IL._is_pipe_byline_shares_header(text), text
        assert not buffer_store._is_pipe_byline_shares_header(text), text
def test_portal_counter_bar_comparison_is_gated_on_both_paths():
    """A portal counter bar welded to a comparison headline is not knowledge.

    Live 19.09.26 (class 85), verbatim from the buffer row (cycle_g_security):
      "Instant 23-Aug-2026 0 207 Technology OpenAI Workspace Agents vs Google
       Gemini Enterprise: Complete Comparison 2026 OpenAI Workspace Agents vs
       Google Gemini Enterprise is a comparison of two enterprise agent
       platforms introduced on April 22, 2026."
    The listing page's own counter bar (`Instant <dd-Mon-yyyy> <n> <n>
    <Category>`) welded onto the headline and its lede. 246 chars WITH digits,
    so both the >=90 length trust and the technical-signal gate fired.

    The discriminator is a CONJUNCTION, not a phrase (the AU rule). Two
    narrower forms were measured and REJECTED: the bare date + two counters +
    category label scored 4 hostile recombinants (`The log line 23-Aug-2026 0
    207 Technology was parsed by the tool.`), and adding the leading `Instant`
    token still left 2 (`Instant 23-Aug-2026 0 207 Technology is the scraped
    badge text.`). Adding the site's own headline label `Complete Comparison`
    within 120 chars reached 0 on every corpus.
    """
    import buffer_store
    leaks = (
        "Instant 23-Aug-2026 0 207 Technology OpenAI Workspace Agents vs Google "
        "Gemini Enterprise: Complete Comparison 2026 OpenAI Workspace Agents "
        "vs Google Gemini Enterprise is a comparison of two enterprise agent "
        "platforms introduced on April 22, 2026.",
        "Instant 3-Mar-2026 0 88 Business Vector Databases vs Graph Databases: "
        "Complete Comparison 2026 Both approaches index embeddings but differ "
        "in traversal cost.",
    )
    for text in leaks:
        assert IL._is_portal_counter_bar_comparison(text), text
        assert IL._is_junk(text), text
        assert buffer_store._is_portal_counter_bar_comparison(text), text
        assert buffer_store._is_nav_chrome(text), text
        assert IL._clean_insight(text) == "", text

    # counter-cases: prose that merely carries a date, counters and a category,
    # or that names a comparison, must stay learnable
    clean = (
        "OpenAI Workspace Agents vs Google Gemini Enterprise: Complete "
        "Comparison 2026",
        "The article compares OpenAI Workspace Agents and Google Gemini "
        "Enterprise.",
        "The log line 23-Aug-2026 0 207 Technology was parsed by the tool.",
        "Instant 23-Aug-2026 0 207 Technology is the scraped badge text.",
        "On 23-Aug-2026 we recorded 0 failures and 207 requests in the "
        "Technology category.",
        "Metrics for 23-Aug-2026: 0 errors, 207 requests, category Technology.",
        "The dashboard row reads 23-Aug-2026, 0, 207, Technology in the CSV "
        "export.",
        "A complete comparison of 0 downtime deployments and 207 benchmarks in "
        "Technology.",
        "Two enterprise agent platforms introduced on April 22, 2026 diverge "
        "in pricing.",
        "The survey dated 22-Apr-2026 shows 207 responses and 0 skips in "
        "Politics.",
        "The review compares two platforms; a complete comparison is in "
        "appendix B.",
        "Complete Comparison covers 207 vendors and 0 exclusions in Business.",
    )
    for text in clean:
        assert not IL._is_portal_counter_bar_comparison(text), text
        assert not buffer_store._is_portal_counter_bar_comparison(text), text


def test_release_notes_pr_bullet_is_gated_on_both_paths():
    """A release-notes changelog bullet welded to its PR number (class 86).

    Live 19.09.26: `cycle_b_papers` stored
      "HMX flash-attention head_dim padding (support DK=DV=72) ( #26539 )
       Allow HMX flash-attention to run with head_dim not a multiple of 64 (e."
    The discriminator is the WELD (parenthesised PR number immediately followed
    by a changelog imperative), never the bare `( #N )` form, which is ordinary
    prose about a patch.
    """
    import buffer_store
    leak = ("HMX flash-attention head_dim padding (support DK=DV=72) ( #26539 ) "
            "Allow HMX flash-attention to run with head_dim not a multiple of 64 (e.")
    assert IL._is_release_notes_pr_bullet(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)
    assert IL._clean_insight(leak, 300) == ""

    for text in (
        "The changelog says Add HMX flash-attention support with head_dim not a multiple of 64.",
        "We fixed the padding bug (issue #26539) reported by the community.",
        "The patch ( #1234 ) allows the kernel to run on older GPUs.",
        "The patch ( #1234 ) was reverted after the regression report.",
        "The PR ( #26539 ) was merged after the reviewers approved it.",
    ):
        assert not IL._is_release_notes_pr_bullet(text), text


def test_midtext_byline_counter_run_is_gated_on_both_paths():
    """A headline run welded to a mid-text byline counter bar (class 87).

    Live 19.09.26: `cycle_d_docs` stored the `Demystifying the Compression ...`
    header row. `_strip_byline_stack` (class 15) covers the same vocabulary but
    uses `.match()`, so it only fires when the byline LEADS the text -- here a
    TitleCase headline run precedes it, which is the discriminator.
    """
    import buffer_store
    leak = ("Demystifying the Compression of Large Language Models Maarten "
            "Grootendorst Jul 22, 2024 544 26 47 Share Translations - Korean - "
            "Chinese - French As their name suggests, Large Language Models "
            "(LLMs) are often too large to run on consumer hardware.")
    assert IL._is_midtext_byline_counter_run(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)

    for text in (
        "Authors: Smith Feb 3, 2026 12 4 9 Share the findings in the appendix.",
        "Smith Feb 3, 2026 12 4 9 Share the findings in the appendix.",
        "Maarten Grootendorst wrote a good overview of quantization for LLMs.",
        "Alice Smith Jan 5, 2026 reported 40% lower decode latency in the quantized model.",
        "The table reported 544 26 47 Share values across the ablation study.",
        "Translations - Korean - Chinese - French were added to the documentation.",
    ):
        assert not IL._is_midtext_byline_counter_run(text), text


def test_relative_time_counter_row_is_gated_on_both_paths():
    """A feed row: section label + relative time + bare counters + headline (88).

    Live 19.09.26: `cycle_f_multi_domain` / `cycle_a_technews` stored two physics
    feed rows. The conjunction (relative time AND two bare counters AND a
    Capitalized headline word) is the discriminator; the bare relative time is
    ordinary prose.
    """
    import buffer_store
    leak_a = ("General Physics 52 minutes ago 0 0 Circular Rydberg atoms set three "
              "records, staying stable for 11 milliseconds Rydberg atoms are "
              "considered promising building blocks for quantum computers.")
    leak_b = ("Physics 6 hours ago 0 6 Mobile trap transports 92 antiprotons by road "
              "and stores them for over a month in world first In March 2026, "
              "scientists succeeded in transporting antiprotons by road.")
    for leak in (leak_a, leak_b):
        assert IL._is_relative_time_counter_row(leak)
        assert IL._is_junk(leak)
        assert buffer_store.is_junk(leak)

    for text in (
        "The job finished 52 minutes ago and 0 0 errors were logged by the runner.",
        "It ran 3 hours ago with 12 4 retries recorded in the log.",
        "Physics 6 hours ago reported 0 errors in the log file.",
        "Circular Rydberg atoms stayed stable for 11 milliseconds in the experiment.",
        "The feed listed 0 0 failures 6 hours ago in the summary.",
    ):
        assert not IL._is_relative_time_counter_row(text), text


def test_project_count_news_tail_is_gated_on_both_paths():
    """A newsroom cross-post counter bar anchored at the TAIL (class 89).

    Live 19.09.26: `cycle_e_competitors` stored
      "PowerContext, Context for work that humans and agents hand off and
       continue 1 project | news."
    Only 93 chars, so the >=90 length trust never applied. The `$` anchor is the
    discriminator -- `2 projects | news.` mid-sentence is ordinary prose.
    """
    import buffer_store
    leak = ("PowerContext, Context for work that humans and agents hand off and "
            "continue 1 project | news.")
    assert IL._is_project_count_news_tail(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)

    for text in (
        "We reviewed 3 projects | news. and wrote summaries afterwards.",
        "PowerContext is a context layer for work that humans and agents hand off.",
        "The newsroom covered 5 projects in its weekly roundup.",
    ):
        assert not IL._is_project_count_news_tail(text), text


def test_course_cta_opener_is_gated_on_both_paths():
    """A course landing-page arrow CTA welded to its bundle headline (class 90).

    Live 19.09.26: `cycle_g_security` stored the `Start this course -> Building
    AI Agents ...` row. `_is_course_cta_chrome` keys on a promo voice AND a
    bundle phrase and does not match this shape; the START-anchored arrow CTA is
    the discriminator (the bare phrase is ordinary prose).
    """
    import buffer_store
    leak = ("Start this course \u2192 Building AI Agents How agents work, how they "
            "fail, and how to design ones worth deploying.")
    assert IL._is_course_cta_opener(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)

    for text in (
        "Start this course to learn how agents work and how they fail in production.",
        "The course starts with an overview of agent architectures and evaluation.",
        "Building AI Agents How agents work, how they fail, and how to design ones worth deploying.",
    ):
        assert not IL._is_course_cta_opener(text), text


def test_code_linenum_run_is_gated_on_both_paths():
    """A code block whose line-number gutter was welded in (class 92).

    Live 19.09.26: `cycle_d_docs` stored the `The Challenge: Full Fine-Tuning
    Limitations ...` row twice. The discriminator is the digit RUN welded
    directly to a code comment (`# <Cap>`); a bare `1 2 3 4 5 6` run is
    pagination chrome / ordinary prose.
    """
    import buffer_store
    leak = ("The Challenge: Full Fine-Tuning Limitations Resource Requirements Full "
            "fine-tuning requires updating all model parameters, leading to "
            "substantial computational overhead: 1 2 3 4 5 6 # Full fine-tuning a "
            "7B parameter model model = AutoModelForCausalLM .")
    assert IL._is_code_linenum_run(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)

    for text in (
        "Line 1 2 3 4 5 6 of the config shows the setup steps.",
        "The code `1 2 3 4 5 6 # setup` appears in the notebook listing.",
        "The notebook shows model = AutoModelForCausalLM with a 7B parameter model.",
        "Full fine-tuning requires updating all model parameters, leading to overhead.",
    ):
        assert not IL._is_code_linenum_run(text), text


def test_share_exec_summary_header_is_gated_on_both_paths():
    """An article header's `Share Executive Summary` affordance pair (class 93).

    Live 19.09.26: `cycle_g_security` stored the `LLM Prompt injection Share
    Executive Summary Palo Alto Networks ...` row. The space-glued PAIR of the
    page's OWN two affordances is the discriminator; each word alone is ordinary
    English.
    """
    import buffer_store
    leak = ("LLM Prompt injection Share Executive Summary Palo Alto Networks has "
            "released \u201c Securing GenAI: A Comprehensive Report on Prompt "
            "Attacks: Taxonomy, Risks, and Solutions ,\u201d which surveys "
            "emerging prompt-based attacks on AI applications and AI agents.")
    assert IL._is_share_exec_summary_header(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)

    for text in (
        "Readers can Share an Executive Summary with their team.",
        "The Share button and the Executive Summary tab were both added.",
        "The Executive Summary is at the top of the report.",
        "Palo Alto Networks released a report on prompt-based attacks on AI apps.",
    ):
        assert not IL._is_share_exec_summary_header(text), text


def test_citation_counter_run_is_gated_on_both_paths():
    """A reference-counter run welded into prose (class 94).

    Live 19.09.26: `cycle_f_multi_domain` stored the `AI systems without human
    supervision ... 4 4 5 5 However ... 1 1 2 2 .` row -- an academic page whose
    citation-marker runs were welded into the prose. The four-number run welded
    to a Capitalized word is the discriminator.
    """
    import buffer_store
    leak = ("AI systems without human supervision for worker surveillance and "
            "quality inspection in industrial sectors 4 4 5 5 However, the bill "
            "does allow authorities to use real-time biometric surveillance in "
            "public spaces for national security reasons 1 1 2 2 .")
    assert IL._is_citation_counter_run(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)

    for text in (
        "The report counted 248 and 191 and 28 events across the window.",
        "The ablation used 544 26 47 combinations in the study.",
        "AI systems without human supervision are a regulatory concern.",
        "Authorities may use real-time biometric surveillance for national security.",
    ):
        assert not IL._is_citation_counter_run(text), text


def test_relative_stamp_news_run_is_gated_on_both_paths():
    """A newsroom feed run welded to its own composite relative stamps (class 95).

    Live 19.09.26: `cycle_f_multi_domain` stored the `OpenAI is buying failed
    biotech trade secrets to train medical models 3 days, 11 hours ago
    Salesforce built Koa ... 3 days, 12 hours ago Anthropic and OpenAI want an
    AI freeze.` row -- three news headlines, each welded to a composite
    `<n> days, <n> hours ago` stamp. The COMPOSITE stamp plus REPETITION plus a
    capitalised headline word is the discriminator: the bare composite stamp
    matches declarative prose, and the plain relative stamp is deliberately
    ungated (class 94's archive entry). Do NOT apply `re.IGNORECASE` here --
    `[A-Z][a-z]` must stay case-sensitive or the rule becomes a topic word.
    """
    import buffer_store
    leak = ("OpenAI is buying failed biotech trade secrets to train medical models "
            "3 days, 11 hours ago Salesforce built Koa to stop paying Anthropic "
            "and OpenAI millions 3 days, 12 hours ago Anthropic and OpenAI want "
            "an AI freeze.")
    assert IL._is_relative_stamp_news_run(leak)
    assert IL._is_junk(leak)
    assert buffer_store.is_junk(leak)

    for text in (
        "The migration finished 3 days, 11 hours ago and the report captured it.",
        "We compared 3 days, 11 hours ago against 2 weeks, 5 hours ago in the benchmark.",
        "It was posted 2 days ago. For the latest trending models, see Section 3.",
        "Posts appeared 3 days, 2 hours ago and 4 days, 1 hour ago on the site.",
        "The review took 2 days ago | 4 comments per reviewer were recorded.",
        "CameronBanga 5 hours ago | 10 comments 58 points Some headline about models.",
        "The paper was published 12 days, 3 hours ago in the journal.",
        "A fix landed 5 hours ago in the parser and another 2 hours ago in the router.",
        "Last Update: 2 days ago See Project 9 SomeRepo An agent framework.",
        "The incident started 3 days, 11 hours ago and the postmortem followed, but the timeline is clear.",
        "AshleysBrain 3 hours ago | 9 comments 77 Neovim have a ~$800k Bitcoin donation.",
    ):
        assert not IL._is_relative_stamp_news_run(text), text


def test_bare_markdown_heading_fragment_is_gated_on_both_paths():
    """A stored answer that is ONE markdown heading line (class 96, 19.09.26).

    Live leak: `## Ollama Model Analysis for Your Hardware` (42 chars, so the
    >=90 length trust never applied). Both gates missed it because no marker
    matched a bare heading. A real heading WITH a body, a hashtag run and
    ordinary one-line prose must all stay learnable.
    """
    import buffer_store
    leak = "## Ollama Model Analysis for Your Hardware"
    assert IL._is_bare_markdown_heading_fragment(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True
    assert IL._is_bare_markdown_heading_fragment("## LoRA Fine-Tuning Best Practices") is True

    for prose in (
        "## Optimization\n\nPagedAttention reduces memory fragmentation by up to 60% in practice.",
        "The docs use a ## heading level for the feature name.\nInstall with pip.",
        "## Ollama Model Analysis for Your Hardware is the section we read.",
        "Markdown headings like ## Usage appear throughout the guide.",
        "# Title\nSome body text follows the heading here.",
        "## Usage\npip install vllm",
        "# ai # webdev # tutorial # productivity A coding agent that writes code",
        "vLLM reduces memory fragmentation and improves throughput on 7B to 70B models.",
    ):
        assert not IL._is_bare_markdown_heading_fragment(prose), prose
        assert not buffer_store._is_nav_chrome(prose), prose


def test_german_glossary_echo_is_gated_on_both_paths():
    """The agent's own two-pair German glossary line (class 97, 19.09.26).

    Live leak: `German: Fehler-Capture = error capture, Kategorisierung =
    categorization, Memory` (80 chars). Two `=` pairs AND no closing punctuation
    is the discriminator; real glossary prose carries a period, or one pair.
    """
    import buffer_store
    leak = "German: Fehler-Capture = error capture, Kategorisierung = categorization, Memory"
    assert IL._is_german_glossary_echo(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True

    for prose in (
        "German: Wort = word, Satz = sentence.",
        "German: this sentence explains the German word for error handling.",
        "We translated the German: Wort = word list into the glossary.",
        "The German: prefix marks the glossary entries in the file.",
        "Fehler-Capture = error capture, Kategorisierung = categorization in the log.",
    ):
        assert not IL._is_german_glossary_echo(prose), prose
        assert not buffer_store._is_nav_chrome(prose), prose


def test_related_subjects_sidebar_is_gated_on_both_paths():
    """A publisher's welded related-content sidebar label run (class 99, 19.09.26).

    Live leak (240 chars, so the >=90 length trust applied and the digit-bearing
    `(c) 2024` fed the technical-signal gate): the whole answer was the article
    card PLUS the site's "Explore related subjects Discover the latest articles,
    books and news ... suggested using machine learning" sidebar. The
    discriminator is the sidebar's own welded label run, not the topic:
    `Discover the latest articles in our library and read them.` is ordinary
    prose and must stay learnable.
    """
    import buffer_store
    leak = ("Techno-Critics\u2019 Article 30 June 2025 Considerations About the Regulatory "
            "Framework of Cryptocurrency Chapter \u00a9 2024 Explore related subjects Discover "
            "the latest articles, books and news in related subjects, suggested using machine learning.")
    assert IL._is_related_subjects_sidebar(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True

    for prose in (
        "Discover the latest articles in our library and read them.",
        "Explore related subjects in the paper before you start the experiment.",
        "The agent recommends related subjects, books and news every morning.",
        "We suggest using machine learning for the routing decision.",
        "Machine learning suggests related subjects for the reader.",
        "Chapter 3 covers the regulatory framework of cryptocurrency.",
        "Discover the latest articles, books and news in the field.",
    ):
        assert not IL._is_related_subjects_sidebar(prose), prose
        assert not buffer_store._is_nav_chrome(prose), prose
def test_aggregator_affordance_min_run_is_gated_on_both_paths():
    """A model-aggregator landing page stored as the answer (class 102, 19.09.26).

    Live leak (221 chars, so the >=90 length trust applied and the digits fed the
    technical-signal gate): a pricing/ranking page whose affordance labels
    (`Read full article`, `Try on Vincony`) are welded to the site's own read-time
    label `· 9 min`. The discriminator is that WELD, not the topic: the read-time
    label alone matches a legitimate article header
    (`General Compute · March 18, 2026 · 6 min read Quantization reduces ...`),
    and the topic sentence alone (`AI aggregators let you access GPT-5, Claude and
    Gemini from one account without switching tabs.`) is ordinary prose.
    """
    import buffer_store
    leak = ("Pricing GPT-5 Claude Gemini Vincony Read full article \u2192 Try on Vincony "
            "Ranking Jul 15, 2026 \u00b7 9 min Best AI Model Aggregators in 2026 (Ranked) "
            "AI aggregators let you access GPT-5, Claude, Gemini and more from one account.")
    assert IL._is_aggregator_affordance_min_run(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_aggregator_affordance_min_run(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True

    for prose in (
        "AI aggregators let you access GPT-5, Claude and Gemini from one account without switching tabs.",
        "You can try the aggregator before paying: the free tier covers 200 requests per day.",
        "Read the full article before you cite the benchmark numbers in your own report.",
        "Try on a smaller model first and compare the latency yourself.",
        "Our ranking puts the fastest model first and the cheapest one second.",
        "The pricing page lists GPT-5, Claude and Gemini side by side for comparison.",
        "General Compute \u00b7 March 18, 2026 \u00b7 6 min read Quantization reduces the memory footprint of large language models.",
    ):
        assert not IL._is_aggregator_affordance_min_run(prose), prose
        assert not buffer_store._is_nav_chrome(prose), prose


def test_startup_portal_nav_run_is_gated_on_both_paths():
    """A tech-startup portal's welded nav label run (class 103, 19.09.26).

    Live leak: the portal's own nav labels (`Featured Startup Spotlight Startups
    Tech Startup News Tech Startups Technology News`) plus a headline and a
    `Posted On <date> <n> <n>.` byline credit, stored as the answer. Each part
    alone is ordinary prose and must stay learnable - the discriminator is the
    portal's OWN three-label nav run.
    """
    import buffer_store
    leak = ("Home \u00bb Artificial Intelligence Data Featured Startup Spotlight Startups "
            "Tech Startup News Tech Startups Technology News Claude-powered AI coding agent "
            "deletes production database and backups in 9 seconds Daniel Levi Posted On "
            "April 28, 2026 0 3.")
    assert IL._is_startup_portal_nav_run(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_startup_portal_nav_run(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True

    for prose in (
        "Featured startup spotlight: our editors pick one young company every week.",
        "Tech startup news and fresh funding rounds reach our desk every Tuesday.",
        "Startups in the data and AI space raised 12 million euros in the second quarter.",
        "Home \u00bb Artificial Intelligence is the breadcrumb the crawler stored as nav.",
        "The article was posted on April 28, 2026 and corrected two days later.",
        "Daniel Levi reported on the outage and the team published a postmortem.",
        "The AI coding agent deleted the production database in nine seconds after a mis-scoped token.",
    ):
        assert not IL._is_startup_portal_nav_run(prose), prose
        assert not buffer_store._is_nav_chrome(prose), prose

def test_leading_clock_artifact_is_stripped_not_rejected():
    """A leading ", HH:MM AM/PM" truncation artifact is STRIPPED, not rejected.

    Live 19.09.26 (class 104): `cycle_c_github` stored
      ", 03:34 PM Anthropic, the AI company behind the Claude models, announced
       it will begin using user data, ..."
    -- an article header cut so only the dateline tail survived. The paragraph
    after it is real knowledge, so the contract is strip-and-keep (like
    `_strip_dateline_fragment`), never reject.
    """
    import internet_learner as IL
    import buffer_store

    leak = (", 03:34 PM Anthropic, the AI company behind the Claude models, "
            "announced it will begin using user data, including new chat "
            "transcripts and coding sessions, to train its AI models.")
    stripped = IL._strip_leading_clock_fragment(leak)
    assert stripped.startswith("Anthropic"), stripped
    assert not stripped.startswith(","), stripped
    assert IL._clean_insight(leak).startswith("Anthropic"), IL._clean_insight(leak)

    # prose that merely MENTIONS a time must be untouched.
    clean = (
        "Anthropic announced at 03:34 PM that it will train on user data by default.",
        "At 03:34 PM the company published its updated training-data policy.",
        "The meeting at 03:34 PM covered the new retention rules for transcripts.",
        "Anthropic's change takes effect September 28, 2025, at 03:34 PM.",
        "The log shows 03:34 PM as the moment the policy was posted by the vendor.",
    )
    for text in clean:
        assert IL._strip_leading_clock_fragment(text) == text, text
        assert not buffer_store.is_junk(text), text


def test_hn_show_run_row_is_gated_on_both_paths():
    """An HN item row with the site's own `Show HN:` tag is chrome (class 105).

    Live 19.09.26 (class 105), verbatim from the buffer row (cycle_b_papers):
      "CameronBanga 9 hours ago | 10 comments 175 Show HN: Cactus Needle 3:
       8-29MB automation models can match DeepSeek V4 Flash (cactuscompute."
    Class 37 needs the feed unit REPEATED and class 49 needs the feed's own
    `by <handle>`/`on Hacker News` / `New ask Hacker News story` label; this
    page ships the HN-native `Show HN:` tag instead.
    """
    import internet_learner as IL
    import buffer_store

    leak = ("CameronBanga 9 hours ago | 10 comments 175 Show HN: Cactus Needle 3: "
            "8-29MB automation models can match DeepSeek V4 Flash (cactuscompute.")
    assert IL._is_hn_show_run_chrome(leak), leak
    assert buffer_store._is_hn_show_run_chrome(leak), leak
    assert IL._is_junk(leak), leak
    assert buffer_store.is_junk(leak), leak

    # class 37's own clean single-occurrence control must STAY learnable: it
    # carries the feed unit but no `Show HN:` tag.
    assert not IL._is_hn_show_run_chrome(
        "CameronBanga 5 hours ago | 10 comments 58 points Some headline about models.")
    assert not IL._is_junk(
        "CameronBanga 5 hours ago | 10 comments 58 points Some headline about models.")

    clean = (
        "The review took 2 days ago | 4 comments per reviewer were recorded.",
        "The ticket was closed 3 days ago | 12 comments in the audit log.",
        "A Show HN post about Cactus Needle gathered 10 comments 9 hours ago.",
        "The Show HN thread had 175 points and 10 comments within 9 hours.",
        "Show HN submissions rarely reach 175 points before the first 9 hours.",
        "Our scraper captured a Show HN item; it showed 9 hours ago and 10 comments.",
    )
    for text in clean:
        assert not IL._is_hn_show_run_chrome(text), text
        assert not buffer_store._is_hn_show_run_chrome(text), text
        assert not IL._is_junk(text), text
        assert not buffer_store.is_junk(text), text



def test_de_double_optin_newsletter_is_gated_on_both_paths():
    """A German newsletter double-opt-in confirmation page (class 107, 20.09.26).

    Live leak: `cycle_e_competitors` stored the whole-page consent chain
    (promo hook + signup confirmation) as the answer. Each part alone is
    ordinary German prose and must stay learnable - the discriminator is the
    CONJUNCTION of >=2 independent confirmation markers.
    """
    import buffer_store
    leak = ("Fast geschafft – mehr als 3000 Urlaubsträume warten auf Sie Bitte bestätigen "
            "Sie Ihre Anmeldung durch einen Klick auf den Link in der E-Mail, die wir Ihnen soeben "
            "geschickt haben.")
    assert IL._is_de_double_optin_newsletter_chrome(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_de_double_optin_newsletter_chrome(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True

    for prose in (
        "Fast geschafft: der Benchmark lief in 42 Sekunden durch, nachdem wir den Tokenizer gecacht haben.",
        "Bitte bestätigen Sie Ihre Anmeldung, sobald Sie das Formular für den Workshop ausgefüllt haben.",
        "Urlaubsträume sind ein häufiges Thema in Reiseprospekten und Werbetexten.",
        "Ein Klick auf den Link in der Fußzeile öffnet die vollständige Dokumentation des Projekts.",
        "Mehr als 3000 Modelle wurden für die Studie evaluiert und die Ergebnisse sind öffentlich.",
        "Die Bestätigungsmail wird soeben geschickt haben, sobald der Server die Queue abarbeitet.",
    ):
        assert not IL._is_de_double_optin_newsletter_chrome(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store._is_nav_chrome(prose), prose


def test_jobboard_ad_run_is_gated_on_both_paths():
    """A job-board ad/slogan run (class 108, 20.09.26).

    Live leak: `cycle_c_github` stored the recruiter brand repeated >=2x welded
    to its own slogan, a SERP ad run rather than knowledge. The slogan alone is
    ordinary prose, so the repeated brand is required - and the framework row
    that carries the brand twice WITHOUT the slogan must stay learnable.
    """
    import buffer_store
    leak = ("Haystack - Tech hiring without the hassle — Explore the tech scene on your terms. "
            "Haystack connects world-class tech talent with employers that match their interests "
            "and values.; Haystack – Get hired without the hassle — Haystack is where the best "
            "in tech go to stay ahead")
    assert IL._is_jobboard_ad_run_chrome(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_jobboard_ad_run_chrome(leak) is True
    assert buffer_store._is_nav_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True

    for prose in (
        "The recruiter said the role was tech hiring without the hassle, which is just their slogan.",
        "Haystack is an open-source NLP framework for building search pipelines in production.",
        "pip install haystack-ai Get Started with Haystack builds an orchestration pipeline.",
        "Without the hassle of a manual migration, the team moved the index in one afternoon.",
        "The job board matches candidates with employers whose interests and values align.",
    ):
        assert not IL._is_jobboard_ad_run_chrome(prose), prose
        assert not IL._is_junk(prose), prose
        assert not buffer_store._is_nav_chrome(prose), prose

def test_own_plan_plus_run_covers_continuous_learning_loop_title():
    """Class 81 (live 20.09.26): the own-artifact deliverable plan with a THIRD
    title -- `Continuous Learning Loop: ...` -- which class 66's dangling-marker
    form and class 80's alternation both missed. Live leak (98 chars, so the
    >=90 length trust never applied):

        Continuous Learning Loop: Error-Capture + Categorization + Memory
        + Auto-Skill-Generation + Trend.

    Measured: 1 buffer hit and it IS the leak -> 0 FPs on 11 prose controls, 0
    test literals; the 4 `longterm_episodes` hits are the SAME own-artifact
    strings (English + German), not world knowledge.
    """
    import buffer_store

    leak = ("Continuous Learning Loop: Error-Capture + Categorization + Memory "
            "+ Auto-Skill-Generation + Trend.")
    assert IL._is_own_plan_plus_run(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_own_plan_plus_run(leak) is True
    assert buffer_store.is_junk(leak) is True

    # the German twin of the same own artifact must be gated too
    leak_de = ("Kontinuierliche Lernschleife: Fehler-Capture + Kategorisierung "
               "+ Memory + Auto-Skill-Generierung + Trend")
    assert IL._is_own_plan_plus_run(leak_de) is True
    assert IL._is_junk(leak_de) is True

    # the class-66/80 originals must keep firing (no regression)
    assert IL._is_own_plan_plus_run(
        "Energy efficiency: AI performance optimization: Python script for RAM/Disk/"
        "Cron monitoring + optimization suggestions + skill + cron job every 12h.") is True

    # ordinary prose that merely mentions the loop, a `+`-run, or a title must stay learnable
    counter_cases = [
        "The pipeline: data ingestion: raw logs + normalization + dedup + feature extraction runs hourly.",
        "Continuous learning matters because models degrade as the world changes.",
        "Continuous Learning Loop: the team monitors drift weekly and retrains quarterly.",
        "The loop is: collect metrics + aggregate + report, and it runs every night.",
        "A reinforcement learning loop uses reward + policy + value estimation.",
        "Error capture + categorization + memory consolidation improved retention.",
        "Agent design: memory + tools + planning + reflection are the four pillars.",
        "The study reports gains from experience replay + target networks + reward shaping.",
        "Auto-skill generation, memory updates and trend tracking form the learning loop.",
        "Vendor: Acme + Globex + Initech were compared in the benchmark.",
        "Continuous Learning Loop: Fehler-Capture + Kategorisierung + Memory.",
    ]
    for c in counter_cases:
        assert IL._is_own_plan_plus_run(c) is False, c
        assert IL._is_junk(c) is False, c
        assert buffer_store._is_own_plan_plus_run(c) is False, c


def test_de_nav_weld_headline_chrome_is_gated_on_both_paths():
    """Class 82 (live 20.09.26): a German site's nav-label WELD stored as the
    answer -- the page's menu lost its separators, so its own labels run into
    the article headline:

        Blogs Karriere Ueber uns U Vertrieb kontaktieren LLM Agent Sandboxing:
        Wie MCP, Tool Permissions und DSGVO zusammenpassen

    The WELD is the discriminator: a `,`/`und`-joined list of the SAME labels
    is ordinary German prose and stays learnable. Measured: 1 buffer hit and it
    IS the leak -> 0 FPs on 14 hostile controls, 0 of 6,118 longterm_episodes,
    0 test literals.
    """
    import buffer_store

    leak = ("Blogs Karriere \u00dcber uns U Vertrieb kontaktieren LLM Agent Sandboxing: "
            "Wie MCP, Tool Permissions und DSGVO zusammenpassen")
    assert IL._is_de_nav_weld_headline_chrome(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_de_nav_weld_headline_chrome(leak) is True
    assert buffer_store.is_junk(leak) is True

    counter_cases = [
        "Unser Blog erklaert, wie Kunden den Vertrieb kontaktieren: Ein Leitfaden fuer Anfaenger.",
        "Die Blogs zeigen, wie man den Vertrieb kontaktieren kann. Praxisbeispiel: Ein Kunde aus Berlin.",
        "Blogs, Karriere, \u00dcber uns \u2014 so sieht eine typische Navigation aus.",
        "Ein Artikel beschreibt: Blogs helfen dem Vertrieb. Kontaktieren Sie uns fuer Details.",
        "Der Blogbeitrag traegt den Titel Vertrieb kontaktieren: Strategien fuer 2026.",
        "Blogs und Karriere sind Menuepunkte, \u00dcber uns folgt danach.",
        "Titel: Blogs im Vertrieb. Kontaktieren Sie uns, um mehr zu erfahren.",
        "Karriere und Blogs sowie Vertrieb kontaktieren sind drei Navigationslinks.",
        "Impressum Datenschutz AGB: rechtliche Pflichtangaben.",
        "News Presse Team: die Abteilungen der Firma.",
        "Kontakt Impressum Datenschutz \u2014 diese Links stehen im Footer der Seite.",
        "Blogs Karriere \u00dcber uns sind drei Menuepunkte nebeneinander.",
        "Blogs Karriere ist eine verkuerzte Navigation mit zwei Punkten.",
    ]
    for c in counter_cases:
        assert IL._is_de_nav_weld_headline_chrome(c) is False, c
        assert buffer_store._is_de_nav_weld_headline_chrome(c) is False, c



def test_dated_listing_run_is_gated_on_both_paths():
    """An aggregator LISTING run of dated headlines (class 113, 20.09.26).

    Live leak: `cycle_e_competitors` (and an earlier `cycle_a_technews`) stored a
    blog INDEX feed -- several unrelated headlines welded together by their own
    `- <date>` tails -- rather than an article. Both gates must refuse it.

    The discriminator had to be tightened during measurement: a form requiring
    only two date stamps 120 chars apart also matched a Markdown metrics TABLE
    (`| Erstellt | 16. August 2026 | ... | Letzter Push | 28. August 2026 |`) in
    `longterm_episodes`, which is real knowledge. Requiring the row DASH in BOTH
    slots removes it, so both prose controls below must stay learnable.
    """
    import buffer_store
    leak = ("ChatGPT Work - 12th September 2026 OpenAI agents attacked RubyGems back in May - "
            "12th September 2026 Some thoughts on the Navier\u2013Stokes Millennium Prize Problem - "
            "8th September 2026 This is a link post by Simon Willison, posted on 27th February 2026 .")
    assert IL._is_dated_listing_run(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_dated_listing_run(leak) is True
    assert buffer_store.is_junk(leak) is True

    for prose in (
        "The model was released on 12 September 2026 and the benchmark ran on 8 September 2026 without errors.",
        "On 3rd September 2026 we shipped v2 and on 12th September 2026 we rolled it back after a regression.",
        "Between 12 September 2026 and 8 September 2026 the eval suite grew from 279 to 280 passing tests.",
        "Released 12. September 2026 - improved throughput by 30% - measured against the 8. September 2026 baseline.",
        "The 2026-09-12 run and the 2026-09-08 run differ by 4% median latency.",
        "March 23, 2026 was a Monday; the release shipped the following Friday.",
    ):
        assert not IL._is_dated_listing_run(prose), prose
        assert not buffer_store._is_dated_listing_run(prose), prose

    table = ("| Erstellt | 16. August 2026 (vor 12 Tagen) | | Letzter Push | 28. August 2026 |")
    assert not IL._is_dated_listing_run(table), table
    assert not buffer_store._is_dated_listing_run(table), table


def test_readtime_card_widget_is_gated_on_both_paths():
    """A CMS review card's date + glued read-time badge (class 114, 20.09.26).

    Live leak: `cycle_f_multi_domain` stored the card header and its read-time
    badge. The badge is the discriminator -- the renderer emits the doubled unit
    `min min read`, which ordinary prose never does.
    """
    import buffer_store
    leak = ("Claw Mar 23, 2026 Comparison 15 min min read OpenClaw vs Other AI Agent Frameworks - "
            "Comprehensive Comparison 2026 In-depth comparison of OpenClaw with LangChain, AutoGPT, "
            "CrewAI, and other popular AI agent frameworks.")
    assert IL._is_readtime_card_widget(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_readtime_card_widget(leak) is True
    assert buffer_store.is_junk(leak) is True

    for prose in (
        "A 15 min read is long for a blog post but short for a technical whitepaper.",
        "min min read appears twice because the badge text was duplicated by the renderer.",
        "The article is a 12 min read and covers PagedAttention and continuous batching.",
        "PagedAttention reduces memory fragmentation; vLLM reports 2-4x throughput on a 12 GB GPU.",
        "LoRA fine-tuning cut trainable parameters to 0.1% while keeping 96% full fine-tune quality.",
        "The aggregator lists 14 articles; each row is a headline followed by a publication date.",
    ):
        assert not IL._is_readtime_card_widget(prose), prose
        assert not buffer_store._is_readtime_card_widget(prose), prose


def test_infobox_factrow_tail_is_gated_on_both_paths():
    """A wiki infobox fact-row tail (class 118, 20.09.26).

    Live leak: `cycle_h_efficiency` stored two infobox fields with the rendered
    relative-age template between them:

        September 2026) Launched 15 January 2001 ; 25 years ago ( 2001-01-15 )
        Content license Creative Commons Attribution/ Share-Alike 4.

    The text OPENS mid-parenthesis -- the extractor cut a field row out of the
    page's infobox, not an article.

    Either half ALONE is a false positive, and measurement proved it before the
    gate was wired: the relative-age template by itself hit 13 hostile prose
    controls (a real sentence may say "PyTorch 1.0 shipped 7 December 2018;
    7 years ago (2018-12-07) the ecosystem was much smaller"), and the license
    label by itself hit 6. The JUXTAPOSITION is the discriminator, so every
    control below must stay learnable.
    """
    import buffer_store

    leak = ("September 2026) Launched 15 January 2001 ; 25 years ago ( 2001-01-15 ) "
            "Content license Creative Commons Attribution/ Share-Alike 4.")
    assert IL._is_infobox_factrow_tail(leak) is True
    assert IL._is_junk(leak) is True
    assert buffer_store._is_infobox_factrow_tail(leak) is True
    assert buffer_store.is_junk(leak) is True

    # Each half on its own, in real sentences -- must stay learnable.
    for prose in (
        "PyTorch 1.0 was released 7 December 2018; 7 years ago (2018-12-07) the ecosystem looked very different.",
        "Launched 15 January 2001; 25 years ago (2001-01-15) the site ran on a single server.",
        "The API went live 3 March 2019 ; 7 years ago ( 2019-03-03 ) and is still on v1.",
        "The transformer paper appeared 12 June 2017; 9 years ago (2017-06-12) attention was a niche idea.",
        "Docker 1.0 landed 9 June 2014; 12 years ago (2014-06-09) containers were already old news.",
        "Python 3.11 shipped 24 October 2022; 3 years ago (2022-10-24) type hints were still optional.",
        "Content license terms: you may share and adapt, provided you attribute the source.",
        "The license header says Content license: Apache-2.0 (see NOTICE for attribution).",
        "The paper's content license is Creative Commons Attribution 4.0, so commercial reuse is allowed.",
        "The model card lists: Created by Meta, Content license CC BY-NC 4.0, and Type of site research.",
        "Wikipedia launched on 15 January 2001 and is licensed under Creative Commons Attribution-ShareAlike 4.0.",
        "The dataset is released under a content license; Creative Commons Attribution 4.0 applies.",
    ):
        assert not IL._is_infobox_factrow_tail(prose), prose
        assert not buffer_store._is_infobox_factrow_tail(prose), prose


def test_gh_releases_row_and_slide_nav_chrome_are_gated_on_both_paths():
    """A GitHub releases-page row and a slide-deck nav trio (classes 123/124,
    live 21.09.26).

    The knowledge-to-action competitor cycle kept landing on "signal NOT
    mappable" because the competitor row it analysed was page chrome, not
    competitor intelligence:

      "Released Stride (GitHub Releases) \u2022 1 day, 18 hours ago How to get
       sound effects for your game #gamedev #sounddesign #elevenlabs #ad"
      "ES Show original Previous slide Next slide 1 year ago in Stocks, AI
       Modeling, Business, AI GOOGL Alphabet Shares ..."

    Both cleared BOTH gates: the relative-time digits satisfied the
    technical-signal gate and the length cleared the floor.

    The GitHub marker requires BOTH the literal site label and a
    relative-time stamp -- a bare "(GitHub Releases)" substring was measured
    and REJECTED because it flags genuine prose that mentions the feature
    (see the counter-cases). The slide marker keys on control ADJACENCY,
    never a single control.

    Measured: 1 buffer hit each, and that hit IS the leaking row -> 0 prose
    FPs over 3,059 longterm_episodes + 7,442 buffer_junk rows.
    """
    sys.path.insert(0, str(TRAINING))
    import buffer_store

    leaks = (
        "Released Stride (GitHub Releases) \u2022 1 day, 18 hours ago How to "
        "get sound effects for your game #gamedev #sounddesign #elevenlabs #ad",
        "ES Show original Previous slide Next slide 1 year ago in Stocks, AI "
        "Modeling, Business, AI GOOGL Alphabet Shares",
    )
    for leak in leaks:
        assert buffer_store.is_junk(leak), leak
        assert IL._is_junk(leak), leak

    # counter-cases: every marker is also a shape real prose can contain.
    for prose in (
        "GitHub Releases are built automatically from tags; the workflow "
        "publishes artifacts and the changelog is generated from commits.",
        "The release pipeline pushes (GitHub Releases) metadata into our "
        "registry so downstream consumers can pin exact versions.",
        "In the previous slide we showed the latency curve; the next slide "
        "covers throughput scaling on the same hardware.",
        "Click Show original to read the untranslated post and its replies.",
    ):
        assert not buffer_store.is_junk(prose), prose
        assert not IL._is_junk(prose), prose



def test_release_note_emoji_bullet_is_gated_on_both_paths():
    """Class 125 (live 21.09.26): a model card's emoji-led changelog tail.

    `cycle_b_papers` stored
      "F16 on BitNet-embedding-270M prefill (8 threads) Supports I2_S conversion
       with optimized kernels on x86 CPUs Lossless inference with 2 bits per
       weight 07/16/2026: <megaphone> Released BitNet Embeddings 0."
    -- a date stamp, then an emoji-led changelog bullet, welded onto the card's
    feature list. 185 chars WITH digits, so the >=90 length trust and the
    technical-signal gate both fired. `_is_release_notes_pr_bullet` needs a
    `( #N )` PR number and `_is_changelog_chain` needs >=3 bracketed links, so
    both missed it.

    The discriminator is the CONJUNCTION (date/version stamp within 40 chars of
    an emoji-led changelog verb). The emoji+verb alone was measured and
    REJECTED: 4 real longterm_episodes rows plus the hostile control
    "openamer ... update" + warning sign matched it. 0 FP on both corpora now.
    """
    import buffer_store
    leak = ("F16 on BitNet-embedding-270M prefill (8 threads) Supports I2_S "
            "conversion with optimized kernels on x86 CPUs Lossless inference "
            "with 2 bits per weight 07/16/2026: \U0001F4E3 Released BitNet "
            "Embeddings 0.")
    assert IL._is_release_note_emoji_bullet(leak) is True
    assert buffer_store._is_release_note_emoji_bullet(leak) is True
    # both public gates must agree, not just the helper
    assert IL._is_junk(leak) is True
    assert buffer_store.is_junk(leak) is True

    # a second shape: bracketed version stamp + rocket bullet
    leak2 = ("B @ 3/4 bits models [2024-10-18] \U0001F310 Open source community "
             "contributes Mistral Large Instruct 2407 (123B) models "
             "[2024-10-14] \U0001F680 Add early ROCm support.")
    assert buffer_store._is_release_note_emoji_bullet(leak2) is True

    # real prose / real knowledge must stay learnable
    clean = [
        "Released the 4-bit quantized weights at a 1.2% accuracy cost.",
        "Added prefix caching so repeated system prompts are served from cache.",
        "\U0001F680 The model hit 92% on the eval, up from 88% last quarter.",
        "Update the config to raise the context window, then re-run the benchmark.",
        "Improved recall by 7 points after switching to the smaller model.",
        "v0.4.1 cut memory 60% and added prefix caching to the agent loop.",
        "Fixed a race in the writer that dropped two records per thousand.",
        "Guten Tag! \U0001F44B Schoener Banner-Start, die Instanz v2026.08.24 laeuft.",
        "Version 2.1 reduced latency by 30% on the same hardware.",
        "The paper reports 07/16/2026 as the submission date and 92% accuracy.",
        "Let me load the key references on delegation and background systems.",
    ]
    for c in clean:
        assert buffer_store._is_release_note_emoji_bullet(c) is False, c
        assert IL._is_release_note_emoji_bullet(c) is False, c
# class 126 (live 21.09.26): a platform's OWN client-SDK package family named as
# the SUBJECT, welded to an "open-source SDKs (e.g. `...`)" opener. Live leak
# (rows 9/137/169 of online_buffer, plus buffer_junk + kta_log +
# internet_learn_log -- 3x on 19.09/21.09):
#   "YouTube's open-source SDKs (e.g., `youtubei1`, `youtubei2`, `youtubei3`) are
#    the only reliable way to programmatically control the API, bypass rate
#    limits, and access private endpoints"
# The sentence DRIFTS between reads (`youtubei-python`/`youtubei-webapp` ->
# `youtubei1`..`youtubei3`), so the exact-match `_is_duplicate` gate let the same
# page into the training buffer twice. This is platform plumbing for that site's
# own API, not agent-actionable knowledge.
#
# A generic same-`u` near-duplicate gate was MEASURED AND REJECTED first: the
# three leak rows score token-set Jaccard 0.241/0.308/0.327 while legitimate
# DISTINCT rows for one `u` reach 0.400 -- no separation, so any threshold would
# delete real learnings. Hence a narrow chrome rule, FP-measured, not a
# similarity threshold.
_IL126_SDK_FAMILY_LEAK = (
    "YouTube's open-source SDKs (e.g., `youtubei1`, `youtubei2`, `youtubei3`) are "
    "the only reliable way to programmatically control the API, bypass rate limits, "
    "and access private endpoints"
)
_IL126_SDK_FAMILY_LEAK_OLD = (
    "YouTube's open-source SDKs (e.g., `youtubei-python`, `youtubei-webapp`) are the "
    "only reliable way to programmatically interact with the platform, bypassing the "
    "restrictive browser-based API"
)
# Generic prose ABOUT open-source SDKs must stay learnable: the package FAMILY is
# the anchor, not the opener.
_IL126_SDK_CONTROLS = [
    "Open-source SDKs for the vector database expose a stable Python API, so an agent "
    "can index documents and query them without re-reading the corpus.",
    "The open-source SDKs (e.g. the Go client) ship weekly releases.",
    "Open-source SDKs are the fastest way to add a provider to an agent, because the "
    "wire format is already documented.",
]


def test_platform_sdk_family_weld_is_rejected():
    import internet_learner as IL
    assert IL._is_platform_sdk_family_weld(_IL126_SDK_FAMILY_LEAK)
    assert IL._is_platform_sdk_family_weld(_IL126_SDK_FAMILY_LEAK_OLD)


def test_platform_sdk_family_weld_reaches_the_learner_gate():
    import internet_learner as IL
    assert IL._is_junk(_IL126_SDK_FAMILY_LEAK)
    assert IL._is_junk(_IL126_SDK_FAMILY_LEAK_OLD)


def test_platform_sdk_family_weld_reaches_the_writer_gate():
    import buffer_store as BS
    assert BS._is_platform_sdk_family_weld(_IL126_SDK_FAMILY_LEAK)
    assert BS.is_junk(_IL126_SDK_FAMILY_LEAK)


def test_generic_open_source_sdk_prose_survives_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL126_SDK_CONTROLS:
        assert not IL._is_platform_sdk_family_weld(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS._is_platform_sdk_family_weld(ctl), ctl
        assert not BS.is_junk(ctl), ctl

# ---------------------------------------------------------------------------
# class 127 (live 21.09.26) -- benchmark-site masthead nav pair (STRIP, not reject)
#
# `cycle_c_github` stored
#   "Aug 10, 2026 See our ethical norms Cite This Benchmark We benchmarked 4
#    popular open-source agentic frameworks across 2,000 runs (5 tasks, 100
#    runs each per framework), measuring end-to-end latency, token
#    consumption, and architectural differences."
# The nav pair carries no capability token, so the KTA competitor-gap
# experiment read the LAST matching buffer row and reported `signal NOT
# mappable` for 46 of its 158 runs -- a CONSUMER defect report that was really
# an UPSTREAM chrome leak. The lede behind the menu is a real multi-framework
# benchmark, so it is a STRIP in the same >= 2-labels-in-the-first-80-chars
# chain form as class 43. Measured: 1 buffer hit (= this leak), 0 prose FPs,
# 0 longterm_episodes FPs, 0 gate-test-literal FPs.
# ---------------------------------------------------------------------------

_IL127_BENCH_MASTHEAD_LEAK = (
    "Aug 10, 2026 See our ethical norms Cite This Benchmark We benchmarked 4 "
    "popular open-source agentic frameworks across 2,000 runs (5 tasks, 100 "
    "runs each per framework), measuring end-to-end latency, token "
    "consumption, and architectural differences."
)

# Topic-matched controls: a sentence a human would write ABOUT the same
# feature. A bare label is ordinary English and must stay byte-identical --
# that is exactly the trap every single-phrase marker died on in class 43.
_IL127_BENCH_MASTHEAD_CONTROLS = [
    "The paper cites this benchmark as the strongest evidence for grouped state tracking.",
    "See our ethical norms page for how we handle user data.",
    "We benchmark our own agent against four open-source frameworks every quarter.",
    "Cite This Benchmark in your paper and the leaderboard updates automatically.",
    "The benchmark measured end-to-end latency and token consumption across runs.",
]


def test_benchmark_masthead_nav_pair_is_stripped_from_the_insight():
    import internet_learner as IL
    stripped = IL._strip_masthead_nav_chain(_IL127_BENCH_MASTHEAD_LEAK)
    assert "See our ethical norms" not in stripped
    assert "Cite This Benchmark" not in stripped
    assert stripped.startswith("We benchmarked 4 popular"), stripped
    # idempotent
    assert IL._strip_masthead_nav_chain(stripped) == stripped
    # the whole pipeline must land on the lede, free of the menu
    cleaned = IL._clean_insight(_IL127_BENCH_MASTHEAD_LEAK, 300)
    assert cleaned, "the benchmark lede is real prose and must survive"
    assert not IL._MASTHEAD_NAV_RE.search(cleaned), cleaned


def test_benchmark_masthead_controls_stay_byte_identical():
    import internet_learner as IL
    for text in _IL127_BENCH_MASTHEAD_CONTROLS:
        assert IL._strip_masthead_nav_chain(text) == text.strip(), text

# ---------------------------------------------------------------------------
# class 128 (live 21.09.26) -- AI-agent INDEX landing page nav run (REJECT)
#
# The second of the TWO rows that made the KTA competitor-gap experiment report
# `signal NOT mappable` / map a false capability. The consumer reads the LAST
# lexicon-matching buffer row, so a nav row appended late poisons every
# subsequent run. Measured: 1 buffer hit (= this leak), 0 prose FPs,
# 0 longterm_episodes FPs, 0 gate-test-literal FPs.
# ---------------------------------------------------------------------------

_IL128_AGENT_INDEX_LEAK = (
    "AI Agent Index Categories Find Agent + Submit Compare Alternatives Stacks "
    "Advertise API Home / AI Coding Agents Best AI Coding Agents (2026): IDEs, "
    "Terminals, Autonomous Updated September 2026 AI coding agents have moved "
    "well beyond autocomplete."
)

# Topic-matched controls: each conjunct ALONE is ordinary English and must stay
# learnable. This is the trap the single-token marker died on.
_IL128_AGENT_INDEX_CONTROLS = [
    "When you compare alternatives, look at latency before price.",
    "The Advertise API lets partners buy placements programmatically.",
    "Sites often put a Find Agent and a Submit button side by side.",
    "Compare alternatives across frameworks is what the benchmark does.",
    "We advertise an API for partners and compare alternatives in our review.",
]


def test_agent_index_nav_run_is_rejected_on_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_agent_index_nav_run(_IL128_AGENT_INDEX_LEAK)
    assert IL._is_junk(_IL128_AGENT_INDEX_LEAK)
    assert BS._is_agent_index_nav_run(_IL128_AGENT_INDEX_LEAK)
    assert BS.is_junk(_IL128_AGENT_INDEX_LEAK)
    # a landing page must never become a learned insight
    assert IL._clean_insight(_IL128_AGENT_INDEX_LEAK, 300) == ""


def test_agent_index_single_conjunct_prose_survives_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL128_AGENT_INDEX_CONTROLS:
        assert not IL._is_agent_index_nav_run(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS._is_agent_index_nav_run(ctl), ctl
        assert not BS.is_junk(ctl), ctl

# ---------------------------------------------------------------------------
# class 129 (live 21.09.26) -- blog badge ribbon welded to a headline stack
# (REJECT, not strip)
#
# `cycle_d_docs` stored:
#   "Arab World #3 Featured Blog 85% 3 Machine Learning RAG Systems in
#    Production: Architecture, Tradeoffs, and Failure Modes
#    Retrieval-augmented generation (RAG) is the dominant application"
# The site's own card ribbon (rank badge + `Featured Blog` label + percent
# counter + bare index) is welded to the headline stack and its lede. 239
# chars WITH digits, so the >=90 length trust AND the technical-signal gate
# both fired; class 106's rule needs a >=8-token nav vocabulary run and this
# ribbon has none.
#
# REJECT, not strip: the prose behind the ribbon is a generic RAG lede with no
# capability token (same call as class 128). Measured: 1 buffer hit (= this
# leak), 0/7,984 buffer_junk rows, 0/3,059 longterm_episodes, 0/3 controls.
# ---------------------------------------------------------------------------

_IL129_BADGE_RIBBON_LEAK = (
    "Arab World #3 Featured Blog 85% 3 Machine Learning RAG Systems in "
    "Production: Architecture, Tradeoffs, and Failure Modes "
    "Retrieval-augmented generation (RAG) is the dominant application pattern "
    "for large language models in 2026."
)

# Topic-matched controls: the label ALONE is ordinary English. A bare
# `Featured Blog` marker was measured and rejected as too broad -- it fired
# on every one of these.
_IL129_BADGE_RIBBON_CONTROLS = [
    "The site's Featured Blog section covers RAG in production systems, and "
    "the 2026 article explains chunking and reranking tradeoffs.",
    "Our Featured Blog post on quantization recovers 97% of fp16 accuracy at INT4.",
    "The Featured Blog archive lists 3 posts about agent evaluation harnesses.",
    "RAG is the dominant application pattern for large language models in 2026, "
    "and chunking decides most of the retrieval quality.",
]


def test_badge_ribbon_chrome_is_rejected_on_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_badge_ribbon_chrome(_IL129_BADGE_RIBBON_LEAK)
    assert IL._is_junk(_IL129_BADGE_RIBBON_LEAK)
    assert BS._is_badge_ribbon_chrome(_IL129_BADGE_RIBBON_LEAK)
    assert BS.is_junk(_IL129_BADGE_RIBBON_LEAK)
    # a badge ribbon must never become a learned insight
    assert IL._clean_insight(_IL129_BADGE_RIBBON_LEAK, 300) == ""


def test_badge_ribbon_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL129_BADGE_RIBBON_CONTROLS:
        assert not IL._is_badge_ribbon_chrome(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS._is_badge_ribbon_chrome(ctl), ctl
        assert not BS.is_junk(ctl), ctl



# class 130 (live 22.09.26): the papers cycle stored a search widget's own
# source tally as a finding. Verbatim from online_buffer.jsonl:
#   Curated from 71 sources: Anthropic, OpenAI, HN, arXiv, GitHub and more.
# Both gates passed it, so both must refuse it; the anchored rule keeps real
# prose that merely mentions a source count.
_IL130_SOURCE_TALLY_LEAK = "Curated from 71 sources: Anthropic, OpenAI, HN, arXiv, GitHub and more."

_IL130_CONTROLS = [
    "The survey was curated from 71 sources across three labs.",
    "Compiled from 12 sources, the report concludes that quantization "
    "recovers 97% of fp16 accuracy.",
    "Data aggregated from 240 sources and more than 30 benchmarks was used "
    "to train the model.",
    "The paper draws on a dataset collected from 8 sources and more, with "
    "96% inter-annotator agreement.",
]


def test_source_tally_cta_is_rejected_on_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_source_tally_cta(_IL130_SOURCE_TALLY_LEAK)
    assert IL._is_junk(_IL130_SOURCE_TALLY_LEAK)
    assert BS._is_source_tally_cta(_IL130_SOURCE_TALLY_LEAK)
    assert BS.is_junk(_IL130_SOURCE_TALLY_LEAK)
    assert IL._clean_insight(_IL130_SOURCE_TALLY_LEAK) == ""


def test_source_tally_prose_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL130_CONTROLS:
        assert not IL._is_source_tally_cta(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS._is_source_tally_cta(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# class 131 (live 22.09.26): the efficiency cycle stored a foreign-language
# forum listing strip -- every entry carrying its own bare ISO date glued to an
# author label. Verbatim from online_buffer.jsonl. Both gates passed it, so
# both must refuse it.
_IL131_DATE_STRIP_LEAK = (
    "Olaewg 2007-09-25 sylvu 2008-02-16 Ave 2008-02-17 Autor: tajger "
    "Data: 2006-07-03 12:20:25 Na pocz\u0105tek tabelka 1-BIA\u0141KA, "
    "2-PRODUKTY NEUTRALNE, 3-W\u0118GLOWODANY BIA\u0141KA: -- mi\u0119so "
    "gotowane; nie zaleca si\u0119 stosowania wieprzowiny."
)

# Real prose that carries several dates -- must stay learnable.
_IL131_CONTROLS = [
    "Version 3.2 (2026-04-01) improved throughput; version 3.3 (2026-05-01) "
    "cut memory; 3.4 (2026-06-01) fixed a crash.",
    "We released 2026-01-01 and 2026-02-01, and 2026-03-01 shipped after that.",
    "The paper (arXiv 2026-01-02) compares 2026-02-03 4-bit and 2026-03-04 "
    "8-bit inference.",
    "Migrations 2026-01-15 2026-02-15 2026-03-15 all passed without error; "
    "the schema is consistent.",
    "Model A 2026-01-01 and Model B 2026-02-01 and Model C 2026-03-01 were "
    "each benchmarked on CPU.",
    "Between alpha 2026-01-01 beta 2026-02-01 gamma 2026-03-01 the numbers "
    "differ",
    "The 2025-01-01 release beat the 2026-01-01 build and the 2027-01-01 plan "
    "is already drafted for review",
    "A 2026-01-01 B 2026-02-01 only two here",
]


def test_date_stamp_listing_strip_rejected_on_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_date_stamp_listing_strip(_IL131_DATE_STRIP_LEAK)
    assert IL._is_junk(_IL131_DATE_STRIP_LEAK)
    assert BS._is_date_stamp_listing_strip(_IL131_DATE_STRIP_LEAK)
    assert BS.is_junk(_IL131_DATE_STRIP_LEAK)
    assert IL._clean_insight(_IL131_DATE_STRIP_LEAK) == ""


def test_date_stamp_listing_prose_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL131_CONTROLS:
        assert not IL._is_date_stamp_listing_strip(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS._is_date_stamp_listing_strip(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# class 132 (live 22.09.26): the technews cycle stored a news photo-credit
# strip welded to the article byline and dateline. Verbatim shape from
# online_buffer.jsonl. Both gates must refuse it.
_IL132_CREDIT_LEAK = (
    "D3sign/STOCK PHOTO/Getty Images By Mason Leib April 29, 2026, "
    "5:39 PM A software company founder wen"
)

# Real prose that mentions credits, authors, or dates must stay learnable.
_IL132_CONTROLS = [
    "The photo credit reads Getty Images; the article it illustrates was "
    "published on April 29, 2026 and updated later that day.",
    "A stock photo of a data centre. Caption: the facility went live on "
    "May 3, 2025 after an 18-month build.",
    "By Sarah Chen and Mark Ruiz the paper was submitted on June 2, 2026 at "
    "10:15 AM to the conference.",
    "AP Photo archives hold thousands of frames; the earliest dates from "
    "January 4, 1971.",
    "By Jane Doe September 3, 2026, 8:00 AM the quarterly report landed.",
    "The report, by Mason Leib, argues that quantization recovers most "
    "accuracy at 4 bits.",
]


def test_credit_byline_run_rejected_on_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_credit_byline_run(_IL132_CREDIT_LEAK)
    assert IL._is_junk(_IL132_CREDIT_LEAK)
    assert BS._is_credit_byline_run(_IL132_CREDIT_LEAK)
    assert BS.is_junk(_IL132_CREDIT_LEAK)
    assert IL._clean_insight(_IL132_CREDIT_LEAK) == ""


def test_credit_byline_prose_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL132_CONTROLS:
        assert not IL._is_credit_byline_run(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS._is_credit_byline_run(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# --- class 133 (22.09.26): doc-site product nav welded to a vendor SDK label
# Live leak: cycle_d_docs stored, verbatim from online_buffer.jsonl,
#   "API, Infinite Possibilities Reference Qualcomm Cloud AI home Qualcomm
#    Cloud AI SDK download Qualcomm Cloud AI API reference User Guide OCP
#    Microscaling Formats (MX) Specification efficient-transformers Welcome
#    to Efficient-Transformers Documentation!"
# 250 chars of pure sidebar/product nav, zero prose; the >=90 length trust
# and the digits-free technical-signal gate both let it through.
_IL133_LEAK = (
    "API, Infinite Possibilities Reference Qualcomm Cloud AI home "
    "Qualcomm Cloud AI SDK download Qualcomm Cloud AI API reference User "
    "Guide OCP Microscaling Formats (MX) Specification efficient-transformers "
    "Welcome to Efficient-Transformers Documentation!"
)
# Counter-cases: each carries ONE of the welded tokens pair, never both --
# these are the phrases that made the bare forms unusable.
_IL133_CONTROLS = [
    "The API reference for the agent runtime lists every tool and its parameters.",
    "Infinite possibilities in agent design come from composing narrow tools.",
    "Welcome to Efficient-Transformers Documentation, the reference for CPU inference.",
    "Efficient-Transformers documentation covers quantization recipes for CPU-only inference.",
    "Qualcomm Cloud AI SDK download is documented on the vendor portal, with release notes per version.",
    "The OCP Microscaling Formats (MX) specification defines block-scaled FP8 and FP4 encodings for inference.",
]


def test_docsite_product_nav_weld_rejected_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_junk(_IL133_LEAK), _IL133_LEAK
    assert BS.is_junk(_IL133_LEAK), _IL133_LEAK
    assert IL._clean_insight(_IL133_LEAK) == ""


def test_docsite_product_nav_weld_prose_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL133_CONTROLS:
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl

# --- class 134 (22.09.26): a NEWSROOM INDEX page is not an article
# Live leak: cycle_a_technews stored, verbatim from online_buffer.jsonl,
#   "UK My dream to serve in the UK army was ended by childhood eye surgery
#    Some 114,000 Army application were rejected on medical grounds in the past
#    five years, Freedom of Information figures show."
# The top search result was the truncated URL `https://www.bbc.com/news/articles`
# (an index, not an article). deep_learn scored a "sentence" that is really
# CARD[i]'s country tag welded to CARD[i+1]'s headline; the strip's relative
# stamps sit between the cards and are stripped by `_clean_insight`, so the
# stored string carries no `ago` and no text-level rule can see the boundary.
#
# The fix is PAGE-LEVEL: a newsroom index repeats the site's own relative-stamp
# unit across its card stream; an article carries at most one. This is the real
# BBC index window around the leaking card (measured 22.09.26: 10 stamps in the
# exact 4000-char window deep_learn scores).
_IL134_INDEX_PAGE = (
    "More to explore Fat Bear Week: Which bear has put on the most weight? "
    "The iconic contest run by Katmai National Park in Alaska will run from "
    "22-29 of September this year and votes can be cast online. 6 hrs ago "
    "US &amp; Canada What we found in Earl Spencer&#x27;s controversial Diana "
    "memoir What further revelations are going to appear now the full details "
    "of his Diana book are published? 8 hrs ago UK My dream to serve in the UK "
    "army was ended by childhood eye surgery Some 114,000 Army application were "
    "rejected on medical grounds in the past five years, Freedom of Information "
    "figures show. 5 hrs ago England The simple skincare routine for teens that "
    "actually works - and five expert tips From popping spots to getting enough "
    "sleep, experts share their advice on the best way to look after teenage "
    "skin. 5 hrs ago Health "
    "Toxic chemicals from a fire at a battery recycling plant are flowing into "
    "a nearby river, officials say, prompting a health warning for residents. "
    "2 days ago Science "
    "The court heard the defendant had been dismissed from his post three "
    "months before the incident took place. 12 hours ago UK "
    "A new study suggests the treatment could help thousands of patients each "
    "year if regulators approve it for wider use. 3 days ago Health"
)

# Counter-cases: real ARTICLE prose, each carrying at most ONE relative stamp --
# these are the sentences that made a bare `<n> hours ago` unusable as a signal.
_IL134_PROSE_CONTROLS = [
    # the class-95 rejected control: one stamp inside ordinary prose
    "It ran 3 hours ago with 12 4 retries recorded in the log.",
    # a real technical insight with exactly one stamp
    "The worker restarted 4 hours ago after the GPU driver 535.104.05 was "
    "upgraded, and quantization recovered 97% of fp16 accuracy afterwards.",
    # an article body carrying a single dateline stamp
    "The BBC understands the decision was taken 5 hours ago and that the "
    "ministry will publish its full response to the consultation next week.",
]


def test_news_index_page_is_rejected_as_a_source_page():
    import internet_learner as IL
    assert IL._is_news_index_page(_IL134_INDEX_PAGE), "index page not flagged"


def test_article_pages_with_one_or_no_relative_stamp_survive():
    import internet_learner as IL
    for ctl in _IL134_PROSE_CONTROLS:
        assert not IL._is_news_index_page(ctl), ctl


def test_short_page_text_never_triggers_the_index_rule():
    import internet_learner as IL
    # a SERP snippet is short; it must keep its prose trust even if it repeats
    # a stamp twice (a snippet has no card stream to weld across).
    snip = ("First item 2 hours ago and second item 3 hours ago, both from the "
            "same aggregator listing.")
    assert not IL._is_news_index_page(snip), snip


# class 135 (22.09.26): an arXiv/new-listing row's submitter WELD. Live: the
# security cycle stored a listing page row -- title, author count, submitter
# ordinal, submitter HANDLE -- as knowledge. The page is an INDEX, not content.
_IL135_LEAK = (
    "VLMs to Robotic Control \u00b7 9 authors 1 Submitted by Williams07 9 One to More, "
    "More to One: Category-Aware Iterative Expert Training for Software Engineering "
    "Agents Logics-MLLM 2 Submitted by paulsmith0217 4 Why Do Video Diffusion Models "
    "Violate Physics?"
)
_IL135_CONTROLS = [
    "The paper has 9 authors and was submitted by researchers at DeepMind in 2024.",
    "Submitted by the maintainers, the PR adds 4 authors to the contributor list.",
    "Authors 9 submitted by reviewers: that is the peer-review flow, not a listing.",
    "arXiv lists 9 authors, 1 submitter and a title per paper on the new-listing page.",
    "The listing shows authors, a submitter handle and the submission date.",
]


def test_arxiv_submitter_weld_rejected_on_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_arxiv_submitter_run(_IL135_LEAK), _IL135_LEAK
    assert IL._is_junk(_IL135_LEAK), _IL135_LEAK
    assert BS._is_arxiv_submitter_run(_IL135_LEAK), _IL135_LEAK
    assert BS.is_junk(_IL135_LEAK), _IL135_LEAK
    assert IL._clean_insight(_IL135_LEAK) == ""


def test_arxiv_submitter_weld_prose_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL135_CONTROLS:
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# class 136 (22.09.26): an aggregator card header (date + category + read-time
# badge) welded onto the article's own title and lede. The badge ALONE is not
# the call -- the TitleCase continuation (the article title) is required, which
# is what keeps a sentence that merely QUOTES such a badge learnable.
_IL136_LEAK = (
    "Sep 13, 2026 Read AI Agents 9 min OpenAI Agents API: Managed Infrastructure "
    "for AI Agents OpenAI launched the Agents API in public beta, putting the Codex "
    "agent harness behind one managed API call for building production AI agents."
)
_IL136_CONTROLS = [
    "Sep 13, 2026 Read the OWASP report; it documents the top 10 LLM risks for 2026.",
    "On Sep 13, 2026 Read the docs for 5 min before filing the bug; it saves time.",
    "Sep 13, 2026 Read AI Agents 9 min is the card badge, not a sentence.",
    "Sep 13, 2026 Read AI Agents 9 min and then decide whether the API fits.",
    "Mar 23, 2026 Read OpenClaw vs Other AI Agent Frameworks in 15 min for the TLDR.",
    "The article is a 9 min read and covers the Agents API harness in depth.",
    "In 2024 Read AI Agents covered 9 minutes of context on the harness.",
    "An aggregator renders each row as a date, a title, a category and a read time.",
]


def test_aggregator_card_header_weld_rejected_on_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_aggregator_card_header_weld(_IL136_LEAK), _IL136_LEAK
    assert IL._is_junk(_IL136_LEAK), _IL136_LEAK
    assert BS._is_aggregator_card_header_weld(_IL136_LEAK), _IL136_LEAK
    assert BS.is_junk(_IL136_LEAK), _IL136_LEAK
    assert IL._clean_insight(_IL136_LEAK) == ""


def test_aggregator_card_header_weld_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL136_CONTROLS:
        assert not IL._is_aggregator_card_header_weld(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# class 137 (22.09.26): a docs site's breadcrumb run welded to a REPEATED
# category+title prefix. The crumb run alone is legitimate prose (4 hostile
# controls start "Home / <section> / ..."); only the weld with the restated
# opening four words is chrome.
_IL137_LEAK = (
    "Home / AI Guides / 12 Best Open-Source AI Agent Frameworks (2026) \U0001f4d6 "
    "Guide 12 Best Open-Source AI Agent Frameworks (2026) Compare 12 open-source "
    "AI agent frameworks for production workflows, multi-agent systems, Python "
    "services, TypeScript apps and RAG."
)
_IL137_CONTROLS = [
    "Home / Docs / Getting started with the agent runtime explains how to configure providers.",
    "Home / AI Guides / A practical introduction to retrieval augmented generation for engineers.",
    "Home / Blog / Understanding why language models hallucinate in long contexts.",
    "Home / Learn / How to detect hallucinations in LLM outputs with hidden-state probes.",
    "Home / Guides / Building a production multi-agent system with Python and TypeScript.",
    "Home > Products > The enterprise data platform unifies ingestion, storage and query in one place.",
    "Home / AI Guides / Quantization cuts memory use; the guide walks through four techniques step by step.",
]


def test_breadcrumb_title_repeat_gated_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_breadcrumb_title_repeat(_IL137_LEAK), _IL137_LEAK
    assert IL._is_junk(_IL137_LEAK), _IL137_LEAK
    assert BS._is_breadcrumb_title_repeat(_IL137_LEAK), _IL137_LEAK
    assert BS.is_junk(_IL137_LEAK), _IL137_LEAK
    assert IL._clean_insight(_IL137_LEAK) == ""


def test_breadcrumb_title_repeat_prose_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL137_CONTROLS:
        assert not IL._is_breadcrumb_title_repeat(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# class 35 widening (22.09.26): `_FULL_DATE_RE` accepted only FULL month names,
# so the live leak `Sep 24, 2025 ... Sep 18, 2025 ... ...` (a date-stamped
# headline listing) read 0 hits under class 35 and passed BOTH gates. The
# abbreviated form is now accepted; the Title-Case density test is unchanged,
# which is what keeps ordinary prose that merely CITES two dates learnable.
_IL35_LEAK = (
    "Sep 24, 2025 Deep Dive into Context Engineering for Agents Sep 18, 2025 "
    "Architectures for Multi-Agent Systems Sep 8, 2025 Bringing AI Observability "
    "Behind the Firewall: Deploying On-Premise AI Sep 8, 2025 Understanding Why "
    "Language Models Hallucinate?"
)
_IL35_CONTROLS = [
    "The runtime was updated on Sep 24, 2025 and again on Sep 18, 2025 to fix the parser.",
    "We shipped Sep 24, 2025 builds and compared them with Sep 18, 2025 builds across three machines.",
    "Our release notes for Sep 24, 2025 mention streaming; the Sep 18, 2025 notes mention pagination.",
    "On Jan 5, 2026 the team froze the schema, and on Feb 9, 2026 they migrated it.",
    "GPT-4 (2023) and GPT-5 (2024) were compared on Jan 5, 2026 and Feb 9, 2026 harnesses.",
    "Twelve open-source frameworks were benchmarked on Sep 24, 2025 and Sep 18, 2025.",
    "...posts under headings like Insights Jul 17, 2026 and News May 29, 2026, but the agent should parse the article body.",
]


def test_date_heading_listing_accepts_abbreviated_months():
    import internet_learner as IL
    assert IL._FULL_DATE_RE.findall("Sep 24, 2025 and Sep 18, 2025"), "abbrev months must match"
    assert IL._FULL_DATE_RE.findall("Sept 8, 2025 and Jan. 5, 2026"), "Sept/Jan. forms must match"
    assert not IL._FULL_DATE_RE.findall("The builds were Jan 5 and Feb of 2026"), "must not over-match"
    assert IL._is_date_heading_listing(_IL35_LEAK), _IL35_LEAK


def test_date_heading_listing_abbrev_leak_gated_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_junk(_IL35_LEAK), _IL35_LEAK
    assert BS.is_junk(_IL35_LEAK), _IL35_LEAK
    assert IL._clean_insight(_IL35_LEAK) == ""
    for ctl in _IL35_CONTROLS:
        assert not IL._is_date_heading_listing(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# class 138 (22.09.26): an ALL-CAPS nav lockup welded to prose AND repeated in
# Title Case.  Live leak -- a competitor's "Platform Demo" banner stored TWICE
# in online_buffer.jsonl (241 -> 239 records after the purge):
#   "Platform Demo SOLACE AGENT MESH Take AI agents from idea to production,
#    and keep making them better Solace Agent Mesh is an agent development and
#    runtime platform that lets you build, test, deploy, observe and improve
#    every agent through one lifecycle."
# 252 chars, no digits, dense technical nouns -> the >=90 length trust AND the
# technical-signal gate both passed it.
# NOTE: every control below was MEASURED (tmp/probe_cls138f.py), never invented;
# the two that killed the bare forms are marked.
_IL138_LEAK = (
    "Platform Demo SOLACE AGENT MESH Take AI agents from idea to production, "
    "and keep making them better Solace Agent Mesh is an agent development and "
    "runtime platform that lets you build, test, deploy, observe and improve "
    "every agent through one lifecycle."
)
_IL138_CONTROLS = [
    # killed the WELD-only form (26 prose FPs without the case-shift conjunct)
    "Alles erledigt. Hier die Zusammenfassung:",
    # killed the CASE-SHIFT-only form (2 hits, one of them real prose)
    "Ich habe nun genug recherchiert. Hier ist die vollstaendige, strukturierte Competitive Analysis fuer OpenAmer.",
    # the lockup shape reused in an ordinary sentence
    "Platform Demo AGENT RUNTIME shows how a request is routed to a worker.",
    "Platform Demo AGENT MESH walks through how teams take AI agents from prototype to production.",
    # the vendor's own name in prose -- killed the bare-name forms
    "The Solace Agent Mesh documentation explains how to deploy an agent runtime to production.",
    "We compared three agent development platforms and Solace Agent Mesh came out on top for throughput.",
    "The SOLACE benchmark suite measures latency under load.",
    # the tagline alone -- killed the bare-tagline form
    "Take AI agents from idea to production is a claim every vendor makes; this one backs it with a lifecycle view.",
    # the demo label alone -- killed the bare `platform demo` form
    "Platform Demo: watch a five minute walkthrough of the build pipeline.",
    "Platform demos are useful, but a demo is not an architecture.",
    # the lifecycle sentence alone
    "Our agent platform lets you build, test, deploy, observe and improve every agent through one lifecycle, with 99.9% uptime.",
    # other ALL-CAPS lockups that are NOT case-shifted
    "See the product demo VIDEO LIBRARY for recorded sessions from the launch.",
    "Agent mesh topologies route work between workers; see the ARCHITECTURE NOTES.",
    "The AGENT SDK exposes tools; the Agent SDK also ships a CLI.",
]


def test_caps_nav_lockup_weld_gated_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_caps_nav_lockup_weld(_IL138_LEAK), _IL138_LEAK
    assert BS._is_caps_nav_lockup_weld(_IL138_LEAK), _IL138_LEAK
    assert IL._is_junk(_IL138_LEAK), _IL138_LEAK
    assert BS.is_junk(_IL138_LEAK), _IL138_LEAK
    assert IL._clean_insight(_IL138_LEAK) == ""


def test_caps_nav_lockup_weld_prose_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL138_CONTROLS:
        assert not IL._is_caps_nav_lockup_weld(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# class 139 (22.09.26): a landing-page marketing-SLOGAN clause stored as the
# answer.  Live leak -- first seen and stored 15.09 21:12, REFUSED as duplicate
# on every cycle since, then stored AGAIN 22.09 09:11 (the buffer rotates ~200
# rows/day against a 300-row cap, so exact `_is_duplicate` cannot help across a
# rotation and the row came back):
#   "Operator prepping for month-end Pull 50+ invoices from 15+ portals in
#    under 5 minutes - no mental load."     (103 chars, digits present)
# The digits satisfied the technical-signal gate; the row is a product CLAIM
# with no technical content.
# Every control was MEASURED (tmp/probe_post138b.py), never invented.
_IL139_LEAK = (
    "Operator prepping for month-end Pull 50+ invoices from 15+ portals "
    "in under 5 minutes \u2014 no mental load."
)
_IL139_CONTROLS = [
    # the leak's own words reused in ordinary sentences
    "Operator prepping for month-end pulls invoices from fifteen portals.",
    "The agent reduced the operator's mental load during month-end close.",
    "Pull 50 invoices from 15 portals, then reconcile them against the ledger.",
    "Month-end close needs 50+ invoices pulled from 15+ portals in a batch.",
    "Batch jobs finish in under 5 minutes when the cache is warm.",
    "The scheduler completes the sweep in under 10 minutes \u2014 a useful budget.",
    "The job finishes in under 5 minutes \u2014 the em dash there is just punctuation.",
    "Inference drops to under 2 minutes \u2014 no change to accuracy.",
    # killed the structural "in under N minutes + dash" form (4 control FPs)
    "Reconciliation happens in under 5 minutes \u2014 no mental gymnastics required.",
    "The agent handles 15+ portals in under 5 minutes \u2014 and logs every action.",
    "Retries complete in under 5 minutes, and the ledger is updated afterwards.",
    "The pipeline runs in under 5 minutes, no manual step is needed.",
    "Under 5 minutes is the target for the whole invoice sweep.",
]


def test_marketing_slogan_clause_gated_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_junk(_IL139_LEAK), _IL139_LEAK
    assert BS.is_junk(_IL139_LEAK), _IL139_LEAK
    assert IL._clean_insight(_IL139_LEAK) == ""


def test_marketing_slogan_prose_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL139_CONTROLS:
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# class 140 (22.09.26): a paper/arXiv AUTHOR LIST with affiliation superscripts
# stored as the answer. Live: cycle_g_security stored a paper landing page's
# author block TWICE ("Sahar Abdelnabi* 1 , Benjamin Pannell* 1 , ... , and
# Javier Rando 3 (*: Core contributors)."), 251 chars -> cleared the >=90 "long
# prose" trust, and the affiliation digits fed the technical-signal gate. The
# existing arXiv helpers key on DIFFERENT halves: _is_arxiv_abstract_chrome
# needs page-label markers, class 135 needs the `<N> authors <N> Submitted by`
# submitter weld. Discriminator = >= 5 name+digit SEGMENTS, rejected when a
# segment's leading word is a structural label.
#
# Controls are lists a HUMAN writes in ordinary word order. A run of
# STRUCTURAL units ("Section 3, Figure 2, Table 1, ...") is real content and
# MUST stay learnable -- that is what the struct guard exists for. Every
# control was MEASURED, never invented.
_IL140_LEAK = (
    "Sahar Abdelnabi* 1 , Benjamin Pannell* 1 , Giovanni Cherubin* 1 , "
    "Ahmed Salem 1 , Andrew Paverd 1 , Conor Mac Amhlaoibh 1 , Joshua Rakita 1 , "
    "Santiago Zanella-Beguelin 1 , Egor Zverev 2 , Mark Russinovich 1 , "
    "and Javier Rando 3 (*: Core contributors)."
)

_IL140_CONTROLS = [
    "Section 3, Figure 2, Table 1, Appendix 4, Note 5 and Step 6 hold the detail.",
    "Version 1, Version 2, Version 3, Version 4, Version 5 of the API all shipped.",
    "Layer 3, Layer 4, Layer 5, Layer 6 and Layer 7 dominate the latency budget.",
    "Day 1, Day 2, Day 4, Day 8 and Day 15 are the retry schedule.",
    "Step 1, Step 2, Step 3, Step 4 and Step 5 are all idempotent by design.",
    "Variant 1, Variant 2, Variant 3, Variant 4 and Variant 5 all failed the test.",
    "Sahar Abdelnabi, Benjamin Pannell, Giovanni Cherubin and Andrew Paverd wrote it.",
    "The paper has 3 authors and was submitted by Maria Keller in March 2026.",
    "The report lists 12 contributors, and Javier Rando is the lead.",
    "Nine authors signed the open letter about agent safety research.",
    "PyTorch 2.0 shipped in 2024 with TorchInductor 1 as the default backend.",
    "We tested GPT-4 1 and Claude 3 2 across five benchmark suites.",
    "The invoice arrives on day 1, day 15 and day 30 of the month.",
    "Relevant findings 1 and 2, plus metric 3, contradicted the earlier result.",
    "The benchmark dataset 4 and the dataset 5 disagree on tokenisation.",
]


def test_affiliation_author_list_gated_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_junk(_IL140_LEAK), _IL140_LEAK
    assert BS.is_junk(_IL140_LEAK), _IL140_LEAK
    assert IL._clean_insight(_IL140_LEAK) == ""


def test_affiliation_author_list_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL140_CONTROLS:
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# class 141 (22.09.26): an aggregator CARD AFFORDANCE RAIL welded to the card's
# own title and lede -- "GAIA - Open-source framework ... Apr 13, 2026 -
# galaxyLogic - View Original [star] Save TL;DR Highlight AMD has released ...".
# 246 chars WITH digits -> the >=90 "long prose" trust AND the technical-signal
# gate both fired. The existing aggregator helpers key on the WRONG half:
# _AGGREGATOR_AFFORDANCE_MIN_RE needs "read full article"/"try on X" + a
# "[dot] N min" read-time, and _AGGREGATOR_CARD_HEADER_RE (136) needs a
# "Read <label> N min" badge. Discriminator = the rail itself: "View Original"
# ... bookmark star ... "Save" ... "TL;DR" in ONE run (the conjunction, because
# "View Original" alone and the star alone are ordinary UI words).
_IL141_LEAK = (
    "GAIA \u2013 Open-source framework for building AI agents that run on "
    "local hardware Apr 13, 2026 \u2022 galaxyLogic \u2022 View Original "
    "\u2606 Save TL;DR Highlight AMD has released GAIA, a Python/C++ framework "
    "that allows AI Agents to run on local PCs without the cloud."
)

_IL141_CONTROLS = [
    "We saved the TL;DR for the end of the paper so readers get the full argument first.",
    "Click Save Original to keep a copy of the document in your working directory.",
    "The team wrote a TL;DR Highlight reel summarising the benchmark results.",
    "View Original files before overwriting them; the agent keeps a backup.",
    "A user can save an article for later reading without leaving the page.",
    "The aggregator card shows a title, a date and an author, then the lede follows.",
    "Open the original document and highlight the section that matters most.",
    "Saving a bookmark is how the crawler remembers a page between runs.",
]


def test_aggregator_card_affordance_rail_gated_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    assert IL._is_junk(_IL141_LEAK), _IL141_LEAK
    assert BS.is_junk(_IL141_LEAK), _IL141_LEAK
    assert IL._clean_insight(_IL141_LEAK) == ""


def test_aggregator_card_affordance_rail_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL141_CONTROLS:
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# class 65 WIDENED (22.09.26): the bare form of the learner's own task template.
# The class-65 rule required the trailing "one sentence" ("Shared underlying
# pattern one sentence."). The live cycle stored the SHORTER variant --
# "Shared underlying pattern." -- verbatim, which the old regex missed entirely
# (the phrase was optional in the prompt, so the model dropped it).
_IL65_BARE_LEAK = "Shared underlying pattern."
_IL65_FULL_LEAK = "Shared underlying pattern one sentence."


def test_bare_prompt_echo_fragment_is_gated_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    for leak in (_IL65_BARE_LEAK, _IL65_FULL_LEAK):
        assert IL._is_prompt_echo_fragment(leak), leak
        assert IL._is_junk(leak), leak
        assert BS.is_junk(leak), leak
        assert IL._clean_insight(leak) == ""


def test_bare_prompt_echo_widening_keeps_real_answers_learnable():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in (
        "The shared underlying pattern is a closed-loop feedback system that "
        "keeps the agent aligned.",
        "Both systems share an underlying pattern: a feedback loop between "
        "planning and evaluation.",
        "Shared underlying patterns across two situations usually reduce to a "
        "feedback loop.",
        "The structural connection between tool usage and system failure is a "
        "missing validation step.",
    ):
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl
# class 141 (22.09.26): a SERP title welded to its own snippet by a YEAR-COLON
# weld, where a NUMERAL phrase or a >=4-token run from the title RECURS in the
# snippet. Live: the 260-row buffer tail carried FOUR rows of one family --
#   "Grok Pricing 2026: $10 Lite, $30 SuperGrok, ... free access, $10 Lite,
#    $30 SuperGrok, $300 Heavy, and $30/user Business plans."
#   "Claude Opus 5 Review 2026: $5/$25, 61 Score, Real API Catch Claude Opus 5
#    launched at $5/$25 per million tokens with 1M context and 128K output."
#   "AI-Agent Tokens Surge 5% as Market Interest Returns May 3, 2026: Virtuals
#    Protocol surged 5% as AI-agent tokens roared back, ..."
#   "Retrieval and Language Systems NER Guide 2026: GLiNER, spaCy, Transformers,
#    and LLMs NER in 2026 means choosing between GLiNER, spaCy, Transformers,
#    and LLM extraction for latency, accuracy, and schema control."
# All four cleared the >=90 "long prose" trust and the technical-signal gate
# (the year stamp, the price tiers, the counts).
#
# NEITHER conjunct separates alone (the AJ/AQ/AR law): the year-colon weld alone
# matched 6 hand-written prose controls, and a bare repeat matched 201
# longterm_episodes. The WELD must be a year-colon inside the first 80 chars and
# the RESTATEMENT must be the same price token, the same `<verb> <n> %` pair, or
# the same 4-token run (naive plural-stemmed, because the NER row drifts
# `LLMs` -> `LLM` and no backreference can see that).
#
# THE CONTROL THAT DECIDES THE RULE is the China-chip row -- a real article the
# strip test asserts must survive byte-identical. It repeats a bare `417%`
# across DIFFERENT verbs, so it is not a pct-pair, and its repeated runs are 2-3
# tokens, so no 4-token window repeats. Every control below was MEASURED against
# the live corpora, never invented.
_IL141_LEAKS = [
    "Grok Pricing 2026: $10 Lite, $30 SuperGrok, $300 Heavy Grok now spans free "
    "access, $10 Lite, $30 SuperGrok, $300 Heavy, and $30/user Business plans.",
    "Claude Opus 5 Review 2026: $5/$25, 61 Score, Real API Catch Claude Opus 5 "
    "launched at $5/$25 per million tokens with 1M context and 128K output.",
    "AI-Agent Tokens Surge 5% as Market Interest Returns May 3, 2026: Virtuals "
    "Protocol surged 5% as AI-agent tokens roared back, fueled by rising volume, "
    "stronger market momentum, and renewed demand for AI-powered crypto projects.",
    "Retrieval and Language Systems NER Guide 2026: GLiNER, spaCy, Transformers, "
    "and LLMs NER in 2026 means choosing between GLiNER, spaCy, Transformers, and "
    "LLM extraction for latency, accuracy, and schema control.",
]

_IL141_CONTROLS = [
    # a real article body that repeats a bare percentage across DIFFERENT verbs:
    # the discriminator test. It must survive BOTH gates byte-identical.
    "China AI Chip Boom: CAICT 417% Demand vs 128% Supply 2026 Caixin Sept 15, "
    "2026: CAICT says China AI compute demand jumped 417% YoY in Q1 vs 128% supply.",
    # a year-colon opening with a price but NO restatement
    "In 2026: the API price is $5 per million tokens and it fell 40% over the year.",
    "Pricing changed in 2026: $10 buys 1M tokens of the small model on the endpoint.",
    "vLLM 0.9 shipped in 2026: PagedAttention cut peak KV-cache memory by 4x on long contexts.",
    "Report 2026: revenue grew to $40M and the margin held at 60% for the quarter.",
    "Training finished on 2026-09-15: 3 epochs, 128 GPUs, and a final loss of 1.82.",
    # a real tier list, no year weld
    "The tiers are Lite $10, Pro $30 and Heavy $300 per month for the same agent runtime.",
    "Cost per token: $5 input, $25 output, which halves at a 90% cache-hit rate.",
    # real prose that repeats a verb+percent pair but has no year weld
    "Accuracy surged 5% after the fix, and the same pipeline held the gain over 10 runs.",
    # real prose naming several tools in a row (the NER row's content twin)
    "We compared GLiNER, spaCy and Transformers for entity extraction, then benchmarked accuracy.",
    "Quantization methods such as GPTQ, AWQ, and SmoothQuant trade accuracy for memory.",
]


def test_serp_title_snippet_repeat_gated_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    for leak in _IL141_LEAKS:
        assert IL._is_junk(leak), leak
        assert BS.is_junk(leak), leak
        assert IL._clean_insight(leak) == "", leak


def test_serp_title_snippet_repeat_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL141_CONTROLS:
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl

_IL142_LEAKS = [
    # the live 22.09.26 leak: article byline + dateline + "Key Takeaways"
    "Written by Gus Mallett Published on April 29, 2026 Key Takeaways PocketOS, "
    "a company that designs software for car rental businesses, had its entire "
    "database mistakenly wiped by an AI agent .",
    # a "min read" blog header leading with the headline
    "NVIDIA RTX PRO 5500 Blackwell: What Actually Fits in 84GB for Local LLMs "
    "(2026) 11 min read Sep 15, 2026 NVIDIA quietly dropped the memory footprint.",
    # a forum byline + piped dateline + comment affordance
    "OpenClaw Like Like Posted by kim Bruning | February 13, 2026, 5:05 pm "
    "Reply to this comment ps.",
    # a CVE advisory card: dateline + Key Takeaways + lede
    "CVE-2026-58138: Orkes Conductor RCE Threatens Agentic Workflows 2026-09-20 "
    "Key Takeaways CVE-2026-58138 is a critical unauthenticated RCE.",
    # a byline-first header
    "Written by Christian Gleitze | Published on June 11, 2026 | 5 min read.",
]

_IL142_CONTROLS = [
    # prose that merely reports a publication act (case-insensitive form fired
    # on this one before the affordance regex was made case-sensitive)
    "The photo credit reads Getty Images; the article it illustrates was "
    "published on April 29, 2026 and updated later that day.",
    "Published on June 17, 2025 / 5:28 PM EDT and later revised, the piece "
    "covers agentic AI.",
    # a genuine technical insight carrying a real dateline and a number -- the
    # topic key is what the gate must NOT react to
    "TLS 1.3 removes a handshake round trip, cutting connection latency by "
    "~33% on high-RTT links, as measured on Sep 15, 2026.",
    # an affordance word in real prose, with no article header shape
    "vLLM prefill throughput improved 40% after enabling prefix caching with "
    "--max-model-len 32768 in the 2.12.0 release.",
    "The paper, published in 2026, shows quantization to 2 bits keeps "
    "perplexity within 5% of fp16.",
]


_IL142_STRIPPED = {
    # index -> the prose that must survive once the header stack is cut.
    # Measured 22.09.26: the strip rescues 24 of the 60 class-142 rows across
    # buffer_junk.jsonl + buffer_junk_archive.jsonl; the rest keep refusing.
    0: "PocketOS, a company that designs software for car rental businesses, had "
       "its entire database mistakenly wiped by an AI agent .",
    1: "NVIDIA quietly dropped the memory footprint.",
}


def test_article_byline_chrome_gated_on_both_paths():
    """An article byline/dateline header stack is refused by BOTH gates.

    Class 142 was added 22.09.26 as a pure reject predicate. That over-rejected:
    24 of 60 refused rows carry REAL prose behind the header, and the cycle only
    logged the bare "shallow + deep read both gated" for them. The header is now
    STRIPPED when the prose behind it survives -- the same doctrine this repo
    already applies to every other header class -- so the raw form is still
    refused while `_clean_insight` returns the salvaged lede.
    """
    import internet_learner as IL
    import buffer_store as BS
    for i, leak in enumerate(_IL142_LEAKS):
        assert IL._is_junk(leak), leak
        assert BS.is_junk(leak), leak          # the raw leak is still refused
        cleaned = IL._clean_insight(leak)
        if i in _IL142_STRIPPED:
            assert cleaned == _IL142_STRIPPED[i], cleaned
        else:
            assert cleaned == "", leak         # header-only rows stay refused


def test_article_byline_chrome_strip_is_precise():
    """The strip must not fire on prose that merely cites a date or an author.

    `region=100` is the guard: measured on 6,128 real episode rows the strip
    fires 0 times, and 0 of the 5 prose controls change. Without it (region=200)
    it fired on 58 rows and broke 36. Do not widen the window.
    """
    import internet_learner as IL
    for ctl in _IL142_CONTROLS:
        assert IL._strip_article_byline_header(ctl) == ctl, ctl


def test_article_byline_chrome_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL142_CONTROLS:
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


_IL145_LEAKS = [
    # the two rows STORED in the live buffer on 22.09.26 -- both passed BOTH
    # gates because the class-142 vocabulary had no spelled-out read-time weld
    # and the dateline had no ordinal day suffix.
    "Category Agents Product Claude apps Date November 10, 2025 Reading time "
    "5 min Share https://claude.",
    "When Models and Chatbots Make Mistakes \U0001f7e2 This article is rated "
    "easy Reading Time: 5 minutes Last updated on March 6th, 2025 Sander "
    "Schulhoff large language models (LLMs) like ChatGPT and GPT-4 have "
    "transformed how we interact with technology.",
]

_IL145_CONTROLS = [
    # REAL prose that opens with the spelled-out read time -- this is the row
    # that killed the UNANCHORED form. No header label follows the weld, so
    # the lookahead keeps it learnable.
    "Reading time: 5 min per 1,000 tokens is the budget we target for the "
    "summarizer, measured on May 3, 2026.",
    # prose that MENTIONS a reading time inside a sentence
    "The team published an article on April 29, 2026 explaining how prompt "
    "injection bypasses tool sandboxes; the reading time was about 8 minutes.",
    "We measured the reading time of the pipeline: 8 min for 4,000 tokens, so "
    "batching cuts it to 2 min.",
    # prose carrying an ORDINAL dateline, which the widened dateline now sees
    "The model was evaluated on March 12th, 2026 and reached 0.81 recall at "
    "5k pairs, a 12% gain over the groupwise INT4 baseline.",
    # a prose row that carries BOTH the widened affordance vocabulary AND an
    # ordinal dateline, but opens as a sentence -- must stay learnable
    "The write-up is dated March 3rd, 2025 and its Reading time 6 min claim "
    "refers to the vLLM benchmark, which reached 41 tok/s at int4.",
]


def test_ordinal_dateline_and_spelled_read_time_gated_on_both_paths():
    """Class 145: the spelled-out read-time weld plus an ORDINAL dateline.

    Live 22.09.26 two rows were STORED (not just refused) -- an article header
    with "Reading time 5 min Share <url>" and one with "This article is rated
    easy Reading Time: 5 minutes Last updated on March 6th, 2025 <lede>". Both
    satisfy the long-prose length trust AND the technical-signal gate (digits),
    so the page's own affordance is the only reliable discriminator.

    Asserted on BOTH gates: `buffer_store.is_junk` must refuse the same rows the
    learner refuses, or the cycle burns itself on a write the writer drops.
    """
    import internet_learner as IL
    import buffer_store as BS
    for leak in _IL145_LEAKS:
        assert IL._is_article_byline_chrome(leak), leak
        assert IL._is_junk(leak), leak
        assert BS.is_junk(leak), leak


def test_spelled_read_time_controls_survive_both_gates():
    """The UNANCHORED weld was MEASURED-AND-REJECTED.

    Without the header-label lookahead the pattern truncates real prose that
    opens with "Reading time: 5 min per 1,000 tokens is the budget ...". The
    anchor is what makes the weld a page-affordance test instead of a topic word
    (the class-135/136 TitleCase-continuation doctrine).
    """
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL145_CONTROLS:
        assert not IL._is_article_byline_chrome(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl
        assert IL._clean_insight(ctl), ctl


# class 143 (22.09.26): a SINGLE Hacker-News-style feed row -- submitter
# handle + relative time + `| N comments` + points + a capitalized trailing
# handle + a colon -- is feed chrome, not knowledge. class 37 keys on the
# unit REPEATED, class 49 on the aggregator's own name, class 83 on an arXiv
# year tail, so a one-item row passed all three.
_IL143_LEAKS = (
    "DeepLogin 5 hours ago | 20 comments 193 Kev: Tiny Jev-like family of "
    "decision models built on top of Qwen3.",
)

# `The review took 2 days ago | 4 comments per reviewer were recorded.` is
# class 37's own pinned clean control -- the new rule must not claim it.
# The `... and then 193 runs: ...` row pins the SCOPED case-sensitivity: a
# plain IGNORECASE `[A-Z]` token flagged that prose in the first draft.
_IL143_CONTROLS = (
    "The review took 2 days ago | 4 comments per reviewer were recorded.",
    "The release added 1,200 commits 5 hours ago | 12 comments and 88 "
    "points per the tracker.",
    "In this paper the authors report 20 comments and 193 downloads: Tiny "
    "Jev is a decision model.",
    "The team logged 5 hours ago | 20 comments and then 193 runs: the "
    "result held.",
    "The 193 comments on the tracker were filed by users in the last 5 "
    "hours ago.",
    "A model card lists 20 comments: 193 runs of the evaluation.",
    "Kev: a Tiny Jev-like family of decision models built on top of "
    "Qwen3 improves accuracy by 9%.",
    "The migration finished 3 days, 11 hours ago and the report captured "
    "it.",
)


def test_feed_handle_unit_row_gated_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    for leak in _IL143_LEAKS:
        assert IL._is_feed_handle_unit_row(leak), leak
        assert IL._is_junk(leak), leak
        assert BS._is_feed_handle_unit_row(leak), leak
        assert BS.is_junk(leak), leak


def test_feed_handle_unit_row_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL143_CONTROLS:
        assert not IL._is_feed_handle_unit_row(ctl), ctl
        assert not BS._is_feed_handle_unit_row(ctl), ctl


# class 144 (22.09.26): a German shop's nav lockup welded to its
# consultation block -- hotline number + opening hours -- is page
# furniture, not knowledge. 104 chars WITH digits, so the length trust
# and the technical-signal gate both fired; no `_is_de_*` rule matched.
_IL144_LEAKS = (
    "Produkten PRODUKTBERATUNG Wir beraten Sie pers\u00f6nlich unter "
    "0681 5866-4466 (Mo-Do 9-18 Uhr, Fr 9-17 Uhr).",
    "Die Beratung erfolgt telefonisch unter der Nummer 0681 5866-4466.",
)

# Neither half may fire alone: `Uhr` is an ordinary German word and a phone
# form is ordinary prose, so the conjunction is what the rule tests.
_IL144_CONTROLS = (
    "Die Beratung erfolgt telefonisch.",
    "Der Anbieter nennt eine Hotline und oeffnende Zeiten.",
    "The evaluation ran for 9-18 hours and produced 0681 samples.",
    "vLLM prefill throughput improved 40% after enabling prefix caching "
    "with --max-model-len 32768 in the 2.12.0 release.",
    "TLS 1.3 removes a handshake round trip, cutting connection latency "
    "by ~33% on high-RTT links, as measured on Sep 15, 2026.",
)


def test_de_consultation_contact_chrome_gated_on_both_paths():
    import internet_learner as IL
    import buffer_store as BS
    for leak in _IL144_LEAKS:
        assert IL._is_de_consultation_contact_chrome(leak), leak
        assert IL._is_junk(leak), leak
        assert BS._is_de_consultation_contact_chrome(leak), leak
        assert BS.is_junk(leak), leak


def test_de_consultation_contact_controls_survive_both_gates():
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL144_CONTROLS:
        assert not IL._is_de_consultation_contact_chrome(ctl), ctl
        assert not BS._is_de_consultation_contact_chrome(ctl), ctl

# class 148 (22.09.26): the learner's OWN bare "Need ..." generation plan.
# `internet_learner._INSTRUCTION_OPENER_RE` refused these at extraction time, so
# `--once` reported "shallow + deep read both gated" -- yet the WRITER gate had
# no counterpart and 12 of them were STORED. The asymmetry is the bug: a row the
# extractor refuses must never reach the buffer. Measured: 12/300 buffer hits,
# all 12 the leak; 0/3,064 `longterm_episodes`; 0/1,278 asserted-clean literals.
_IL148_LEAKS = (
    "Need maybe answer: no single property; safety is multi-layered.",
    "Need address inner alignment, outer alignment, deceptive alignment.",
    "Need maybe structure: - No single property guarantees safety.",
    "Need maybe discuss distributed AI systems = training/inference across many nodes.",
    "Need structure: intro: memory consolidation is offline processing.",
    "Need likely from AI safety.",
    "Need maybe mention no known complete solution.",
    "Need avoid Goodhart, specification gaming.",
    "Need root cause analysis: controlled experiments, change management.",
    "Need maybe",
    "Need likely comprehensive.",
    "Need likely discuss distributed AI systems: training/inference across clusters.",
)

_IL148_CONTROLS = (
    "The plan needs three properties: determinism, bounded latency and replayability.",
    "You need to structure the schema so the migration stays backward compatible.",
    "The router needs a fallback: when the GPU worker is down, the CPU path answers.",
    "Schedulers need to avoid starvation, so the queue uses weighted fair sharing.",
    "The compiler needs to mention which pass removed the dead branch.",
    "Distributed systems need fault tolerance; Raft replicates the log across five nodes.",
    "The shared underlying pattern is a closed-loop feedback system between agent and environment.",
)


def test_need_plan_echo_gated_on_both_paths():
    """A bare imperative "Need ..." echo is refused by BOTH gates."""
    import internet_learner as IL
    import buffer_store as BS
    for leak in _IL148_LEAKS:
        assert IL._INSTRUCTION_OPENER_RE.search(leak), leak
        assert BS._is_need_plan_echo(leak), leak
        assert BS.is_junk(leak), leak


def test_need_plan_echo_controls_survive_both_gates():
    """Real prose that embeds a plan verb (never STARTS with it) stays learnable."""
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL148_CONTROLS:
        assert not BS._is_need_plan_echo(ctl), ctl
        assert not IL._INSTRUCTION_OPENER_RE.search(ctl), ctl


# --- class 149 (23.09.26): a site's nav-menu WELD run into a card title that is
# then repeated.  The leak was STORED (252 chars with digits -> the `>=90` length
# trust AND the technical-signal gate both fired); class 82 is the same family
# but wants labels welded to EACH OTHER plus a TitleCase colon headline, and
# this row welds them to a comma headline instead.
_IL149_LEAKS = (
    "Start Suche VPS-Rechner Vergleichen Blog Suchen \U0001f319 EN DE Home Blog "
    "Haystack: The Open-Source AI Orchestration Framework for Production-Ready RAG "
    "Haystack: The Open-Source AI Orchestration Framework for Production-Ready RAG "
    "Jun 27, 2026 What Is Haystack?",
)

_IL149_CONTROLS = (
    # the topic-word trap: German/English sentences that LIST the same labels
    "Suche, Blog, Preise, Kontakt, Impressum und Datenschutz sind die Menuepunkte.",
    "Die Navigation enthaelt Suche, Blog, Preise und Kontakt in der Kopfzeile.",
    "Der Vergleich der Preise zeigt, dass die Suche im Blog besser funktioniert.",
    "Wir haben die Preise verglichen und die Suche im Blog getestet.",
    "The site navigation offers Suche, Blog and Kontakt in the top bar of every page.",
    "Our crawler skips the navbar: Start, Blog, Suche and Kontakt are all chrome.",
    "The nav bar shows Home, Docs, Pricing, Careers and About Us on one line.",
    "Home Docs Pricing Careers About Us is what the markup literally contains.",
    "The menu labels are Home, Produkte, Preise and Impressum in the German locale.",
    "Startseite, Preise and Kontakt were the three labels we had to white-list.",
    "We compared the nav labels used by three documentation portals for consistency.",
    "The docs and pricing links sit in the footer nav rather than the sidebar.",
    "Login and Sign up are the only two links the crawler could not resolve.",
    "The pricing page and the careers page both redirect to the same marketing site.",
    "A good agent reads the privacy policy and the terms of service before scraping.",
    "The resources section links to docs, a newsletter and a cookie policy notice.",
    # a legit repeat / a legit mention of the brand, each ALONE
    "The pipeline reads docs, then docs again after the cache is cleared, which is fine.",
    "Haystack is an open-source orchestration framework for RAG pipelines.",
    "The Haystack docs explain how to build a production-ready RAG pipeline.",
    "Our slogan is simple: build fast, ship fast, and build fast again tomorrow.",
)


def test_nav_weld_repeat_chrome_gated_on_both_paths():
    """A nav-menu weld run + adjacent exact repeat is refused by BOTH gates."""
    import internet_learner as IL
    import buffer_store as BS
    for leak in _IL149_LEAKS:
        assert BS._is_nav_weld_repeat_chrome(leak), leak
        assert BS.is_junk(leak), leak
        assert IL._is_nav_weld_repeat_chrome(leak), leak
        assert IL._writer_gate_refuses(leak), leak
        assert IL._is_junk(leak), leak


def test_nav_weld_repeat_controls_survive_both_gates():
    """Prose that lists the same nav labels, or repeats a phrase, stays learnable.

    Neither half of the conjunction may fire alone: nav tokens in prose score a
    run of 3-6 (the trap), and an ordinary repeat is not ADJACENT.
    """
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL149_CONTROLS:
        assert not BS._is_nav_weld_repeat_chrome(ctl), ctl
        assert not IL._is_nav_weld_repeat_chrome(ctl), ctl


def test_nav_weld_repeat_neither_half_is_sufficient():
    """Disjoint halves: the conjunction is the discriminator, not either side."""
    import buffer_store as BS
    nav_only = "Suche, Blog, Preise, Kontakt, Impressum und Datenschutz sind die Menuepunkte."
    assert BS._nav_weld_run(nav_only) >= 3
    assert not BS._has_adjacent_exact_repeat(nav_only)
    rep_only = "The pipeline reads docs, then docs again after the cache is cleared, which is fine."
    assert not BS._nav_weld_run(rep_only) >= 3
    assert not BS._has_adjacent_exact_repeat(rep_only)


def test_vllm_server_log_line_gated_on_both_paths():
    """A raw vLLM server log line is refused by BOTH gates (class 155).

    Live 23.09.26: the docs cycle stored "Using max model len 98304 (APIServer
    pid=90) INFO 11-28 11:46:45 [scheduler." -- chrome truncated mid-token; its
    digits satisfied the technical-signal gate and it cleared the length check.
    """
    import internet_learner as IL
    import buffer_store as BS
    for leak in _IL155_LEAKS:
        assert IL._is_junk(leak), leak
        assert IL._writer_gate_refuses(leak), leak
        assert BS.is_junk(leak), leak


def test_vllm_log_controls_survive_both_gates():
    """Same-topic PROSE stays learnable: the gate targets the log SHAPE only."""
    import internet_learner as IL
    import buffer_store as BS
    for ctl in _IL155_CONTROLS:
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


# --- class 155: a raw vLLM server log line is chrome, not knowledge ----------
_IL155_LEAKS = (
    "Using max model len 98304 (APIServer pid=90) INFO 11-28 11:46:45 [scheduler.",
)
# Same TOPIC as the leak (the classic trap), but real prose -> must survive.
_IL155_CONTROLS = (
    "Set max_model_len to your longest served context, then tune "
    "gpu_memory_utilization so the KV cache still fits.",
    "vLLM raises max_num_batched_tokens to 98304 so long prompts fit while the "
    "KV cache footprint stays predictable.",
    "The scheduler processes waiting and running queues every step; prefill and "
    "decode are split across them.",
    "A worker process with pid 90 failed to bind the port; the runbook explains "
    "how to detect a stale port holder.",
    "The docs describe the APIServer as an OpenAI-compatible front end for the "
    "continuous-batching scheduler.",
    "Reading a raw log line is not learning until it is interpreted in a runbook "
    "entry that names the symptom and the fix.",
    "We measured a 31 percent peak-memory reduction from paged attention during "
    "warmup of the inference server.",
)
# --- class 157: a docs/TOC heading stack welded to an interrogative heading ---
_IL157_LEAKS = (
    "Evaluate API Compatibility And Integration Needs Plan For Monitoring, "
    "Scaling, And Maintenance vLLM Alternatives By Deployment Scenario "
    "Production LLM Inference Needs More Than A Serving Engine FAQs About "
    "vLLM Alternatives Is SGLang Better Than vLLM?",
    "Batch Scheduling and Concurrency Tensor Parallelism for Multi-GPU "
    "Monitoring Memory in Real Time Full Production Configuration How vLLM "
    "Uses GPU Memory vLLM allocates GPU memory into three pools: model "
    "weights, KV cache, and activation memory.",
)
# Same TOPIC as the leaks (the classic trap), but real prose -> must survive.
_IL157_CONTROLS = (
    "Evaluate API compatibility and integration needs before choosing a serving "
    "stack; plan for monitoring, scaling, and maintenance over the first year.",
    "Production LLM inference needs more than a serving engine: you also need a "
    "scheduler with continuous batching and a KV-cache aware router.",
    "Is SGLang better than vLLM for prefix-heavy workloads? Benchmarks suggest a "
    "30% throughput gain on shared system prompts.",
    "Step 2 explains How the scheduler batches requests, and Step 3 covers Why "
    "the KV cache is pooled.",
    "The agent must decide Which Tool To Call and How To Recover from a failed call.",
    "Q: Which model should I use for coding? A: Use the larger variant; it "
    "handles long contexts better.",
    "The pipeline has three stages. What happens next is that the scheduler "
    "reorders the queue and the cache is flushed.",
    "vLLM allocates GPU memory into three pools: model weights, KV cache, and "
    "activation memory.",
)


def test_docs_heading_qweld_is_gated_on_both_paths():
    """A docs heading stack welded to a question is chrome on BOTH gates."""
    import internet_learner as IL
    import buffer_store as BS
    for leak in _IL157_LEAKS:
        assert IL.is_docs_heading_qweld(leak), leak
        assert BS.is_docs_heading_qweld(leak), leak
        assert IL._is_junk(leak), leak
        assert BS.is_junk(leak), leak
    for ctl in _IL157_CONTROLS:
        assert not IL.is_docs_heading_qweld(ctl), ctl
        assert not BS.is_docs_heading_qweld(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


def test_docs_heading_qweld_requires_the_question_weld():
    """A plain heading stack with no interrogative heading stays learnable."""
    import buffer_store as BS
    stack = ("Install The Tool Configure The Proxy Run The Benchmark Check The "
             "Logs Inspect The Output.")
    assert not BS.is_docs_heading_qweld(stack), stack
    # a long lowercase question sentence is prose, not a heading stack
    prose = ("What is prefix caching, and how does it help a serving stack? It "
             "reuses the KV blocks of a shared prompt prefix, which cuts the "
             "prefill cost for every request that repeats the same system prompt.")
    assert not BS.is_docs_heading_qweld(prose), prose
# --- class 158: a BibTeX citation record welded to a license footer --------
_IL158_LEAKS = (
    "Findings of the Association for Computational Linguistics: EMNLP 2025}, "
    "pages = {23934-23949}, year = {2025}, publisher = {Association for "
    "Computational Linguistics} } This website is licensed under a Creative "
    "Commons Attribution-ShareAlike 4.",
)
# Same TOPIC as the leak (the classic trap), but real prose -> must survive.
_IL158_CONTROLS = (
    # prose ABOUT a Creative Commons license is real knowledge
    "This website is licensed under a Creative Commons Attribution-ShareAlike 4.0 "
    "license; please cite the original paper when you reuse the figures.",
    "The reference lists pages 23934-23949 for the EMNLP 2025 findings volume, "
    "published by the ACL and licensed under Creative Commons.",
    "Add a BibTeX entry with the author, title, journal and year fields so the "
    "citation renders correctly in the paper.",
    # a PROSE-VALUED assignment with NO license footer (the rejected one-part rule)
    "Set system_prompt = {You are a helpful assistant} and temperature = {0.2}.",
    "Configure persona = {A concise technical writer} and style = {formal} now.",
    "The template uses greeting = {Hello there friend} and name = {Ada}.",
    # config chains with SCALAR values (the discriminator's clean side)
    "The recipe fixes seed = {42}, epochs = {3} and lr = {5e-5} for every run.",
    "We set batch_size = {32} and learning_rate = {1e-4} before the fine-tune.",
    "The dataset card sets license = {cc-by-4.0} and language = {en} plus "
    "size = {1.2M} rows.",
    "Our serving config pins gpu_memory_utilization = {0.9}, max_model_len = "
    "{8192} and dtype = {bfloat16} for the production profile.",
)


def test_citation_record_weld_is_gated_on_both_paths():
    """A BibTeX record welded to a license footer is chrome on BOTH gates."""
    import internet_learner as IL
    import buffer_store as BS
    for leak in _IL158_LEAKS:
        assert IL.is_citation_record_weld(leak), leak
        assert BS.is_citation_record_weld(leak), leak
        assert IL._is_junk(leak), leak
        assert BS.is_junk(leak), leak
    for ctl in _IL158_CONTROLS:
        assert not IL.is_citation_record_weld(ctl), ctl
        assert not BS.is_citation_record_weld(ctl), ctl
        assert not IL._is_junk(ctl), ctl
        assert not BS.is_junk(ctl), ctl


def test_citation_record_weld_requires_BOTH_parts():
    """Each part alone is insufficient -- the rejection is the contract."""
    import buffer_store as BS
    license_only = ("This website is licensed under a Creative Commons "
                    "Attribution-ShareAlike 4.0 license.")
    assert not BS.is_citation_record_weld(license_only), license_only
    assignment_only = ("Set system_prompt = {You are a helpful assistant} and "
                       "temperature = {0.2}.")
    assert not BS.is_citation_record_weld(assignment_only), assignment_only
    scalar_only = ("Set pages = {23934-23949} with year = {2025} for the record.")
    assert not BS.is_citation_record_weld(scalar_only), scalar_only
