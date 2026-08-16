# OpenAmer Agent

**Agent ya AI yiyongerera ubushobozi — yige ku bunararibonye, ireme ubuhanga, yibuke ibyo ukunda, kandi ikur**

Koresha model iyo ari yo yose wifuza — OpenRouter, OpenAI, DeepSeek, n'izindi. Hindura ukoresheje `openamer model` — nta mpinduka z'imvugo ya code (code changes) zisabwa.

## Ibice by’ingenze

- **Interface y'izindi zishobora gukoreshwa (terminal) nyayo — TUI yuzuye ifite autocomplete, amateka (history), n'isohoka ry'ibikoresho rishobora kuryama (streaming tool output)**
- **Biba aho na we aba — Telegram, Discord, Slack, WhatsApp n'izindi zinshi binyuze mu mwanzuro umwe**
- **Yiga uko igihe gishize — urwibutso, ubushobozi bwo kwiyoshyura, kwibuka ibyize mu bihe bitandukanye**
- **Yitaba kandi ikanga mu buryo bwinshi — ihitamo abashinzwe imirimo (subagents) kugira ngo bakore imirimo itandukanye icyarimwe.**
- **Automations ziteganyijwe — cron yisanzwe yo kohereza raporo za buri munsi, backup, n'isuzuma (audits)**
- **Ikora aho ari kwose — mu buryo bwa local, Docker, SSH, cloud, cyangwa serverless**

## Gushyiraho vuba

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Gutangira

```bash
openamer              # Tangira kuganira
openamer setup        # Shyiraho imfunguzo zawe za API (API keys) n'uwitangira serivisi (provider)
openamer model        # Hitamo imodoka yawe
openamer update       # Kora update ugeze ku nsanganySura nshya (version) ya nyuma
```

## Kugenzura/Kuvugurura

OpenAmer ikenzura niba hari updates nshya akoherana kandi ikagaragaze itandukaniro mu kimenyetso cy’ikaze (welcome banner). Koresha itangazo rya `openamer update` kugira ngo ubone verisiyo ishya — itangira ikabika amakuru yawe (backup) mbere y’iyo yatangira.

## Kugira uruhare

Uruhimbi rwose rwemerewe — fungura ibibazo (issues), ohereza impande zishya (pull requests), cyangwa winjire mu muryango.

## Icyemezo cyo gukoresha

Apache License 2.0. Reba {LICENSE}.
