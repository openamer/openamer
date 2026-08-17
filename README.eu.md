# OpenAmer Agent

**Automelora AI agentea — esperientziatik ikasi, trebetasunak sortu, zure gustukoak gogoratu eta zuretzat lan egin edozein lekutan.***

Erabili nahi izan zuen edozein modelo — OpenRouter, OpenAI, DeepSeek eta besteak. Aldatu `openamer model` agerera — koditzeen aldaketarik gabe.

## Ezaugarriak

- **Terminal interfaze benizpea — TUI osoa autosagardoa, historiak eta tresnen irteeraren streaming-a barnez**
- **Zurea bezalako lekukoetan — Telegram, Discord, Slack, WhatsApp eta askoz gehiago, ate bakargo batetik**
- **Denborarekin ikasten du —memoria, auto-hobekuntza gaitasunak, saioak arteko gogoratzea—**
- **Suentu eta paralelizatzen du — sub-agenteak sortzen ditu lan paraleloak egiteko**
- **Automatizazio programatuak — cron integratua eguneroko txostenak, kopiak eta auditoretzak egiteko**
- **Edin izarrenean funtzionatzen du — lokal own, Docker, SSH, hodeian, serverless**

## Instalazio Azkarra

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Hasi behin

```bash
openamer              # Hasi txateatzea
openamer setup        # Konfiguratu zure API gakoak eta hornitzailea
openamer model        # Aukeratu zure modela
openamer update       # eguneratu bertsio berrienatzera
```

## Eguneratzen ari da

OpenAmer-ek eguneratzeak automatikoki bilatzen ditu eta ohartarazpen bat erakutsi ditu ongizleko bannerrean. `openamer update` komandoa exekutatu azken bertsioa lortzeko —lehenik lehen zure datuen kopia bat egiten du—.

## Bidali laguntza

Ekarpenak ongin dira — ireki arazoak, bidali pull request-ak edo elkartu komunitatean.

## Lizentzia

Apache License 2.0. Ikusi {LICENSE}.
