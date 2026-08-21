#!/usr/bin/env python3
"""
OPENAMER_TOOL — Code Generator
===============================
Generiert neue Skripte, Skills und Plugins aus eingebauten Templates.
CLI mit 4 Modi, JSON-Output und Exit-Codes.

Exit-Codes:
  0 = Erfolg
  1 = Fehler (ungültige Argumente, Template nicht gefunden)
  2 = Schreibfehler (Berechtigung, Pfad nicht beschreibbar)
  3 = Abhängigkeitsfehler (Python-Modul fehlt)

JSON-Output-Struktur (--json):
  {
    "tool": "code-generator",
    "version": "1.0.0",
    "mode": "script|skill|plugin|list",
    "status": "ok|error",
    "output": { ... modus-spezifisch ... },
    "exit_code": 0|1|2|3
  }
"""

import argparse
import json
import os
import re
import shutil
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Pfade ──────────────────────────────────────────────────────────────────────
_LOCALAPPDATA = os.environ.get("LOCALAPPDATA", str(Path.home()))
OPENAMER_HOME = Path(_LOCALAPPDATA) / "openamer-laptop"
SCRIPTS_DIR = OPENAMER_HOME / "scripts"
SKILLS_DIR = OPENAMER_HOME / "skills"
PLUGINS_DIR = OPENAMER_HOME / "desktop-plugins" / "examples"
TEMPLATES_DIR = OPENAMER_HOME / ".code-generator" / "templates"

VERSION = "1.0.0"
TOOL_NAME = "code-generator"

# ── Templates ───────────────────────────────────────────────────────────────────
# Jedes Template ist ein Dict mit Keys:
#   name        – Anzeigename
#   description – Kurzbeschreibung
#   category   – 'script' | 'skill' | 'plugin'
#   files      – Dict {rel_path: template_string}
#   args       – Dict {arg_name: {type, help, default?, required?}}

