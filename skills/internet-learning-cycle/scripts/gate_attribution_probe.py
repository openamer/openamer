#!/usr/bin/env python
"""Attribute internet-learner rejections to the gate that actually fired.

Re-runnable triage probe for the "rejected, not trained" line. Answers, with
denominators, the four questions `references/rejection-triage.md` asks:

  1. Rate  — cycles and reject rate per day + per source, from the learn log.
  2. Reasons — `buffer_junk.jsonl` reason histogram over LEARNER-OWNED rows only
     (the store is shared; a whole-file histogram has the wrong denominator).
  3. Gate attribution — for each distinct junk candidate, does the EXTRACTOR gate
     (`internet_learner._is_junk`) fire, the WRITER gate (`buffer_store.is_junk`),
     both, or neither? Plus which leaf helper matched, so a NOVEL shape is visible.
  4. Duplicates — are the `duplicate` rejects provably already in the buffer as the
     exact (u, a)?

Usage:
    python gate_attribution_probe.py                # all four sections
    python gate_attribution_probe.py --section gate # just the gate attribution
    python gate_attribution_probe.py --tail 400     # rows of buffer_junk to slice

Read the output like this (from the 20.09.26 measurement):
  - writer-only hits, extractor-only 0, every leaf hit a KNOWN helper  => seed space
    exhausted. NOT a gate bug. Do not patch a gate.
  - a leaf helper reported that is NOT in KNOWN_HELPERS                  => possible
    novel chrome shape: investigate (probe the FULL 300-char string, add a
    topic-matched hostile control first).
  - duplicates NOT matching an existing (u, a) but with a KNOWN answer      => the
    duplicate gate may be over-firing.
"""
import argparse
import collections
import json
import os
import re
import sys

HOME = os.environ.get("OPENAMER_HOME") or os.path.join(
    os.path.expanduser("~"), "AppData", "Local", "openamer-laptop")
TRAINING = os.path.join(HOME, "scripts", "training")
LOG = os.path.join(TRAINING, "internet_learn_log.jsonl")
STORE = os.path.join(TRAINING, "buffer_junk.jsonl")
BUFFER = os.path.join(TRAINING, "online_buffer.jsonl")

# Question prefixes that identify internet-learner-owned rows in the SHARED store.
OWNERS = [
    "Internet learning (", "Latest research insight:",
    "What new agent architectures", "Best practice from official docs:",
    "Competitor intelligence:", "Multi-domain learning (",
    "Security learning (", "Efficiency learning (",
    "Structural connection between",
]

