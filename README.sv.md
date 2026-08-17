# OpenAmer Agent

**Den självförbättrande AI-agenten — lär dig av erfarenhet, skapa färdigheter, kom ihåg dina preferenser och arbeta för dig överallt.**

Använd vilken modell du vill — OpenRouter, OpenAI, DeepSeek och fler. Växla med `openamer model` — inga kodändringar krävs.

## Funktioner

- **Riktigt terminalgränssnitt — fullständig TUI med autokomplettering, historik och strömmande verktygsutdata**
- **Finns där du är — Telegram, Discord, Slack, WhatsApp och mer från en och samma gateway**
- **Lär sig över tid — minne, självförbättrande färdigheter, återkallelse mellan sessioner**
- **Delegerar & parallelliserar — skapar underagenter för parallellt arbete**
- **Schemalagda automatiseringar — inbyggd cron för dagliga rapporter, säkerhetskopior och granskningar**
- **Körs var som helst — lokalt, Docker, SSH, molnet, serverless**

## Snabbinstallation

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Kom igång

```bash
openamer              # Börja chatta
openamer setup        # Konfigurera dina API-nycklar och leverantör
openamer model        # Välj din modell
openamer update       # Uppdatera till den senaste versionen
```

## Uppdaterar

OpenAmer letar automatiskt efter uppdateringar och visar en varning i välkomstbanderollen. Kör `openamer update` för att hämta den senaste versionen — den gör en säkerhetskopia av dina data först.

## Bidra

Bidrag är välkomna — öppna issues, skicka in pull requests eller gå med i communityn.

## Licens

Apache License 2.0. Se {LICENSE}.
