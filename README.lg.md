# OpenAmer Agent

**Omulala w'okozesa AI ow'okyeesa — weyigire okuva mu byonna by'okukozese, kola obumanyulivu, jjukire ebintu by'oyagala, era akozere wye w'oba oli.**

Kozesa model yonna gy’oyagala — OpenRouter, OpenAI, DeepSeek, n’ezinywe. Weesa n’okukozesa `openamer model` — tewali kkyalo ky’oyandika mu code.

## Ebintu ebikwata ku nsonga

- **Interface y'omu terminal ey'amazima — TUI eyenkulu ey'okukoppola ebigambo (autocomplete), eky’okujjukira ebyakozesswa (history), n'okulaga eby’okunoonya ebiva mu tool mu kaseera akasaze (streaming tool output)**
- **Beera weeri — Telegram, Discord, Slack, WhatsApp n'ebirala bingi okuva mu kkuba ly'omu**
- **Yeyiga okumala obudde — okujjukira, obunnyonyi obweyongeramu, n’okujjukira ebintu ebikolebwa mu mikutu egyi eri egyi**
- **Okuyigiriza n'okukola ebintu omuli—okulutula abasaayisizibwa (subagents) okukola emirimu gy’omuli.**
- **Okukozesa okugenda okola ebintu kyokka (Scheduled automations) — cron eyitiridde mu musaanu okutereka ripooti z'olunaku, okugumya ebintu (backups), n'okunoonyereza (audits)**
- **Kikola wewuufu — ku kompyuta yo, Docker, SSH, cloud, serverless**

## Okutegeka Okutambula

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Okutandika

```bash
openamer              # Tandika okutegeka
openamer setup        # Teekaamu API keys zyo n'omulala ow'okuteekamu (provider)
openamer model        # Londa omulimiro gwo
openamer update       # Yaganyiza ku kye ky’ekitundu ekisembayo
```

## Okuggyamu okuggyamu/Okuggyamu okuggyamu (Updating)

OpenAmer ekola okunoonya ebizibu eby'okuggyako (updates) okugenda okugenda, era eraga okutandikira mu kkubo kw'okukwasibwa (welcome banner). Kolerera `openamer update` okufuna ekinnampula eky'omulembe — kino kiyamba okukuuma ebintu byo (backup) okusooka.

## Okuyamba

Obuyambi bwonna bukuddamu — ffunye ebizibu eby'okukola, teeka pull requests, oba wejume mu kibiina.

## Olupapula lw’okukozesa (License)

Apache License 2.0. Jjula {LICENSE}.
