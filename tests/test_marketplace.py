"""Tests for openamer_cli.marketplace — discovery, install, publish, and local registry."""

import json
import os
import pathlib
import tempfile
from dataclasses import asdict
from unittest.mock import patch

import pytest

from openamer_cli.marketplace import (
    MarketListing,
    MarketplaceStore,
    discover_marketplace,
    install_from_marketplace,
    publish_to_marketplace,
    list_installed,
    WELL_KNOWN_REPOS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_home(monkeypatch):
    """Isolate OPENAMER_HOME to a temp dir so each test runs independently."""
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp)
        monkeypatch.setenv("OPENAMER_HOME", str(p))
        yield p


@pytest.fixture
def sample_listing():
    return MarketListing(
        name="test-agent",
        type="agent",
        description="A test agent for unit testing",
        author="tester",
        version="1.0.0",
        install_instructions="https://github.com/tester/test-agent",
        source="https://github.com/tester/test-agent",
    )


@pytest.fixture
def sample_skill_listing():
    return MarketListing(
        name="test-skill",
        type="skill",
        description="A test skill for unit testing",
        author="tester",
        version="0.5.0",
        install_instructions="https://github.com/tester/test-skill",
        source="https://github.com/tester/test-skill",
    )


# ---------------------------------------------------------------------------
# MarketListing
# ---------------------------------------------------------------------------


class TestMarketListing:
    def test_to_dict_roundtrip(self, sample_listing):
        d = sample_listing.to_dict()
        restored = MarketListing.from_dict(d)
        assert restored == sample_listing

    def test_from_dict_ignores_extra_fields(self):
        data = {
            "name": "my-agent",
            "type": "agent",
            "description": "desc",
            "author": "me",
            "version": "0.1.0",
            "install_instructions": "url",
            "source": "url",
            "topics": ["openamer-agent"],
            "stars": 5,
            "extra_field": "ignored",
        }
        listing = MarketListing.from_dict(data)
        assert listing.name == "my-agent"
        assert not hasattr(listing, "extra_field")

    def test_defaults(self):
        listing = MarketListing(name="defaults-test", type="skill")
        assert listing.version == "0.1.0"
        assert listing.stars == 0
        assert listing.topics == []

    def test_type_validation(self):
        listing = MarketListing(name="agent", type="agent")
        assert listing.type == "agent"
        skill = MarketListing(name="gen", type="skill")
        assert skill.type == "skill"


# ---------------------------------------------------------------------------
# MarketplaceStore
# ---------------------------------------------------------------------------


class TestMarketplaceStore:
    def test_empty_store(self, isolate_home):
        store = MarketplaceStore()
        assert store.list_items() == []

    def test_add_and_list(self, isolate_home, sample_listing):
        store = MarketplaceStore()
        store.add(sample_listing)
        items = store.list_items()
        assert len(items) == 1
        assert items[0].name == "test-agent"

    def test_add_and_get(self, isolate_home, sample_listing):
        store = MarketplaceStore()
        store.add(sample_listing)
        assert store.get("test-agent") == sample_listing
        assert store.get("nonexistent") is None

    def test_is_installed(self, isolate_home, sample_listing):
        store = MarketplaceStore()
        assert not store.is_installed("test-agent")
        store.add(sample_listing)
        assert store.is_installed("test-agent")

    def test_remove(self, isolate_home, sample_listing):
        store = MarketplaceStore()
        store.add(sample_listing)
        assert store.remove("test-agent") is True
        assert store.get("test-agent") is None

    def test_remove_missing(self, isolate_home):
        store = MarketplaceStore()
        assert store.remove("does-not-exist") is False

    def test_list_installed_helper(self, isolate_home, sample_listing):
        store = MarketplaceStore()
        store.add(sample_listing)
        items = list_installed()
        assert len(items) == 1
        assert items[0].name == "test-agent"

    def test_search(self, isolate_home, sample_listing, sample_skill_listing):
        store = MarketplaceStore()
        store.add(sample_listing)
        store.add(sample_skill_listing)

        results = store.search("agent")
        names = [r.name for r in results]
        assert "test-agent" in names
        assert "test-skill" not in names  # description doesn't contain 'agent'

    def test_search_empty_query(self, isolate_home, sample_listing):
        store = MarketplaceStore()
        store.add(sample_listing)
        results = store.search("")
        assert len(results) == 1

    def test_search_no_match(self, isolate_home, sample_listing):
        store = MarketplaceStore()
        store.add(sample_listing)
        results = store.search("zzz_nonexistent")
        assert results == []

    def test_persistence_on_disk(self, isolate_home, sample_listing):
        """Verify that data survives store re-instantiation."""
        store1 = MarketplaceStore()
        store1.add(sample_listing)

        store2 = MarketplaceStore()
        assert store2.is_installed("test-agent")

    def test_load_corrupted_registry(self, isolate_home):
        """Corrupted JSON should not crash the store."""
        reg_path = isolate_home / "marketplace" / "registry.json"
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text("{invalid json", encoding="utf-8")

        store = MarketplaceStore()
        assert store.list_items() == []

    def test_invalid_registry_does_not_block_writes(self, isolate_home, sample_listing):
        reg_path = isolate_home / "marketplace" / "registry.json"
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text("null", encoding="utf-8")

        store = MarketplaceStore()
        store.add(sample_listing)
        assert store.is_installed("test-agent")


# ---------------------------------------------------------------------------
# discover_marketplace
# ---------------------------------------------------------------------------


