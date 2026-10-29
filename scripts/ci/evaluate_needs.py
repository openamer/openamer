#!/usr/bin/env python3
"""Fail the ``all-checks-pass`` gate unless every required lane actually passed.

The gate used to fail only on ``result == 'failure'``. Everything else — a
``cancelled`` job in particular — counted as a pass, so a run whose classifier
was cancelled and whose fourteen dependent lanes were therefore all skipped
reported::

    ✅ All required checks pass

Nothing had been validated. That is the worst failure mode a gate has: it does
not report a wrong shade of green, it reports green with an empty run behind it.

Verdict rules:

``success``   passes.
``skipped``   passes — that is the path-based lane gating working as designed.
``failure``   fails.
``cancelled`` fails — a cancelled job did not pass. If the run was superseded,
              the superseding run carries the real verdict anyway.
``detect``    additionally has to be ``success``: every lane is gated on its
              outputs, so a skipped/failed/cancelled classifier means the rest
              of the list proves nothing.

Reads ``$NEEDS`` (``toJSON(needs)`` from the workflow) and appends
``needs-json=<compact map>`` to ``$GITHUB_OUTPUT`` for the review-comment
assembler.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Iterable, Mapping

# The classifier every other lane depends on.
PREREQUISITE = "detect"


def verdict(needs: Mapping[str, Mapping[str, str]]) -> list[str]:
    """Return the job names that block the gate, sorted."""
    blocking: list[str] = []
    for name, info in needs.items():
        result = str(info.get("result", ""))
        if result in ("failure", "cancelled"):
            blocking.append(name)
    # `skipped` normally means "this lane does not apply to the diff". For the
    # classifier it means nothing was classified, so no lane can be trusted.
    detect_result = str(needs.get(PREREQUISITE, {}).get("result", ""))
    if detect_result != "success" and PREREQUISITE not in blocking:
        blocking.insert(0, PREREQUISITE)
    return sorted(set(blocking))


def render(needs: Mapping[str, Mapping[str, str]]) -> Iterable[str]:
    for name, info in sorted(needs.items()):
        result = str(info.get("result", ""))
        icon = "✅" if result in ("success", "skipped") else "❌"
        yield f"{icon} {name}: {result}"


def main(argv: list[str] | None = None) -> int:
    raw = os.environ.get("NEEDS", "")
    if not raw.strip():
        print("::error::NEEDS is empty; nothing to evaluate")
        return 1
    try:
        needs = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"::error::NEEDS is not valid JSON: {exc}")
        return 1
    if not isinstance(needs, dict) or not needs:
        print("::error::NEEDS is not a non-empty object")
        return 1

    compact = {name: info.get("result", "") for name, info in needs.items()}
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as handle:
            handle.write(f"needs-json={json.dumps(compact)}\n")

    blocking = verdict(needs)
    for line in render(needs):
        print(line)

    if blocking:
        print(f"::error::{len(blocking)} job(s) did not pass: {', '.join(blocking)}")
        return 1
    print("All required checks passed")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
