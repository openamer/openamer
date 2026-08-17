# OpenAmer Agent

**Samoimprovizujúci AI agent — učí sa zo skúseností, vytvára zručnosti, pamätá si vaše preferencie a pracuje pre vás kdekoľvek.**

Použite akýkoľvek model, ktorý chcete — OpenRouter, OpenAI, DeepSeek a ďalšie. Prepínajte pomocou `openamer model` — bez zmeny kódu.

## Funkcie

- **Skutočné rozhranie terminála — plnohodnotné TUI s dopĺňovaním, históriou a streamovaným výstupom nástrojov**
- **Býva tam, kde vy — Telegram, Discord, Slack, WhatsApp a ďalšie aplikácie z jednej brány**
- **Učí sa postupne — pamäť, schopnosti samodoskonalenia, pripomínanie si informácií medzi reláciami**
- **Deleguje a paralelizuje — spúšťa podagentov pre paralelnú prácu**
- **Plánované automatizácie — vstavaný cron pre denné reporty, zálohy a audity**
- **Beží kdekoľvek — lokálne, v Dockeri, cez SSH, v cloude, serverless**

## Rýchla inštalácia

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Začiatok

```bash
openamer              # Začnite četovať
openamer setup        # Nastavte si svoje API kľúče a poskytovateľa
openamer model        # Vyberte si svoj model
openamer update       # Aktualizujte na najnovšiu verziu
```

## Aktualizovanie

OpenAmer automaticky kontroluje aktualizácie a zobrazuje varovanie v uvítacom banneri. Spustite príkaz `openamer update` pre získanie najnovšej verzie — predovšetkým vytvorí zálohu vašich dát.

## Prispievanie

Prispievanie je vítané — otvárajte problémy (issues), posielajte pull requesty alebo sa pridajte k komunite.

## Licencia

Licencia Apache 2.0. Pozrite si {LICENSE}.