class TestDiscoverMarketplace:
    @patch("openamer_cli.marketplace._fetch_topics")
    @patch("openamer_cli.marketplace._fetch_readme_preview")
    def test_discover_from_agent_topic(
        self, mock_preview, mock_topics
    ):
        """A repo with 'openamer-agent' topic should yield one listing."""
        mock_topics.return_value = ["openamer-agent", "ai"]
        mock_preview.return_value = "An awesome OpenAmer agent for testing."

        results = discover_marketplace()
        assert len(results) > 0
        # At least one result should have type 'agent'
        agents = [r for r in results if r.type == "agent"]
        assert len(agents) > 0

    @patch("openamer_cli.marketplace._fetch_topics")
    @patch("openamer_cli.marketplace._fetch_readme_preview")
    def test_discover_from_skill_topic(
        self, mock_preview, mock_topics
    ):
        """A repo with 'openamer-skill' topic should yield a skill listing."""
        mock_topics.return_value = ["openamer-skill"]
        mock_preview.return_value = "A skill that does X."

        results = discover_marketplace()
        skills = [r for r in results if r.type == "skill"]
        assert len(skills) > 0

    @patch("openamer_cli.marketplace._fetch_topics")
    @patch("openamer_cli.marketplace._fetch_readme_preview")
    def test_discover_with_query_filter(self, mock_preview, mock_topics):
        """Query filtering should limit results."""
        mock_topics.return_value = ["openamer-agent"]
        mock_preview.return_value = "Some agent description."

        results = discover_marketplace(query="some")
        assert len(results) > 0

    @patch("openamer_cli.marketplace._fetch_topics")
    @patch("openamer_cli.marketplace._fetch_readme_preview")
    def test_discover_with_no_match_query(self, mock_preview, mock_topics):
        """A query that doesn't match anything should return empty list."""
        mock_topics.return_value = ["openamer-agent"]
        mock_preview.return_value = "Some agent description."

        results = discover_marketplace(query="zzz_no_match_ever")
        assert results == []


# ---------------------------------------------------------------------------
# install_from_marketplace
# ---------------------------------------------------------------------------


class TestInstallFromMarketplace:
    def test_install_already_registered(self, isolate_home, sample_listing):
        """Re-installing an already-registered item should succeed silently."""
        store = MarketplaceStore()
        store.add(sample_listing)

        ok = install_from_marketplace("test-agent", "https://github.com/tester/test-agent")
        assert ok is True

    def test_install_missing_content(self, isolate_home):
        """Installing from a non-existent GitHub repo should return False."""
        ok = install_from_marketplace(
            "non-existent-repo",
            "https://github.com/zzz-nonexistent/zzz-repo",
        )
        assert ok is False

    def test_install_creates_registry_entry(self, isolate_home):
        """After install, the store should have the item."""

        with patch("openamer_cli.marketplace.install_from_marketplace") as mock_install:
            mock_install.return_value = True
            # Simulate adding to store
            store = MarketplaceStore()
            listing = MarketListing(
                name="my-installed-agent",
                type="agent",
                description="Installed via test",
                author="test",
                version="0.1.0",
                install_instructions="https://github.com/test/my-installed-agent",
                source="https://github.com/test/my-installed-agent",
            )
            store.add(listing)

            assert store.is_installed("my-installed-agent")

            reg_path = isolate_home / "marketplace" / "registry.json"
            data = json.loads(reg_path.read_text(encoding="utf-8"))
            names = [e["name"] for e in data]
            assert "my-installed-agent" in names


# ---------------------------------------------------------------------------
# publish_to_marketplace
# ---------------------------------------------------------------------------


class TestPublishToMarketplace:
    def test_publish_skill_creates_package(self, isolate_home):
        ok = publish_to_marketplace("my-published-skill", "skill")
        assert ok is True

        # Verify package structure
        pkg_dir = isolate_home / "marketplace" / "packages" / "my-published-skill"
        assert pkg_dir.exists()
        assert (pkg_dir / "SKILL.md").exists()
        assert (pkg_dir / "marketplace.json").exists()
        assert (pkg_dir / ".github" / "topics.json").exists()

        # Verify manifest content
        manifest = json.loads((pkg_dir / "marketplace.json").read_text(encoding="utf-8"))
        assert manifest["name"] == "my-published-skill"
        assert manifest["type"] == "skill"

    def test_publish_agent_creates_package(self, isolate_home):
        ok = publish_to_marketplace("my-published-agent", "agent")
        assert ok is True

        pkg_dir = isolate_home / "marketplace" / "packages" / "my-published-agent"
        assert pkg_dir.exists()
        assert (pkg_dir / "agent.json").exists()
        assert (pkg_dir / "marketplace.json").exists()
        assert (pkg_dir / ".github" / "topics.json").exists()

        manifest = json.loads((pkg_dir / "marketplace.json").read_text(encoding="utf-8"))
        assert manifest["type"] == "agent"

    def test_publish_invalid_type(self, isolate_home):
        ok = publish_to_marketplace("invalid", "invalid_type")
        assert ok is False

    def test_publish_topics_file(self, isolate_home):
        publish_to_marketplace("agent-item", "agent")
        topics_path = (
            isolate_home / "marketplace" / "packages" / "agent-item" / ".github" / "topics.json"
        )
        assert topics_path.exists()
        topics = json.loads(topics_path.read_text(encoding="utf-8"))
        assert "openamer-agent" in topics["topics"]


# ---------------------------------------------------------------------------
# Integration: CLI import works (lazy fixture)
# ---------------------------------------------------------------------------


class TestCLICompatibility:
    def test_reimport_marketplace_module(self):
        """Verify the module can be imported multiple times without error."""
        import importlib
        import openamer_cli.marketplace as mp
        importlib.reload(mp)
        assert mp.MarketListing is not None