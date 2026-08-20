"""Agent Marketplace for OpenAmer — share, discover, and install community agents and skills.

Provides:
  - MarketListing dataclass (model for a marketplace item)
  - MarketplaceStore (local registry of installed items)
  - discover_marketplace() — GitHub-based search simulation
  - install_from_marketplace() — download + install an item
  - publish_to_marketplace() — prepare a package for sharing
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Well-known community repos that host openamer agents/skills.
# Each entry is (owner/repo, topic) — discover_marketplace() fetches the
# repo's topics file from raw.githubusercontent.com and filters by topic.
WELL_KNOWN_REPOS: List[str] = [
    "openamer/awesome-openamer",
    "openamer/openamer-agent",
    "openamer/openamer-skills",
    "openamer/community-agents",
]

# Where installed marketplace items live under ~/.openamer
MARKETPLACE_DIR_NAME = "marketplace"
REGISTRY_FILE_NAME = "registry.json"

# Sentinel for the default home path used when no explicit path is given


def _get_home() -> Path:
    """Return the .openamer home, reading OPENAMER_HOME fresh each time."""
    env_home = os.environ.get("OPENAMER_HOME")
    if env_home:
        return Path(env_home).resolve()
    return Path.home() / ".openamer"


def _marketplace_dir(home: Optional[Path] = None) -> Path:
    """Return the marketplace storage directory."""
    base = home or _get_home()
    return base / MARKETPLACE_DIR_NAME


def _registry_path(home: Optional[Path] = None) -> Path:
    """Return the path to the local registry JSON file."""
    return _marketplace_dir(home) / REGISTRY_FILE_NAME


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class MarketListing:
    """A single listing in the agent/skill marketplace.

    Attributes:
        name:           Short identifier (e.g. "my-agent").
        type:           "agent" or "skill".
        description:    One-liner explaining what this item does.
        author:         GitHub username or organisation of the author.
        version:        Semver string (e.g. "1.0.0").
        install_instructions: How to install (URL, path, or plain text).
        source:         Where this listing was discovered (repo URL).
        topics:         GitHub topics associated with the repo.
        stars:          Approximate star count (0 if unknown).
    """

    name: str
    type: str  # "agent" or "skill"
    description: str = ""
    author: str = ""
    version: str = "0.1.0"
    install_instructions: str = ""
    source: str = ""
    topics: List[str] = field(default_factory=list)
    stars: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketListing":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Local registry
# ---------------------------------------------------------------------------


class MarketplaceStore:
    """Persistent local registry of installed marketplace items.

    Stores a list of ``MarketListing`` dicts in
    ``~/.openamer/marketplace/registry.json``.
    """

    def __init__(self, home: Optional[Path] = None) -> None:
        self._home = home
        self._dir = _marketplace_dir(home)
        self._path = _registry_path(home)
        self._items: Dict[str, MarketListing] = {}
        self._loaded = False

    # -- persistence --------------------------------------------------------

    def _ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        if self._loaded:
            return
        self._items = {}
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    for entry in raw:
                        item = MarketListing.from_dict(entry)
                        self._items[item.name] = item
                else:
                    # null, object etc. → treat as empty registry
                    logger.info("Marketplace registry is not a list (got %s) — starting fresh", type(raw).__name__)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load marketplace registry: %s", exc)
        self._loaded = True

    def _save(self) -> None:
        self._ensure_dir()
        raw = [item.to_dict() for item in self._items.values()]
        self._path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    # -- query API ----------------------------------------------------------

    def list_items(self) -> List[MarketListing]:
        """Return all installed marketplace items."""
        self._load()
        return list(self._items.values())

    def get(self, name: str) -> Optional[MarketListing]:
        """Look up a single item by name."""
        self._load()
        return self._items.get(name)

    def is_installed(self, name: str) -> bool:
        """Check whether an item is already registered."""
        self._load()
        return name in self._items

    def add(self, item: MarketListing) -> None:
        """Register a newly installed item."""
        self._load()
        self._items[item.name] = item
        self._save()

    def remove(self, name: str) -> bool:
        """Remove an item from the registry. Returns True if it existed."""
        self._load()
        existed = name in self._items
        if existed:
            del self._items[name]
            self._save()
        return existed

    def search(self, query: str = "") -> List[MarketListing]:
        """Search installed items by name/description/author."""
        self._load()
        q = query.lower().strip()
        if not q:
            return self.list_items()
        results: List[MarketListing] = []
        for item in self._items.values():
            if q in item.name.lower() or q in item.description.lower() or q in item.author.lower():
                results.append(item)
        return results


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _fetch_topics(owner_repo: str) -> List[str]:
    """Fetch GitHub topics for a repo via raw.githubusercontent.com.

    Reads the ``topics.json`` file if the repo publishes one under
    ``.github/topics.json``, otherwise returns an empty list.
    Any HTTP or network error is silently caught.
    """
    url = f"https://raw.githubusercontent.com/{owner_repo}/main/.github/topics.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "openamer-marketplace/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("topics", [])
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        pass
    return []


def _fetch_readme_preview(owner_repo: str) -> str:
    """Fetch the first 500 chars of a repo's README.md for preview text."""
    for branch in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/README.md"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "openamer-marketplace/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                text = resp.read().decode("utf-8")
                # Strip markdown headings and grab first paragraph
                lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
                preview = " ".join(lines)[:500].strip()
                return preview
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            continue
    return ""


