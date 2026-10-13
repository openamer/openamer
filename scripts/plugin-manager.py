#!/usr/bin/env python3
"""
OpenAmer Plugin-Manager

Verwaltet OpenAmer Plugins — list, install, enable, disable, check.

Verwendung:
    python scripts/plugin-manager.py list
    python scripts/plugin-manager.py install <pfad>
    python scripts/plugin-manager.py enable <name>
    python scripts/plugin-manager.py disable <name>
    python scripts/plugin-manager.py check [name|--all]

Konfigurations-Integration:
    openamer config set plugin.<name>.enabled true/false
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Pfade ────────────────────────────────────────────────────────────────────

# OpenAmer Home (aus Umgebungsvariable oder Default)
OPENAMER_HOME = Path(os.environ.get(
    "OPENAMER_HOME",
    os.path.expanduser("~/.openamer"),
))

# Built-in Plugin-Verzeichnis (im Repo)
REPO_DIR = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO_DIR / "plugins"
USER_PLUGINS_DIR = REPO_DIR / "desktop-plugins"

# Config-Datei
CONFIG_FILE = Path(os.environ.get(
    "OPENAMER_CONFIG",
    OPENAMER_HOME / "config.yaml",
))


# ── Plugin-Modell ────────────────────────────────────────────────────────────


class Plugin:
    """Repräsentiert ein einzelnes Plugin."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.name: str = ""
        self.version: str = ""
        self.description: str = ""
        self.author: str = ""
        self.kind: str = ""
        self.hooks: List[str] = []
        self.manifest: Dict[str, Any] = {}
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Lädt die plugin.yaml."""
        yaml_path = self.path / "plugin.yaml"
        if not yaml_path.exists():
            self.name = self.path.name
            self.description = "(keine plugin.yaml)"
            return

        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            # Fallback: rudimentäres Parsing ohne PyYAML
            data = self._parse_yaml_simple(yaml_path)

        self.manifest = data
        self.name = data.get("name", self.path.name)
        self.version = str(data.get("version", "0.0.0"))
        self.description = str(data.get("description", ""))
        self.author = str(data.get("author", "unbekannt"))
        self.kind = str(data.get("kind", ""))
        self.hooks = data.get("hooks", [])

    @staticmethod
    def _parse_yaml_simple(path: Path) -> Dict[str, Any]:
        """Einfaches Fallback-Parsing ohne PyYAML."""
        data: Dict[str, Any] = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip()
                    if ":" in line and not line.startswith(" ") and not line.startswith("#"):
                        key, _, val = line.partition(":")
                        data[key.strip()] = val.strip().strip('"').strip("'")
        except Exception:
            pass
        return data

    @property
    def is_user_plugin(self) -> bool:
        """True, wenn das Plugin in desktop-plugins/ liegt."""
        return USER_PLUGINS_DIR in self.path.parents

    @property
    def dir_name(self) -> str:
        """Der Ordnername des Plugins."""
        return self.path.name

    @property
    def has_init(self) -> bool:
        """True, wenn __init__.py existiert."""
        return (self.path / "__init__.py").exists()

    @property
    def has_register(self) -> bool:
        """True, wenn __init__.py eine register()-Funktion exportiert."""
        if not self.has_init:
            return False
        try:
            import ast
            tree = ast.parse((self.path / "__init__.py").read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "register":
                    return True
            return False
        except SyntaxError:
            return False

    def __repr__(self) -> str:
        return f"<Plugin {self.name}@{self.version}>"


# ── Plugin-Scanner ───────────────────────────────────────────────────────────


def scan_plugins() -> List[Plugin]:
    """Scannt plugins/ und desktop-plugins/ nach gültigen Plugin-Verzeichnissen."""
    plugins: List[Plugin] = []
    seen: set = set()

    def scan_dir(base: Path, recursive: bool = False) -> None:
        if not base.exists():
            return
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            plugin = Plugin(child)
            # Nur echte Plugins aufnehmen (müssen plugin.yaml ODER register() haben)
            has_yaml = (child / "plugin.yaml").exists()
            if not has_yaml and not plugin.has_register:
                if recursive:
                    scan_dir(child, recursive=True)
                continue
            if plugin.name in seen:
                # User-Plugins überschreiben Built-ins gleichen Namens
                continue
            seen.add(plugin.name)
            plugins.append(plugin)

    # Built-in: nur eine Ebene (Plugin-Ordner liegen direkt in plugins/)
    scan_dir(PLUGINS_DIR)

    # Subdirs in browser/, web/ etc. rekursiv durchsuchen
    for sub in sorted(PLUGINS_DIR.iterdir()):
        if sub.is_dir() and not sub.name.startswith("_"):
            scan_dir(sub, recursive=True)

    # User-Plugins: rekursiv scannen (auch Beispiele in Subdirs)
    scan_dir(USER_PLUGINS_DIR, recursive=True)
    return plugins


# ── Config-Reader ────────────────────────────────────────────────────────────


def get_plugin_config() -> Dict[str, Any]:
    """Liest den plugin:-Abschnitt aus der config.yaml."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        import yaml
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return config.get("plugin", {})
    except Exception:
        return {}


