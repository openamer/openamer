# OpenAmer Agent

**Samoočuvajući AI agent — nauči se iz iskustva, stvori vještine, zapamti vaše preferencije, i radi za vas bilo gdje.**

**Translation:**

Ako želite da koristite bilo koji od modela, kao što su OpenRouter, OpenAI, DeepSeek ili drugi, možete da menjate model koristeći `openamer model`.

## Karakteristike

- ****Prava terminalna interfaca** — potpun TUI sa autoumecompletom, historijom i streamovanim izlazom alata.**
- **Živi gde god ste — Telegram, Discord, Slack, WhatsApp i više od jednog vrata.**
- **Учи се током времена — меморија, самопреувијајући вештина, међусесијски сећање**
- **Делегати и паралелизују — спају подагенције за паралелно радење**
- **Ažurirane automatske aktivnosti — građenje ugrađenog kruna za dnevne izveštaje, rezervne kopije, auditove**
- **Radna na bilo kojem mjestu — lokalno, Docker, SSH, u oblaku, bez servera.**

## Brzo Ustanovite

Виндоус (Пауершел)
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Početak rada

```bash
openamer              # Počnimo razgovor.
openamer setup        # **Konfigurirajte API ključeve i pružatelja**

Da biste nastavili, potrebno je da konfigurirate API ključeve i pružatelja. Ovo je neophodno za pristup vašim računima i aplikacijama koje koristite u kombinaciji sa ovim servisom.

1. **Pristup API ključevima:**
   - Pogledajte dokumentaciju pružatelja za detalje o kako da dobijete API ključ.
   - Upute za postavljanje API ključeva variraju ovisno o pružatelju, ali obično se radi o sledećim koracima:
     - Prijavite se na vaš račun na sajtu pružatelja.
     - Idu na stranu za postavke ili postavke računa.
     - Pretražujte po "API ključ" ili "API pristup" i kliknite na relevantnu opciju.
     - Slijedi upute za postavljanje API ključa, koji mogu uključivati generisanje ključa, podešavanje pristupa, itd.

2. **Konfiguriranje pružatelja:**
   - Pogledajte dokumentaciju pružatelja za detalje o kako da se konfigurira pružatelj.
   - Upute za konfigurisanje pružatelja variraju ovisno o pružatelju, ali obično se radi o sledećim koracima:
     - Prijavite se na vaš račun na sajtu pružatelja.
     - Idu na stranu za postav
openamer model        # Изаберите модел
openamer update       # Ажурирајте на најновију верзију.
```

## Ажурирање

Otvori Amer provjerava automatski ažuravanja i prikazuje upozorenje u uvodnom baneru. Pokreni openamer update da bi ste dobili najnoviju verziju — ona prvo će sprečiti vaše podatke.

## Улагивач

Донације су добродошле — отворите проблеме, поднесите туге, или се прикључите заједници.

## Лиценца

Apache Licenca 2.0. Vidi {LICENSE}.
