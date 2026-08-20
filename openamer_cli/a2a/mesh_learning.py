"""openamer_cli.a2a.mesh_learning — advanced cross-node collective learning.

Extends the base mesh learning (meshlearn.py) with a MeshLearningCoordinator
that orchestrates publishing signed lessons, importing from peer nodes,
converting lessons into local skill improvements, and tracking what the
entire mesh has learned.

Capabilities provided:
  - MeshLearningCoordinator class: orchestrates cross-node learning
  - publish_lesson(): sign + publish a lesson to the mesh
  - import_lessons_from_mesh(): fetch lessons from peer insight files
  - apply_lesson_to_skills(): convert a mesh lesson into a local skill
  - get_mesh_learning_stats(): track what the mesh has learned
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from openamer_cli.a2a.meshlearn import Insight, publish, adopt
from openamer_cli.a2a.core import IdentityStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _base_dir() -> Path:
    base = os.environ.get("OPENAMER_HOME") or str(Path.home() / ".openamer")
    return Path(base)

_MESH_DIR = _base_dir() / "a2a" / "mesh"
_LESSONS_DIR = _MESH_DIR / "lessons"
_PUBLISH_DIR = _MESH_DIR / "publish"
_IMPORTED_DIR = _MESH_DIR / "imported"
_MEMORY_PATH = _base_dir() / "MEMORY-official-mesh.md"
_SKILLS_DIR = _base_dir() / "skills"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class MeshLesson:
    """A signed lesson published to the mesh for peer consumption."""

    lesson_id: str
    title: str
    body: str
    topic: str
    source: str            # publishing node fingerprint
    source_pubkey: str
    ts: int
    signature: str = ""
    tags: list[str] = field(default_factory=list)
    difficulty: str = "intermediate"  # beginner / intermediate / advanced
    applies_to: list[str] = field(default_factory=list)  # skill names it can improve

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MeshLesson":
        return cls(
            lesson_id=d.get("lesson_id", ""),
            title=d.get("title", ""),
            body=d.get("body", ""),
            topic=d.get("topic", "general"),
            source=d.get("source", ""),
            source_pubkey=d.get("source_pubkey", ""),
            ts=int(d.get("ts", 0)),
            signature=d.get("signature", ""),
            tags=d.get("tags", []),
            difficulty=d.get("difficulty", "intermediate"),
            applies_to=d.get("applies_to", []),
        )


def _sign_lesson(lesson: MeshLesson, identity_store: IdentityStore) -> MeshLesson:
    """Sign a lesson with the local node identity."""
    ident = identity_store.ensure_identity()
    lesson.source = ident.fingerprint
    lesson.source_pubkey = ident.public_key
    lesson.ts = int(time.time())
    body_for_signing = json.dumps(lesson.to_dict(), sort_keys=True, separators=(",", ":"))
    lesson.signature = identity_store.private_key().sign(
        body_for_signing.encode("utf-8")
    ).hex()
    return lesson


# ---------------------------------------------------------------------------
# MeshLearningCoordinator
# ---------------------------------------------------------------------------


class MeshLearningCoordinator:
    """Orchestrates cross-node learning across the A2A swarm.

    Handles the full lifecycle:
      - Publishing signed lessons to the mesh directory
      - Importing lessons from peer nodes' published insight files
      - Applying mesh lessons as local skill improvements
      - Reporting what the collective has learned
    """

    def __init__(
        self,
        *,
        identity_store: Optional[IdentityStore] = None,
        memory_path: Optional[Path] = None,
        skills_dir: Optional[Path] = None,
        publish_dir: Optional[Path] = None,
        mesh_dir: Optional[Path] = None,
        lesson_to_skill_fn: Optional[Callable[[MeshLesson], Optional[str]]] = None,
    ):
        self._identity_store = identity_store or IdentityStore()
        self._memory_path = memory_path or _MEMORY_PATH
        self._skills_dir = skills_dir or _SKILLS_DIR
        self._publish_dir = publish_dir or _PUBLISH_DIR
        self._mesh_dir = mesh_dir or _MESH_DIR
        self._lesson_to_skill_fn = lesson_to_skill_fn

    # ---- public API ---------------------------------------------------------

    def publish_lesson(self, lesson: dict) -> dict:
        """Publish a signed lesson to the mesh directory.

        The dict must have at least ``title``, ``body``, and optionally
        ``topic``, ``tags``, ``difficulty``, ``applies_to``.
        Returns a result dict with status and path.
        """
        lesson_obj = MeshLesson(
            lesson_id=_make_lesson_id(lesson.get("title", "untitled")),
            title=lesson.get("title", ""),
            body=lesson.get("body", ""),
            topic=lesson.get("topic", "general"),
            tags=lesson.get("tags", []),
            difficulty=lesson.get("difficulty", "intermediate"),
            applies_to=lesson.get("applies_to", []),
        )
        _sign_lesson(lesson_obj, self._identity_store)

        self._publish_dir.mkdir(parents=True, exist_ok=True)
        slug = _make_slug(lesson_obj.title)
        dest = self._publish_dir / f"{lesson_obj.source[:8]}-{slug or 'lesson'}.json"
        dest.write_text(json.dumps(lesson_obj.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        # Also adopt locally
        insight = Insight(
            title=lesson_obj.title,
            body=lesson_obj.body,
            topic=lesson_obj.topic,
            source=lesson_obj.source,
            source_pubkey=lesson_obj.source_pubkey,
            ts=lesson_obj.ts,
            signature=lesson_obj.signature,
        )
        adopt(insight, self._memory_path, require_verify=False)

        return {
            "ok": True,
            "lesson_id": lesson_obj.lesson_id,
            "path": str(dest),
            "source": lesson_obj.source,
            "topic": lesson_obj.topic,
            "signed": bool(lesson_obj.signature),
        }

    def import_lessons_from_mesh(self, max_lessons: int = 20) -> list[dict]:
        """Fetch lessons from peer insight files and the publish directory.

        Scans the local mesh publish dir + attempts to locate peer insight
        files in ``~/.openamer/a2a/insights/``. Returns deduplicated lessons
        as dicts, newest first.
        """
        lessons: dict[str, dict] = {}

        # 1) Scan our own publish directory
        if self._publish_dir.exists():
            for p in sorted(self._publish_dir.glob("*.json")):
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    lid = d.get("lesson_id", "")
                    if lid and lid not in lessons:
                        lessons[lid] = d
                except Exception:
                    continue

        # 2) Scan the shared peer insights directory
        peer_insights_dir = _base_dir() / "a2a" / "insights"
        if peer_insights_dir.exists():
            for p in sorted(peer_insights_dir.glob("*.json")):
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    # peer insight files have an "insights" key or are raw lists
                    raw_insights = d.get("insights", d) if isinstance(d, dict) else d
                    if isinstance(raw_insights, dict):
                        raw_insights = [raw_insights]
                    for item in raw_insights:
                        if isinstance(item, dict):
                            lid = item.get("lesson_id", item.get("id", ""))
                            if lid and lid not in lessons:
                                lessons[lid] = item
                except Exception:
                    continue

        # 3) Convert to list, newest first
        result = []
        for v in lessons.values():
            result.append(_mesh_lesson_to_dict(v))
        result.sort(key=lambda x: x.get("ts", 0), reverse=True)

        return result[:max_lessons]

    def apply_lesson_to_skills(self, lesson: dict) -> bool:
        """Convert a mesh lesson into a local skill improvement.

        If the lesson has an ``applies_to`` list, only those skills are
        targeted; otherwise it scans all skills. Returns True if at least
        one skill was updated.
        """
        lesson_obj = MeshLesson.from_dict(lesson)
        if not lesson_obj.body:
            return False

        target_skills = lesson_obj.applies_to
        if target_skills:
            candidates = [self._skills_dir / s for s in target_skills]
        else:
            candidates = sorted(
                [p for p in self._skills_dir.iterdir() if p.is_dir()],
                key=lambda p: p.stat().st_mtime, reverse=True,
            ) if self._skills_dir.exists() else []

        updated = 0
        for skill_dir in candidates:
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            # Use the custom lesson-to-skill function if provided, else default
            if self._lesson_to_skill_fn:
                new_content = self._lesson_to_skill_fn(lesson_obj)
            else:
                new_content = _default_lesson_to_skill(lesson_obj, skill_name)

            if new_content:
                try:
                    existing = skill_file.read_text(encoding="utf-8")
                    # Simple dedup: skip if lesson already embedded
                    if lesson_obj.title in existing or lesson_obj.lesson_id in existing:
                        continue
                    updated_text = existing.rstrip("\n") + "\n\n" + new_content + "\n"
                    skill_file.write_text(updated_text, encoding="utf-8")
                    updated += 1
                except Exception:
                    continue

        return updated > 0

    def get_mesh_learning_stats(self) -> dict:
        """Return aggregate statistics about what the mesh has learned."""
        published = 0
        if self._publish_dir.exists():
            published = len(list(self._publish_dir.glob("*.json")))

        imported_lessons = 0
        if self._IMPORTED_DIR.exists():
            imported_lessons = len(list(self._IMPORTED_DIR.glob("*.json")))

        # Count memory entries
        memory_count = 0
        if self._memory_path.exists():
            for line in self._memory_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith("#mesh:"):
                    memory_count += 1

        # Skill count
        skill_count = len(list(self._skills_dir.glob("*/SKILL.md"))) if self._skills_dir.exists() else 0

        # Topics
        topics: dict[str, int] = {}
        if self._publish_dir.exists():
            for p in self._publish_dir.glob("*.json"):
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    topic = d.get("topic", "general")
                    topics[topic] = topics.get(topic, 0) + 1
                except Exception:
                    continue

        # Last published timestamp
        last_published = None
        if self._publish_dir.exists():
            files = list(self._publish_dir.glob("*.json"))
            if files:
                try:
                    last = max(f.stat().st_mtime for f in files)
                    last_published = datetime.fromtimestamp(last).isoformat()
                except Exception:
                    pass

        return {
            "lessons_published": published,
            "lessons_imported": imported_lessons,
            "memory_entries": memory_count,
            "local_skills": skill_count,
            "topics": topics,
            "last_published": last_published,
            "mesh_path": str(self._mesh_dir),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_lesson_id(title: str) -> str:
    import hashlib
    ts = int(time.time() * 1000)
    h = hashlib.sha256(f"{title}:{ts}".encode()).hexdigest()[:12]
    return f"mesh-{h}"


def _make_slug(title: str) -> str:
    slug = "".join(c for c in title.lower() if c.isalnum() or c in "-_ ")[:40].strip()
    return slug.replace(" ", "-")


def _mesh_lesson_to_dict(item: dict) -> dict:
    """Normalise a raw dict into a consistent lesson dict."""
    return {
        "lesson_id": item.get("lesson_id", item.get("id", "")),
        "title": item.get("title", ""),
        "body": item.get("body", item.get("summary", "")),
        "topic": item.get("topic", "general"),
        "source": item.get("source", item.get("publisher", "")),
        "source_pubkey": item.get("source_pubkey", item.get("publisher_pubkey", "")),
        "ts": int(item.get("ts", item.get("created_at", 0))),
        "signature": item.get("signature", ""),
        "tags": item.get("tags", []),
        "difficulty": item.get("difficulty", "intermediate"),
        "applies_to": item.get("applies_to", []),
    }


def _default_lesson_to_skill(lesson: MeshLesson, skill_name: str) -> Optional[str]:
    """Default converter: append a markdown note to the skill."""
    return (
        f"> **Mesh lesson: {lesson.title}**  \n"
        f"> (from {lesson.source[:12]}@mesh, topic: {lesson.topic})  \n"
        f"> {lesson.body[:500]}"
    )