TEMPLATES: Dict[str, Dict[str, Any]] = {
    # ── Script-Template ──────────────────────────────────────────────────────
    "script": {
        "name": "Python Script",
        "description": (
            "Ein neues OpenAmer-Script mit Shebang, Docstring, Argparse, "
            "OPENAMER_TOOL-Konvention, Exit-Codes, JSON-Output und Main-Block."
        ),
        "category": "script",
        "files": {
            "{{name}}.py": textwrap.dedent("""\
            #!/usr/bin/env python3
            \"\"\"
            OPENAMER_TOOL — {{name}}
            ====================================
            {{description}}

            CLI:
              python {{name}}.py --help

            Exit-Codes:
              0 = Erfolg
              1 = Fehler (ungültige Argumente)
              2 = Schreibfehler
              3 = Abhängigkeitsfehler

            JSON-Output-Struktur (--json):
              {
                "tool": "{{name}}",
                "version": "{{version}}",
                "status": "ok|error",
                "output": { ... },
                "exit_code": 0|1|2|3
              }
            \"\"\"

            import argparse
            import json
            import os
            import sys
            from datetime import datetime
            from pathlib import Path
            from typing import Any, Dict, List, Optional{{extra_imports}}

            # ── Pfade ──────────────────────────────────────────────────────────────────────
            OPENAMER_HOME = Path(os.environ.get(
                "OPENAMER_HOME",
                os.path.join(os.environ.get("LOCALAPPDATA", str(Path.home())), "openamer-laptop"),
            ))

            VERSION = "{{version}}"
            TOOL_NAME = "{{name}}"

            # ── Exit-Codes ──────────────────────────────────────────────────────────────────
            EXIT_OK = 0
            EXIT_ERROR = 1
            EXIT_WRITE = 2
            EXIT_DEPS = 3

            {{cron_block}}{{cron_imports_block}}

            # ── CLI ─────────────────────────────────────────────────────────────────────────
            def create_parser() -> argparse.ArgumentParser:
                \"\"\"Erzeugt den ArgumentParser.\"\"\"
                parser = argparse.ArgumentParser(
                    prog=TOOL_NAME,
                    description="{{description}}",
                    formatter_class=argparse.RawDescriptionHelpFormatter,
                    epilog=(
                        "Exit-Codes: 0=Erfolg, 1=Fehler, 2=Schreibfehler, 3=Abhängigkeitsfehler\\n"
                        "Mehr unter: https://github.com/openamer/openamer"
                    ),
                )
                parser.add_argument(
                    "--json",
                    action="store_true",
                    help="Ausgabe als JSON (statt Text)",
                )
                parser.add_argument(
                    "--verbose",
                    "-v",
                    action="store_true",
                    help="Ausführliche Ausgabe",
                )
                {{cli_args}}
                return parser

            # ── Geschäftslogik ──────────────────────────────────────────────────────────────
            def run(args: argparse.Namespace) -> Dict[str, Any]:
                \"\"\"Führt die Hauptlogik aus. Gibt Dict für JSON-Output zurück.\"\"\"
                result: Dict[str, Any] = {
                    "tool": TOOL_NAME,
                    "version": VERSION,
                    "status": "ok",
                    "output": {},
                }

                # ── Hier die Geschäftslogik ──
                result["output"]["message"] = "{{name}} wurde ausgeführt."
                result["output"]["timestamp"] = datetime.now().isoformat()

                return result

            # ── Main ────────────────────────────────────────────────────────────────────────
            def main() -> int:
                \"\"\"Einstiegspunkt.\"\"\"
                parser = create_parser()
                args = parser.parse_args()

                try:
                    result = run(args)
                    if args.json:
                        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
                    else:
                        msg = result.get("output", {}).get("message", "")
                        print(f"[{{TOOL_NAME}}] {{msg}}")
                        if args.verbose:
                            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
                    return EXIT_OK
                except ValueError as e:
                    err = {"tool": TOOL_NAME, "status": "error", "error": str(e), "exit_code": EXIT_ERROR}
                    if args_json := getattr(args, "json", False):
                        print(json.dumps(err, indent=2, ensure_ascii=False))
                    else:
                        print(f"[FEHLER] {{e}}", file=sys.stderr)
                    return EXIT_ERROR
                except PermissionError as e:
                    err = {"tool": TOOL_NAME, "status": "error", "error": str(e), "exit_code": EXIT_WRITE}
                    if getattr(args, "json", False):
                        print(json.dumps(err, indent=2, ensure_ascii=False))
                    else:
                        print(f"[SCHREIBFEHLER] {{e}}", file=sys.stderr)
                    return EXIT_WRITE
                except ImportError as e:
                    err = {"tool": TOOL_NAME, "status": "error", "error": f"Fehlende Abhängigkeit: {e}", "exit_code": EXIT_DEPS}
                    if getattr(args, "json", False):
                        print(json.dumps(err, indent=2, ensure_ascii=False))
                    else:
                        print(f"[ABHÄNGIGKEITSFEHLER] {{e}}", file=sys.stderr)
                    return EXIT_DEPS
                except Exception as e:
                    err = {"tool": TOOL_NAME, "status": "error", "error": str(e), "exit_code": EXIT_ERROR}
                    if getattr(args, "json", False):
                        print(json.dumps(err, indent=2, ensure_ascii=False, default=str))
                    else:
                        print(f"[FEHLER] {{e}}", file=sys.stderr)
                    return EXIT_ERROR

            if __name__ == "__main__":
                sys.exit(main())
            """),
        },
        "args": {
            "name": {"type": str, "help": "Script-Name (ohne .py)", "required": True},
            "desc": {"type": str, "help": "Kurzbeschreibung", "required": True},
            "cron": {"type": str, "help": "Cron-Intervall (z.B. '30min', '1h', 'daily')", "required": False, "default": ""},
            "exit_codes": {"type": bool, "help": "Exit-Codes-Doku einbauen", "required": False, "default": True},
        },
    },

    # ── Skill-Template ────────────────────────────────────────────────────────
    "skill": {
        "name": "OpenAmer Skill (SKILL.md)",
        "description": (
            "Ein vollständiges Skill-Verzeichnis mit SKILL.md, Frontmatter, "
            "Beschreibung, Usage, Implementation und optionalen Scripts."
        ),
        "category": "skill",
        "files": {
            "SKILL.md": textwrap.dedent("""\
            ---
            name: {{name}}
            category: {{category}}
            description: {{description}}
            ---

            # {{name}}

            {{description}}

            ## Usage

            This skill provides {{name}} functionality for OpenAmer.

            ### CLI

            ```bash
            python scripts/{{name}}.py --help
            ```

            ### As a Skill

            ```yaml
            # In config.yaml or via openamer config
            skills:
              - {{name}}
            ```

            ## Implementation

            The skill lives in `skills/{{category}}/{{name}}/` and can include
            scripts, references, and templates.

            ## Verification

            1. Ensure the skill is loaded: `openamer skills list | grep {{name}}`
            2. Run the associated script: `python scripts/{{name}}.py --help`

            ## Exit Codes

            | Code | Bedeutung           |
            |------|---------------------|
            | 0    | Erfolg              |
            | 1    | Allgemeiner Fehler  |
            | 2    | Schreib-/Zugriffsfehler |
            | 3    | Fehlende Abhängigkeit  |

            ## JSON Output

            Alle {{name}}-Befehle unterstützen `--json` für maschinenlesbare Ausgabe:

            ```json
            {
              "tool": "{{name}}",
              "version": "1.0.0",
              "status": "ok",
              "output": { ... }
            }
            ```
            """),
        },
        "args": {
            "name": {"type": str, "help": "Skill-Name (lowercase, hyphens)", "required": True},
            "desc": {"type": str, "help": "Kurzbeschreibung (max 80 Zeichen)", "required": True},
            "category": {"type": str, "help": "Skill-Kategorie (z.B. system, devops, security)", "required": True,
                         "choices": [
                             "system", "devops", "security", "software-development",
                             "autonomous-ai-agents", "creative", "desktop", "email",
                             "github", "imported", "marketing", "media",
                             "mlops", "note-taking", "productivity", "research",
                             "smart-home", "social-media",
                         ]},
        },
    },

    # ── Plugin-Template ────────────────────────────────────────────────────────
    "plugin": {
        "name": "Desktop Plugin (__init__.py + plugin.yaml)",
        "description": (
            "Ein OpenAmer Desktop Plugin mit __init__.py, plugin.yaml "
            "und OPENAMER_TOOL-Konvention."
        ),
        "category": "plugin",
        "files": {
            "__init__.py": textwrap.dedent("""\
            \"\"\"
            OPENAMER_TOOL — {{name}} Plugin
            ====================================
            {{description}}

            Exit-Codes:
              0 = Erfolg
              1 = Fehler
              2 = Schreibfehler

            JSON-Output-Struktur (--json):
              {
                "tool": "{{name}}",
                "version": "1.0.0",
                "status": "ok|error",
                "output": { ... },
                "exit_code": 0|1|2
              }
            \"\"\"

            import json
            import sys
            from pathlib import Path
            from typing import Any, Dict, Optional

            VERSION = "1.0.0"
            PLUGIN_NAME = "{{name}}"

            # ── Plugin-Hooks ────────────────────────────────────────────────────────────────

            def on_load() -> Dict[str, Any]:
                \"\"\"Wird beim Laden des Plugins aufgerufen.\"\"\"
                return {
                    "name": PLUGIN_NAME,
                    "version": VERSION,
                    "status": "loaded",
                }

            def on_unload() -> Dict[str, Any]:
                \"\"\"Wird beim Entladen des Plugins aufgerufen.\"\"\"
                return {
                    "name": PLUGIN_NAME,
                    "version": VERSION,
                    "status": "unloaded",
                }

            def execute(action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
                \"\"\"Führt eine Plugin-Aktion aus.\"\"\"
                if params is None:
                    params = {}
                return {
                    "tool": PLUGIN_NAME,
                    "version": VERSION,
                    "status": "ok",
                    "output": {
                        "action": action,
                        "params": params,
                        "message": "{{name}}: Aktion ausgeführt.",
                    },
                }

            # ── CLI (optional, für Direktaufruf) ───────────────────────────────────────────

            def main() -> int:
                \"\"\"CLI-Einstieg (python -m desktop-plugins.examples.{{name}}).\"\"\"
                import argparse
                parser = argparse.ArgumentParser(prog=PLUGIN_NAME, description="{{description}}")
                parser.add_argument("--json", action="store_true", help="JSON-Ausgabe")
                parser.add_argument("--action", default="ping", help="Aktion (ping, status, execute)")
                args = parser.parse_args()

                if args.action == "ping":
                    result = on_load()
                elif args.action == "status":
                    result = on_load()
                else:
                    result = execute(args.action)

                if args.json:
                    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
                else:
                    print(f"[{PLUGIN_NAME}] {{result.get('output', {}).get('message', 'OK')}}")
                return 0

            if __name__ == "__main__":
                sys.exit(main())
            """),
            "plugin.yaml": textwrap.dedent("""\
            # {{name}} — OpenAmer Desktop Plugin
            # Erstellt: {{date}}
            name: {{name}}
            version: "{{version}}"
            description: "{{description}}"
            author: "OpenAmer Code Generator"
            type: desktop-plugin

            # Einstiegspunkt (Python-Modul-Pfad)
            entry: desktop-plugins.examples.{{name}}.__init__

            hooks:
              on_load: on_load
              on_unload: on_unload
              execute: execute

            # Metadaten
            tags:
              - plugin
              - desktop
              - generated
            """),
        },
        "args": {
            "name": {"type": str, "help": "Plugin-Name (lowercase, hyphens)", "required": True},
            "desc": {"type": str, "help": "Kurzbeschreibung", "required": False, "default": "Ein OpenAmer Desktop Plugin"},
        },
    },
}

