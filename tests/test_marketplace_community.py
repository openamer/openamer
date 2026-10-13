"""Tests for openamer_cli.marketplace_community — Community marketplace features."""
import json
import pathlib
import tempfile

import pytest

from openamer_cli.marketplace_community import (
    add_rating,
    get_ratings,
    track_install,
    get_install_count,
    get_popular_items,
    get_trending_items,
    get_community_stats,
    cmd_community,
)


@pytest.fixture(autouse=True)
def isolate_home(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp)
        community_dir = p / "marketplace" / "community"
        community_dir.mkdir(parents=True)
        monkeypatch.setattr("openamer_cli.marketplace_community._COMMUNITY_DIR", community_dir)
        yield p


class TestRatings:
    def test_add_rating(self):
        assert add_rating("test-agent", 5, "Great!")

    def test_add_rating_invalid(self):
        assert not add_rating("test-agent", 6)

    def test_get_ratings_empty(self):
        stats = get_ratings("unknown")
        assert stats["count"] == 0

    def test_get_ratings_with_data(self):
        add_rating("my-agent", 5, "Excellent")
        add_rating("my-agent", 4, "Good")
        stats = get_ratings("my-agent")
        assert stats["count"] == 2
        assert stats["average"] == 4.5

    def test_rating_distribution(self):
        add_rating("dist-agent", 5)
        add_rating("dist-agent", 3)
        stats = get_ratings("dist-agent")
        assert stats["distribution"][5] == 1
        assert stats["distribution"][3] == 1


class TestInstallTracking:
    def test_track_install(self):
        track_install("my-agent")
        assert get_install_count("my-agent") == 1

    def test_multiple_installs(self):
        track_install("pop-agent")
        track_install("pop-agent")
        track_install("pop-agent")
        assert get_install_count("pop-agent") == 3

    def test_unknown_count(self):
        assert get_install_count("ghost") == 0


class TestPopular:
    def test_popular_items(self):
        track_install("most-popular")
        track_install("most-popular")
        track_install("least-popular")
        items = get_popular_items(limit=5)
        assert items[0]["name"] == "most-popular"
        assert items[0]["installs"] == 2


class TestCommunityStats:
    def test_empty_stats(self):
        stats = get_community_stats()
        assert stats["total_ratings"] == 0
        assert stats["total_installs"] == 0

    def test_with_data(self):
        add_rating("a", 5)
        add_rating("b", 3)
        track_install("a")
        track_install("a")
        track_install("b")
        stats = get_community_stats()
        assert stats["total_ratings"] == 2
        assert stats["total_installs"] == 3
        assert stats["average_rating"] == 4.0


class TestCLI:
    def test_cmd_community_importable(self):
        assert callable(cmd_community)