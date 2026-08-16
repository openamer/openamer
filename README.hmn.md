# OpenAmer Agent

**Lub AI agent uas txhim kho nws tus kheej — kawm los ntawm kev paub, tsim cov txuj ci, nco koj cov kev nyiam, thiab ua haujlwm rau koj txhua qhov chaw.**

Siv txhua lub model uas koj xav tau — OpenRouter, OpenAI, DeepSeek, thiab ntau ntxiv. Hloov pauv nrog `openamer model` — tsis tas yuav hloov code.

## Cov tswv yim tseem ceeb

- **Interface terminal tiag — TUI txuas lus tag nrho nrog autocomplete, keeb kwv, thiab streaming tool output**
- **Nyob qhov chaw uas koj nyob — Telegram, Discord, Slack, WhatsApp thiab ntau ntxiv los ntawm ib qho gateway xwb**
- **Kawm tau ntev ntev — kev nco, kev txhim kho kev txawj ntse ntawm tus kheej, kev nco tau txhua lub session**
- **Faib haujlwm & ua ib ncig — tsim cov subagents rau kev ua haujlwm sib nrog**
- **Kev ua haujlwm automatic raws li sijhawm — muaj cron nyob hauv kev tsim txhawm rau cov report hnub own, kev backup, thiab kev tshuaj xyuas (audits)**
- **Ua tau txhua qhov — local, Docker, SSH, cloud, serverless**

## Kev Txhim Kho Ceev

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Kev pib kawm

```bash
openamer              # Pib tham
openamer setup        # Kev teeb tsa koj cov API keys & tus provider
openamer model        # Xaiv koj tus model
openamer update       # Hauv qib tshiab tshaj plaws
```

## Hauv kev kho tshiab

OpenAmer tshawb nrhiav kev hloov tshiab (updates) ua kev ntsewg thiab qhia kev ceeb cai hauv daim banner welcome. Siv txoj haujlwm `openamer update` txhawm rau tau txais version tshiab tshaj plaws — nws yuav ua backup koj cov ntaub ntawv ua ntej.

## Kev pab txhawb nqa

Kev pab yog txais tos — qhib cov teeb meem (issues), xa pull requests, lossis tuaj koom nrog pawg zej zog.

## Kev tso cai

Apache License 2.0. Saib {LICENSE}.