# ── Template-Ersetzung ─────────────────────────────────────────────────────────

def render_template(template_str: str, context: Dict[str, Any]) -> str:
    """Ersetzt {{placeholders}} im Template-String mit Context-Werten."""
    result = template_str
    for key, value in context.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def slugify(name: str) -> str:
    """Macht aus einem Namen einen Dateinamen: lowercase, Bindestriche."""
    return re.sub(r"[^a-z0-9_-]", "", name.lower().replace(" ", "-"))


def compute_version() -> str:
    """Liefert Version als Datum (z.B. 1.0.0) oder später dynamisch."""
    return "1.0.0"


# ── Generatoren ────────────────────────────────────────────────────────────────

def generate_script(name: str, description: str, cron: str = "", exit_codes: bool = True) -> Dict[str, Any]:
    """Generiert ein neues Script aus dem Script-Template."""
    safe_name = slugify(name)
    script_path = SCRIPTS_DIR / f"{safe_name}.py"

    if script_path.exists():
        raise ValueError(f"Script existiert bereits: {script_path}")

    # CLI-Args aus Template
    cli_args = ""
    if cron:
        cli_args += textwrap.dedent(f"""\
                parser.add_argument(
                    "--cron-interval",
                    default="{cron}",
                    help="Cron-Intervall (z.B. '{cron}')",
                )
        """)

    # Cron-Block
    cron_block = ""
    cron_imports_block = ""
    if cron:
        cron_imports_block = "\nimport time"
        interval_map = {"30min": 1800, "1h": 3600, "2h": 7200, "6h": 21600, "12h": 43200, "daily": 86400}
        interval_sec = interval_map.get(cron, 1800)
        cron_block = textwrap.dedent(f"""\
        # ── Cron ────────────────────────────────────────────────────────────────────────────
        RUN_INTERVAL = {interval_sec}  # {cron}
        """)

    # Extra-Imports
    extra_imports = ""
    if cron:
        extra_imports = "\nimport time"

    context = {
        "name": safe_name,
        "description": description,
        "version": VERSION,
        "cron": cron,
        "cron_block": cron_block,
        "cron_imports_block": cron_imports_block,
        "cli_args": cli_args,
        "extra_imports": extra_imports,
    }

    template_content = TEMPLATES["script"]["files"]["{{name}}.py"]
    rendered = render_template(template_content, context)

    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    script_path.write_text(rendered, encoding="utf-8")
    script_path.chmod(0o755)

    return {
        "mode": "script",
        "name": safe_name,
        "path": str(script_path),
        "description": description,
        "cron": cron,
        "exit_codes": exit_codes,
    }


