---
name: openamer-skill-pack-productivity
description: 'Use for shipping the OpenAmer Pro Skill Pack: a sellable bundle of top-rated OpenAmer skills with installer and license validation.'
---

# OpenAmer Pro Skill Pack — verkaufbares Micro-Produkt

## Was es ist
Ein kuratiertes Bundle der OpenAmer-Skills mit den höchsten Validator-Scores
(B+ oder besser), verpackt als installierbares Paket mit Installer-Script.

## Aufbau (was hier liegt)
- `packs/pro-pack/skills/`     — die kuratierten Skills (kopiert, nicht verlinkt)
- `packs/pro-pack/install.py`  — Installer: kopiert Skills nach ~/.openamer/skills/, validiert je Skill >= 70 Punkte, bricht sonst ab
- `packs/pro-pack/MANIFEST.json` — Skill-Liste + Mindestscores + Version

## Verkaufs-Kanäle
1. GitHub Sponsors "Sponsor-tier" (FUNDING.yml existiert bereits: github: openamer, ko-fi, buymeacoffee, PH-Link)
2. Gumroad/LemonSqueezy-Später: erst wenn erste 10 zahlende Sponsoren

## Preislogik (Empfehlung)
- Free: OpenAmer Open-Source-Kern (bleibt immer frei)
- Pro Pack: 19 € einmalig via ko-fi/buymeacoffee-Shop-Link
- Updates: 12 Monate included, dann 9 €/Jahr

## Procedure (Pack bauen)
1. `python scripts/build_pro_pack.py` — liest reports/skill-validator-latest.json,
   wählt alle Skills mit Score >= 70 und nutzbarem, eigenständigem Inhalt
   (keinedamir-spezifischen Pfade), kopiert sie nach packs/pro-pack/skills/.
2. Installer generieren lassen (Script macht das).
3. ZIP erzeugen: `cd packs && python -m zipfile -c pro-pack-v1.zip pro-pack/`
4. Test-Install in einen Temp-Ordner: `python pro-pack/install.py --target <tmp> --check`
5. Upload-Link + Preis in GitHub Issue "Pro Pack" dokumentieren.

## Pitfalls
- Keine Skills mit hartcodierten Pfaden (C:\Users\damir) in das Pack — Installer-Check fängt das.
- Lizenz: erst simple "Fair-Use-Hinweis"-Datei, keine Over-Engineering-Lizenzmaschine.
- Erster Verkaufsschritt ist Sponsoren-Traffic (README-Button + Dashboard), nicht die Shop-Infrastruktur.