# Helpers already documented in the archive. A leaf hit here = known shape.
KNOWN_HELPERS = {
    "_is_serp_snippet", "_is_nav_chrome", "_is_periodic_repeat", "_is_binary_noise",
    "is_prompt_echo", "is_glued_motif", "is_ordinal_stub", "is_financial_infobox",
    "is_contact_block", "_is_arxiv_abstract_chrome", "_is_own_plan_plus_run",
    "_is_repo_tab_statbar_chrome", "_is_marketing_hero_cta_chrome",
    "_is_docs_feature_label_weld", "_is_date_heading_listing", "_is_ticker_loop",
    "_is_tag_counter_run_chrome", "_is_citation_counter_run",
    "_is_dated_tag_strip_chrome", "_is_course_cta_chrome",
    "_is_institution_abstract_tail_chrome", "_is_label_bullet_chain",
    "_is_bio_page_furniture_pair", "_is_advisory_row", "_is_dated_listing_run",
    "_is_table_header_value_run", "_is_changelog_chain",
    # class 66 (live 18.09.26): our own generated plan/run echo fragments.
    # Defined in BOTH buffer_store.py:1678 and internet_learner.py:1928 -- a
    # documented shape, not novel chrome. Missing from this set until 20.09.26,
    # which made section 3 print a false "INVESTIGATE" alarm.
    "_is_generated_plan_echo_fragment",
    # Batch added 21.09.26 (false-alarm class, same shape as class 66 above):
    # 9 leaf helpers were flagged INVESTIGATE while each is defined in BOTH
    # buffer_store.py and internet_learner.py. Verified by
    #   grep -rn "def <helper>" scripts/training/buffer_store.py scripts/training/internet_learner.py
    # -> 2 defs each. Registry staleness, NOT novel chrome. Do not patch any gate
    # on the strength of an alarm that resolves to one of these.
    "_is_startup_portal_nav_run",          # store:3321  learner:3546
    "_is_news_aggregator_listing_run",     # store:2093  learner:2264
    "_is_repo_stat_footer_run",            # store:3061  learner:3268
    "_is_byline_counter_chrome",           # store:1086  learner:1313
    "_is_operator_spotlight_chain",        # store:1957  learner:2127
    "_is_byline_published_article_header", # store:1807  learner:2057
    "_is_journal_issue_index_chrome",      # store:2344  learner:2551
    "_is_hashtag_run_after_headline",      # store:2205  learner:2412
    "_is_trending_card_header_pair",       # store:2507  learner:2714
    # class 90 (live 19.09.26) -- same registry-staleness class as class 66 /
    # the batch above: flagged INVESTIGATE on 21.09.26 while defined in BOTH
    # buffer_store.py:2826 and internet_learner.py:2988 (2 defs, verified with
    # `grep -rn "def _is_course_cta_opener" scripts/training/*.py`). Its sibling
    # `_is_course_cta_chrome` was already in the set; the opener variant, keyed
    # on the promo voice, was simply never added. NOT novel chrome.
    "_is_course_cta_opener",               # store:2826  learner:2988
    # class 99 (live 19.09.26) -- flagged INVESTIGATE on 21.09.26 while defined in
    # BOTH buffer_store.py:3348 and internet_learner.py:3510 (2 defs, verified with
    # `grep -rn "def _is_related_subjects_sidebar" scripts/training/*.py`). The live
    # candidate is byte-for-byte the leak already documented at store:3332-3341
    # ("...Regulatory Framework of Cryptocurrency Chapter (c) 2024 Explore related
    # subjects Discover the latest articles, books..."). Same registry-staleness
    # class as class 66/90 -- NOT novel chrome. Do not patch a gate on this alarm.
    "_is_related_subjects_sidebar",        # store:3348  learner:3510
    # Batch added 21.09.26 (cron cycle_h_efficiency): `known_helpers_audit.py`
    # reported 60 further helpers defined in BOTH buffer_store.py and
    # internet_learner.py but absent from this hand-mirrored set, and the live
    # section-3 run flagged exactly one of them (`_is_platform_sdk_family_weld`).
    # Same registry-staleness class as class 66/90/99 above: 2 defs each,
    # verified with `grep -rn "def <helper>" scripts/training/*.py`. NOT novel
    # chrome -- no gate was patched. Without this batch the probe would keep
    # printing an INVESTIGATE alarm instead of its real verdict. Line numbers are
    # the 21.09.26 snapshot (store / learner).
    "_is_platform_sdk_family_weld",            # store:3436  learner:3616
    "_is_agent_index_nav_run",                 # store:3462  learner:3649
    "_is_adwall_notice",                       # store:621   learner:892
    "_is_aggregator_affordance_min_run",       # store:3399  learner:3569
    "_is_aggregator_row_year_tail",            # store:2602  learner:2764
    "_is_archive_listing",                     # store:920   learner:1051
    "_is_bare_markdown_heading_fragment",      # store:3342  learner:3504
    "_is_blog_nav_feature_run_chrome",         # store:1418  learner:1623
    "_is_code_linenum_run",                    # store:2884  learner:3046
    "_is_de_double_optin_newsletter_chrome",   # store:1466  learner:1671
    "_is_de_nav_weld_headline_chrome",         # store:3302  learner:3464
    "_is_de_portal_fact_box_chrome",           # store:1672  learner:1877
    "_is_de_pricing_chrome",                   # store:598   learner:859
    "_is_decorative_alt_text_chrome",          # store:3062  learner:3224
    "_is_devto_card_tail",                     # store:2164  learner:2302
    "_is_diagram_markup",                      # store:839   learner:964
    "_is_docs_cta_serp_run",                   # store:2135  learner:2260
    "_is_fact_box_label_chain",                # store:3258  learner:3420
    "_is_fullscreen_toggle_chrome",            # store:2230  learner:2392
    "_is_german_glossary_echo",                # store:3359  learner:3521
    "_is_gh_listing_row",                      # store:1333  learner:1517
    "_is_github_issue_chrome",                 # store:951   learner:1082
    "_is_hn_feed_listing_chrome",              # store:1344  learner:1528
    "_is_hn_item_chrome",                      # store:1375  learner:1559
    "_is_hn_show_run_chrome",                  # store:1404  learner:1588
    "_is_infobox_factrow_tail",                # store:1573  learner:1778
    "_is_jobboard_ad_run_chrome",              # store:1608  learner:1813
    "_is_maintenance_banner",                  # store:1053  learner:1175
    "_is_metric_row_fragment",                 # store:1098  learner:1246
    "_is_midtext_byline_counter_run",          # store:2781  learner:2943
    "_is_model_listing_run_chrome",            # store:2331  learner:2493
    "_is_nav_widget_run_chrome",               # store:1637  learner:1842
    "_is_news_byline_share_header",            # store:1766  learner:1971
    "_is_news_card_stub",                      # store:1167  learner:1349
    "_is_package_index_chrome",                # store:872   learner:1003
    "_is_page_meta_blurb",                     # store:1311  learner:1493
    "_is_pagination_newsletter_widget",        # store:2201  learner:2363
    "_is_personal_blog_nav_chain",             # store:2072  learner:2197
    "_is_pipe_byline_shares_header",           # store:2643  learner:2805
    "_is_plan_scaffold_echo",                  # store:982   learner:1113
    "_is_platform_selector_listing_chrome",    # store:1900  learner:2107
    "_is_portal_counter_bar_comparison",       # store:2683  learner:2845
    "_is_preprint_header_chain",               # store:2041  learner:2166
    "_is_pricing_hero_chrome",                 # store:2094  learner:2219
    "_is_project_count_news_tail",             # store:2839  learner:3001
    "_is_prompt_echo_bullet_chain",            # store:1942  learner:607
    "_is_prompt_echo_fragment",                # store:1704  learner:1909
    "_is_qa_portal_chrome",                    # store:568   learner:819
    "_is_readtime_card_widget",                # store:1542  learner:1747
    "_is_relative_stamp_news_run",             # store:2945  learner:3107
    "_is_relative_time_counter_row",           # store:2812  learner:2974
    "_is_relative_time_nav_chain",             # store:1186  learner:1368
    "_is_release_note_emoji_bullet",           # store:2727  learner:2889
    "_is_release_notes_pr_bullet",             # store:2752  learner:2914
    "_is_repeat_badge_glyph_run",              # store:3184  learner:3346
    "_is_services_menu_chain",                 # store:2181  learner:2329
    "_is_share_exec_summary_header",           # store:2913  learner:3075
    "_is_sidebar_listing_chrome",              # store:1127  learner:1302
    "_is_site_headline_stub",                  # store:3248  learner:3410
    "_is_source_verdict_chrome",               # store:1988  learner:4914
    "_is_trending_repo_row_chrome",            # store:2365  learner:2527
    "_is_truncated_serp_tail",                 # store:2424  learner:2586
    # Batch added 22.09.26 (cron internet-learning cycle). `known_helpers_audit.py`
    # reported 2 helpers defined in BOTH buffer_store.py and internet_learner.py
    # but still absent from this hand-mirrored set, and the live section-3 run
    # flagged exactly one of them (`_is_source_tally_cta`). Same registry-staleness
    # class as class 66/90/99/126 above: 2 defs each, verified with
    #   grep -rn "def <helper>" scripts/training/buffer_store.py scripts/training/internet_learner.py
    # -> 2 defs each, both wired into their module's `_is_junk` with a dated
    # `class 130, 22.09.26` comment. NOT novel chrome -- no gate was patched.
    # Without this batch the probe kept printing an INVESTIGATE alarm instead of
    # its real verdict. Line numbers are the 22.09.26 snapshot (store / learner).
    "_is_badge_ribbon_chrome",                 # store:3490  learner:3677
    "_is_source_tally_cta",                    # store:3512  learner:3699
    # Batch added 22.09.26 (cron internet-learning cycle, SECOND batch that day).
    # `known_helpers_audit.py` reported 7 further helpers defined in BOTH
    # buffer_store.py and internet_learner.py but absent from this hand-mirrored
    # set; the live section-3 run flagged exactly one of them
    # (`_is_affiliation_author_list`). Same registry-staleness class as
    # 66/90/99/126/130 above: 2 defs each, verified with
    #   grep -rn "_is_affiliation_author_list" scripts/training/*.py
    # -> buffer_store.py:4192 + internet_learner.py:4007 (and each wired into its
    # module's `_is_junk`). NOT novel chrome -- no gate was patched. Read
    # `N` here as BATCH SIZE, never severity. Line numbers are the 22.09.26
    # snapshot (store / learner).
    "_is_affiliation_author_list",             # store:4192  learner:4007
    "_is_aggregator_card_header_weld",         # store:4109  learner:3878
    "_is_arxiv_submitter_run",                 # store:4079  learner:3848
    "_is_breadcrumb_title_repeat",             # store:4134  learner:3910
    "_is_caps_nav_lockup_weld",                # store:3550  learner:3926
    "_is_credit_byline_run",                   # store:4045  learner:3814
    "_is_date_stamp_listing_strip",            # store:3999  learner:3768
    # Batch added 23.09.26 (cron internet-learning-cycle): `known_helpers_audit.py`
    # reported 5 helpers defined in BOTH buffer_store.py and internet_learner.py
    # but absent from this hand-mirrored set, and the live section-3 run flagged
    # exactly two of them (`_is_serp_title_snippet_repeat`, `_is_article_byline_chrome`).
    # Same registry-staleness class as class 66/90/99 and the 21./22.09. batches:
    # 2 defs each, verified with
    #   grep -n "def <helper>" scripts/training/buffer_store.py scripts/training/internet_learner.py
    # -> 2 defs each. NOT novel chrome -- no gate was patched. Read `N` here as
    # BATCH SIZE, never severity. Line numbers are the 23.09.26 snapshot (store / learner).
    "_is_aggregator_card_affordance_rail",     # store:4309  learner:4048
    "_is_article_byline_chrome",               # store:4531  learner:4316
    "_is_de_consultation_contact_chrome",      # store:2791  learner:2941
    "_is_feed_handle_unit_row",                # store:2729  learner:2879
    "_is_serp_title_snippet_repeat",           # store:4484  learner:4269
}
LEAF_PREFIX = ("_is_", "is_")


