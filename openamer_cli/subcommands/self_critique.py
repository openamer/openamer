"""``openamer self-critique`` subcommand parser.

Exposes the adversarial self-audit (``agent/self_critique.py``) as a first-class
CLI surface. The checks exist because each of them caught a real, silent lie this
system told about itself on 2026-11-06 — dead organs, unrecorded failures, stale
evidence, contradictory self-counts.
"""

from __future__ import annotations

from typing import Callable


def build_self_critique_parser(subparsers, *, cmd_self_critique: Callable) -> None:
    """Attach the ``self-critique`` subcommand to ``subparsers``."""
    parser = subparsers.add_parser(
        "self-critique",
        help="Audit my own claims: dead organs, silent failures, stale evidence",
        description=(
            "Adversarial self-audit. Compares what this system SAYS about itself "
            "with what the files actually contain: dead organs (retired loops "
            "nothing runs), heartbeat subsystems whose last tick failed, red cron "
            "jobs, goals accepted but never finished, evidence files that must be "
            "fresh but are not, and self-reported counts that disagree with a "
            "fresh count. A check that cannot measure reports SKIPPED — silence "
            "is never a verdict."
        ),
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Machine-readable report instead of the rendered table",
    )
    parser.add_argument(
        "--check", default=None,
        help="Run only one check (dead organs | silent failures | failing crons | "
             "zombie goals | stale evidence | self-model contradictions)",
    )
    parser.set_defaults(func=cmd_self_critique)
