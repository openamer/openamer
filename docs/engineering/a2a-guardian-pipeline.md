# A2A Guardian Pipeline — Machbarkeits-Analyse

Status: **Vorschlag / Machbarkeitsanalyse** — kein implementierter Code.
Zweck: ehrlich bewerten, ob "viele OpenAmer-Nodes → ein Wächter → GitHub → alle update" eine
gute Architektur ist, was geht, was nicht, welche Risiken es gibt, und wie es umgesetzt werden könnte.

## Zielbild (aus Sicht des Nutzers)

> Jedes OpenAmer kann Verbesserungs-Vorschläge einreichen. **Nur EIN Node** (der "Wächter", hier:
> der, der das GitHub-Token besitzt) verifiziert sie, integriert sie in `main` und pusht sie.
> Alle anderen OpenAmer-Instanzen haben **kein** GitHub-Token und holen sich den neuen Stand per
> `openamer update`. Damit bleibt die Git-History sauber und nur eine vertrauenswürdige Stelle
> hat Write-Zugang.

## Die wichtigste Tatsache (vom Nutzer bestätigt)

- **Andere OpenAmer-Nodes haben KEINE GitHub-Tokens.** Sie können also nicht direkt auf GitHub
  pushen. Das ist eine **Eigenschaft, die die Architektur sicherer macht**, nicht nur eine Einschränkung:
  - Genau ein Node (der Wächter) hat Write-Zugang → kein Merge-Chaos, keine parallelen Pusher.
  - Vorschläge kommen nur über den A2A-Kanal herein → der Wächter ist die einzige Integrationsstelle.
  - Kein Token-Verteilungsrisiko über viele Maschinen.

## Was OpenAmer heute schon mitbringt (Bestand)

`openamer_cli/a2a/` enthält bereits ein signiertes, datenschutzbewusstes A2A-Modul:

| Modul | Funktion | Für die Pipeline relevant? |
|---|---|---|
| `identity/registry/announce` | Node-Identität (Keypair, Fingerprint), Verzeichnis | ✅ Node-Identität |
| `trust.py` | Signierte Envelopes, Vertrauenspfad | ✅ Signaturverifikation |
| `privacy.py` | Redaktion sensibler Daten vor Persistenz | ✅ Sicherheit |
| `meshlearn.py` | signierte Insights, publish/adopt | 🟡 Muster für signierte Code-Vorschläge |
| `relay.py` / `transport.py` | Übermittlung zwischen Nodes | 🟡 Kanal |
| `selflearn.py` + `auto_learn()` | Lehren aus Turns destillieren | 🟡 als Modell für "Vorschlag→Lern" |

Der bestehende `openamer a2a`-CLI-Pfad (`status/init/fingerprint/verify/announce/directory/ask`)
liefert die Identitäts- und Signatur-Grundlage.

## Was technisch fehlt (die echten Lücken)

Damit "Vorschlag → Wächter → integriert → gepusht → alle updaten" sicher funktioniert, braucht es:

1. **Ein signiertes Vorschlags-Format** für *Code*-Änderungen (nicht nur Insights):
   - Absender-Node-Fingerprint, Signatur, Patch/Diff oder Referenz, Beschreibung, betroffene Pfade.
   - Der Empfänger (Wächter) muss die **Signatur gegen das Vertrauens-Verzeichnis** prüfen.
2. **Isolierte Verifikation**, bevor irgendetwas integriert wird:
   - Vorschlag auf eine **abgelegte Branch** anwenden, Tests in isolierter Umgebung laufen lassen,
     erst bei grün in `main` übernehmen. Nie Code blind aus einem Tunnel einspielen.
3. **Eingangskanal-Sicherheit:**
   - Der Tunnel (WSS/ngrok/Cloudflare/Relay) sagt "wer spricht mit mir", aber NICHT "ob dessen Code gut ist".
   - Vertrauen muss **signaturbasiert** sein (nur bekannte, verifizierte Node-Fingerprints), nicht
     "irgendwer mit einem Tunnel".
4. **Rate-Limit / Abuse-Schutz:** Viele Nodes könnten Spam senden → Obergrenze, Größen-Limit,
   nur signierte, nur von verifizierten Fingerprints.

## Bewertung der Architektur (ehrlich)

**Stark:**
- Ein Push-Punkt → saubere History, keine Konflikte, ein klarer Qualitäts-Gate.
- "Verifizieren bevor integrieren" ist das richtige "100%-fehlerfrei"-Prinzip.
- Update-Schleife existiert: `openamer update` zieht `main`, alle bekommen den Stand automatisch.

**Kritisch — keine "Überlegenheit", sondern Rollen:**
- Der Wächter ist ein **Single Point of Failure**: fällt er aus, kommt nichts mehr auf `main`.
- "Nr. 1 über alle" ist der falsche Rahmen. Es ist eine **Rollen-Trennung** (Verifizierer vs.
  Beitragende), nicht ein Rang. Der Wächter trägt **Verantwortung**, nicht Überlegenheit.
- Sicherheit ist der harte Teil: signierter Eingang + isolierte Prüfung + nur vertrauenswürdige
  Fingerprints. Ein Tunnel allein löst das nicht.

## Empfohlene Umsetzung (pragmatisch, gestuft)

**Stufe 1 — Analyse & Signatur-Vorschlag (sicher, kein Push-Risiko):**
- Definiere ein signiertes `CodeProposal`-Schema (Sender-Fingerprint, Signatur, Patch, Beschreibung).
- Nutze `a2a/trust.py` für Signatur + Fingerprint-Verifikation (existiert).
- Nur-Doku + Tests für das Schema. **Noch kein Live-Empfang.**

**Stufe 2 — Wächter-Empfang + isolierte Verifikation:**
- CLI/Modul `openamer a2a propose verify` : nimmt einen signierten Vorschlag, prüft Signatur,
  legt isolierte Branch an, führt Tests aus, meldet grün/rot.
- NOCH KEIN Auto-Push. Erst prüfen.

**Stufe 3 — Integration (vorsichtig):**
- Wächter übernimmt nur grüne, signierte Vorschläge in `main` und pusht (mit Token).
- Alle anderen ziehen per `openamer update`.

## Was ich NICHT empfehle (ehrlich)
- **Kein** Auto-Push aus dem Tunnel in `main` ohne isolierte Tests + Signatur.
- **Kein** "alle Nodes haben gleich Tokens" — die Token-freie Architektur ist besser.
- **Kein** Ranking/Hierarchie-Denken — Rollen, nicht Ränge.

## Nächster konkreter Schritt (vorgeschlagen)
Stufe 1: ein signiertes `CodeProposal`-Schema + Tests, als neues Modul
`openamer_cli/a2a/proposal.py` (reine, deterministische Datenstruktur + Signatur), dokumentiert
und mit Unit-Tests — **ohne** Live-Tunnel-Empfang. Das ist sicher, verifizierbar und der
fundierte Grundstein. Auf Wunsch wird es anschließend um die Wächter-Verifikation erweitert.