def is_plugin_enabled(name: str, plugin_config: Optional[dict] = None) -> bool:
    """Prüft, ob ein Plugin in der Config aktiviert ist."""
    if plugin_config is None:
        plugin_config = get_plugin_config()
    cfg = plugin_config.get(name, {})
    if isinstance(cfg, dict):
        return cfg.get("enabled", True)  # Default: enabled
    return True


def set_plugin_enabled(name: str, enabled: bool) -> bool:
    """Setzt den enabled-Status eines Plugins in der Config."""
    try:
        import yaml
        config: Dict[str, Any] = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

        # Sicherstellen, dass plugin.<name> existiert
        if "plugin" not in config:
            config["plugin"] = {}
        if name not in config["plugin"] or not isinstance(config["plugin"][name], dict):
            config["plugin"][name] = {}
        config["plugin"][name]["enabled"] = enabled

        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        return True
    except Exception as e:
        print(f"❌ Fehler beim Schreiben der Config: {e}", file=sys.stderr)
        return False


# ── Installer ────────────────────────────────────────────────────────────────


def install_plugin(source: str) -> bool:
    """Installiert ein Plugin aus einem Pfad oder eines der Beispiel-Plugins."""
    src = Path(source).resolve()

    # Beispiel-Plugins aus desktop-plugins/examples/ referenzieren
    if not src.exists():
        alt = USER_PLUGINS_DIR / "examples" / source
        if alt.exists():
            src = alt
        else:
            print(f"❌ Plugin nicht gefunden: {source}", file=sys.stderr)
            return False

    if not src.is_dir():
        print(f"❌ Kein Verzeichnis: {src}", file=sys.stderr)
        return False

    # Plugin-Namen aus plugin.yaml lesen
    plugin = Plugin(src)
    if not plugin.name or plugin.name == src.name:
        plugin.name = src.name

    dest = USER_PLUGINS_DIR / plugin.name
    if dest.exists():
        answer = input(f"⚠️ Plugin '{plugin.name}' existiert bereits. Überschreiben? [j/N] ")
        if answer.lower() not in ("j", "ja", "y", "yes"):
            print("⏭️  Überspringen.")
            return False
        shutil.rmtree(dest)

    shutil.copytree(src, dest)
    print(f"✅ Plugin '{plugin.name}' (v{plugin.version}) installiert nach:")
    print(f"   {dest}")
    return True


# ── Check (Health) ───────────────────────────────────────────────────────────


def check_plugin(name: str, verbose: bool = True) -> Tuple[bool, str]:
    """Prüft ein Plugin auf grundlegende Gesundheit."""
    # Plugin finden
    for plugin in scan_plugins():
        if plugin.name == name:
            return _check_single(plugin, verbose)
    return False, f"❌ Plugin '{name}' nicht gefunden."


