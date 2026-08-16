# OpenAmer Agent

**L-aġent AI li j-improvi lilu nnifsu — itgħallem mill-esperjenza, oħloq ħiliet, ifakkar il-preferenzi tiegħek, u ħadem għalik f'kull post.**

Uża kwalunkelat mudell li trid — OpenRouter, OpenAI, DeepSeek, u aktar. Ibiddel b’ `openamer model` — mingħer ebda bidla fil-kodu.

## Karatteristiċi

- **Interfaccia terminali reali — TUI sħiħa b'awtokompljamenti, storja, u output tal-għodda b'mod streaming**
- **Għix fejn għalixxixxi — Telegram, Discord, Slack, WhatsApp u aktar minn gateway waħda**
- **Jisapri maż-żmien — memorja, ħiliejiet li jitiġġraw għal rashom, rikkjuri cross-session**
- **Delegaw u parallelizza — iċċreja sub-aġenti għal xogħol parallel**
- **Awtomazzjonijiet skedjati — cron integrat għal rapporti dijurnali, backup, u awdits**
- **Jaġixxi f'kull post — lokalment, Docker, SSH, cloud, serverless**

## Installazzjoni Rapida

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Kif tibda

```bash
openamer              # Ibda chatting
openamer setup        # Isetja l-api keys u l-provider tiegħek
openamer model        # Agħżel il-mudell tiegħek
openamer update       # Aġġorna għall-aktar verżjoni reċenti
```

## Aġġornament

OpenAmer ifittex aġġornamenti awtomatikament u juri twissija fil-banner tal-benvenuti. Eżekuta `openamer update` biex tieħu l-aktar verżjoni reċenti — dan jagħmel backup tad-dejta tiegħek l-ewwel.

## Kif tikkontribi

Il-kontribuzzjonijiet huma mistoqsija — iftah issues, ibgħat pull requests, jew ingħaqad ma'l-komunità.

## Liċenza

Liċenza Apache 2.0. Ara {LICENSE}.
