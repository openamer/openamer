# OpenAmer Agent

**AI agent inozvigadzirisa — dzidza kubva mukuvimbiso, sika hunyanzvi, rangarira zvounoda, uye shanda kwauri kwose.**

Shandisa chero model yaunoda — OpenRouter, OpenAI, DeepSeek, uye dzimwe dzacho. Chinja uchishandisa `openamer model` — hapana kushandura kwecode.

## Zviratidzo

- **Interface ye terminal chaiyo — TUI yakazara ine autocomplete, history, uye streaming ye output yezvishandiso (tools)**
- **Inogara kwaunogara — Telegram, Discord, Slack, WhatsApp nezvimwe kubva pagedhi rimwe chete**
- **Inodzidza zvishoma nezvishoma — memory, hunyanzvi hunozvigadzirisa, uye kuyeuka zvakaitika kune dzimwe session**
- **Inodelaidza uye kuita mabasa akawanda panguva imwe chete — kugadzira subagents kuti mabasa aitwe zvakabatana**
- **Zvirongwa zvinozvishandisa zvakarongeka — cron yakavakirwa mukati yezvireport zvezuva nezuva, kubhaka data (backups), uye kuongorora (audits)**
- **Inoshanda kwese-kwese — local, Docker, SSH, cloud, serverless**

## Kuisisa Kwakukurumidza

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Kutanga

```bash
openamer              # Tanga kutaura
openamer setup        # Gadzirira mau keys eAPI yako uye provider
openamer model        # Sarudza model yako
openamer update       # Kumbodisa kuverishoni yema-update matsva
```

## Kuvhura-vhura

OpenAmer inotsvaga updates zvishiri zvizvishiri uye inoratidza yambiro mu welcome banner. Run **openamer update** kuti uwane version itsva — inotanga nekuchengetedza (back up) data rako.

## Kubatsira

Rubatsiro rwunogamuchirwa — vhura nyaya (issues), tumira zvikumbiro zvekugadzirisa (pull requests), kana kuti joina nharaunda yedu.

## Chinyorwa chemvumo

Apache License 2.0. Tarisa {LICENSE}.