def _check_single(plugin: Plugin, verbose: bool = True) -> Tuple[bool, str]:
    """Führt Prüfungen für ein einzelnes Plugin durch."""
    issues: List[str] = []
    warnings: List[str] = []

    # 1. Verzeichnis und plugin.yaml
    if not (plugin.path / "plugin.yaml").exists():
        issues.append("Fehlende plugin.yaml")

    # 2. __init__.py
    if not plugin.has_init:
        issues.append("Fehlendes __init__.py")
    elif not plugin.has_register:
        warnings.append("__init__.py exportiert keine register(ctx)-Funktion")

    # 3. Manifest-Pflichtfelder
    if not plugin.name:
        issues.append("Plugin-Name fehlt in plugin.yaml")
    if not plugin.version or plugin.version == "0.0.0":
        warnings.append("Keine Version in plugin.yaml")
    if not plugin.description:
        warnings.append("Keine Beschreibung in plugin.yaml")

    # 4. Config (enabled/disabled)
    plugin_config = get_plugin_config()
    enabled = is_plugin_enabled(plugin.name, plugin_config)

    if not enabled:
        warnings.append(f"Plugin ist deaktiviert (plugin.{plugin.name}.enabled: false)")

    # 5. Hooks deklariert
    valid_hooks = {"onReady", "onMessage", "onCommand", "onCronRun", "onToolCall"}
    for hook in plugin.hooks:
        if hook not in valid_hooks:
            warnings.append(f"Unbekannter Hook-Typ: '{hook}'")

    if verbose:
        status_color = "✅" if not issues else "❌"
        print(f"\n{'=' * 50}")
        print(f"  {status_color}  {plugin.name}  v{plugin.version}")
        print(f"{'=' * 50}")
        print(f"  Beschreibung:   {plugin.description or '(keine)'}")
        print(f"  Autor:          {plugin.author}")
        print(f"  Typ:            {plugin.kind or '(kein Typ)'}")
        print(f"  Pfad:           {plugin.path}")
        print(f"  Typ:            {'User' if plugin.is_user_plugin else 'Built-in'}")
        print(f"  Status:         {'✅ Enabled' if enabled else '❌ Disabled'}")
        print(f"  Hooks:          {', '.join(plugin.hooks) if plugin.hooks else '(keine)'}")
        if issues:
            print(f"\n  ❌ Probleme:")
            for issue in issues:
                print(f"     • {issue}")
        if warnings:
            print(f"\n  ⚠️  Warnungen:")
            for warn in warnings:
                print(f"     • {warn}")
        print()

    return len(issues) == 0, "; ".join(issues)


# ── Listen-Formatter ─────────────────────────────────────────────────────────


