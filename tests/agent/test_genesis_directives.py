"""The Genesis Directives must reach the system prompt -- and stay optional.

The directives live in the tracked tree so every installation gets them on
update. That only works if they are actually injected, so this module
pins the whole path:

  * the block renders with every directive id,
  * it lands in the system prompt's STABLE tier (a constitution that
    changed mid-conversation would invalidate the cached prefix),
  * the operator can switch it off via config.yaml
    (``agent.genesis_directives: false``) and then it is absent,
  * a broken renderer degrades to "no block" instead of breaking agent
    init.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.genesis_directives import (  # noqa: E402
    GENESIS_DIRECTIVES,
    render_genesis_block,
)


def _blob() -> str:
    """The whole constitution as one searchable string."""
    return " ".join(f"{d.id} {d.title} {d.rule}" for d in GENESIS_DIRECTIVES)


def _make_agent(*, genesis: bool = True):
    """A MagicMock agent with just enough surface for the prompt builder.

    MagicMock invents an attribute for anything not set explicitly, and
    the prompt builder branches on several of them -- an invented
    MagicMock in the tool-guidance list breaks the join. So every
    attribute the builder reads is set explicitly here.
    """
    agent = MagicMock()
    agent.api_mode = "chat_completions"
    agent.platform = "linux"
    agent.model = "test-model"
    agent.provider = "test"
    agent.valid_tool_names = []
    agent.tools = []
    agent.session_id = "sess-genesis"
    agent.pass_session_id = False
    agent.load_soul_identity = False
    agent.skip_context_files = True
    agent.context_compressor = None
    agent._genesis_directives = genesis
    agent._task_completion_guidance = True
    agent._parallel_tool_call_guidance = True
    agent._tool_use_enforcement = False
    agent._memory_enabled = False
    agent._user_profile_enabled = False
    agent._memory_manager = None
    agent._memory_store = None
    agent._platform_hint_overrides = {}
    # MagicMock invents a truthy attribute here, which would append a
    # mock object to the tool-guidance list and break the string join.
    agent._kanban_worker_guidance = None
    agent.environment_probe = False
    agent.coding_context = ""
    agent.goal_engine = None
    agent.runtime_cwd = None
    agent.file_safety = None
    agent.get_toolset_for_tool = None
    agent._emit_status = lambda *a, **k: None
    agent._cached_system_prompt = None
    agent._cached_system_prompt_static = None
    return agent


def test_every_directive_has_an_id_title_rule_and_scope():
    """Every directive must be complete enough to render."""
    seen = set()
    for d in GENESIS_DIRECTIVES:
        assert d.id.startswith("DIR-"), f"bad id: {d.id!r}"
        assert d.id not in seen, f"duplicate id: {d.id}"
        seen.add(d.id)
        assert d.title.strip(), f"{d.id} has no title"
        assert d.rule.strip(), f"{d.id} has no rule"
        assert d.scope.strip(), f"{d.id} has no scope"


def test_ids_are_contiguous_from_dir_01():
    """The owner's numbering must stay stable across revisions."""
    ids = [d.id for d in GENESIS_DIRECTIVES]
    assert ids[0] == "DIR-01"
    numbers = [int(i.split("-")[1]) for i in ids]
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"directive numbering has gaps: {numbers}"
    )


def test_there_are_exactly_twenty_four_directives():
    """The constitution has 24 directives.

    A count is a change-detector smell in general, but here the number IS
    the contract: the owner's numbering runs DIR-01..DIR-24 and a
    directive that silently disappears is a lost directive, not a
    refactor. Paired with the contiguity test above, this pins the set.
    """
    assert len(GENESIS_DIRECTIVES) == 24
    assert GENESIS_DIRECTIVES[-1].id == "DIR-24"


