# OpenAmer Agent

**A magas szintű, önmagát fejlesztő AI ügynök — tanuljon tapasztalataiból, fejlesszen képességeket, emlékezzen meg preferenciáira, és dolgozzon Önnek bárhol.**

**Szeretném megváltoztatni a modellt.** 

Kérlek, adj meg egy új kérdést vagy szöveget, amelyet át kellene fordítanom.

## Szállítások

- **Teljes TUI (Text User Interface) — teljes körű terminálkezelő felület, amely tartalmaz autómatelepítést, történelmi megjegyzéseket és streamelési eszköz kimenetet.**
- **Ahol lakol — Telegram, Discord, Slack, WhatsApp és még sok más egy portálon**
- **Tanul a tapasztalattal - emlékezet, önszabályozó képességek, kereszt-szessziós visszaemlékezés**
- **Delegál és párhuzamosít — szubagenteket indít a párhuzamos munkához**
- **Naplózási automatizálások — beépített cron a napi jelentésekhez, visszaállításokhoz, auditokhoz.**
- **Bárhol fut — lokális, Docker, SSH, felhő, server nélküli**

## Gyors Telepítés

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Kezdés

```bash
openamer              # Beszéljünk!
openamer setup        # **API kulcsok beállítása & szolgáltató**

Az API kulcsok beállításához a következő lépéseket kell követni:

1. **Regisztráció**: Regisztráljon a kiválasztott API szolgáltató oldalán.
2. **API kulcs létrehozása**: A regisztráció után létrehozzon egy új API kulcsot a szolgáltató oldalán.
3. **API kulcs beállítása**: A létrehozott API kulcsot be kell állítani a kódjába, ahol a kulcsot használni fogja.

**API Provider**:

*   [Google Cloud Platform](https://console.cloud.google.com/): A Google Cloud Platform API kulcsait a [Google Cloud Console](https://console.cloud.google.com/) oldalon lehet kezelni.
*   [Microsoft Azure](https://azure.microsoft.com/): Az Azure API kulcsait a [Azure Portal](https://portal.azure.com/) oldalon lehet kezelni.
*   [Amazon Web Services (AWS)](https://aws.amazon.com/): Az AWS API kulcsait a [AWS Management Console](https://console.aws.amazon.com/) oldalon lehet kezelni.

**API kulcsok kezelése**:

*   A API kulcsokat a szolgáltató oldalán lehet kezelni.
*   A API kulcsokat titkosítani kell, hogy megakadályozzák a rosszindulatú személyek számára a hozzáférést.
*   A API kulcsokat frissíteni kell, ha a szolgáltató új kulcsot generál.
openamer model        # Válasszon modellt!
openamer update       # Frissítsd a legújabb verzióra.
```

## **Frissítés**

OpenAmer automatikusan ellenőrzi a frissítéseket és figyelmeztet a köszöntő sávban. Futassa el openamer update, hogy megkapja a legújabb verziót – előtte megmenti az adatait.

## **Hozzájárulás**

Szeretnénk, ha hozzájárulnál a fejlesztéshez – nyisd meg az aktív ügyfelet, küldj be egy pull requestet, vagy csatlakozz a közösséghez.

## Licenc

Apache Licenc 2.0. Lásd a {LICENSE}-ot.