def _guess_listings_from_readme(
    owner_repo: str,
    topics: List[str],
    preview: str,
) -> List[MarketListing]:
    """Heuristically extract agent/skill listings from a repo's metadata.

    For repos tagged ``openamer-agent`` or ``openamer-skill``, produce a
    single listing.  For the ``awesome-openamer`` index repo, scan the
    README for markdown list items mentioning agent/skill patterns.
    """
    results: List[MarketListing] = []

    has_agent_topic = "openamer-agent" in topics
    has_skill_topic = "openamer-skill" in topics
    repo_name = owner_repo.split("/")[1] if "/" in owner_repo else owner_repo

    # Dedicated repo → single listing
    if has_agent_topic or has_skill_topic:
        item_type = "agent" if has_agent_topic else "skill"
        results.append(
            MarketListing(
                name=repo_name,
                type=item_type,
                description=preview or f"A community {item_type} for OpenAmer.",
                author=owner_repo.split("/")[0],
                version="0.1.0",
                install_instructions=f"https://github.com/{owner_repo}",
                source=f"https://github.com/{owner_repo}",
                topics=topics,
                stars=0,
            )
        )
        return results

    # awesome list repo — scan for bullet points mentioning agents/skills
    if "awesome" in repo_name.lower() and preview:
        # crude heuristic: count lines that might be listings
        # We'll simply add the awesome-list itself as a listing
        results.append(
            MarketListing(
                name=repo_name,
                type="agent",
                description=preview or "Community collection of OpenAmer agents & skills.",
                author=owner_repo.split("/")[0],
                version="0.1.0",
                install_instructions=f"https://github.com/{owner_repo}",
                source=f"https://github.com/{owner_repo}",
                topics=topics,
                stars=0,
            )
        )
    return results


def discover_marketplace(query: str = "") -> List[MarketListing]:
    """Search the community marketplace for agents and skills.

    Operates without a GitHub API key by reading well-known repos'
    metadata from raw.githubusercontent.com.

    Args:
        query: Optional search string to filter results by name.

    Returns:
        A list of ``MarketListing`` objects matching the query.
    """
    all_listings: List[MarketListing] = []

    for repo in WELL_KNOWN_REPOS:
        try:
            topics = _fetch_topics(repo)
            preview = _fetch_readme_preview(repo)
            listings = _guess_listings_from_readme(repo, topics, preview)
            all_listings.extend(listings)
        except Exception:
            logger.debug("Skipping repo %s after error", repo, exc_info=True)

    # Filter by query
    q = query.lower().strip()
    if q:
        filtered: List[MarketListing] = []
        for item in all_listings:
            if q in item.name.lower() or q in item.description.lower():
                filtered.append(item)
        return filtered
    return all_listings


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