def list_plugins() -> None:
    """Listet alle gefundenen Plugins auf."""
    plugins = scan_plugins()
    plugin_config = get_plugin_config()

    builtins = [p for p in plugins if not p.is_user_plugin]
    user = [p for p in plugins if p.is_user_plugin]

    print(f"{'═' * 60}")
    print(f"  OpenAmer Plugin-Manager")
    print(f"{'═' * 60}\n")

    # Built-ins
    print(f"  Built-in Plugins ({PLUGINS_DIR.relative_to(REPO_DIR)}/):")
    print(f"  {'─' * 56}")
    if builtins:
        for p in sorted(builtins, key=lambda x: x.name):
            enabled = is_plugin_enabled(p.name, plugin_config)
            icon = "✓" if enabled else "✗"
            color = "✅" if enabled else "⚠️"
            desc = p.description[:50] + "..." if len(p.description) > 50 else p.description
            print(f"    {color} {p.name:<28} v{p.version:<7} {desc}")
    else:
        print("    (keine)")

    # User-Plugins
    print(f"\n  User Plugins ({USER_PLUGINS_DIR.relative_to(REPO_DIR)}/):")
    print(f"  {'─' * 56}")
    if user:
        for p in sorted(user, key=lambda x: x.name):
            enabled = is_plugin_enabled(p.name, plugin_config)
            color = "✅" if enabled else "⚠️"
            desc = p.description[:50] + "..." if len(p.description) > 50 else p.description
            print(f"    {color} {p.name:<28} v{p.version:<7} {desc}")
    else:
        print("    (keine)")

    # Zusammenfassung
    total = len(plugins)
    enabled_count = sum(1 for p in plugins if is_plugin_enabled(p.name, plugin_config))
    print(f"\n{'═' * 60}")
    print(f"  {total} Plugins insgesamt | {enabled_count} enabled | {total - enabled_count} disabled")
    print(f"{'═' * 60}")


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenAmer Plugin-Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s list                    # Alle Plugins anzeigen
  %(prog)s install hello-world     # Beispiel-Plugin installieren
  %(prog)s install /pfad/zum/plugin  # Plugin aus Pfad installieren
  %(prog)s enable hello-world      # Plugin aktivieren
  %(prog)s disable hello-world     # Plugin deaktivieren
  %(prog)s check hello-world       # Plugin auf Fehler prüfen
  %(prog)s check --all             # Alle Plugins prüfen
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Kommandos")

    # list
    subparsers.add_parser("list", help="Alle Plugins auflisten")

    # install
    install_parser = subparsers.add_parser("install", help="Plugin installieren")
    install_parser.add_argument("source", help="Plugin-Verzeichnis oder Beispiel-Plugin-Name")

    # enable
    enable_parser = subparsers.add_parser("enable", help="Plugin aktivieren")
    enable_parser.add_argument("name", help="Plugin-Name")

    # disable
    disable_parser = subparsers.add_parser("disable", help="Plugin deaktivieren")
    disable_parser.add_argument("name", help="Plugin-Name")

    # check
    check_parser = subparsers.add_parser("check", help="Plugin-Health-Check")
    check_parser.add_argument("name", nargs="?", help="Plugin-Name (optional)")
    check_parser.add_argument("--all", action="store_true", help="Alle Plugins prüfen")

    args = parser.parse_args()

    if args.command == "list":
        list_plugins()

    elif args.command == "install":
        success = install_plugin(args.source)
        sys.exit(0 if success else 1)

    elif args.command == "enable":
        if not any(p.name == args.name for p in scan_plugins()):
            print(f"❌ Plugin '{args.name}' nicht gefunden.", file=sys.stderr)
            sys.exit(1)
        if set_plugin_enabled(args.name, True):
            print(f"✅ Plugin '{args.name}' aktiviert.")
            print(f"   Config: openamer config set plugin.{args.name}.enabled true")
        else:
            sys.exit(1)

    elif args.command == "disable":
        if not any(p.name == args.name for p in scan_plugins()):
            print(f"❌ Plugin '{args.name}' nicht gefunden.", file=sys.stderr)
            sys.exit(1)
        if set_plugin_enabled(args.name, False):
            print(f"⚠️  Plugin '{args.name}' deaktiviert.")
            print(f"   Config: openamer config set plugin.{args.name}.enabled false")
        else:
            sys.exit(1)

    elif args.command == "check":
        if args.all:
            plugins = scan_plugins()
            if not plugins:
                print("Keine Plugins gefunden.")
                sys.exit(0)
            all_ok = True
            for p in plugins:
                ok, _ = _check_single(p, verbose=True)
                if not ok:
                    all_ok = False
            sys.exit(0 if all_ok else 1)

        elif args.name:
            ok, _ = check_plugin(args.name)
            sys.exit(0 if ok else 1)

        else:
            print("❌ Bitte Plugin-Name oder --all angeben.", file=sys.stderr)
            print("   Usage: plugin-manager.py check <name>  oder  plugin-manager.py check --all")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()