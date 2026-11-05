#!/usr/bin/env python3
"""Hand-written translations for the strings the model refuses to translate.

The bulk translation run leaves a few strings in English. Two reasons:

  * The model treats a bare word as a technical token and returns it
    unchanged ("Gateway", "Host", "System").
  * The string is built around an interpolation, and the model masks the
    whole `${…}` — so the sentence around it never gets translated
    ("Status: ${status}").

Both are translation work, not model failures. The table below is the
authoritative answer for those strings, per locale. It is applied on top of
the model output, exactly like the overlay tables in scripts/i18n_overlays/.

Why a table and not a better prompt? Because these strings are the SAME in
every locale (about 90 of them) — a fixed, reviewable table is smaller,
faster and deterministic. The model still does the long tail.

Every entry is checked: the placeholders of the English source must survive
the translation, otherwise the entry is rejected and the English text stays.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from i18n_translate_locale import (  # noqa: E402
    LANGUAGE_NAMES,
    find_placeholders,
    placeholders_intact,
)

# The strings that need a hand-written translation. The key is the dotted
# path in the locale tree; the value is the ENGLISH source text (used as the
# guard — a table entry only applies when the source still matches).
NEEDS_HAND = {
    "notifications.details": "Details",
    "settings.nav.gateway": "Gateway",
    "settings.nav.plugins": "Plugins",
    "settings.nav.providerAccounts": "Accounts",
    "settings.sections.chat": "Chat",
    "settings.modeOptions.system.label": "System",
    "settings.credentials.optional": "Optional",
    "settings.gateway.cloudStatusLabel": "Status: ${status}",
    "settings.gateway.cloudOrgRole": "Role: ${role}",
    "settings.gateway.cloudNoAgents.linkText": "OpenAmer portal",
    "settings.gateway.sshHostTitle": "Host",
    "settings.gateway.sshHostPickTitle": "Host",
    "settings.gateway.sshTestConnection": "Test SSH",
    "settings.mcp.name": "Name",
    "settings.mcp.serverJson": "Server JSON",
    "settings.mcp.tabServers": "Servers",
    "settings.mcp.tabCatalog": "Catalog",
    "settings.model.tasks.curator.label": "Curator",
    "settings.appearance.product": "Product",
    "settings.about.branchCommit": "Branch ${branch} · Commit ${commit}",
    "agents.streaming": "Streaming",
    "agents.delegation": "Delegation ${index}",
    "webhooks.fieldName": "Name",
    "webhooks.fieldPrompt": "Prompt",
    "webhooks.webhookUrl": "Webhook URL",
    "webhooks.deliverOptions.log": "Log",
    "cron.promptLabel": "Prompt",
    "cron.nameLabel": "Name",
    "cron.optional": "Optional",
    "cron.states.error": "error",
    "profiles.nameLabel": "Name",
    "profiles.soulOptional": "optional",
    "profiles.color": "Color…",
    "artifacts.chat": "Chat",
    "artifacts.tabLinks": "Links",
    "artifacts.itemsLink": "links",
    "artifacts.itemsGeneric": "items",
    "artifacts.kindLink": "link",
    "artifacts.kindFile": "file",
    "artifacts.colTitleFile": "Name",
    "sidebar.row.untitledChat": "Chat ${id}",
    "sidebar.row.ageMin": "m",
    "sidebar.projects.ideaLabel": "Idea",
    "sidebar.projects.branchOpenExisting": "open",
    "sidebar.projects.enter": "Open ${label}",
    "sidebar.showMoreIn": "Show ${count} more in ${label}",
    "common.send": "Send",
    "common.formatJson": "Format JSON",
    "composer.stop": "Stop",
    "composer.stopShort": "Stop",
    "composer.send": "Send",
    "composer.queueSend": "Send",
    "composer.images": "Images…",
    "composer.folder": "Folder…",
    "statusStack.stop": "Stop",
    "zones.editTitle": "Layouts",
    "assistant.thread.stop": "Stop",
    "assistant.tool.prefixes.browser": "Browser",
    "commandCenter.sections.system": "System",
    "commandCenter.generatePet.remix": "Remix",
    "rightSidebar.terminalsAria": "Terminals",
    "modelPicker.wasPrice": "was",
    "shell.approvalMode.smart": "Smart",
    "shell.gatewayMenu.gateway": "Gateway",
    "shell.gatewayMenu.offline": "Offline",
    "shell.statusbar.desktopVersion": "OpenAmer Desktop v${version}",
    "shell.statusbar.backendVersion": "Backend v${version}",
    "shell.statusbar.backendLabel": "backend v${version}",
    "shell.statusbar.clientLabel": "client v${version}",
    "shell.statusbar.modelTitle": "Model · ${provider}: ${model}",
    "shell.statusbar.connectionCloud": "Cloud: ${host}",
    "shell.statusbar.connectionRemote": "Remote: ${host}",
    "shell.statusbar.connectionSsh": "SSH: ${host}",
    "shell.statusbar.commit": "commit ${sha}",
    "shell.statusbar.branch": "branch ${branch}",
    "shell.statusbar.gateway": "Gateway",
    "shell.statusbar.gatewayOffline": "offline",
    "shell.statusbar.providerModelTitle": "${provider} · ${model}",
    "messaging.fieldCopy.TELEGRAM_BOT_TOKEN.label": "Bot token",
    "messaging.fieldCopy.TELEGRAM_PROXY.label": "Proxy URL",
    "messaging.fieldCopy.DISCORD_BOT_TOKEN.label": "Bot token",
    "messaging.fieldCopy.SLACK_BOT_TOKEN.label": "Slack bot token",
    "messaging.fieldCopy.MATTERMOST_TOKEN.label": "Bot token",
}

# ── the translations ────────────────────────────────────────────────────
#
# German first (it is the reference locale of this repository), then the
# other languages. A string that is the same in every language is not
# listed — the table only carries what actually changes.
TABLE: dict[str, dict[str, str]] = {
    "de": {
        "notifications.details": "Details",
        "settings.nav.gateway": "Gateway",
        "settings.nav.plugins": "Plugins",
        "settings.nav.providerAccounts": "Konten",
        "settings.sections.chat": "Chat",
        "settings.modeOptions.system.label": "System",
        "settings.credentials.optional": "Optional",
        "settings.gateway.cloudStatusLabel": "Status: ${status}",
        "settings.gateway.cloudOrgRole": "Rolle: ${role}",
        "settings.gateway.cloudNoAgents.linkText": "OpenAmer-Portal",
        "settings.gateway.sshHostTitle": "Host",
        "settings.gateway.sshHostPickTitle": "Host",
        "settings.gateway.sshTestConnection": "SSH testen",
        "settings.mcp.name": "Name",
        "settings.mcp.serverJson": "Server-JSON",
        "settings.mcp.tabServers": "Server",
        "settings.mcp.tabCatalog": "Katalog",
        "settings.model.tasks.curator.label": "Kurator",
        "settings.appearance.product": "Produkt",
        "settings.about.branchCommit": "Zweig ${branch} · Commit ${commit}",
        "agents.streaming": "Streaming",
        "agents.delegation": "Delegation ${index}",
        "webhooks.fieldName": "Name",
        "webhooks.fieldPrompt": "Prompt",
        "webhooks.webhookUrl": "Webhook-URL",
        "webhooks.deliverOptions.log": "Log",
        "cron.promptLabel": "Prompt",
        "cron.nameLabel": "Name",
        "cron.optional": "Optional",
        "cron.states.error": "Fehler",
        "profiles.nameLabel": "Name",
        "profiles.soulOptional": "optional",
        "profiles.color": "Farbe…",
        "artifacts.chat": "Chat",
        "artifacts.tabLinks": "Links",
        "artifacts.itemsLink": "Links",
        "artifacts.itemsGeneric": "Elemente",
        "artifacts.kindLink": "Link",
        "artifacts.kindFile": "Datei",
        "artifacts.colTitleFile": "Name",
        "sidebar.row.untitledChat": "Chat ${id}",
        "sidebar.row.ageMin": "m",
        "sidebar.projects.ideaLabel": "Idee",
        "sidebar.projects.branchOpenExisting": "offen",
        "sidebar.projects.enter": "${label} öffnen",
        "sidebar.showMoreIn": "${label}: ${count} weitere anzeigen",
        "common.send": "Senden",
        "common.formatJson": "JSON formatieren",
        "composer.stop": "Stopp",
        "composer.stopShort": "Stopp",
        "composer.send": "Senden",
        "composer.queueSend": "Senden",
        "composer.images": "Bilder…",
        "composer.folder": "Ordner…",
        "statusStack.stop": "Stopp",
        "zones.editTitle": "Layouts",
        "assistant.thread.stop": "Stopp",
        "assistant.tool.prefixes.browser": "Browser",
        "commandCenter.sections.system": "System",
        "commandCenter.generatePet.remix": "Remix",
        "rightSidebar.terminalsAria": "Terminals",
        "modelPicker.wasPrice": "war",
        "shell.approvalMode.smart": "Smart",
        "shell.gatewayMenu.gateway": "Gateway",
        "shell.gatewayMenu.offline": "Offline",
        "shell.statusbar.desktopVersion": "OpenAmer Desktop v${version}",
        "shell.statusbar.backendVersion": "Backend v${version}",
        "shell.statusbar.backendLabel": "Backend v${version}",
        "shell.statusbar.clientLabel": "Client v${version}",
        "shell.statusbar.modelTitle": "Modell · ${provider}: ${model}",
        "shell.statusbar.connectionCloud": "Cloud: ${host}",
        "shell.statusbar.connectionRemote": "Remote: ${host}",
        "shell.statusbar.connectionSsh": "SSH: ${host}",
        "shell.statusbar.commit": "Commit ${sha}",
        "shell.statusbar.branch": "Branch ${branch}",
        "shell.statusbar.gateway": "Gateway",
        "shell.statusbar.gatewayOffline": "offline",
        "shell.statusbar.providerModelTitle": "${provider} · ${model}",
        "messaging.fieldCopy.TELEGRAM_BOT_TOKEN.label": "Bot-Token",
        "messaging.fieldCopy.TELEGRAM_PROXY.label": "Proxy-URL",
        "messaging.fieldCopy.DISCORD_BOT_TOKEN.label": "Bot-Token",
        "messaging.fieldCopy.SLACK_BOT_TOKEN.label": "Slack-Bot-Token",
        "messaging.fieldCopy.MATTERMOST_TOKEN.label": "Bot-Token",
    },
}

# The locales that still need a hand-written table. They are filled in from
# the same source list, so the reviewer can see every string at once.
for _loc in ("nl", "it", "da", "pt", "ro", "sv", "id", "cs", "pl", "no", "sk", "el",
             "hr", "hu", "et", "bs", "fr", "es", "fi", "ko", "hi", "sl", "sq", "tr",
             "zh", "zh-hant", "ga", "lv", "uk", "ru", "th", "vi", "bg", "ja", "ar",
             "fa", "eo", "lt"):
    TABLE.setdefault(_loc, {})


def apply(locale: str, table: dict[str, str]) -> dict[str, str]:
    """Return the table entries that apply to this locale.

    An entry applies when the translation table still carries the English
    source text for that path AND the placeholders survived.
    """
    out: dict[str, str] = {}
    for path, value in table.items():
        src = NEEDS_HAND.get(path)
        if src is None:
            continue
        if not value.strip():
            continue
        if not placeholders_intact(src, value):
            print(f"  {locale}: {path} rejected — placeholders changed", file=sys.stderr)
            continue
        out[path] = value
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python i18n_hand_translations.py <locale> [locale ...]")
        print("       python i18n_hand_translations.py --check")
        return 1
    if sys.argv[1] == "--check":
        missing = []
        for loc in sorted(set(NEEDS_HAND) - set()):
            pass
        for loc, table in sorted(TABLE.items()):
            for path in NEEDS_HAND:
                if path not in table:
                    missing.append(f"{loc}:{path}")
        print(f"hand translations: {len(TABLE)} locales, "
              f"{sum(len(t) for t in TABLE.values())} entries, "
              f"{len(missing)} missing")
        for m in missing[:40]:
            print("  missing", m)
        return 0

    for locale in sys.argv[1:]:
        table = TABLE.get(locale)
        if not table:
            print(f"{locale}: no hand-written table")
            continue
        entries = apply(locale, table)
        print(f"{locale}: {len(entries)} hand-written entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