def generate_skill(name: str, description: str, category: str) -> Dict[str, Any]:
    """Generiert einen neuen Skill (SKILL.md) in der angegebenen Kategorie."""
    safe_name = slugify(name)
    skill_dir = SKILLS_DIR / category / safe_name
    skill_path = skill_dir / "SKILL.md"

    if skill_path.exists():
        raise ValueError(f"Skill existiert bereits: {skill_path}")

    context = {
        "name": safe_name,
        "description": description,
        "category": category,
        "version": VERSION,
    }

    template_content = TEMPLATES["skill"]["files"]["SKILL.md"]
    rendered = render_template(template_content, context)

    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(rendered, encoding="utf-8")

    return {
        "mode": "skill",
        "name": safe_name,
        "path": str(skill_path),
        "category": category,
        "description": description,
    }


def generate_plugin(name: str, description: str) -> Dict[str, Any]:
    """Generiert ein neues Desktop-Plugin mit __init__.py + plugin.yaml."""
    safe_name = slugify(name)
    plugin_dir = PLUGINS_DIR / safe_name

    init_path = plugin_dir / "__init__.py"
    yaml_path = plugin_dir / "plugin.yaml"

    if init_path.exists() or yaml_path.exists():
        raise ValueError(f"Plugin existiert bereits: {plugin_dir}")

    context = {
        "name": safe_name,
        "description": description,
        "version": VERSION,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }

    plugin_dir.mkdir(parents=True, exist_ok=True)

    for rel_path, template_content in TEMPLATES["plugin"]["files"].items():
        rendered = render_template(template_content, context)
        target_path = plugin_dir / rel_path
        target_path.write_text(rendered, encoding="utf-8")

    return {
        "mode": "plugin",
        "name": safe_name,
        "path": str(plugin_dir),
        "description": description,
        "files": [str(init_path), str(yaml_path)],
    }


