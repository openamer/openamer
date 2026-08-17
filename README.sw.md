# OpenAmer Agent

**Agent wa AI anayejiboresha mwenyewe — jifunze kutokana na uzoefu, tengeneza ujuzi, kumbuka mapendeleo yako, na ufanye kazi kwa ajili yako popote.**

Tumia modeli yoyote unayotaka — OpenRouter, OpenAI, DeepSeek, na nyinginezo. Badilisha kwa kutumia `openamer model` — bila kubadilisha kodi.

## Sifa

- **Kiolesura halisi cha terminal — TUI kamili yenye autocomplete, historia, na matokeo ya zana yanayotiririka (streaming)**
- **Inapatikana kule ulipo — Telegram, Discord, Slack, WhatsApp na nyinginezo kupitia lango moja**
- **Hujifunza kadiri muda unavyopita — kumbukumbu, stadi zinazojiboresha, ukumbukaji kati ya vipindi (cross-session recall)**
- **Huwakilisha & hufanya sambamba — huunda mawakala wadogo kwa ajili ya kazi zinazofanyika kwa wakati mmoja**
- **Automations zilizopangwa — cron ya ndani kwa ripoti za kila siku, nakala za usalama, na ukaguzi**
- **Inafanya kazi popote — ndani ya kifaa (local), Docker, SSH, wingu (cloud), serverless**

## Ufungaji wa Haraka

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Kuanza

```bash
openamer              # Anza kuzungumza
openamer setup        # Weka funguo zako za API (API keys) na mtoa huduma (provider)
openamer model        # Chagua modeli yako
openamer update       # Sasisha hadi toleo jipya zaidi
```

## Kusasisha

OpenAmer hukagua sasisho kiotomatiki na kuonyesha onyo kwenye bango la karibu. Endesha `openamer update` ili kupata toleo la hivi karibuni — itahifadhi nakala ya data yako kwanza.

## Kuchangia

Michango inakaribishwa — fungua masuala (issues), tuma maombi ya mabadiliko (pull requests), au jiunge na jumuiya.

## Leseni

Leseni ya Apache 2.0. Tazama {LICENSE}.
