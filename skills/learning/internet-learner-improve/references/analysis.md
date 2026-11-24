## Analyse des aktuellen Lern‑Zyklus

- **Download‑Prozess**: paralleles 4‑Thread‑Download mit Range‑Requests, hoher Durchsatz. 
- **Quellen‑Rotation**: 6 Quellen (A–F), 2 Tasks pro Zyklus. 
- **Satz‑Rotation**: 8 thematische Winkel, `il_rotation` wird pro Invocation inkrementiert. 
- **Query‑Auswahl**: 
  * Live Headline (HN) → sofern nicht Junk. 
  * LLM‑synthetisierte Query → Long‑Prompt-Stil, Terminologie‑Filter. 
  * Statische Seeds → vor Gebrauch auf Plausibilit"t prüfen. 
- **Gaten**: `Junk`, `Tech‑Signal`, `Duplicate`, `Writer‑Gate`. 
- **Herausforderung**: wenn alle Quellen *No Insight* zurückgeben, wirkt das System wiederholend. 
- **Verbesserungs‑Punkte**: 
  1. Headline‑Erfassung mit mehr Seiten und feineren Filtern. 
  2. LLM‑synthetisierte Queries konsistenter gestalten (Prompt‑Steuerung, Stop‑Wörter). 
  3. Seed‑Validierung (z. B. Länge, nicht‑Duplicate, Fruchtbarkeit). 
- **Deployed Status**: NPU‑Download 100 %, NPU‑Server läuft, Tool‑Server nutzt `mini_backend`. 

Dieser Bericht dient als Referenz für zukünftige Wiederholungen der Internet‑Learning‑Pipeline.
