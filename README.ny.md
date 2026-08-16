# OpenAmer Agent

**AI agent yomwe imadzilongerera — phunzirani kuchokera ku zochitika, pangani luso, kukumbukirani zofuna zanu, ndipo igwire ntchito kwa inu kulikonse.**

Gwiritsani ntchito model iliyonse yomwe mukufuna — OpenRouter, OpenAI, DeepSeek, ndi zina zake. Sinthani pogwiritsa ntchito `openamer model` — popanda kusintha code.

## Zimene zilimo

- **Interface ya terminal yeniyeni — TUI yonse imene ili ndi autocomplete, history, komanso streaming ya zotsatira za tool**
- **Zimakhala pomwe inu muli — Telegram, Discord, Slack, WhatsApp ndi zina zochuluka kuchokera ku gateway imodzi**
- **Zimapita patsogolo m’kupita kwa nthawi — kukumbukira, luso lodzikonza, komanso kukumbukira zinthu kuchokera ku zokambirana zakale**
- **Imapereka ntchito & imachita zinthu nthawi imodzi — imapanga subagents kuti tigwire ntchito zambiri nthawi imodzi**
- **Zochitika zozikidwa nthawi — cron yomangidwa mkati yofuna kupanga ripoti za tsiku lililonse, kusamalira kopi (backups), ndi kukonzetsa zolemba (audits)**
- **Imagwira kulikonse — local, Docker, SSH, cloud, serverless**

## Kukhazikitsa mofulumika

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Kuyamba

```bash
openamer              # Yambani kucheza
openamer setup        # Konzani API keys zanu ndi provider
openamer model        # Sankhani model yanu
openamer update       # Sinthani kukhala version yatsopano kwambiri
```

## Kusintha

OpenAmer imafufuza zosinthidwa zaposachedwa yokha ndipo imasonyeza chenjezo pa banner ya welcome. Gwiza command ya `openamer update` kuti mupeze version yatsopano — imasungira data yanu (backup) poyamba.

## Kupereka thandizo

Zithandizo zanu n'zoikilidwa — tsegulani mfufu wa zovuta (**open issues**), tumizani mapempha a kusintha (**pull requests**), kapena kulumikizana ndi gulu lathu.

## Layisensi

Apache License 2.0. Onani {LICENSE}.
