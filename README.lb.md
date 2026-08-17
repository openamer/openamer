# OpenAmer Agent

**De selwer verbesséende AI-Agent — lern op Erfahrung, kreesch Fäschter, erinnert sech an d'Préférenzen, an hëllt fir dëch ëmmer.**

I'll use the OpenAI model. What is the text you'd like me to translate into Luxembourgish (Lëtzebuergesch)?

## Funktiounen

- **Reeel Terminal Interface — voll TUI mat Autocomplete, Geschicht, an Streaming-Toolausgabe**
- **Op däerem Plaz — Telegram, Discord, Slack, WhatsApp an ochentlech méi vun enger Zentralplaz aus**
- **Léiert iwwer Zäit — Gedächtnis, verbessert Fäegeschaften, Kruuchsessen-Erwierzung**
- **Delegéiert & paralleliséiert — Subagenten fir parallel Wierk spawnen**
- **Geschéiert Automatiséierungen — eegentlech Cron für Dagelëchten Rapporten, Backupen, Audite.**
- **Gëtt op all Plätzer — lokal, Docker, SSH, Cloud, serverless**

## **Rapid Installierung**

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## En Ufank ginn

```bash
openamer              # **Wann du wëllst, kannst du och mat mir chatten.**
openamer setup        # **API-Schlëssel installéieren & Provider**

Um mat eiser API-Schlësselen ze setzen, gëtt et fir déi meescht API-Provider eng Registriéierung oder e Konto erëffnen. Dëst ass normalerweis gratis, awer fir d'API-Schlëssel ze kréien, gëtt et méi wäit. D'API-Schlëssel ginn normalerweis an engem JSON-Format zerstouss, wou d'Kategorie, d'Schlëssel, d'Secretecht, d'Beschreiwung an d'Beschreiwung vum Schlëssel enthalten.

**Beispill:**

```json
{
  "category": "geoloc",
  "key": "YOUR_API_KEY",
  "secret": "YOUR_API_SECRET",
  "description": "Geoloc API Schlëssel",
  "description_en": "Geoloc API Key"
}
```

**Provider:** 

*   [Google Cloud](https://cloud.google.com/)
*   [Amazon Web Services (AWS)](https://aws.amazon.com/)
*   [Microsoft Azure](https://azure.microsoft.com/)
*   [OpenWeatherMap](https://openweathermap.org/)
*   [Weather API](https://www.weatherapi.com/)
*   [IP Geolocation API](https://ipgeolocation.io/)
*   [IP2Location](https://ip2location.com/)
*   [IP Geolocation](https://www.ipgeolocation.io/)
openamer model        # **Wäisst du, wou dech dat wëllt?**
openamer update       # Aktualiséiert op déi lescht Versioun.
```

## Aktualiséierung

OpenAmer checkt automatesch op Updates an anziegt en Erwäinung am Welcome-Banner. Lëtzt OpenAmer update fir d'lescht Version ze kréien — et bewaart d'Daten zanterhalen.

## **Contribueren**

Contributiounen sinn uewen — offene Fragen, Pull Requests iwwerreeën oder der Communautéite bäi drécken.

## Lizenz

Apache Lizenz 2.0. Kuckt sech bei {LICENSE}.