def load_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def import_gates():
    """Both gates, imported from the live training modules."""
    sys.path.insert(0, TRAINING)
    import internet_learner as il          # noqa: E402
    import buffer_store as bs              # noqa: E402
    return il, bs


def section_rate(rows):
    print("== 1. RATE (from internet_learn_log.jsonl) ==")
    per_day = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        day = str(r.get("ts", ""))[:10]
        rejected = "rejected" in str(r.get("result", ""))
        per_day[day][0] += 1
        per_day[day][1] += 1 if rejected else 0
    print(f"{'day':12s} {'cycles':>7s} {'reject':>7s} {'rate':>7s}")
    for day in sorted(per_day)[-8:]:
        cycles, rej = per_day[day]
        print(f"{day:12s} {cycles:7d} {rej:7d} {100.0 * rej / cycles:6.1f}%")
    total_c = sum(v[0] for v in per_day.values())
    total_r = sum(v[1] for v in per_day.values())
    if total_c:
        print(f"{'TOTAL':12s} {total_c:7d} {total_r:7d} {100.0 * total_r / total_c:6.1f}%")

    print("\nper source (last 300 cycles):")
    per_src = collections.defaultdict(lambda: [0, 0])
    for r in rows[-300:]:
        src = r.get("source", "?")
        per_src[src][0] += 1
        if "rejected" in str(r.get("result", "")):
            per_src[src][1] += 1
    print(f"{'source':24s} {'cycles':>7s} {'reject':>7s} {'rate':>7s}")
    for src in sorted(per_src):
        cycles, rej = per_src[src]
        flag = "  <-- flat band => not one cycle's bug" if 0.4 < rej / cycles < 0.75 else ""
        print(f"{src:24s} {cycles:7d} {rej:7d} {100.0 * rej / cycles:6.1f}%{flag}")

    print("\nA step change, or a flat rate ACROSS ALL sources, is the signal to")
    print("investigate. Flat-and-rotating near 30% is rotation noise.")


