#!/usr/bin/env python3
"""Rotating item selection for the capability benchmark.

Why this module exists
----------------------
`benchmark.py` scored itself against a fixed slice of its question pool:
`questions[:2]` for every domain, every run. Twenty-two scored runs therefore
measured the same ~22 sentences. That is a *recognition* score, not a
capability score — and `desire_engine.sense_mastery` correctly refused to
report it, because a score that cannot tell learning from repetition is not a
number, it is a ritual.

This module makes the item set an explicit, rotating, auditable object:

* ``select_items`` picks the least-recently-used items per domain, derived from
  the recorded history of previous sets (no RNG state to go stale).
* Every selection carries a deterministic ``set_id`` (a hash of the chosen
  item ids), so two runs on the same items are *provably* the same instrument,
  and two runs on different items are provably different.
* ``pool_health`` states how much fresh material is left. Once every item has
  been seen twice the pool is exhausted, and a further score has to be reported
  as non-comparable instead of as progress. Growing the pool is the only honest
  way to keep measuring; there is deliberately no silent wrap-around.

The functions here are pure: no file I/O, no model calls. That keeps the
instrument testable without spending tokens.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Sequence

#: How many times a single item may be scored before its reuse makes the pool
#: exhausted. Two allows one repeat (so a set can be re-confirmed), a third
#: exposure is recognition, not capability.
MAX_ITEM_EXPOSURES = 2


def _item_id(item: Dict[str, Any], domain: str) -> str:
    """Stable identity for one pool item.

    Uses the question text, not the answer, so fixing a wrong expected answer
    does not silently mint a "new" item and fake a rotation.
    """
    text = str(item.get("q", "")).strip()
    return f"{domain}:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}"


def _history_sets(history: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize whatever the store holds into a list of set records.

    A record with a ``set_id`` but no item list still counts for rotation
    proof: the point of that check is which *sets* were used, not which items
    they contained. Dropping it would let a half-written entry hide a repeat.
    """
    out: List[Dict[str, Any]] = []
    for entry in history or []:
        # A bare string is a set id — an older store wrote `sets: ["v1","v2"]`.
        if isinstance(entry, str):
            out.append({"set_id": entry, "item_ids": []})
            continue
        if not isinstance(entry, dict):
            continue
        ids = entry.get("item_ids") or entry.get("items")
        if isinstance(ids, list) or entry.get("set_id"):
            out.append({"set_id": entry.get("set_id"),
                        "item_ids": [i for i in (ids or []) if isinstance(i, str)]})
    return out


def exposure_counts(pool: Dict[str, Sequence[Dict[str, Any]]],
                    history: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """How often each pool item has already been scored."""
    counts: Dict[str, int] = {}
    for domain, items in pool.items():
        for item in items:
            counts[_item_id(item, domain)] = 0
    for rec in _history_sets(history):
        for iid in rec["item_ids"]:
            if iid in counts:
                counts[iid] += 1
    return counts


def pool_health(pool: Dict[str, Sequence[Dict[str, Any]]],
                history: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Fresh material left in the pool.

    ``fresh`` is the number of items never scored; ``min_used`` is the exposure
    floor. A pool is exhausted when no item is below ``MAX_ITEM_EXPOSURES`` —
    at that point every possible set is a repeat and a new score cannot be
    compared to the old ones.
    """
    counts = exposure_counts(pool, history)
    total = len(counts)
    fresh = sum(1 for n in counts.values() if n == 0)
    min_used = min(counts.values()) if counts else 0
    return {
        "total": total,
        "fresh": fresh,
        "min_used": min_used,
        "max_used": max(counts.values()) if counts else 0,
        "exhausted": bool(counts) and min_used >= MAX_ITEM_EXPOSURES,
    }


def select_items(pool: Dict[str, Sequence[Dict[str, Any]]],
                 per_domain: int,
                 history: Iterable[Dict[str, Any]] | None = None,
                 ) -> Dict[str, Any]:
    """Pick the least-recently-used ``per_domain`` items from every domain.

    Returns ``{"items": {domain: [item, ...]}, "set_id": str,
    "item_ids": [...], "exhausted": bool, "health": {...}}``.

    Ordering inside a domain is deterministic: exposure count first, then the
    item id. Two calls with the same history and pool always yield the same set
    (that reproducibility is what makes a score comparable at all).
    """
    history = list(history or [])
    counts = exposure_counts(pool, history)
    health = pool_health(pool, history)

    chosen: Dict[str, List[Dict[str, Any]]] = {}
    item_ids: List[str] = []

    for domain in sorted(pool):
        candidates = list(pool[domain])
        candidates.sort(key=lambda it: (counts.get(_item_id(it, domain), 0),
                                        _item_id(it, domain)))
        take = candidates[:max(1, per_domain)]
        chosen[domain] = take
        item_ids.extend(_item_id(it, domain) for it in take)

    digest = hashlib.sha256("|".join(sorted(item_ids)).encode("utf-8")).hexdigest()
    return {
        "items": chosen,
        "set_id": f"v2-{digest[:12]}",
        "item_ids": item_ids,
        "exhausted": health["exhausted"],
        "health": health,
    }


def rotation_proof(sets: Iterable[Dict[str, Any]], window: int = 3) -> Dict[str, Any]:
    """Did the recent runs actually use different item sets?

    This is the check `desire_engine` needs: a recorded ``set_id`` key alone
    proves nothing (anyone can write one). What proves rotation is *distinct*
    set ids across consecutive scored runs — and enough fresh material left to
    keep doing it.
    """
    recs = [r for r in _history_sets(sets) if r.get("set_id")]
    recent = recs[-window:]
    ids = [r["set_id"] for r in recent]
    return {
        "scored_sets": len(recs),
        "recent": ids,
        "distinct_recent": len(set(ids)),
        "rotated": len(ids) >= 2 and len(set(ids)) == len(ids),
    }
