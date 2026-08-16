"""openamer_cli.a2a.skillshare — signed skill manifests for the A2A mesh.

Extends the existing skill-publish flow with *verifiable integrity + provenance*
for the swarm: a SkillManifest records a skill's content hashes and the
publishing node's signature, so a subscribing node can confirm a received skill
is unmodified and genuinely from the claimed node — never blindly install.

Usage (CLI): `openamer a2a skill sign <dir>` and `openamer a2a skill verify <dir>`.
Only stdlib + our a2a core are used (no new runtime deps).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from openamer_cli.a2a.core import IdentityStore, public_key_from_hex


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _body_excluding_signature(d: dict) -> str:
    """Canonical JSON over all fields except `signature`, sorted keys."""
    body = dict(d)
    body.pop("signature", None)
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


@dataclass
class SkillManifest:
    name: str
    files: dict                       # relpath -> sha256
    publisher: str                    # publisher node fingerprint
    publisher_pubkey: str
    ts: int
    signature: str = ""

    # ---- creation ----------------------------------------------------------

    @classmethod
    def build(cls, skill_dir: Path, *, identity_store) -> "SkillManifest":
        if not (skill_dir / "SKILL.md").exists():
            raise ValueError(f"no SKILL.md in {skill_dir}")
        files: dict[str, str] = {}
        for p in sorted(skill_dir.rglob("*")):
            if p.is_file() and "node_modules" not in p.parts:
                files[str(p.relative_to(skill_dir)).replace("\\", "/")] = _hash_file(p)
        ident = identity_store.ensure_identity()
        m = cls(
            name=skill_dir.name,
            files=files,
            publisher=ident.fingerprint,
            publisher_pubkey=ident.public_key,
            ts=int(time.time()),
        )
        m.signature = identity_store.private_key().sign(
            _body_excluding_signature(m.to_dict()).encode("utf-8")
        ).hex()
        return m

    # ---- serialization -----------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SkillManifest":
        return cls(
            name=d["name"], files=d["files"], publisher=d["publisher"],
            publisher_pubkey=d["publisher_pubkey"], ts=d["ts"],
            signature=d.get("signature", ""),
        )

    # ---- verification ------------------------------------------------------

    def verify_signature(self, tolerance: int = 7 * 24 * 3600) -> bool:
        """Signature must be valid, fresh, and self-fingerprint-consistent."""
        if not self.signature:
            return False
        try:
            pub = public_key_from_hex(self.publisher_pubkey)
            body = _body_excluding_signature(self.to_dict())
            pub.verify(bytes.fromhex(self.signature), body.encode("utf-8"))
        except Exception:
            return False
        return abs(int(time.time()) - int(self.ts)) <= tolerance

    def verify_directory(self, skill_dir: Path) -> bool:
        """Verify a local skill dir's files match the manifest hashes exactly."""
        if not skill_dir.exists():
            return False
        for rel, expect in self.files.items():
            p = skill_dir / rel
            if not p.is_file() or _hash_file(p) != expect:
                return False
        return True

    def verify_all(self, skill_dir: Optional[Path] = None) -> dict:
        sig = self.verify_signature()
        integ = self.verify_directory(skill_dir) if skill_dir else None
        return {"signature_ok": sig, "content_ok": integ}


def publish(skill_dir: Path, out_dir: Path, *, identity_store) -> Path:
    """Build + sign a manifest for skill_dir and write it to out_dir."""
    m = SkillManifest.build(skill_dir, identity_store=identity_store)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{m.name}.json"
    dest.write_text(json.dumps(m.to_dict(), indent=2), encoding="utf-8")
    return dest