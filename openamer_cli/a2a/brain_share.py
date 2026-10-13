"""A2A Brain Share — share and import knowledge across the agent swarm.

Uses the existing A2A relay/mesh infrastructure to:
- Publish curated insights from the local brain
- Import insights from peer nodes
- Rank and merge imported knowledge
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BRAIN_DIR = Path.home() / ".openamer" / "a2a"
_INSIGHTS_DIR = _BRAIN_DIR / "insights"
_IMPORTED_DIR = _BRAIN_DIR / "imported"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class BrainInsight:
    """A single distilled insight from the local brain."""

    id: str
    topic: str
    summary: str
    source: str  # "skill", "memory", "trajectory", "imported"
    confidence: float  # 0.0 to 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    peer_fingerprint: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BrainInsight":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Local insight extraction
# ---------------------------------------------------------------------------


def extract_insights_from_brain(max_insights: int = 10) -> List[BrainInsight]:
    """Extract insights from the local brain dataset.

    Reads the brain JSONL file and distills lessons from trajectories.
    """
    brain_file = _BRAIN_DIR / "openamer-brain.jsonl"
    if not brain_file.exists():
        return []

    insights = []
    seen_topics = set()

    try:
        with open(brain_file, "r", encoding="utf-8") as f:
            for line in f:
                if len(insights) >= max_insights:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Extract topic from record
                topic = record.get("topic", "") or record.get("messages", [{}])[0].get(
                    "content", ""
                )[:80]
                if topic in seen_topics:
                    continue
                seen_topics.add(topic)

                # Determine source
                engine = record.get("engine", "trajectory")
                source_map = {"trajectory": "trajectory", "insight": "skill", "memory": "memory"}
                source = source_map.get(engine, "trajectory")

                msg_count = len(record.get("messages", []))
                confidence = min(1.0, msg_count / 20)

                insight = BrainInsight(
                    id=f"local-{len(insights)}",
                    topic=topic[:60],
                    summary=f"Learned from {engine} session with {msg_count} messages",
                    source=source,
                    confidence=confidence,
                    tags=[engine, source],
                )
                insights.append(insight)

    except Exception as exc:
        logger.error("Failed to extract brain insights: %s", exc)

    return insights


def export_insights(
    insights: List[BrainInsight],
    output_dir: Optional[Path] = None,
) -> int:
    """Export insights to a JSON file for sharing with peers.

    Returns the number of insights exported.
    """
    out_dir = output_dir or _INSIGHTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / f"insights-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    data = {
        "exported_at": datetime.now().isoformat(),
        "count": len(insights),
        "insights": [i.to_dict() for i in insights],
    }
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    logger.info("Exported %d insights to %s", len(insights), path)
    return len(insights)


def import_insights(source_path: Path) -> List[BrainInsight]:
    """Import insights from a peer's export file.

    Returns the list of imported insights.
    """
    if not source_path.exists():
        logger.warning("Import source not found: %s", source_path)
        return []

    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
        raw = data.get("insights", data) if isinstance(data, dict) else data
        if isinstance(raw, dict):
            raw = [raw]

        imported = []
        for item in raw:
            if isinstance(item, dict):
                imported.append(BrainInsight.from_dict(item))

        # Save to imported directory
        _IMPORTED_DIR.mkdir(parents=True, exist_ok=True)
        dest = _IMPORTED_DIR / source_path.name
        dest.write_text(
            json.dumps(
                {"imported_at": datetime.now().isoformat(), "count": len(imported), "insights": [i.to_dict() for i in imported]},
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        logger.info("Imported %d insights from %s", len(imported), source_path)
        return imported

    except Exception as exc:
        logger.error("Failed to import insights from %s: %s", source_path, exc)
        return []


def list_imported_insights() -> List[Dict[str, Any]]:
    """List all imported insight files with metadata."""
    if not _IMPORTED_DIR.exists():
        return []
    results = []
    for f in sorted(_IMPORTED_DIR.iterdir()):
        if f.suffix == ".json":
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append({
                    "file": f.name,
                    "imported_at": data.get("imported_at", ""),
                    "count": data.get("count", 0),
                    "size": f.stat().st_size,
                })
            except Exception:
                pass
    return results


def get_brain_share_stats() -> Dict[str, Any]:
    """Return statistics about shared brain data."""
    local_insights = len(extract_insights_from_brain(max_insights=100))
    exported = sum(1 for _ in _INSIGHTS_DIR.glob("*.json")) if _INSIGHTS_DIR.exists() else 0
    imported = len(list_imported_insights())

    return {
        "local_insights": local_insights,
        "exported_files": exported,
        "imported_files": imported,
    }


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------


def cmd_brain_share(args) -> None:
    """Handle ``openamer a2a brain share|import|list``."""
    action = getattr(args, "brain_share_action", None)

    if action == "export":
        insights = extract_insights_from_brain(max_insights=20)
        if not insights:
            print("No insights to export.")
            return
        count = export_insights(insights)
        print(f"Exported {count} insights to ~/.openamer/a2a/insights/")

    elif action == "import":
        source = getattr(args, "source", "")
        if not source:
            print("Usage: openamer a2a brain import <path>")
            return
        path = Path(source)
        if not path.exists():
            print(f"Source not found: {source}")
            return
        imported = import_insights(path)
        if imported:
            print(f"Imported {len(imported)} insights from {source}")
            for ins in imported[:5]:
                print(f"  • {ins.topic}: {ins.summary[:60]}")
            if len(imported) > 5:
                print(f"  ... and {len(imported) - 5} more")
        else:
            print("No insights imported.")

    elif action == "list":
        local = extract_insights_from_brain(max_insights=20)
        imported = list_imported_insights()
        print(f"Local insights: {len(local)}")
        print(f"Imported files: {len(imported)}")
        for ins in local[:5]:
            print(f"  • [{ins.source}] {ins.topic}")
        if imported:
            print("\nImported insight files:")
            for f in imported:
                print(f"  • {f['file']} ({f['count']} insights, {f['imported_at'][:10]})")

    else:
        stats = get_brain_share_stats()
        print("A2A Brain Share Status:")
        print(f"  Local insights: {stats['local_insights']}")
        print(f"  Exported files: {stats['exported_files']}")
        print(f"  Imported files: {stats['imported_files']}")
        print("  Use: openamer a2a brain share export|import|list")


def build_brain_share_parser(sub) -> None:
    """Add ``openamer a2a brain share`` subcommand."""
    p = sub.add_parser(
        "share",
        help="Share and import brain insights across the A2A swarm",
        description=(
            "Export local brain insights for sharing with peers, "
            "import insights from peers, and list shared knowledge."
        ),
    )
    p.add_argument(
        "brain_share_action",
        nargs="?",
        choices=["export", "import", "list"],
        default=None,
        help="Action to perform",
    )
    p.add_argument(
        "source",
        nargs="?",
        default="",
        help="Source file path (for 'import' action)",
    )
    p.set_defaults(func=cmd_brain_share)