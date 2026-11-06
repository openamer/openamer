#!/usr/bin/env python3
"""Fill the overlay strings for a locale using a plural-word table.

The translation model refuses to translate a ternary such as

    ${count} ${count === 1 ? 'message' : 'messages'}

because it treats the whole interpolation as code. The words inside the
ternary ARE user-facing text, so they have to be translated — but they must
not be translated by a model that would rewrite the surrounding code.

So we do it with a table instead: for each locale we list the singular and
plural form of the words that appear inside ternaries, and the script
substitutes them into the English source. The code structure is therefore
untouched by construction — only the literal words change.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OVERLAYS = REPO / "scripts" / "i18n_overlays"

# The words that appear inside ternaries in en.ts, with their translation per
# locale. Only the words, not the code.
#
#   en.ts:  ${count === 1 ? 'message' : 'messages'}
#   fr:     ${count === 1 ? 'message' : 'messages'}
#   de:     ${count === 1 ? 'Nachricht' : 'Nachrichten'}
PLURAL_WORDS: dict[str, dict[str, tuple[str, str]]] = {
    "fr": {
        "message": ("message", "messages"),
        "agent": ("agent", "agents"),
        "profile": ("profil", "profils"),
        "skill": ("compétence", "compétences"),
        "job": ("tâche", "tâches"),
        "item": ("élément", "éléments"),
        "session": ("session", "sessions"),
        "notification": ("notification", "notifications"),
        "change": ("modification", "modifications"),
        "service": ("service", "services"),
        "tool": ("outil", "outils"),
        "image": ("image", "images"),
        "node": ("nœud", "nœuds"),
        "result": ("résultat", "résultats"),
        "finding": ("détection", "détections"),
        "pet": ("animal", "animaux"),
        "action": ("action", "actions"),
        "zone": ("zone", "zones"),
        "model": ("modèle", "modèles"),
        "prompt": ("invite", "invites"),
        "resource": ("ressource", "ressources"),
        "option": ("option", "options"),
        "task": ("tâche", "tâches"),
        "file": ("fichier", "fichiers"),
        "folder": ("dossier", "dossiers"),
        "plugin": ("extension", "extensions"),
        "voice": ("voix", "voix"),
        "hour": ("heure", "heures"),
        "minute": ("minute", "minutes"),
        "second": ("seconde", "secondes"),
        "day": ("jour", "jours"),
        "week": ("semaine", "semaines"),
        "month": ("mois", "mois"),
        "year": ("an", "ans"),
        "entry": ("entrée", "entrées"),
        "update": ("mise à jour", "mises à jour"),
        "warning": ("avertissement", "avertissements"),
        "error": ("erreur", "erreurs"),
        "command": ("commande", "commandes"),
        "step": ("étape", "étapes"),
        "token": ("jeton", "jetons"),
        "credit": ("crédit", "crédits"),
        "reply": ("réponse", "réponses"),
        "provider": ("fournisseur", "fournisseurs"),
        "branch": ("branche", "branches"),
        "commit": ("commit", "commits"),
        "release": ("version", "versions"),
        "cron": ("tâche planifiée", "tâches planifiées"),
        "webhook": ("webhook", "webhooks"),
        "artifact": ("artefact", "artefauts"),
        "memory": ("mémoire", "mémoires"),
        "database": ("base de données", "bases de données"),
        "workspace": ("espace de travail", "espaces de travail"),
        "context": ("contexte", "contextes"),
    },
    "de": {
        "message": ("Nachricht", "Nachrichten"),
        "agent": ("Agent", "Agenten"),
        "profile": ("Profil", "Profile"),
        "skill": ("Fähigkeit", "Fähigkeiten"),
        "job": ("Aufgabe", "Aufgaben"),
        "item": ("Element", "Elemente"),
        "session": ("Sitzung", "Sitzungen"),
        "notification": ("Benachrichtigung", "Benachrichtigungen"),
        "change": ("Änderung", "Änderungen"),
        "service": ("Dienst", "Dienste"),
        "tool": ("Werkzeug", "Werkzeuge"),
        "image": ("Bild", "Bilder"),
        "node": ("Knoten", "Knoten"),
        "result": ("Ergebnis", "Ergebnisse"),
        "finding": ("Fund", "Funde"),
        "pet": ("Haustier", "Haustiere"),
        "action": ("Aktion", "Aktionen"),
        "zone": ("Zone", "Zonen"),
        "model": ("Modell", "Modelle"),
        "prompt": ("Aufforderung", "Aufforderungen"),
        "resource": ("Ressource", "Ressourcen"),
        "option": ("Option", "Optionen"),
        "task": ("Aufgabe", "Aufgaben"),
        "file": ("Datei", "Dateien"),
        "folder": ("Ordner", "Ordner"),
        "plugin": ("Plugin", "Plugins"),
        "voice": ("Stimme", "Stimmen"),
        "hour": ("Stunde", "Stunden"),
        "minute": ("Minute", "Minuten"),
        "second": ("Sekunde", "Sekunden"),
        "day": ("Tag", "Tage"),
        "week": ("Woche", "Wochen"),
        "month": ("Monat", "Monate"),
        "year": ("Jahr", "Jahre"),
        "entry": ("Eintrag", "Einträge"),
        "update": ("Aktualisierung", "Aktualisierungen"),
        "warning": ("Warnung", "Warnungen"),
        "error": ("Fehler", "Fehler"),
        "command": ("Befehl", "Befehle"),
        "step": ("Schritt", "Schritte"),
        "token": ("Token", "Token"),
        "credit": ("Guthaben", "Guthaben"),
        "reply": ("Antwort", "Antworten"),
        "provider": ("Anbieter", "Anbieter"),
        "branch": ("Zweig", "Zweige"),
        "commit": ("Commit", "Commits"),
        "release": ("Version", "Versionen"),
        "cron": ("Cronjob", "Cronjobs"),
        "webhook": ("Webhook", "Webhooks"),
        "artifact": ("Artefakt", "Artefakte"),
        "memory": ("Speicher", "Speicher"),
        "database": ("Datenbank", "Datenbanken"),
        "workspace": ("Arbeitsbereich", "Arbeitsbereiche"),
        "context": ("Kontext", "Kontexte"),
    },
}

# The generated table (scripts/i18n_plural_words.json) wins over the
# hand-written one above: it covers every locale and every word.
GENERATED = REPO / "scripts" / "i18n_plural_words.json"
if GENERATED.exists():
    try:
        _gen = json.loads(GENERATED.read_text(encoding="utf-8"))
        for _loc, _pairs in _gen.items():
            _merged = dict(PLURAL_WORDS.get(_loc, {}))
            for _w, _pair in _pairs.items():
                if isinstance(_pair, list) and len(_pair) == 2:
                    _merged[_w] = (_pair[0], _pair[1])
            PLURAL_WORDS[_loc] = _merged
    except (json.JSONDecodeError, OSError):
        pass

# Strings that need more than a word swap: the whole text outside the
# interpolation is translated by the model, only the ternary is handled here.
_SPECIAL_SEED: dict[str, dict[str, str]] = {
    "fr": {
        "settings.about.version": "Version ${value}",
        "agents.durationSeconds": "${seconds} s",
        "agents.durationMinutes": "${minutes} min ${seconds} s",
        "commandCenter.actions": "${count} actions",
        "composer.images": "Images…",
        "composer.url": "URL…",
        "shell.statusbar.desktopVersion": "OpenAmer Desktop v${version}",
        "shell.statusbar.clientLabel": "client v${version}",
        "shell.statusbar.providerModelTitle": "${provider} · ${model}",
        "zones.zoneTag": "zone ${index}",
        "zones.zoneCount": "${count} zones",
        "assistant.tool.titleTemplates.actionCommand": "${action} ${command}",
        "assistant.tool.titleTemplates.actionQuoted": "${action} « ${value} »",
        "assistant.tool.titleTemplates.actionTarget": "${action} ${target}",
        "assistant.tool.titleTemplates.prefixedDone": "${prefix} ${action}",
    },
    "de": {
        "settings.about.version": "Version ${value}",
        "agents.durationSeconds": "${seconds} s",
        "agents.durationMinutes": "${minutes} min. ${seconds} s",
        "commandCenter.actions": "${count} Aktionen",
        "composer.images": "Bilder…",
        "composer.url": "URL…",
        "shell.statusbar.desktopVersion": "OpenAmer Desktop v${version}",
        "shell.statusbar.clientLabel": "Client v${version}",
        "shell.statusbar.providerModelTitle": "${provider} · ${model}",
        "zones.zoneTag": "Zone ${index}",
        "zones.zoneCount": "${count} Zonen",
        "assistant.tool.titleTemplates.actionCommand": "${action} ${command}",
        "assistant.tool.titleTemplates.actionQuoted": "${action} „${value}“",
        "assistant.tool.titleTemplates.actionTarget": "${action} ${target}",
        "assistant.tool.titleTemplates.prefixedDone": "${prefix} ${action}",
    },
    "es": {
        "settings.about.version": "Versión ${value}",
        "agents.durationSeconds": "${seconds} s",
        "agents.durationMinutes": "${minutes} min ${seconds} s",
        "commandCenter.actions": "${count} acciones",
        "composer.images": "Imágenes…",
        "composer.url": "URL…",
        "shell.statusbar.desktopVersion": "OpenAmer Desktop v${version}",
        "shell.statusbar.clientLabel": "cliente v${version}",
        "shell.statusbar.providerModelTitle": "${provider} · ${model}",
        "zones.zoneTag": "zona ${index}",
        "zones.zoneCount": "${count} zonas",
        "assistant.tool.titleTemplates.actionCommand": "${action} ${command}",
        "assistant.tool.titleTemplates.actionQuoted": "${action} «${value}»",
        "assistant.tool.titleTemplates.actionTarget": "${action} ${target}",
        "assistant.tool.titleTemplates.prefixedDone": "${prefix} ${action}",
    },
    "it": {
        "settings.about.version": "Versione ${value}",
        "agents.durationSeconds": "${seconds} s",
        "agents.durationMinutes": "${minutes} min ${seconds} s",
        "commandCenter.actions": "${count} azioni",
        "composer.images": "Immagini…",
        "composer.url": "URL…",
        "shell.statusbar.desktopVersion": "OpenAmer Desktop v${version}",
        "shell.statusbar.clientLabel": "client v${version}",
        "shell.statusbar.providerModelTitle": "${provider} · ${model}",
        "zones.zoneTag": "zona ${index}",
        "zones.zoneCount": "${count} zone",
        "assistant.tool.titleTemplates.actionCommand": "${action} ${command}",
        "assistant.tool.titleTemplates.actionQuoted": "${action} «${value}»",
        "assistant.tool.titleTemplates.actionTarget": "${action} ${target}",
        "assistant.tool.titleTemplates.prefixedDone": "${prefix} ${action}",
    },
    "pt": {
        "settings.about.version": "Versão ${value}",
        "agents.durationSeconds": "${seconds} s",
        "agents.durationMinutes": "${minutes} min ${seconds} s",
        "commandCenter.actions": "${count} ações",
        "composer.images": "Imagens…",
        "composer.url": "URL…",
        "shell.statusbar.desktopVersion": "OpenAmer Desktop v${version}",
        "shell.statusbar.clientLabel": "cliente v${version}",
        "shell.statusbar.providerModelTitle": "${provider} · ${model}",
        "zones.zoneTag": "zona ${index}",
        "zones.zoneCount": "${count} zonas",
        "assistant.tool.titleTemplates.actionCommand": "${action} ${command}",
        "assistant.tool.titleTemplates.actionQuoted": "${action} «${value}»",
        "assistant.tool.titleTemplates.actionTarget": "${action} ${target}",
        "assistant.tool.titleTemplates.prefixedDone": "${prefix} ${action}",
    },
}

SPECIAL: dict[str, dict[str, str]] = {}
SPECIAL.update(_SPECIAL_SEED)

# The generated table (scripts/i18n_special_words.json) fills in every
# locale the hand-written seed does not cover.
_GENERATED_SPECIAL = REPO / "scripts" / "i18n_special_words.json"
if _GENERATED_SPECIAL.exists():
    try:
        _gen = json.loads(_GENERATED_SPECIAL.read_text(encoding="utf-8"))
        for _loc, _pairs in _gen.items():
            _merged = dict(SPECIAL.get(_loc, {}))
            _merged.update(_pairs)
            SPECIAL[_loc] = _merged
    except (json.JSONDecodeError, OSError):
        pass

# The hand-written seed above covers the five languages that were done
# first. For every other locale the model translates the special strings —
# they contain no ternary, so the model handles them fine.
SPECIAL_KEYS = [
    "settings.about.version",
    "agents.durationSeconds",
    "agents.durationMinutes",
    "commandCenter.actions",
    "composer.images",
    "composer.url",
    "shell.statusbar.desktopVersion",
    "shell.statusbar.clientLabel",
    "shell.statusbar.providerModelTitle",
    "zones.zoneTag",
    "zones.zoneCount",
    "assistant.tool.titleTemplates.actionCommand",
    "assistant.tool.titleTemplates.actionQuoted",
    "assistant.tool.titleTemplates.actionTarget",
    "assistant.tool.titleTemplates.prefixedDone",
]

# The pattern of a ternary inside an interpolation:  ${x === 1 ? 'a' : 'b'}
TERNARY = re.compile(r"\? '([^']*)' : '([^']*)'")


def apply_words(text: str, words: dict[str, tuple[str, str]]) -> str:
    """Replace the literal words inside every ternary with their translation."""
    def repl(m):
        singular, plural = m.group(1), m.group(2)
        if singular in words:
            s, p = words[singular]
            return f"? '{s}' : '{p}'"
        if plural in words:
            s, p = words[plural]
            return f"? '{s}' : '{p}'"
        return m.group(0)
    return TERNARY.sub(repl, text)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_build_overlays.py <locale> [locale ...]")
        return 1
    for locale in sys.argv[1:]:
        words = PLURAL_WORDS.get(locale, {})
        special = SPECIAL.get(locale, {})
        if not words and not special:
            print(f"{locale}: no overlay data")
            continue
        path = OVERLAYS / f"{locale}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(special, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
        print(f"{locale}: wrote {path} ({len(special)} special strings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
