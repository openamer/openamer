# OpenAmer Agent

**Samodoskonalący się agent AI — uczy się z doświadczenia, tworzy umiejętności, zapamiętuje Twoje preferencje i pracuje dla Ciebie w każdym miejscu.**

Korzystaj z dowolnego modelu — OpenRouter, OpenAI, DeepSeek i innych. Przełączaj je za pomocą `openamer model` — bez zmian w kodzie.

## Funkcje

- **Prawdziwy interfejs terminala — pełne TUI z autouzupełnianiem, historią i strumieniowaniem wyjścia narzędzi**
- **Działa tam, gdzie Ty — Telegram, Discord, Slack, WhatsApp i inne komunikatory z jednej bramki**
- **Uczy się z czasem — pamięć, samodoskonalące się umiejętności, przywoływanie informacji między sesjami**
- **Deleguje i równolegli — tworzy subagentów do pracy równoległej**
- **Harmonogram automatyzacji — wbudowany cron dla raportów dziennych, kopii zapasowych i audytów**
- **Działa wszędzie — lokalnie, w Dockerze, przez SSH, w chmurze, serverless**

## Szybka instalacja

Windows (PowerShell):
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## Pierwsze kroki

```bash
openamer              # Zacznijmy rozmowę
openamer setup        # Skonfiguruj swoje klucze API i dostawcę
openamer model        # Wybierz swój model
openamer update       # Aktualizuj do najnowszej wersji
```

## Aktualizowanie

OpenAmer automatycznie sprawdza dostępność aktualizacji i wyświetla ostrzeżenie w banerze powitalnym. Uruchom polecenie `openamer update`, aby pobrać najnowszą wersję — program najpierw wykona kopię zapasową Twoich danych.

## Wkład

Zapraszamy do współtworzenia projektu — otwórz zgłoszenie (issue), prześlij pull request lub dołącz do społeczności.

## Licencja

Licencja Apache 2.0. Zobacz {LICENSE}.