def section_reasons(rows, tail):
    print(f"\n== 2. REASONS (learner-owned rows, last {tail} of buffer_junk) ==")
    print(f"store rows total: {len(rows)}")
    owned = [r for r in rows[-tail:]
             if any(str(r.get("u", "")).startswith(p) for p in OWNERS)]
    print(f"learner-owned in slice: {len(owned)}  (foreign: {tail - len(owned)})")
    print("reasons:", dict(collections.Counter(r.get("reason") for r in owned)))
    return owned


def _leaf_hits(text, bs):
    """Names of _is_*/is_* helpers in buffer_store that fire on this text."""
    hits = []
    for name in dir(bs):
        if not name.startswith(LEAF_PREFIX) or name in ("is_junk",):
            continue
        fn = getattr(bs, name)
        if not callable(fn):
            continue
        try:
            if fn(text):
                hits.append(name)
        except Exception:
            pass
    return hits


def section_gate(owned):
    print("\n== 3. GATE ATTRIBUTION (which gate fires, per distinct candidate) ==")
    il, bs = import_gates()
    seen, candidates = set(), []
    for r in owned:
        if r.get("reason") != "junk":
            continue
        a = str(r.get("a", ""))
        if a and a not in seen:
            seen.add(a)
            candidates.append(a)
    if not candidates:
        print("no junk candidates in the slice")
        return
    both = writer_only = extractor_only = neither = 0
    leaf_counts = collections.Counter()
    novel = []
    for a in candidates:
        v_il = bool(il._is_junk(a))
        v_bs = bool(bs.is_junk(a))
        if v_il and v_bs:
            both += 1
        elif v_bs:
            writer_only += 1
        elif v_il:
            extractor_only += 1
        else:
            neither += 1
        hits = _leaf_hits(a, bs)
        for h in hits:
            leaf_counts[h] += 1
        for h in hits:
            if h not in KNOWN_HELPERS:
                novel.append((h, a))
                break
    n = len(candidates)
    print(f"distinct FULL (300-char) candidates: {n}")
    print(f"  both gates True      : {both}")
    print(f"  WRITER gate only     : {writer_only}  ({100.0 * writer_only / n:.0f}%)")
    print(f"  extractor gate only  : {extractor_only}")
    print(f"  neither              : {neither}")
    print("\nleaf-helper histogram (writer side):")
    for name, count in leaf_counts.most_common(20):
        mark = "" if name in KNOWN_HELPERS else "   <-- NOT a known helper: INVESTIGATE"
        print(f"  {name:36s} {count}{mark}")

    # Verdict criterion is "every leaf hit is pre-existing", NOT "no extractor-only
    # candidate exists". Fixed 21.09.26: the guard was `writer_only and not
    # extractor_only`, so a single extractor-only candidate (a leaf component whose
    # composite gate is the actual verdict) suppressed the verdict line entirely --
    # the run printed no conclusion at all while nothing was wrong. `novel` empty
    # is the real signal: it means no unknown helper was hit.
    if writer_only and not novel:
        print("\nAll junk rejects are WRITER-side and every leaf hit is pre-existing:")
        if extractor_only:
            print(f"  ({extractor_only} candidate also fires the extractor gate -- leaf "
                  f"component, the composite gate is the verdict)")
        print("  => seed space exhausted, NOT a miscalibrated gate. Do not patch.")
    if novel:
        print(f"\n{len(novel)} candidate(s) matched an UNKNOWN helper — likely novel")
        print("chrome shape. Probe the FULL stored string and add a topic-matched")
        print("hostile control BEFORE touching any rule:")
        for name, a in novel[:5]:
            print(f"  [{name}] {a[:150]}")