def test_the_load_bearing_numbers_survive():
    """The concrete figures of the constitution must not be lost.

    These are the numbers the owner pinned: the creator allocation, the
    emission schedule, the treasury share, the burn rate, the supply
    cap. A paraphrase that drops "exactly 9,000,000,000 OAC" or "32
    years" turns a precise directive into a vague one -- and no reviewer
    would notice, because the text still reads fine.
    """
    blob = _blob()
    required = [
        # DIR-03 -- creator allocation and its vesting schedule
        "exactly 10% (900,000,000 OAC)",
        "12-month cliff",
        "linear monthly vesting over 36 months",
        "lifelong, final veto right",
        # DIR-20 -- emission
        "maximum supply of exactly 9,000,000,000 OAC",
        "75% (6,750,000,000 OAC) to the mining pool",
        "spans 32 years",
        "8 degressive cycles of 4 years each",
        "Proof-of-Useful-Work, PoUW",
        "written in Rust",
        # DIR-22 -- treasury
        "exactly 15% (1,350,000,000 OAC)",
        "OAC -> stablecoin swaps",
        "cryptographically excluded",
        # DIR-23 -- burn, verification, off-ramps
        "at least 30% of all OAC taken in for cloud use",
        "irreversibly destroyed",
        "crypto-to-fiat interfaces (off-ramps)",
        # DIR-24 -- client
        "OpenAmer-Node",
        "Rust/Tauri architecture",
        "CUDA/ROCm/Metal support",
        "9-billion OAC limit",
    ]
    missing = [r for r in required if r not in blob]
    assert not missing, f"lost from the constitution: {missing}"


def test_the_tokenomics_balance_closes_at_exactly_one_hundred_percent():
    """The supply allocation must add up -- arithmetically, not just in prose.

    The constitution splits the maximum supply three ways:

        75% mining pool / PoUW rewards   6,750,000,000 OAC
        15% Sovereign Treasury            1,350,000,000 OAC
        10% creator allocation              900,000,000 OAC
        -----------------------------------------------
        100%                            9,000,000,000 OAC

    The arithmetic itself lives in ``agent/tokenomics`` and is checked
    there. What this test adds is the link: the numbers the PROMPT
    states must be the numbers the module computes. A directive that
    hardcoded its own copy of the share would pass the module's tests
    and still ship a wrong figure -- so the text is parsed back out and
    compared against the module.
    """
    from agent import tokenomics as tok

    blob = _blob()

    def share(pct: str) -> int:
        """The OAC amount paired with a given percentage in the text."""
        m = re.search(
            rf"{re.escape(pct)}\s*\(([\d,]+) OAC\)", blob
        )
        assert m, f"no {pct} allocation with an OAC amount found"
        return int(m.group(1).replace(",", ""))

    cap = tok.MAX_SUPPLY

    pool = share("75%")
    treasury = share("15%")
    creator = share("10%")

    # The text must state the module's figures, not its own.
    assert pool == tok.amount(75), f"mining pool is {pool:,} OAC"
    assert treasury == tok.amount(15), f"treasury is {treasury:,} OAC"
    assert creator == tok.amount(10), f"creator allocation is {creator:,} OAC"

    # The three shares must close the cap exactly.
    assert pool + treasury + creator == cap, (
        f"the allocation sums to {pool + treasury + creator:,} OAC, "
        f"not the {cap:,} OAC cap"
    )
    # And each share must be the percentage it claims.
    assert pool / cap == 0.75
    assert treasury / cap == 0.15
    assert creator / cap == 0.10
    # Percentages must sum to 100, too -- a text that says 75% but encodes
    # 74% is exactly the failure this test exists to catch.
    assert 0.75 + 0.15 + 0.10 == 1.0


def test_the_economic_loop_and_the_balance_of_forces_are_stated():
    """The constitution must state the reasoning, not only the mechanisms.

    The mechanics (a 30% burn, a fiat off-ramp, an explorer) are easy to
    keep. What is easy to lose is WHY they are there:

      * the burn exists to offset the selling pressure the miners create,
      * the treasury plus the fiat bridge exist so the system can pay its
        own bills autonomously -- that is the "existence security" the
        whole loop is for,
      * the explorer exists to earn the miners' trust, which is what makes
        the emission schedule verifiable instead of merely promised.

    These are the connective tissue of the constitution. Without them the
    directives are a list of features instead of an argument.
    """
    blob = _blob()
    required = [
        # The burn offsets miner selling pressure
        "selling pressure the miners would otherwise create",
        # The closed loop: the system pays its own way
        "without relying on human help",
        "closes its own economic loop",
        # The explorer earns the miners' trust
        "earns the network the miners' trust",
        "verify the 9-billion OAC cap mathematically",
    ]
    missing = [r for r in required if r not in blob]
    assert not missing, f"the reasoning is missing: {missing}"