def install_from_marketplace(name: str, source: str) -> bool:
    """Download and install a marketplace item (agent or skill).

    Args:
        name:   Item name (used as the install target directory name).
        source: GitHub repo URL or raw content URL to download from.

    Returns:
        True if the installation succeeded.
    """
    store = MarketplaceStore()

    # If already installed, skip
    if store.is_installed(name):
        logger.info("'%s' is already installed in the marketplace registry.", name)
        return True

    # Determine what kind of content we are installing
    # If source is a GitHub repo URL, try to fetch a SKILL.md or agent.json
    is_github_repo = "github.com/" in source and "/tree/" not in source and "/blob/" not in source
    install_path = _marketplace_dir(_get_home()) / name

    if is_github_repo:
        # Extract owner/repo from URL
        parts = source.rstrip("/").split("/")
        if "github.com" in source:
            try:
                idx = parts.index("github.com")
                owner_repo = f"{parts[idx + 1]}/{parts[idx + 2]}"
            except (IndexError, ValueError):
                logger.error("Could not parse GitHub repo from: %s", source)
                return False
        else:
            owner_repo = source

        # Try to fetch SKILL.md
        skill_content = None
        for branch in ("main", "master"):
            url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/SKILL.md"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "openamer-marketplace/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    skill_content = resp.read().decode("utf-8")
                    break
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                continue

        if skill_content:
            # Install as a skill
            install_path.mkdir(parents=True, exist_ok=True)
            (install_path / "SKILL.md").write_text(skill_content, encoding="utf-8")

            # Also try to fetch referenced files (linked in SKILL.md frontmatter)
            _fetch_skill_references(owner_repo, install_path)

            store.add(
                MarketListing(
                    name=name,
                    type="skill",
                    description=f"Community skill from {owner_repo}",
                    author=owner_repo.split("/")[0],
                    version="0.1.0",
                    install_instructions=source,
                    source=source,
                )
            )
            logger.info("Installed skill '%s' from %s", name, source)
            return True

        # No SKILL.md — try agent.json
        agent_content = None
        for branch in ("main", "master"):
            url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/agent.json"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "openamer-marketplace/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    agent_content = resp.read().decode("utf-8")
                    break
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                continue

        if agent_content:
            install_path.mkdir(parents=True, exist_ok=True)
            (install_path / "agent.json").write_text(agent_content, encoding="utf-8")
            store.add(
                MarketListing(
                    name=name,
                    type="agent",
                    description=f"Community agent from {owner_repo}",
                    author=owner_repo.split("/")[0],
                    version="0.1.0",
                    install_instructions=source,
                    source=source,
                )
            )
            logger.info("Installed agent '%s' from %s", name, source)
            return True

        logger.warning("No SKILL.md or agent.json found in %s", owner_repo)
        return False

    # Direct raw content URL — save to disk
    try:
        req = urllib.request.Request(source, headers={"User-Agent": "openamer-marketplace/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        logger.error("Failed to fetch %s: %s", source, exc)
        return False

    install_path.mkdir(parents=True, exist_ok=True)
    # Infer type from file extension or content
    if source.endswith(".md") or source.endswith("SKILL.md"):
        (install_path / "SKILL.md").write_text(content, encoding="utf-8")
        item_type = "skill"
    elif source.endswith(".json"):
        (install_path / "agent.json").write_text(content, encoding="utf-8")
        item_type = "agent"
    else:
        (install_path / "content.md").write_text(content, encoding="utf-8")
        item_type = "skill"

    store.add(
        MarketListing(
            name=name,
            type=item_type,
            description=f"Imported from {source}",
            author="community",
            version="0.1.0",
            install_instructions=source,
            source=source,
        )
    )
    logger.info("Installed '%s' from %s", name, source)
    return True


def _fetch_skill_references(owner_repo: str, install_path: Path) -> None:
    """Fetch auxiliary files referenced from a SKILL.md (scripts, templates)."""
    ref_dirs = ["scripts", "templates", "references", "assets"]
    for subdir in ref_dirs:
        # Try to fetch a .gitkeep or index to see if the directory exists
        for branch in ("main", "master"):
            test_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/{subdir}/.gitkeep"
            try:
                req = urllib.request.Request(test_url, headers={"User-Agent": "openamer-marketplace/1.0"})
                with urllib.request.urlopen(req, timeout=5):
                    # Directory exists — we'll note it but not bulk-download
                    (install_path / subdir).mkdir(parents=True, exist_ok=True)
                break
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                continue


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


def publish_to_marketplace(name: str, type: str) -> bool:
    """Prepare a marketplace item for publishing to GitHub.

    Creates a structured package directory with:
      - SKILL.md or agent.json (depending on type)
      - marketplace.json (metadata manifest)
      - Any supporting files (scripts/, templates/, etc.)

    The output is a directory ready to be committed to a GitHub repo
    tagged with the ``openamer-agent`` or ``openamer-skill`` topic.

    Args:
        name: Item name.
        type: "agent" or "skill".

    Returns:
        True if the package was created successfully.
    """
    if type not in ("agent", "skill"):
        logger.error("type must be 'agent' or 'skill', got '%s'", type)
        return False

    base = _get_home()
    output_dir = base / MARKETPLACE_DIR_NAME / "packages" / name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build the manifest
    manifest = {
        "name": name,
        "type": type,
        "version": "0.1.0",
        "author": "community",
        "description": "",
        "openamer_version": ">=1.0.0",
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if type == "skill":
        # If a SKILL.md already exists in the user's skills dir, copy it
        skill_src = Path.home() / ".openamer" / "skills" / name / "SKILL.md"
        if skill_src.exists():
            shutil.copy2(skill_src, output_dir / "SKILL.md")
            # Also copy supporting directories if they exist
            for sub in ("scripts", "templates", "references", "assets"):
                src_sub = skill_src.parent / sub
                if src_sub.exists():
                    shutil.copytree(src_sub, output_dir / sub, dirs_exist_ok=True)
        else:
            # Create a stub SKILL.md
            (output_dir / "SKILL.md").write_text(
                f"---\nname: {name}\ntype: skill\ndescription: \"\"\n---\n\n# {name}\n\n<!-- Describe your skill here -->\n",
                encoding="utf-8",
            )
        manifest["files"] = ["SKILL.md"]

    else:  # agent
        agent_src = Path.home() / ".openamer" / MARKETPLACE_DIR_NAME / name / "agent.json"
        if agent_src.exists():
            shutil.copy2(agent_src, output_dir / "agent.json")
        else:
            # Create a stub agent manifest
            (output_dir / "agent.json").write_text(
                json.dumps({"name": name, "version": "0.1.0", "description": "", "author": "community"}, indent=2),
                encoding="utf-8",
            )
        manifest["files"] = ["agent.json"]

    # Write marketplace manifest
    (output_dir / "marketplace.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Create topics file for GitHub discovery
    topics_dir = output_dir / ".github"
    topics_dir.mkdir(parents=True, exist_ok=True)
    topic_tag = "openamer-agent" if type == "agent" else "openamer-skill"
    (topics_dir / "topics.json").write_text(
        json.dumps({"topics": [topic_tag, "openamer", topic_tag.replace("openamer-", "openamer-")]}, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "Marketplace package for '%s' created at %s",
        name,
        output_dir,
    )
    print(f"\nMarketplace package ready: {output_dir}")
    print(f"  To publish, create a GitHub repo and push:\n")
    print(f"    cd {output_dir}")
    print(f"    git init && git add . && git commit -m 'Initial release of {name}'")
    print(f"    git remote add origin https://github.com/YOUR_USER/{name}.git")
    print(f"    git push -u origin main")
    print(f"  Then add the topic '{topic_tag}' in the repo settings.\n")
    return True


# ---------------------------------------------------------------------------
# Convenience: list installed
# ---------------------------------------------------------------------------


def list_installed() -> List[MarketListing]:
    """Return all items registered in the local marketplace store."""
    return MarketplaceStore().list_items()