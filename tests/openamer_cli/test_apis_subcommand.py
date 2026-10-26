"""`openamer apis` — parser wiring, catalogue parsing and the search filters.

The catalogue is a document, so the parsing is where it can quietly go wrong: a
missed category heading silently files 2,000 entries under "Uncategorised", and a
mis-split row drops an entry without any error. Both are asserted here against a
fixture that contains the awkward shapes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from openamer_cli.main import _BUILTIN_SUBCOMMANDS
from openamer_cli.subcommands import apis


FIXTURE = """# Public APIs

Intro prose with a | pipe in it that is not a table.

### Animals
| API | Description | Auth | HTTPS | CORS |
|-----|-------------|------|-------|------|
| [Cat Facts](https://catfact.ninja/?utm_source=x) | Random cat facts | No | Yes | Yes |
| [Dog CEO](https://dog.ceo/api) | Random dog images | No | Yes | No |

### Weather
| API | Description | Auth | HTTPS | CORS |
|-----|-------------|------|-------|------|
| [Meteo](https://meteo.example/api) | Forecast for a point | `apiKey` | Yes | Yes |
| [Open Sky](https://sky.example/api) | Old plaintext endpoint | No | No | Unknown |

Some closing prose.
"""


# --------------------------------------------------------------------------- #
# wiring
# --------------------------------------------------------------------------- #
def test_apis_is_a_builtin_subcommand() -> None:
    assert "apis" in _BUILTIN_SUBCOMMANDS


def test_apis_actions_are_registered() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    apis.build_apis_parser(subparsers)
    actions = subparsers.choices["apis"]._subparsers._group_actions[0].choices
    assert set(actions) == {"refresh", "find", "show", "stats"}


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def test_categories_and_rows_survive_the_table_shape() -> None:
    entries = apis.parse_catalogue(FIXTURE)
    assert len(entries) == 4
    assert [e["name"] for e in entries] == ["Cat Facts", "Dog CEO", "Meteo", "Open Sky"]
    assert entries[0]["category"] == "Animals"
    assert entries[2]["category"] == "Weather"
    # The tracking query string is dropped, the path survives.
    assert entries[0]["url"] == "https://catfact.ninja/"
    # Backticks around the auth value are stripped, CORS keeps only known words.
    assert entries[2]["auth"] == "apiKey"
    assert entries[3]["cors"] == "Unknown"


def test_prose_and_separators_are_not_entries() -> None:
    entries = apis.parse_catalogue(FIXTURE)
    names = {e["name"] for e in entries}
    assert "API" not in names
    assert "Public" not in names


# --------------------------------------------------------------------------- #
# search
# --------------------------------------------------------------------------- #
def test_no_key_filter_excludes_credentialled_apis() -> None:
    entries = apis.parse_catalogue(FIXTURE)
    hits = apis.find(entries, "", no_key=True)
    assert {e["name"] for e in hits} == {"Cat Facts", "Dog CEO", "Open Sky"}


def test_cors_and_https_filters_are_independent() -> None:
    entries = apis.parse_catalogue(FIXTURE)
    assert {e["name"] for e in apis.find(entries, "", https_only=True)} == {
        "Cat Facts", "Dog CEO", "Meteo"
    }
    assert {e["name"] for e in apis.find(entries, "", cors_only=True)} == {
        "Cat Facts", "Meteo"
    }
    assert {e["name"] for e in apis.find(entries, "", no_key=True, https_only=True, cors_only=True)} == {
        "Cat Facts"
    }


def test_name_match_outranks_description_match() -> None:
    entries = apis.parse_catalogue(FIXTURE)
    hits = apis.find(entries, "dog")
    assert hits[0]["name"] == "Dog CEO"


def test_category_and_limit_are_honoured() -> None:
    entries = apis.parse_catalogue(FIXTURE)
    assert {e["name"] for e in apis.find(entries, "", category="weather")} == {"Meteo", "Open Sky"}
    assert len(apis.find(entries, "", limit=2)) == 2


# --------------------------------------------------------------------------- #
# missing catalogue
# --------------------------------------------------------------------------- #
def test_find_without_catalogue_explains_the_fix(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(apis, "_index_path", lambda: tmp_path / "apis.json")
    exit_code = apis.cmd_find(argparse.Namespace(
        query="weather", no_key=False, https=False, cors=False, category=None, limit=5
    ))
    assert exit_code == 1
    assert "apis refresh" in capsys.readouterr().err


def test_stats_reports_the_index_it_reads(tmp_path: Path, monkeypatch, capsys) -> None:
    index = tmp_path / "apis.json"
    index.write_text(json.dumps({
        "source": "fixture",
        "fetched": "2026-10-26T00:00:00+00:00",
        "count": 4,
        "entries": apis.parse_catalogue(FIXTURE),
    }), encoding="utf-8")
    monkeypatch.setattr(apis, "_index_path", lambda: index)
    assert apis.cmd_stats(argparse.Namespace()) == 0
    out = capsys.readouterr().out
    assert "entries      4" in out
    assert "no key+cors  1" in out
