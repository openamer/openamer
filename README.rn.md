# OpenAmer Agent

**Agent ya AI yiyongerera ubushobozi — yigire ku vyatumbuye, ireme ubushobozi bushasha, yibuke ivyo ukunda, kandi igukoreye aho rwose.**

Koresha model yose ushaka — OpenRouter, OpenAI, DeepSeek, n'izindi. Hindura ukoresheje `openamer model` — nta mivugururo y'ikode ikenewe.

## Ibintu biranga

- **Interface y'izindi terminal nyakuri — TUI iruzuye irimo autocomplete, history, n'isohoka ry'ibikoresho rishirwa mu buryo bwa streaming**
- **Biba aho uba — Telegram, Discord, Slack, WhatsApp n'izindi zishoboka binyuze mu nzira imwe (gateway)**
- **Yiga uko igihe gishize — urwibuco, ubushobozi bwo kwitegura no kwiyongerera, kwibuka ibyakozwe mu bihe bitandukanye**
- **Yitugamije & ikora mu buryo bwinshi — itura abashinzwe ibikorwa batandukanye kugira ngo bakore mu gishimikire**
- **Imigendane yateguwe — cron yisanzwe ku manyandiko y'umunsi, kwisubira kw'amakuru (backups), no gukengeza (audits)**
- **Ikora aho ari kwose — mu gace k’imbere (local), Docker, SSH, mu cloud, canke serverless**

## Gushira mu bikoresho vuba

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Gutangura

```bash
openamer              # Tangura tuganire
openamer setup        # Shira imifato yawe ya API (API keys) n'uwuguhaye izo services (provider)
openamer model        # Hitamo imodeli yawe
openamer update       # Saba gushira mu nshuro nshasha
```

## Gushimikangura

OpenAmer irageriza kuraba niba hari amahitamo mashya (updates) mu buryo bwayo, kandi ikerekana intagonzi mu kigabizo c'ikaze (welcome banner). Koresha itangazo **openamer update** kugira urone version nshasha — itangura ifata kopi y'amakuru yawe (backup) mbere y'uko itangira.

## Kugifasha

Ufise gushimikira — fungura ibibazo (**open issues**), ohereza imigambi yo guhindura (**pull requests**), canke winjire mu muryango.

## Uruhusha

Apache License 2.0. Reba {LICENSE}.
