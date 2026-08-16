# OpenAmer Agent

**Selvforbedrende AI-agent — lær fra erfaring, utvikle ferdigheter, husk dine preferanser og arbeid for deg overalt.**

Jeg vil bruke OpenAI-modellen.

## Funksjoner

- ****Fullstendig terminalgrunnflate — full TUI med autokompletering, historikk og strømmende utdata fra verktøy****
- **Bor hvor du bor — Telegram, Discord, Slack, WhatsApp og mer fra én port**
- **Lærer over tid — minne, selvforbedrende ferdigheter, krysstidsinnhenting**
- **Delegerer & parallelerer — spawn underagenter for parallell arbeid**
- **Planlagte automatiseringer — bygget inn en cron for daglige rapporter, sikkerhetskopier, auditorier**
- **Kjører overalt — lokal, Docker, SSH, i skyen, serverløs**

## Rask Installasjon

Vindus (PowerShell)
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## **Innledning**

For å begynne å bruke [GitHub](https://github.com/), følg disse trinnene:

1. **Opprett en konto**: Gå til [GitHub.com](https://github.com/) og klikk på "Sign up" i øverste høyre hjørne.
2. **Velg en brukernavn**: Velg et unikt og relevant brukernavn.
3. **Opprett en repository**: Klikk på "New" i menyen og velg "New repository".
4. **Lag lag av kode**: Klikk på "Upload files" og last opp dine kodefiler.
5. **Commit dine endringer**: Klikk på "Commit" og skriv en beskrivelse av endringene dine.
6. **Push dine endringer**: Klikk på "Push" og send dine endringer til GitHub.

**Tips og råd**

* Les [GitHub-dokumentasjonen](https://docs.github.com/en) for å lære mer om GitHub.
* Bruk [GitHub Desktop](https://desktop.github.com/) for å arbeide lokalt med dine prosjekter.
* Del dine prosjekter med andre ved å opprette en [fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo) eller [pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests).

```bash
openamer              # Begyn å snakke
openamer setup        # **Konfigurer API-nøkler og tjenesteprovider**

1. **Velg en tjenesteprovider**: Velg en tjenesteprovider som tilbyr API-tilgang, slik som [Google Cloud](https://cloud.google.com/), [Amazon Web Services](https://aws.amazon.com/) eller [Microsoft Azure](https://azure.microsoft.com/).
2. **Opprett en konto**: Opprett en konto hos valgt tjenesteprovider og følg deres instruksjoner for å opprette en ny konto.
3. **Generer API-nøkler**: Følg instruksjonene til tjenesteprovideren for å generere API-nøkler. Dette vil typisk involvere å opprette en ny API-nøkkel, eller å kopiere en eksisterende nøkkel fra din konto.
4. **Lagre API-nøkler**: Lagre API-nøkler i en sikker og organisert måte, slik som i en kryptografisk lagringsløsning eller i en verktøy-lagringsløsning som [LastPass](https://lastpass.com/) eller [1Password](https://1password.com/).
5. **Konfigurer API-nøkler i dine prosjekter**: Når du har API-nøkler, kan du konfigurere dem i dine prosjekter og applikasjoner for å tilgå tjenesteprovideren og bruke deres API-er.
openamer model        # Velg din modell
openamer update       # Oppdater til den nyeste versjonen
```

## Oppdatering

OpenAmer sjekker automatiskt etter oppdateringer og viser en varsel i velkomstbanneren. Kjør openamer update for å få den seneste versjonen – den lagrer først dine data.

## Bidragsytere

Bidrag er velkommen — åpne issue, submit pull requests, eller bli med i samfunnet.

## Lisens

Apache-licensen 2.0. Se {LICENSE}.
