# SignPath Foundation — Bewerbung für kostenlose Code-Signierung

## Was ist SignPath Foundation?
Kostenlose Code-Signierung für Open-Source-Projekte. Das Zertifikat wird auf das
**Projekt** ausgestellt (nicht persönlich), der private Schlüssel liegt auf deren
HSM, und es verifiziert, dass das Binary aus dem OSS-Repo gebaut wurde.
→ Keine SmartScreen-Warnung mehr, wirkt wie professionelle Software. **0 €.**

## Unser Projekt (alle Voraussetzungen erfüllt)
- Repo: https://github.com/openamer/openamer
- Lizenz: Apache-2.0 (Open Source)
- Public: ja
- Beschreibung: "The self-improving, self-learning open-source AI agent."

## Bewerbung
1. Gehe auf https://signpath.org/apply
2. Melde dich mit dem GitHub-Konto **openamer** an (Repo-Inhaber)
3. Gib das Repo an: `openamer/openamer`
4. Warte auf Verifizierung (SignPath prüft die Repo-Inhaberschaft)

## Nach der Genehmigung: Signing in GitHub Actions integrieren
SignPath stellt ein Signing-Subscription bereit. Der Build-Workflow
(`.github/workflows/`) muss dann:
1. Den NSIS-Installer bauen (wie jetzt: `npm run dist:win:nsis`)
2. Das Binary an SignPath.io zum Signieren senden (HSM)
3. Das signierte Binary als Release-Asset hochladen

## Aktueller Stand (06.09.2026)
- ✅ NSIS-Installer gebaut: `OpenAmer-2026.9.6-win-x64.exe` (102 MB)
- ✅ GitHub-Release veröffentlicht: https://github.com/openamer/openamer/releases/tag/v2026.09.06
- ⏳ SignPath-Bewerbung (muss der Repo-Inhaber abschicken)
- ⏳ Signing in CI integrieren (nach Genehmigung)

## Wichtige Hinweise
- Die Bewerbung MUSS der Repo-Inhaber (Damir, GitHub-Konto `openamer`) abschicken —
  SignPath verifiziert die Inhaberschaft über das GitHub-Konto.
- Der private Schlüssel wird NIE lokal gespeichert — alles läuft über SignPath.io HSM.
- Für OSS-Projekte ist der Service kostenlos.
