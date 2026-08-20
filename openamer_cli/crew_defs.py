"""JSON Crew Definition system — portable, shareable crew configurations.

Extends the existing crew_orchestrator.py with JSON-serializable crew defs
that can be shared, version-controlled, and imported.

Usage:
    openamer crew export <name> --file crew.json   # Export crew to JSON
    openamer crew import <file>                     # Import crew from JSON
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from openamer_cli.crew_orchestrator import Crew, CrewMember, CrewStore

logger = logging.getLogger(__name__)


@dataclass
class CrewDefinition:
    """A portable crew definition that can be serialized to JSON."""

    format_version: str = "1.0"
    name: str = ""
    description: str = ""
    members: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    author: str = ""

    def to_crew(self) -> Crew:
        """Convert this definition to a Crew object."""
        members = []
        for m in self.members:
            members.append(CrewMember(
                name=m.get("name", "unknown"),
                role=m.get("role", "researcher"),
                goal=m.get("goal", ""),
                backstory=m.get("backstory", ""),
            ))
        return Crew(name=self.name, members=members)

    @classmethod
    def from_crew(cls, crew: Crew, description: str = "") -> "CrewDefinition":
        """Create a definition from an existing Crew."""
        members = []
        for m in crew.members:
            members.append(asdict(m))
        return cls(
            name=crew.name,
            description=description or f"Crew with {len(crew.members)} members",
            members=members,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CrewDefinition":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# CLI functions
# ---------------------------------------------------------------------------


def export_crew(crew_name: str, file_path: Optional[str] = None) -> str:
    """Export a crew to a JSON file.

    Args:
        crew_name: Name of the crew to export
        file_path: Optional output file path. Defaults to <crew_name>.json

    Returns:
        Path to the exported file
    """
    store = CrewStore()
    crew = store.load(crew_name)

    path = Path(file_path) if file_path else Path(f"{crew_name}.json")
    definition = CrewDefinition.from_crew(crew, description=f"Exported crew: {crew_name}")
    path.write_text(json.dumps(definition.to_dict(), indent=2), encoding="utf-8")
    logger.info("Exported crew '%s' to %s", crew_name, path)
    return str(path)


def import_crew(file_path: str) -> str:
    """Import a crew from a JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Name of the imported crew
    """
    path = Path(file_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    definition = CrewDefinition.from_dict(data)
    crew = definition.to_crew()

    store = CrewStore()
    store.save(crew)
    logger.info("Imported crew '%s' from %s", crew.name, file_path)
    return crew.name


def list_portable_crews(directory: str = ".") -> List[Dict[str, Any]]:
    """List all portable crew JSON files in a directory."""
    path = Path(directory)
    crews = []
    for f in sorted(path.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if "format_version" in data and "members" in data:
                crews.append({
                    "file": f.name,
                    "name": data.get("name", "?"),
                    "members": len(data.get("members", [])),
                    "description": data.get("description", "")[:60],
                })
        except Exception:
            pass
    return crews


def cmd_crew_export(args) -> None:
    """Export a crew to JSON."""
    name = getattr(args, "crew_name", "")
    file_path = getattr(args, "file", None)
    result = export_crew(name, file_path)
    print(f"Exported crew '{name}' to {result}")


def cmd_crew_import(args) -> None:
    """Import a crew from JSON."""
    file_path = getattr(args, "file", "")
    name = import_crew(file_path)
    print(f"Imported crew '{name}' from {file_path}")


def build_crew_defs_parser(crew_sub) -> None:
    """Add export/import subcommands to crew parser."""
    export_p = crew_sub.add_parser("export", help="Export crew to portable JSON file")
    export_p.add_argument("crew_name", help="Name of crew to export")
    export_p.add_argument("--file", "-f", default=None, help="Output file path (default: <name>.json)")
    export_p.set_defaults(func=cmd_crew_export)

    import_p = crew_sub.add_parser("import", help="Import crew from portable JSON file")
    import_p.add_argument("file", help="Path to crew JSON file")
    import_p.set_defaults(func=cmd_crew_import)