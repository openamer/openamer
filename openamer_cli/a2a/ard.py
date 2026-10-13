"""Agentic Resource Discovery (ARD) entry for an OpenAmer A2A node.

Makes the OpenAmer agent discoverable via the open ARD standard
(ards-project/ard-spec), the same way MCP servers / A2A agent cards are
catalogued — so external ARD registries can index OpenAmer.

An ARD entry is a JSON-LD node; this module builds one from this node's A2A
identity. See ard-spec §4 (ARD entry) for the field semantics.
"""
from __future__ import annotations

import json
from typing import Optional

DEFAULT_CONTEXT = "https://agenticresourcediscovery.org/context/v1"


def arn_for(fingerprint: str, publisher: str = "openamer.github.io",
            namespace: str = "mesh", name: str = "openamer-agent") -> str:
    """Domain-anchored URN per ARD spec Appendix C.

    urn:air:<publisher>:<namespace>:<agent-name>
    """
    def _slug(s: str, maxlen: int = 40) -> str:
        import re
        s = re.sub(r"[^a-z0-9.-]", "-", s.lower())
        return s[:maxlen]
    return f"urn:air:{_slug(publisher)}:{_slug(namespace)}:{_slug(name)}"


def build_entry(fingerprint: str, name: str = "OpenAmer",
                capabilities: Optional[list] = None,
                endpoints: Optional[list] = None,
                queries: Optional[list] = None) -> dict:
    """Build a spec-conformant ARD entry for this A2A node.

    Carries the discovery signals an ARD registry indexes on: identifier (a
    domain-anchored URN), representativeQueries (so it is searchable), and
    capabilities + endpoints when known.
    """
    caps = capabilities or ["a2a.task.ask", "a2a.task.delegate", "agent-card"]
    return {
        "@context": DEFAULT_CONTEXT,
        "@type": "Agent",
        "identifier": arn_for(fingerprint),
        "name": name,
        "description": "OpenAmer — an autonomous AI agent with agent-to-agent "
                       "(A2A) task delegation over the internet.",
        "representativeQueries": queries or [
            "delegate a task to an autonomous agent",
            "ask an autonomous AI agent a question over the internet",
            "find an A2A-capable open-source agent",
        ],
        "capabilities": caps,
        "endpoints": endpoints or [],
        "publisher": "openamer",
        "nodeFingerprint": fingerprint,
    }


def to_json(entry: dict, indent: int = 2) -> str:
    return json.dumps(entry, ensure_ascii=False, indent=indent)


def write_entry(entry: dict, out_dir) -> str:
    """Write the ARD entry as a discoverable .json file; returns its path."""
    import pathlib
    p = pathlib.Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    f = p / "ard-openamer-agent.json"
    f.write_text(to_json(entry), encoding="utf-8")
    return str(f)