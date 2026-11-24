# Ein Fork ist keine Integration (26.10.2026)

Der Auftrag lautete „REA in OpenAmer integrieren". Geliefert wurde zuerst ein Fork mit
neuem Namen, neuer CLI und neuem MCP-Key — und die Antwort auf „warum ist das nicht *in*
OpenAmer?" war eine Erklärung statt einer Änderung. Das war der Fehler, nicht das
Ergebnis: ein umbenanntes Fremdprojekt bleibt ein Fremdprojekt, solange es nur ein
Nachbarverzeichnis ist.

## Was „integriert" heißt — die Prüfliste

Erst wenn alle fünf Punkte erfüllt sind, ist eine fremde Fähigkeit Teil des Produkts:

1. **Eine Kommando-Oberfläche im Produkt.** `openamer re doctor|scan|recall` — der
   Nutzer muss nie wissen, in welchem Repo der Code liegt.
2. **Registrierung im Produkt.** MCP-Server in der Config, mit begrenztem Tool-Scope
   (229 → 79 Familien), nicht „alle 229 Tools in den Kontext".
3. **Ein Skill**, damit der Agent die Fähigkeit von selbst findet und die Grenzen kennt.
4. **Ein Rückkanal ins Gedächtnis.** Befunde werden als Episode geschrieben, sonst ist
   die Analyse nach dem Turn weg.
5. **Eine dokumentierte Identitätsgrenze** (siehe unten).

Nur 1–3 zu liefern und 4–5 zu vergessen ist der halbe Weg — und genau der fühlt sich
wie „fertig" an.

## Die Identitätsgrenze: Produktoberfläche ja, Protokoll-Identität nein

Ein Rebrand, der auch den **MCP-Server-Key** umbenennt, invalidiert jede bestehende
Client-Registrierung bei jedem Nutzer — ohne eine einzige Fähigkeit zu ändern. Gemessen:
`ClientRegistrationStatus`, das Harness-Patch-Format, die Gemini-Ausschlusslisten und
die Doctor-Ownership prüfen alle gegen denselben String; vier Testdateien wurden rot,
sobald er sich änderte (54 Fehlschläge in einer Datei).

**Regel: die Protokoll-Identität bleibt, die Produktoberfläche wird neu.** Repo, Paket,
CLI-Binary, Skill-Name, Docs — unser. Server-Key, Wire-Format, Registrierungs-Schlüssel —
upstream. Diese Grenze gehört in `NOTICE.md`, sonst sieht sie beim nächsten Mal wie
Nachlässigkeit aus.

## Drop-in-Kompatibilität ist ein Feature, kein Test-Trick

Ein Fork, der Registrierungen des Vorgängers nicht als eigene erkennt, verwaist jede
bestehende Installation: `setup` plant nichts, `doctor` nennt sie fremd, `uninstall`
weigert sich. Die Reparatur ist, die **Upstream-Namen als Aliase anzuerkennen**
(`rea-agents`, `rea`) — danach funktioniert ein Wechsel für Bestandsnutzer.

Das ist keine Gefälligkeit an die Tests: es ist das Migrationsverhalten, das ein Fork
haben muss. Wer stattdessen die Fixtures auf den neuen Namen umschreibt, hat die Tests
grün und den Nutzer verloren.

## Verwaltete Dateilisten sind ein zweiter Ort der Wahrheit

Wird einer gebündelten Skill ein File hinzugefügt (`references/integration.md`), muss die
Liste im Installer (`MANAGED_SKILL_FILES`) mitwachsen — sonst sind Installer, Ledger und
`doctor` uneins, und ein Konformitäts-Digest schlägt fehl. Besser: **der Test leitet die
Liste aus der Quelle ab**, statt sie zu kopieren. Dann kann sie nicht mehr driften.

## Pre-existing failures: erst messen, dann behaupten

Vor jedem „das war schon vorher kaputt" eine **unveränderte Upstream-Arbeitskopie auf
demselben Commit** bauen und dieselben Dateien dort laufen lassen. Gemessen in dieser
Sitzung, pro Datei:

| Datei | Upstream | Fork |
|---|---|---|
| ghidraClient | 67 failed | 67 failed |
| GdbSessionManagerCoverage | 48 failed | 48 failed |
| documentationFacts | 1 failed | 1 failed |
| dshClientConfiguration | **grün** | 54 failed |
| setupClientConfigCleanupOwnership | **grün** | 4 failed |

Erst diese Tabelle macht „115 Fehlschläge sind vorbestehend, diese 58 sind meine" zu
einer Messung. Ohne sie ist es eine Ausrede — und die eigenen Regressionen fallen nicht
auf, weil sie in der roten Masse untergehen.

Praktisch: `git worktree add` auf `upstream/main`, `node_modules` per Junction verlinken,
bauen, dieselben Dateien laufen lassen. Auf Windows reproduzieren plattformbedingte
Fehlschläge identisch — das ist der Beweis, den man braucht.

## Maßstab ehrlich halten

Der ehrliche Satz nach dem Rebrand war: **87 Dateien, +449/−303 Zeilen in einer
Codebasis von 504.173 Zeilen** — 0,1 %. Die Analyse-Engines sind upstream; neu sind
Identität, Scope, Registrierung, Skill und der Rückkanal ins Gedächtnis. Wer das als
„wir haben 504k Zeilen umgeschrieben" erzählt, hat den nächsten Auftrag schon verloren.
