# OpenAmer Agent

**Az önfejlesztő AI ügynök — tanul a tapasztalatokból, készít készségeket, megjegyzi a preferenciáidat, és bárhol dolgozik neked.**

Használjon bármilyen modellt, amely tetszik — OpenRouter, OpenAI, DeepSeek és egytöbb. Váltson velük az `openamer model` paranccsal — kódmódosítás nélkül.

## Funkciók

- **Valódi terminál felület — teljes TUI automatikus kiegészítéssel, előzményekkel és folyamatos eszközkimutatással**
- **Ott van, ahol Te is — Telegram, Discord, Slack, WhatsApp és még több, egyetlen kapun keresztül**
- **Idővel tanul — memória, önfejlesztő készségek, sessionek közötti visszaidézés**
- **Delegál és párhuzosít — alügynököket indít parallel munkafolyamatokhoz**
- **Ütemezett automatizálások — beépített cron napi jelentésekhez, tartalékmentésekhez és auditokhoz**
- **Bárhol futtatható — helyileg, Dockerben, SSH-on, felhőben, serverless környezetben**

## Gyors telepítés

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Kezdés

```bash
openamer              # Kezdjünk a beszélgetést
openamer setup        # Állítsa be az API kulcsait és a szolgáltatót
openamer model        # Válasszon modellt
openamer update       # Frissítse a legújabb verzióra
```

## Frissítés

Az OpenAmer automatikusan ellenőrzi a frissítéseket, és figyelmeztetést jelenít meg az üdvözlő bannerben. Futtassa az `openamer update` parancsot a legújabb verziióhoz — a program először biztonsági másolatot készít az adatairól.

## Hozzászólás / Közreműködés

Szeretnénk fogadni a hozzálé Contribution-okat — nyiss új issue-kat, küldj be pull requesteket, vagy csatlakozz a közösséghez.

## Licenc

Apache License 2.0. Lásd a {LICENSE} fájlt.
