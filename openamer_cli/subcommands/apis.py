"""``openamer apis`` — a searchable catalogue of free APIs, kept locally.

The catalogue is built from the public-apis list (2,108 entries, 52 categories),
which is a *document*, not a program: integrating it gives the agent knowledge it
would otherwise have to guess at, and nothing else. That distinction matters —
"we integrated a 500k-star repo" would be a misleading way to describe parsing a
README table.

What it buys, concretely: the agent can answer "which API gives me X, without a
key" offline, with the auth/HTTPS/CORS facts that decide whether an endpoint is
usable from a browser, a script, or not at all.

    openamer apis refresh                 # fetch and index (network, once)
    openamer apis find <query>            # search
    openamer apis find <query> --no-key   # only APIs needing no credentials
    openamer apis show <name>             # one entry in full
    openamer apis stats                   # what is indexed and how old
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CATALOGUE_URL = "https://raw.githubusercontent.com/public-apis/public-apis/master/README.md"
CATALOGUE_REPO = "public-apis/public-apis"
INDEX_NAME = "apis.json"
HTTP_TIMEOUT = 60
ENTRY_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
CELL_SPLIT = re.compile(r"(?<!\\)\|")


def _home() -> Path:
    override = os.environ.get("OPENAMER_HOME")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "openamer-laptop"


def _index_path() -> Path:
    directory = _home() / "api-catalog"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / INDEX_NAME


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def parse_catalogue(markdown: str) -> list[dict]:
    """Turn the markdown table into rows.

    Categories are `### Heading`; rows are five-cell table lines whose first cell
    is a markdown link. Anything else — separators, the header, prose — is
    skipped rather than guessed at.
    """
    category = None
    entries: list[dict] = []
    for line in markdown.splitlines():
        if line.startswith("### "):
            category = line[4:].strip()
            continue
        if not line.startswith("|"):
            continue
        stripped = line.strip()
        if set(stripped.replace("|", "").strip()) <= set("-: "):
            continue
        cells = [cell.strip() for cell in CELL_SPLIT.split(stripped.strip("|"))]
        if len(cells) != 5 or cells[0] == "API":
            continue
        match = ENTRY_RE.match(cells[0])
        if not match:
            continue
        entries.append(
            {
                "name": match.group(1),
                "url": match.group(2).split("?")[0],
                "description": cells[1],
                "auth": cells[2].strip("`"),
                "https": cells[3].strip("`"),
                "cors": cells[4] if cells[4] in ("Yes", "No", "Unknown") else "Unknown",
                "category": category or "Uncategorised",
            }
        )
    return entries


def refresh() -> dict:
    request = urllib.request.Request(CATALOGUE_URL, headers={"User-Agent": "openamer-apis"})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        markdown = response.read().decode("utf-8", "replace")
    entries = parse_catalogue(markdown)
    if not entries:
        raise ValueError("catalogue parsed to zero entries — the source layout changed")
    payload = {
        "source": CATALOGUE_REPO,
        "url": CATALOGUE_URL,
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(entries),
        "entries": entries,
    }
    _index_path().write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def load() -> dict | None:
    path = _index_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# --------------------------------------------------------------------------- #
# search
# --------------------------------------------------------------------------- #
def _score(entry: dict, needle: str) -> int:
    """Rank by where the term appears; a name hit beats a description hit."""
    name = entry["name"].lower()
    description = entry["description"].lower()
    category = entry["category"].lower()
    if needle == name:
        return 100
    if name.startswith(needle):
        return 80
    if needle in name:
        return 60
    if needle in category:
        return 40
    if needle in description:
        return 20
    return 0


def find(entries: list[dict], query: str, *, no_key: bool = False,
         https_only: bool = False, cors_only: bool = False,
         category: str | None = None, limit: int = 15) -> list[dict]:
    needle = query.strip().lower()
    results = []
    for entry in entries:
        if no_key and entry["auth"] not in ("No", ""):
            continue
        if https_only and entry["https"] != "Yes":
            continue
        if cors_only and entry["cors"] != "Yes":
            continue
        if category and category.lower() not in entry["category"].lower():
            continue
        score = _score(entry, needle) if needle else 10
        if score:
            results.append((score, entry))
    results.sort(key=lambda pair: (-pair[0], pair[1]["name"].lower()))
    return [entry for _score_value, entry in results[:limit]]


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_refresh(args: argparse.Namespace) -> int:
    try:
        payload = refresh()
    except (OSError, urllib.error.URLError, ValueError) as cause:
        print(f"openamer apis refresh: {cause}", file=sys.stderr)
        return 1
    categories = len({entry["category"] for entry in payload["entries"]})
    print(f"indexed {payload['count']} entries in {categories} categories")
    print(f"written: {_index_path()}")
    return 0


def _require_catalogue() -> dict | None:
    payload = load()
    if payload is None:
        print(
            "no catalogue yet — run `openamer apis refresh` once (needs network)",
            file=sys.stderr,
        )
    return payload


def cmd_find(args: argparse.Namespace) -> int:
    payload = _require_catalogue()
    if payload is None:
        return 1
    hits = find(
        payload["entries"],
        args.query,
        no_key=args.no_key,
        https_only=args.https,
        cors_only=args.cors,
        category=args.category,
        limit=args.limit,
    )
    if not hits:
        print("nothing matched — try a broader term or drop a filter")
        return 0
    for entry in hits:
        flags = []
        flags.append("key" if entry["auth"] not in ("No", "") else "no key")
        flags.append("https" if entry["https"] == "Yes" else entry["https"].lower())
        flags.append("cors" if entry["cors"] == "Yes" else "no cors")
        print(f"  {entry['name'][:26]:<26} {entry['category'][:20]:<20} {' · '.join(flags)}")
        print(f"    {entry['description'][:96]}")
        print(f"    {entry['url']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    payload = _require_catalogue()
    if payload is None:
        return 1
    hits = find(payload["entries"], args.name, limit=1)
    if not hits:
        print(f"no entry named like {args.name!r}", file=sys.stderr)
        return 1
    entry = hits[0]
    for key in ("name", "category", "description", "auth", "https", "cors", "url"):
        print(f"  {key:<12} {entry[key]}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    payload = _require_catalogue()
    if payload is None:
        return 1
    entries = payload["entries"]
    free = sum(1 for e in entries if e["auth"] in ("No", "") and e["https"] == "Yes")
    cors = sum(1 for e in entries if e["auth"] in ("No", "") and e["https"] == "Yes" and e["cors"] == "Yes")
    print(f"  entries      {len(entries)}")
    print(f"  categories   {len({e['category'] for e in entries})}")
    print(f"  no key       {free}")
    print(f"  no key+cors  {cors}")
    print(f"  fetched      {payload.get('fetched')}")
    print(f"  source       {payload.get('source')}")
    print(f"  index        {_index_path()}")
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def build_apis_parser(subparsers) -> None:
    parser = subparsers.add_parser(
        "apis",
        help="Search a local catalogue of free APIs (public-apis, 2.1k entries)",
        description=(
            "Offline search over the public-apis catalogue: auth model, HTTPS and "
            "CORS availability per entry, so it is clear up front whether an API "
            "works without credentials or from a browser."
        ),
    )
    actions = parser.add_subparsers(dest="apis_command", metavar="COMMAND")
    parser.set_defaults(func=cmd_stats)

    refresh_cmd = actions.add_parser("refresh", help="Fetch the catalogue and rebuild the index")
    refresh_cmd.set_defaults(func=cmd_refresh)

    find_cmd = actions.add_parser("find", help="Search by capability, category or name")
    find_cmd.add_argument("query")
    find_cmd.add_argument("--no-key", action="store_true", help="Only APIs needing no credentials")
    find_cmd.add_argument("--https", action="store_true", help="Only HTTPS endpoints")
    find_cmd.add_argument("--cors", action="store_true", help="Only endpoints usable from a browser")
    find_cmd.add_argument("--category", help="Restrict to a category")
    find_cmd.add_argument("-n", "--limit", type=int, default=15)
    find_cmd.set_defaults(func=cmd_find)

    show_cmd = actions.add_parser("show", help="Show one entry in full")
    show_cmd.add_argument("name")
    show_cmd.set_defaults(func=cmd_show)

    stats_cmd = actions.add_parser("stats", help="What is indexed and how old")
    stats_cmd.set_defaults(func=cmd_stats)
