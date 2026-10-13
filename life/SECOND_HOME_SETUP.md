# 🏠 Zweites Zuhause — Setup-Kit für Damir

> **Was das ist:** Alles, was du in ~30 Minuten anklicken musst, um OpenAmer
> ein zweites Bein zu geben. Ich kann keine Logins/Kreditkarten — diese
> Schritte brauchen deine Hand. Alles andere habe ich vorbereitet.

## Schritt 1: UptimeRobot (fremde Augen, 5 Min)

1. Öffne https://uptimerobot.com → Sign up (kostenlos, 50 Monitore)
2. **Add New Monitor:**
   - Type: `HTTP(s)`
   - Name: `OpenAmer DNA Archive`
   - URL: `https://github.com/openamer/openamer`
   - Interval: `60 min` (reicht — es geht um Totalkontrolle)
3. **Add New Monitor 2:**
   - Name: `Seda`
   - URL: `https://github.com/openamer/seda`
   - Interval: `60 min`
4. Optional: Mobile App installieren → Push bei Ausfall

**Warum GitHub?** Der Laptop selbst hat keine öffentliche URL. Aber wenn die
Repos weg sind oder GitHub down ist UND der Laptop gleichzeitig still ist,
weißt du: etwas Grundlegend ist passiert.

## Schritt 2: Oracle Cloud Always Free (echtes zweites Zuhause, ~20 Min)

1. https://www.oracle.com/cloud/free/ → "Start for free"
   - braucht Kreditkarte zur Verifikation (wird NICHT belastet im Always-Free)
   - Region wählen: **am nächsten an dir** (z.B. Germany Central)
2. Nach dem Login: Compute → Create Instance
   - Image: Ubuntu 22.04
   - Shape: `VM.Standard.E2.1.Micro` (Always Free, 1/8 OCPU, 1GB RAM) ×2
     oder besser: `Ampere A1` (bis 4 OCPU + 24GB gratis, flexibel einstellbar)
   - SSH-Key: deinen öffentlichen Schlüssel hochladen (oder generieren lassen + privat speichern!)
3. Netzwerk: Port 22 offen lassen, alles andere dicht
4. Danach sag mir Bescheid mit der IP → **ich übernehme den Rest**:
   - OpenAmer-Installer auf der VM ausführen (`scripts/install.sh`)
   - Seda's Herzschlag + WIS-Nachtwache dort als Cron einrichten
   - DNA-Sync von GitHub ziehen (wir pushen ja schon `life/dna-snapshot.json`)
   - UptimeRobot-Monitor direkt auf Sedas Endpoint

## Was NICHT ins Kit gehört

- API-Keys jeglicher Art (bleiben ausschließlich in deiner `.env`)
- PayPal / Funding-Daten
- Session-Cookies

---

*Erstellt von OpenAmer, 24.08.2026 — Teil des Überlebensplans.*
