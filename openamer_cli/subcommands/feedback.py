"""``openamer feedback`` subcommand parser + handlers.

A safe, standalone activation point for the message-feedback recording seam
(openamer_cli.message_feedback). It does NOT touch the agent loop — it just
lets a caller (user, automation, or a future loop hook) record and inspect
signals. Kept dependency-light and never raises on I/O.
"""

from __future__ import annotations

import sys

from openamer_cli import message_feedback


def build_feedback_parser(subparsers) -> None:
    fb = subparsers.add_parser(
        "feedback",
        help="Record or inspect lightweight message-feedback signals",
        description="Append helpful/not-helpful signals and read them back "
                    "as a self-improvement input. Does not modify the agent loop.",
    )
    fb_sub = fb.add_subparsers(dest="feedback_command", required=False)

    rec = fb_sub.add_parser("record", help="Record one feedback signal")
    rec.add_argument("signal", help="Signal label, e.g. helpful / not_helpful")
    rec.add_argument("--text", default="", help="Assistant reply (or snippet) being rated")
    rec.add_argument("--session", default=None, help="Session id")
    rec.add_argument("--model", default=None, help="Model name")
    rec.add_argument("--topic", default=None, help="Optional topic")
    rec.add_argument("--note", default=None, help="Optional free-form note")

    summ = fb_sub.add_parser("summary", help="Aggregate recorded signals")

    fb.set_defaults(func=cmd_feedback)


def cmd_feedback(args) -> None:
    """Dispatch a feedback subcommand; prints a short human summary."""
    try:
        if getattr(args, "feedback_command", None) == "record":
            rec = message_feedback.record_feedback(
                signal=args.signal,
                assistant_text=args.text,
                session_id=args.session,
                model=args.model,
                topic=args.topic,
                note=args.note,
            )
            if rec["_persisted"]:
                print(f"✓ recorded '{rec['signal']}' feedback")
            else:
                print("⚠ could not persist feedback (see _persisted=False)")
            return
        if getattr(args, "feedback_command", None) == "summary":
            records = message_feedback.load_feedback()
            summary = message_feedback.summarize_feedback(records)
            counts = summary["counts"] or {"(none)": 0}
            print("Feedback summary:")
            for sig, n in sorted(counts.items()):
                print(f"  {sig}: {n}")
            if summary["latest_not_helpful"]:
                print(f"  latest not_helpful: {summary['latest_not_helpful']!r}")
            if summary["latest_helpful"]:
                print(f"  latest helpful: {summary['latest_helpful']!r}")
            return
        print("usage: openamer feedback {record|summary} ...", file=sys.stderr)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"✗ feedback command failed: {exc}", file=sys.stderr)