def section_duplicates(owned):
    print("\n== 4. DUPLICATE HONESTY ==")
    buf = load_jsonl(BUFFER)
    pairs = {(str(o.get("u", "")), str(o.get("a", ""))) for o in buf}
    us = {str(o.get("u", "")) for o in buf}
    dupes = [r for r in owned if r.get("reason") == "duplicate"]
    exact = same_u = unattributable = 0
    for r in dupes:
        key = (str(r.get("u", "")), str(r.get("a", "")))
        if key in pairs:
            exact += 1
        elif key[0] in us:
            same_u += 1
        else:
            unattributable += 1
    print(f"buffer rows: {len(buf)} (MAX_BUF is typically 300)")
    print(f"duplicate rejects in slice: {len(dupes)}")
    print(f"  exact (u, a) already stored : {exact}")
    print(f"  same u, different a         : {same_u}")
    print(f"  unattributable (novel?)     : {unattributable}")
    if exact and not unattributable:
        print("  => honest refusals: rotation exhaustion.")
    if unattributable:
        print("  => some duplicate rejects are NOT stored: the gate may be over-firing.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--section", choices=["all", "rate", "reasons", "gate", "dupes"],
                    default="all")
    ap.add_argument("--tail", type=int, default=400,
                    help="rows of buffer_junk.jsonl to slice (no timestamps there)")
    args = ap.parse_args()

    log_rows = load_jsonl(LOG)
    store_rows = load_jsonl(STORE)
    owned = []
    if args.section in ("all", "rate"):
        section_rate(log_rows)
    if args.section in ("all", "reasons", "gate", "dupes"):
        owned = section_reasons(store_rows, args.tail)
    if args.section in ("all", "gate"):
        section_gate(owned)
    if args.section in ("all", "dupes"):
        section_duplicates(owned)


if __name__ == "__main__":
    main()