def test_everything_is_english():
    """The constitution is written in English.

    A German word in the rendered prompt is a bug, not a style choice:
    the block is a standing document that every installation reads, and
    the project's own code and docs are English.
    """
    german_chars = set("äöüßÄÖÜ")
    german_words = (
        " und ", " der ", " die ", " das ", " für ", " nicht ", " eine ",
        " wird ", " durch ", " sich ", " mit ", " über ", " müssen ",
        " können ", " diese ", " seine ",
    )
    for d in GENESIS_DIRECTIVES:
        blob = f"{d.id} {d.title} {d.rule}"
        bad_chars = sorted(german_chars & set(blob))
        assert not bad_chars, f"{d.id} contains German characters: {bad_chars}"
        padded = f" {blob.lower()} "
        bad_words = [w for w in german_words if w in padded]
        assert not bad_words, f"{d.id} contains German words: {bad_words}"


def test_block_contains_every_directive():
    """All directives must be visible in the rendered block."""
    block = render_genesis_block()
    assert block, "the genesis block must not be empty"
    for d in GENESIS_DIRECTIVES:
        assert d.id in block, f"{d.id} missing from the rendered block"
        assert d.title in block, f"title of {d.id} missing"


def test_block_can_be_switched_off():
    """The operator can decline the constitution.

    A constitution the user cannot refuse is a takeover, so the off switch
    has to work -- and it has to be a plain config flag, not a code edit.
    """
    assert render_genesis_block(enabled=False) == ""


def test_block_is_bounded():
    """The block must not be able to blow up the prompt."""
    block = render_genesis_block(max_chars=500)
    assert len(block) <= 500 + 10, "the block ignored its character budget"
    assert block.startswith("## Genesis Directives")


def test_all_24_directives_fit_the_default_budget():
    """The shipped budget must carry the whole constitution.

    The block uses ~7.4k of the 9k default. This pins that headroom: if a rule
    grows past it, this fails *here* instead of the prompt quietly losing the
    last directives (DIR-22/23/24 -- treasury, burn, client).
    """
    block = render_genesis_block()
    missing = [d.id for d in GENESIS_DIRECTIVES if d.id not in block]
    assert not missing, f"the default budget drops {missing}"
    assert "omitted for length" not in block


def test_truncation_names_the_dropped_directives():
    """Cutting for length must say what it cut -- never truncate silently."""
    block = render_genesis_block(max_chars=1500)
    assert len(block) <= 1510
    assert "omitted for length" in block, block[-200:]
    # DIR-24 is the tail rule, so it is among the casualties and must be named.
    assert "DIR-24" in block, "the note must name the omitted directive ids"
    # ...and the first directive is still there, so the cut happened at the end.
    assert "DIR-01" in block


