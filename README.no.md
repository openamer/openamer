# OpenAmer Agent

**Den selvforbedrende AI-agenten — lær av erfaring, skap ferdigheter, husk preferansene dine, og jobb for deg overalt.**

Bruk hvilken som helst modell du vil — OpenRouter, OpenAI, DeepSeek og flere. Bytt med `openamer model` — ingen kodeendringer nødvendig.

## Funksjoner

- **Ekte terminalgrensesnitt — full TUI med autoutfylling, historikk og strømming av verktøyutdata**
- **Finnes der du er — Telegram, Discord, Slack, WhatsApp og mer fra én gateway**
- **Lærer over tid — minne, selvforbedrende ferdigheter, gjenkalling på tvers av sesjoner**
- **Delegerer og parallelliserer — oppretter underagenter for parallelt arbeid**
- **Planlagte automatiseringer — innebygd cron for daglige rapporter, sikkerhetskopier og revisjoner**
- **Kjører overalt — lokalt, Docker, SSH, skyen, serverless**

## Hurtiginstallasjon

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Kom i gang

```bash
openamer              # Start chatting
openamer setup        # Konfigurer API-nøkler og leverandør
openamer model        # Velg din modell
openamer update       # Oppdater til nyeste versjon
```

## Oppdatering

OpenAmer sjekker automatisk etter oppdateringer og viser en advarsel i velkomstbanneret. Kjør `openamer update` for å få den nyeste versjonen — den tar sikkerhetskopi av dataene dine først.

## Bidra

Bidrag er velkomne — opprett åpne saker (issues), send inn pull-forespørsler, eller bli med i fellesskapet.

## Lisens

Apache License 2.0. Se {LICENSE}.
