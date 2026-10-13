"""Agent Marketplace Community — Community features for the marketplace.

Extends the marketplace with:
- Community ratings and reviews
- Installation tracking and popularity
- Featured/trending listings
- Community hub: top contributors, most installed
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HOME = Path(os.environ.get("OPENAMER_HOME", Path.home() / ".openamer"))
_COMMUNITY_DIR = _HOME / "marketplace" / "community"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CommunityRating:
    """A user rating for a marketplace item."""

    item_name: str
    rating: int  # 1-5
    review: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    author: str = "local"


@dataclass
class InstallRecord:
    """Record of an installation."""

    item_name: str
    installed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    install_count: int = 1


# ---------------------------------------------------------------------------
# Community Store
# ---------------------------------------------------------------------------


def _ensure_dir() -> Path:
    _COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)
    return _COMMUNITY_DIR


def _ratings_path() -> Path:
    return _ensure_dir() / "ratings.json"


def _install_counts_path() -> Path:
    return _ensure_dir() / "install_counts.json"


def _load_ratings() -> List[dict]:
    path = _ratings_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_ratings(ratings: List[dict]) -> None:
    _ratings_path().write_text(json.dumps(ratings, indent=2), encoding="utf-8")


def _load_install_counts() -> Dict[str, int]:
    path = _install_counts_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_install_counts(counts: Dict[str, int]) -> None:
    _install_counts_path().write_text(json.dumps(counts, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Community API
# ---------------------------------------------------------------------------


def add_rating(item_name: str, rating: int, review: str = "") -> bool:
    """Add a rating for a marketplace item.

    Args:
        item_name: Name of the marketplace item
        rating: 1-5 star rating
        review: Optional text review

    Returns:
        True if added successfully
    """
    if not 1 <= rating <= 5:
        return False

    ratings = _load_ratings()
    ratings.append(asdict(CommunityRating(item_name=item_name, rating=rating, review=review)))
    _save_ratings(ratings)
    return True


def get_ratings(item_name: str) -> Dict[str, Any]:
    """Get ratings for a marketplace item."""
    all_ratings = _load_ratings()
    item_ratings = [r for r in all_ratings if r.get("item_name") == item_name]

    if not item_ratings:
        return {"average": 0, "count": 0, "distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}}

    total = sum(r["rating"] for r in item_ratings)
    dist = Counter(r["rating"] for r in item_ratings)
    return {
        "average": round(total / len(item_ratings), 1),
        "count": len(item_ratings),
        "distribution": {i: dist.get(i, 0) for i in range(1, 6)},
    }


def track_install(item_name: str) -> None:
    """Track an installation of a marketplace item."""
    counts = _load_install_counts()
    counts[item_name] = counts.get(item_name, 0) + 1
    _save_install_counts(counts)


def get_install_count(item_name: str) -> int:
    """Get the install count for a marketplace item."""
    counts = _load_install_counts()
    return counts.get(item_name, 0)


def get_popular_items(limit: int = 10) -> List[Dict[str, Any]]:
    """Get the most popular marketplace items by install count."""
    counts = _load_install_counts()
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"name": name, "installs": count} for name, count in sorted_items[:limit]]


def get_trending_items(days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recently trending items based on recent installs."""
    all_ratings = _load_ratings()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    recent_installs = Counter()
    for r in all_ratings:
        if r.get("created_at", "") >= cutoff:
            recent_installs[r["item_name"]] += 1

    return [
        {"name": name, "recent_activity": count}
        for name, count in recent_installs.most_common(limit)
    ]


def get_community_stats() -> Dict[str, Any]:
    """Get overall community statistics."""
    ratings = _load_ratings()
    install_counts = _load_install_counts()

    total_ratings = len(ratings)
    avg_rating = 0
    if total_ratings > 0:
        avg_rating = round(sum(r["rating"] for r in ratings) / total_ratings, 1)

    total_installs = sum(install_counts.values())
    unique_items = len(install_counts)
    items_with_reviews = len(set(r["item_name"] for r in ratings if r.get("review")))

    return {
        "total_ratings": total_ratings,
        "average_rating": avg_rating,
        "total_installs": total_installs,
        "unique_items_installed": unique_items,
        "items_with_reviews": items_with_reviews,
    }


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------


def cmd_community(args) -> None:
    """Handle ``openamer marketplace community <subcommand>``."""
    action = getattr(args, "community_action", None)

    if action == "rate":
        item = getattr(args, "item_name", "")
        rating = getattr(args, "rating", 5)
        review = getattr(args, "review", "")
        if add_rating(item, rating, review):
            print(f"Rated '{item}' with {rating} stars.")
        else:
            print("Rating must be between 1 and 5.")

    elif action == "ratings":
        item = getattr(args, "item_name", "")
        stats = get_ratings(item)
        if stats["count"] > 0:
            print(f"Ratings for '{item}':")
            print(f"  Average: {stats['average']} / 5 ({stats['count']} ratings)")
            print(f"  Distribution:")
            for star in range(5, 0, -1):
                bar = "█" * stats["distribution"].get(star, 0)
                print(f"    {star}★: {bar}")
        else:
            print(f"No ratings for '{item}' yet.")

    elif action == "popular":
        items = get_popular_items(limit=10)
        if items:
            print("Most Popular Items:")
            for i, item in enumerate(items, 1):
                print(f"  {i}. {item['name']} ({item['installs']} installs)")
        else:
            print("No install data yet.")

    elif action == "trending":
        items = get_trending_items(days=7, limit=10)
        if items:
            print("Trending This Week:")
            for i, item in enumerate(items, 1):
                print(f"  {i}. {item['name']} ({item['recent_activity']} recent)")
        else:
            print("No trending items yet.")

    elif action == "stats":
        stats = get_community_stats()
        print("Community Statistics:")
        print(f"  Total ratings: {stats['total_ratings']}")
        print(f"  Average rating: {stats['average_rating']} / 5")
        print(f"  Total installs: {stats['total_installs']}")
        print(f"  Unique items: {stats['unique_items_installed']}")
        print(f"  Items with reviews: {stats['items_with_reviews']}")

    else:
        print("Usage: openamer marketplace community <rate|ratings|popular|trending|stats> [args]")


def build_community_parser(marketplace_parser) -> None:
    """Add the ``openamer marketplace community`` subcommand to the marketplace parser."""
    # Find the marketplace subparsers
    sub = marketplace_parser._subparsers._group_actions[0].choices

    # Check if community already exists
    if "community" in sub:
        return

    p = marketplace_parser.add_parser(
        "community",
        help="Community features: ratings, reviews, trending",
        description="Community marketplace features — rate items, see trending, check popularity.",
    )
    c_sub = p.add_subparsers(dest="community_action")

    rate_p = c_sub.add_parser("rate", help="Rate a marketplace item")
    rate_p.add_argument("item_name", help="Item name")
    rate_p.add_argument("--rating", "-r", type=int, default=5, choices=range(1, 6), help="Rating 1-5")
    rate_p.add_argument("--review", "-v", default="", help="Optional review text")

    ratings_p = c_sub.add_parser("ratings", help="Show ratings for an item")
    ratings_p.add_argument("item_name", help="Item name")

    c_sub.add_parser("popular", help="Show most popular items")
    c_sub.add_parser("trending", help="Show trending items")
    c_sub.add_parser("stats", help="Show community statistics")

    p.set_defaults(func=cmd_community)