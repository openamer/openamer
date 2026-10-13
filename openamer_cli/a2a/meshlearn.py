"""openamer_cli.a2a.meshlearn — shared mesh learning memory for the swarm.

Phase 4: the "the organism learns". A node publishes small, signed *insights*
(distilled lessons: a fix, a tip, a shortcut), they are staged into an official
GitHub directory for the mesh (github.com/openamer/openamer/directory/a2a/
insights/), and a trusting node can adopt a verified insight into its own
curated memory. Adoption is always pin==receive, opt-in, provenance-verified --
never blind.

Capabilities provided:
  - Insight.new / .sign / .to_dict / .from_dict / .verify
  - publish(): write a signed insight JSON into a publish/insights dir
  - adopt(): verify + append to the local memory file (MEMORY.md / mesh.md)

Only stdlib + our a2a core. No new deps.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from openamer_cli.a2a.core import IdentityStore, public_key_from_hex


def _body(d: dict) -> str:
    b = dict(d); b.pop("signature", None)
    return json.dumps(b, sort_keys=True, separators=(",", ":"))


@dataclass
class Insight:
    title: str
    body: str                 # the lesson / fix / tip text
    topic: str                # coarse bucket for routing (e.g. "debug", "skill", "mesh")
    source: str               # publishing node fingerprint  <fp>@openamer
    source_pubkey: str
    ts: int
    signature: str = ""

    @classmethod
    def build(cls, *, identity_store, title: str, body: str, topic: str) -> "Insight":
        ident = identity_store.ensure_identity()
        ins = cls(title=title, body=body, topic=topic,
                  source=ident.fingerprint, source_pubkey=ident.public_key,
                  ts=int(time.time()))
        ins.signature = identity_store.private_key().sign(
            _body(ins.to_dict()).encode("utf-8")).hex()
        return ins

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Insight":
        return cls(title=d["title"], body=d["body"], topic=d.get("topic", "general"),
                   source=d["source"], source_pubkey=d["source_pubkey"],
                   ts=int(d["ts"]), signature=d.get("signature", ""))

    def verify(self, tolerance: int = 30 * 24 * 3600) -> bool:
        """Signature valid + fresh (30d)."""
        if not self.signature:
            return False
        try:
            pub = public_key_from_hex(self.source_pubkey)
            pub.verify(bytes.fromhex(self.signature), _body(self.to_dict()).encode("utf-8"))
        except Exception:
            return False
        return abs(int(time.time()) - int(self.ts)) <= tolerance


def publish(insight: Insight, out_dir: Path) -> Path:
    """Stage a signed insight for the GitHub mesh directory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c for c in insight.title.lower() if c.isalnum() or c in "-_ ")[:40].strip().replace(" ", "-")
    dest = out_dir / f"{insight.source[:8]}-{slug or 'insight'}.json"
    dest.write_text(json.dumps(insight.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return dest


def adopt(insight: Insight, memory_path: Path, *, require_verify: bool = True) -> bool:
    """Adopt a verified insight into the node's local learning memory.

    Appends one line to memory_path (default MEMORY or a mesh-memory file) so the
    sw level 'learned' shows up next session. Only if signature verifies.
    """
    if require_verify and not insight.verify():
        return False
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"#mesh:{insight.topic}: {insight.title} — {insight.body}"[:500]
    # de-dupe simple
    if memory_path.exists():
        cur = memory_path.read_text(encoding="utf-8", errors="replace")
        if insight.title in cur:
            return True  # already adopted
        new = cur.rstrip("\n") + "\n" + line + "\n"
    else:
        new = "# OpenAmer mesh-learning memory\n" + line + "\n"
    memory_path.write_text(new, encoding="utf-8")
    return True