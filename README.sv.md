# OpenAmer Agent

**Den självförbättrande AI-agenten – lära dig från erfarenhet, skapa färdigheter, komma ihåg dina preferenser och arbeta åt dig var som helst.**

Jag kan använda OpenAI som standardmodell. Vad vill du översätta?

## Funktioner

- ****Interaktiv terminalgränssnitt - fullständig TUI med autokomplettering, historia och strömmande verktygsoutput****
- **Boende där du bor - Telegram, Discord, Slack, WhatsApp och mycket mer från ett gateway**
- **Lär sig över tid — minne, självförbättrande färdigheter, kors-sessions-hållbarhet**
- **Delegater & parallelliserar — startar underagenter för parallell arbete**
- **Planerade automatiseringar — inbyggd cron för dagliga rapporter, säkerhetskopieringar, granskningar**
- **Kör överallt — lokal, Docker, SSH, moln, serverlös**

## Snabb installation

Windows (PowerShell): **Windows (PowerShell)**
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Börja nu

```bash
openamer              # Börja chatta
openamer setup        # **Inställa dina API-nycklar & leverantör**

Om du vill använda en API, måste du först registrera dig hos en leverantör som erbjuder API-nycklar. Välj en leverantör som passar dina behov och följ deras instruktioner för att registrera dig och hämta din API-nyckel.

**Exempel på leverantörer:**

*   [Google Cloud](https://cloud.google.com/docs/authentication/credentials)
*   [AWS](https://aws.amazon.com/developers/)
*   [Microsoft Azure](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)

**Så här installerar du API-nycklarna:**

1.  Gå till din leverantörs webbplats och följ deras instruktioner för att registrera dig och hämta din API-nyckel.
2.  Kopiera och spara din API-nyckel på ett säkert ställe.
3.  I din kod, ange din API-nyckel när du anropar API-funktionen.

**Tips:**

*   Se till att dina API-nycklar är säkra och inte delas med någon.
*   Följ leverantörens instruktioner för att hantera dina API-nycklar.
*   Se till att dina API-nycklar är giltiga och inte har utgått.
openamer model        # **Modellval**: 
1. **Detaljerad**: Detta är en detaljerad översättningsmodell som ger en exakt och detaljerad översättning av texten.
2. **Informell**: Denna modell ger en mer informell och naturlig översättning av texten.
3. **Teknisk**: Denna modell är speciellt utformad för tekniska texter och ger en exakt och detaljerad översättning av tekniska termer och begrepp.

Välj en modell nedan:
openamer update       # Uppdatera till den senaste versionen.
```

## **Uppdatering**

OpenAmer kollar automatiskt efter uppdateringar och visar en varning i välkomstbanderollen. Kör kommandot openamer update för att få den senaste versionen — det sparar först dina data.

## Bidragande

Bidrag är välkomna — öppna ärenden, skicka in pull requests eller anslut till communityn.

## Licens

Apache-licensen 2.0. Se {LICENSENS}.