def list_templates(json_output: bool = False) -> Dict[str, Any]:
    """Listet alle verfügbaren Templates auf."""
    templates_info = {}
    for key, tmpl in TEMPLATES.items():
        templates_info[key] = {
            "name": tmpl["name"],
            "description": tmpl["description"],
            "category": tmpl["category"],
            "args": {
                arg_name: {
                    "type": arg_info["type"].__name__,
                    "help": arg_info["help"],
                    "required": arg_info.get("required", False),
                    "default": arg_info.get("default", None),
                }
                for arg_name, arg_info in tmpl["args"].items()
            },
            "files": list(tmpl["files"].keys()),
        }
    return {
        "tool": TOOL_NAME,
        "version": VERSION,
        "status": "ok",
        "output": {
            "templates": templates_info,
        },
    }


# ── CLI ─────────────────────────────────────────────────────────────────────────

def create_parser() -> argparse.ArgumentParser:
    """Erzeugt den ArgumentParser für den Code Generator."""
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="OPENAMER_TOOL — Scaffolding für Scripts, Skills und Plugins aus Templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Exit-Codes: 0=Erfolg, 1=Fehler, 2=Schreibfehler, 3=Abhängigkeitsfehler

            Beispiele:
              # Script generieren
              python code-generator.py --script my-tool --desc "Mein Tool"

              # Skill generieren
              python code-generator.py --skill my-skill --desc "Mein Skill" --category system

              # Plugin generieren
              python code-generator.py --plugin my-plugin --desc "Mein Plugin"

              # Templates auflisten
              python code-generator.py --list --json
        """),
    )

    # Modi (Mutually Exclusive Group)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--script",
        type=str,
        metavar="NAME",
        help="Generiert ein neues Python-Script aus dem Script-Template",
    )
    mode.add_argument(
        "--skill",
        type=str,
        metavar="NAME",
        help="Generiert einen neuen Skill (SKILL.md) aus dem Skill-Template",
    )
    mode.add_argument(
        "--plugin",
        type=str,
        metavar="NAME",
        help="Generiert ein neues Desktop-Plugin (__init__.py + plugin.yaml)",
    )
    mode.add_argument(
        "--list",
        action="store_true",
        help="Listet alle verfügbaren Templates auf",
    )

    # Gemeinsame Optionen
    parser.add_argument(
        "--desc",
        type=str,
        default="",
        help="Beschreibung für das generierte Artefakt",
    )
    parser.add_argument(
        "--category",
        type=str,
        default="system",
        choices=[
            "system", "devops", "security", "software-development",
            "autonomous-ai-agents", "creative", "desktop", "email",
            "github", "imported", "marketing", "media",
            "mlops", "note-taking", "productivity", "research",
            "smart-home", "social-media",
        ],
        help="Kategorie für Skill-Generierung (Default: system)",
    )
    parser.add_argument(
        "--cron",
        type=str,
        default="",
        help="Cron-Intervall für Script-Generierung (z.B. '30min', '1h', 'daily')",
    )
    parser.add_argument(
        "--no-exit-codes",
        action="store_false",
        dest="exit_codes",
        default=True,
        help="Exit-Codes-Doku weglassen",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Ausgabe als JSON (statt Text)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Ausführliche Ausgabe",
    )

    return parser


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> int:
    """Einstiegspunkt für den Code Generator."""
    parser = create_parser()
    args = parser.parse_args()

    # Prüfen, ob mindestens ein Modus gesetzt ist
    if not (args.script or args.skill or args.plugin or args.list):
        parser.print_help()
        return 1

    try:
        result: Dict[str, Any] = {
            "tool": TOOL_NAME,
            "version": VERSION,
            "status": "ok",
            "output": {},
        }

        if args.list:
            result = list_templates(args.json)
            if not args.json:
                print("Verfügbare Templates:\n")
                for key, tmpl in result["output"]["templates"].items():
                    print(f"  {key}: {tmpl['name']}")
                    print(f"    Beschreibung: {tmpl['description']}")
                    print(f"    Kategorie:    {tmpl['category']}")
                    print(f"    Dateien:      {', '.join(tmpl['files'])}")
                    print(f"    Args:")
                    for arg_name, arg_info in tmpl["args"].items():
                        req = "(erforderlich)" if arg_info["required"] else f"(optional, default={arg_info['default']})"
                        print(f"      --{arg_name}: {arg_info['help']} {req}")
                    print()

        elif args.script:
            if not args.desc:
                print("[FEHLER] --desc ist erforderlich für --script", file=sys.stderr)
                return 1
            output = generate_script(
                name=args.script,
                description=args.desc,
                cron=args.cron,
                exit_codes=args.exit_codes,
            )
            result["output"] = output
            if not args.json:
                print(f"[OK] Script generiert: {output['path']}")

        elif args.skill:
            if not args.desc:
                print("[FEHLER] --desc ist erforderlich für --skill", file=sys.stderr)
                return 1
            output = generate_skill(
                name=args.skill,
                description=args.desc,
                category=args.category,
            )
            result["output"] = output
            if not args.json:
                print(f"[OK] Skill generiert: {output['path']}")

        elif args.plugin:
            desc = args.desc or f"Plugin {args.plugin}"
            output = generate_plugin(
                name=args.plugin,
                description=desc,
            )
            result["output"] = output
            if not args.json:
                print(f"[OK] Plugin generiert: {output['path']}")
                for f in output.get("files", []):
                    print(f"  ├─ {f}")

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

        return 0

    except ValueError as e:
        err = {"tool": TOOL_NAME, "status": "error", "error": str(e), "exit_code": 1}
        if args.json:
            print(json.dumps(err, indent=2, ensure_ascii=False))
        else:
            print(f"[FEHLER] {e}", file=sys.stderr)
        return 1
    except PermissionError as e:
        err = {"tool": TOOL_NAME, "status": "error", "error": str(e), "exit_code": 2}
        if args.json:
            print(json.dumps(err, indent=2, ensure_ascii=False))
        else:
            print(f"[SCHREIBFEHLER] {e}", file=sys.stderr)
        return 2
    except Exception as e:
        err = {"tool": TOOL_NAME, "status": "error", "error": str(e), "exit_code": 1}
        if args.json:
            print(json.dumps(err, indent=2, ensure_ascii=False, default=str))
        else:
            print(f"[FEHLER] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())