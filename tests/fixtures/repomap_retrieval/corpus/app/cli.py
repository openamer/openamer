"""Command line entry point for the fixture service."""

from __future__ import annotations

import argparse

from app.telemetry import SpanRecorder, record_span
from app.transport import HttpClient


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fleetctl")
    parser.add_argument("url")
    parser.add_argument("--attempts", type=int, default=3)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    recorder = SpanRecorder()
    client = HttpClient()
    response = {"body": ""}
    for _ in range(args.attempts):
        response = client.send_request(args.url)
    record_span("fetch", recorder)
    print(response["body"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
