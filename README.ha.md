# OpenAmer Agent

**Hukumar AI mai gyara kanta — koyo daga gogewa, ƙirƙirar fasahohi, tuna abubuwan da kake so, kuma yi maka aiki a ko'ina.**

Yi amfani da kowane samfuri (model) da kake so — OpenRouter, OpenAI, DeepSeek, da sauransu. Canza su ta hanyar amfani da `openamer model` — ba sai ka canza wani lambar sirri (code) ba.

## Siffofi

- **Kayan gwada na gaske (terminal interface) — cikakken TUI tare da raba-rubutu (autocomplete), tarihin ayyuka (history), da kuma fitar da sakamakon kayan aiki kai-tsaye (streaming tool output)**
- **Yana nan inda kake — Telegram, Discord, Slack, WhatsApp da sauran su daga hanyar sadarwa guda ɗaya**
- **Yana koyon abu a kan lokaci — ƙwaƙasancewa, fasahohin inganta kai, da kuma tunawa bayan an gama zamana (cross-session recall)**
- **Yana raba ayyuka kuma yana yin su tare — yana ƙirƙirar ƙananan wakilai (subagents) don yin ayyuka a lokaci guda.**
- **Saitattun ayyukan automatization — cron da aka gina a ciki don rahotannin yau da kullum, back-ups, da binciken audit**
- **Yana aiki a ko’ina — na gida (local), Docker, SSH, gajimare (cloud), serverless**

## Saurin Shigarwa

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Fara amfani

```bash
openamer              # Fara hira
openamer setup        # Saita mabuɗan API (API keys) ɗinka da mai samarwa (provider)
openamer model        # Zaɓi samfurinka
openamer update       # Karin update zuwa ga sabon version
```

## Karin bayani / Sabuntawa

OpenAmer yana duba sabuntawa (updates) ta atomatik kuma yana nuna gargaɗi a sashin maraba (welcome banner). Yi amfani da `openamer update` don samun sabon sigar — yana yin kwafi (backup) na bayananka tukunnanin yin hakan.

## Yarda da Gudummawa

Ana welcomed gudammawa — bude matsaloli (issues), tura buƙatun haɗaka (pull requests), ko kuma haɗa kai da al'ummar mu.

## Lasisi

Lasisin Apache 2.0. Duba {LICENSE}.
