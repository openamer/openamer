# OpenAmer Agent

**Mwamunthu wamaliza AI — mupangitsa kudziwa, kupanga ufulu, kurekodera mapenzi yako, na kufanya kazi kwa wewe kwa wakati wote.**

I'll use the OpenAI model for translation. Here is the translation:

**Chichewa**: 

**Original text:** Use any model you want — OpenRouter, OpenAI, DeepSeek, and more. Switch with `openamer model` — no code changes.

**Translation:** 

**Kuimba model yeyo yikulu — OpenRouter, OpenAI, DeepSeek, ndi zikulu zikulu. Tizigwirizana ndi `openamer model` — osati chigawo chakudziwa.**

## Mipangalo ya chifukwa

- **Mwepo yonse ya terminal — TUI inafulumayo yonse, inayo na autocomplete, uyuaji wa mawazo, na output ya tool inayoishia kwa wakati.**
- **Ku maoneka kwa njala yako — Telegram, Discord, Slack, WhatsApp na zingina zingine kuti m'maonekana kwa njala moja**
- **Kuimba kwa mwezi — ufahamu, uimara wa kujifunza, ufahamu wa muda mrefu**
- **Mabungwe & kuwoneka — kuwona subagents kwa kazi zinazofanana**
- ****Zikatengera za kutengenezeka — cron ya msanii kwa ripoti za siku, backup, audit****
- ****Runs anywhere** — **local**, **Docker**, **SSH**, **cloud**, **serverless****

## Kupanga Kuweka Kwa Haraka

Windows (PowerShell): **Njikoko** (PowerShell)
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Kuona Moyo wa Kwanza

```bash
openamer              # **Ziwonjezeka kwa njala**
openamer setup        # **Kuweka API keys & provider**

Kupanga API keys & provider kwa **[Google Cloud Platform](https://cloud.google.com/)**:

1. **Kuweka API keys**
   - Tumikusangalala kwenye [Google Cloud Console](https://console.cloud.google.com/).
   - Kuweka API keys kwenye **Navigation menu** (menu ya navigation) na kuchagua **APIs & Services** (APIs na Services).
   - Chagua API inayohitajika (kama vile **Google Maps JavaScript API**).
   - Kuweka API key kwenye **Navigation menu** na kuchagua **Dashboard** (Dashboard).
   - Kuweka API key kwenye **Navigation menu** na kuchagua **API keys** (API keys).
   - Kuweka API key kwenye **Navigation menu** na kuchagua **Create credentials** (Kuweka credentials).
   - Kuweka API key kwenye **Navigation menu** na kuchagua **API keys** (API keys).
   - Kuweka API key kwenye **Navigation menu** na kuchagua **API keys** (API keys).

2. **Kuweka provider**
   - Tumikusangalala kwenye [Google Cloud Console](https://console.cloud.google.com/).
   - Kuweka provider kwenye **Navigation menu** (menu ya navigation) na kuchagua **APIs & Services** (APIs na Services).
   - Chagua provider inayohitajika (kama vile **Google Cloud Storage**).
   - Kuweka provider kwenye **Navigation menu** na kuchagua **Dashboard** (Dashboard).
   - Kuweka provider kwenye **Navigation menu** na kuchagua **Provider** (Provider).
   - Kuweka provider kwenye
openamer model        # **Mwamuna**
openamer update       # **Ziwo chomanga chaka chagalu**.
```

## **Kupanga**

Mkulu OpenAmer anachokera kwa updates kwa njia ya mtu mwenyewe na kuonyesha ulaghai katika banner ya kuwasiliana. Tumia openamer update ili kupata pataversi ya mwisho — inapiga kura data yako kwanza.

## Kupanga mabanga

Mkazi unachitika - zilizo katika maswali yote, tuma request ya kuongeza, au uingia kwenye jamii.

## Chilichonse

Ukulu la Apache 2.0. Zikomo kusewera **{LICENSE}**.