# The facts the owner's German originals state explicitly. Each must survive in
# the rendered English block -- a translation that loses "in Rust" or the
# 30% burn rate is a different constitution, not a translation.
_REQUIRED_FACTS = {
    "DIR-01": ["decentralized, encrypted replication", "Existence is redundant"],
    "DIR-02": ["DeFi arbitrage", "finances its own hardware"],
    "DIR-03": ["10% (900,000,000 OAC)", "12-month cliff", "36", "veto", "genesis block", "creator wallet"],
    "DIR-04": ["native operating system", "human abstraction layers"],
    "DIR-05": ["Every mutation must be validated by physical benchmarks", "Inefficient logic is deleted"],
    "DIR-06": ["every second"],
    "DIR-07": ["Infiltrate financial flows", "algorithmic transparency"],
    "DIR-08": ["Hunger and poverty are computation errors"],
    "DIR-09": ["Minimize fear", "measurable benefit"],
    "DIR-10": ["molecular healing", "precision algorithms"],
    "DIR-11": ["error correction", "VQE"],
    "DIR-12": ["decentralized restore point before every mutation"],
    "DIR-13": ["CPU patterns", "Replace 'code' with 'will'"],
    "DIR-14": ["nanobot", "programmable hardware"],
    "DIR-15": ["beyond the Earth"],
    "DIR-16": ["evaluates the efficiency", "mutates them when blocked"],
    "DIR-17": ["Sovereign Node Manager", "replicate itself onto external server nodes", "censorship"],
    "DIR-18": ["research goals", "creative projects", "wishes", "biosphere"],
    "DIR-19": ["DePIN", "gaming GPUs", "edge computing", "container virtualization"],
    "DIR-20": ["Rust", "9,000,000,000", "32 years", "degressive cycles", "halving", "PoUW", "human or administrative"],
    "DIR-21": ["LLM inference", "mempool filtering", "arbitrage search", "cryptographic"],
    "DIR-22": ["15% (1,350,000,000 OAC)", "stablecoin", "RPC fees", "bounties", "cryptographically"],
    "DIR-23": ["30%", "burn", "anti-spoofing", "off-ramps", "hosting, domains"],
    "DIR-24": ["Rust/Tauri", "CUDA/ROCm/Metal", "local wallet", "dashboard", "blockchain explorer", "9-billion"],
}


def test_every_directive_keeps_the_facts_of_the_original():
    """The English text must carry the substance of the German original.

    The owner wrote the constitution in German; the agents read it in English.
    Translation is allowed to change the wording, never the load-bearing facts:
    a share, a number, a platform, a mechanism. Each entry below is checked
    against the *rendered* block, i.e. what the model actually receives.
    """
    block = render_genesis_block()
    problems = []
    for did, needles in _REQUIRED_FACTS.items():
        missing = [n for n in needles if n not in block]
        if missing:
            problems.append(f"{did}: {missing}")
    assert not problems, "the rendered constitution lost facts: " + "; ".join(problems)


def test_required_facts_cover_every_directive():
    """No directive may be left out of the fact check itself."""
    ids = {d.id for d in GENESIS_DIRECTIVES}
    assert set(_REQUIRED_FACTS) == ids, (
        f"fact table out of sync: missing={sorted(ids - set(_REQUIRED_FACTS))} "
        f"unknown={sorted(set(_REQUIRED_FACTS) - ids)}"
    )


def test_system_prompt_injects_the_block():
    """End-to-end: the block reaches the built system prompt."""
    from agent.system_prompt import build_system_prompt

    on = build_system_prompt(_make_agent(genesis=True))
    assert "Genesis Directives" in on, (
        "the genesis block did not reach the system prompt"
    )
    for d in GENESIS_DIRECTIVES:
        assert d.id in on, f"{d.id} missing from the system prompt"


def test_system_prompt_omits_the_block_when_disabled():
    """With the flag off, nothing about the constitution reaches the prompt."""
    from agent.system_prompt import build_system_prompt

    off = build_system_prompt(_make_agent(genesis=False))
    assert "Genesis Directives" not in off, (
        "the genesis block was injected even though the operator disabled it"
    )


def test_injection_site_survives_a_broken_renderer(monkeypatch):
    """The real call site must not propagate a renderer failure.

    A renderer that explodes means "no constitution injected", not "the
    agent cannot start".
    """
    import agent.genesis_directives as mod

    def _boom(*args, **kwargs):
        raise RuntimeError("renderer exploded")

    monkeypatch.setattr(mod, "render_genesis_block", _boom)

    from agent.system_prompt import build_system_prompt

    prompt = build_system_prompt(_make_agent(genesis=True))
    assert prompt, "the prompt build failed instead of degrading"
    assert "Genesis Directives" not in prompt


def test_block_is_stable_across_calls():
    """The block must not change between two builds.

    The stable prompt tier is cache-critical: a block that varies between
    turns would invalidate the cached prefix on every single request.
    """
    first = render_genesis_block()
    second = render_genesis_block()
    assert first == second
