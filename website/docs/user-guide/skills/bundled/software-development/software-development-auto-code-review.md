---
title: "Auto Code Review — Security scan + code quality + auto-fix on git push"
sidebar_label: "Auto Code Review"
description: "Security scan + code quality + auto-fix on git push"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Auto Code Review

Security scan + code quality + auto-fix on git push.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development\auto-code-review` |
| Version | `1.0.0` |
| Author | OpenAmer Agent |
| License | MIT |
| Platforms | windows, linux, macos |
| Tags | `code-review`, `security`, `quality`, `auto-fix`, `push-trigger` |
| Related skills | [`requesting-code-review`](/docs/user-guide/skills/bundled/software-development/software-development-requesting-code-review), [`security-agent`](/docs/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-security-agent), [`github-code-review`](/docs/user-guide/skills/bundled/github/github-github-code-review) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that OpenAmer loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Auto Code Review Agent

Push-getriggerter Code-Review-Agent der Security-Scans, Code-Qualitätsprüfungen
und Style-Checks automatisch durchführt und behebbare Issues patchen kann.

## Verwendung

```bash
# Letzten Commit prüfen
python scripts/auto-code-review.py --repo /pfad/zum/repo

# Letzte 5 Commits prüfen
python scripts/auto-code-review.py --diff HEAD~5

# Nur JSON-Report ausgeben
python scripts/auto-code-review.py --json

# Mit Auto-Fix (trailing whitespace, BOM, EOF)
python scripts/auto-code-review.py --fix

# Still (nur Exit-Code)
python scripts/auto-code-review.py --quiet
```

## Exit-Codes

| Code | Bedeutung |
|------|-----------|
| 0    | Keine Issues gefunden |
| 1    | Warnungen (Quality/Style) |
| 2    | Security Issues gefunden |

## Security-Scan

Sucht nach:

- **Secrets:** Hardcodierte Passwörter, API-Keys, Tokens, Private Keys, AWS-Keys, Connection-Strings, JWT-Tokens
- **SQL-Injection:** f-string/format in execute(), String-Konkatenation in SQL-Queries
- **Dangerous APIs:** os.system(), shell=True, eval(), exec(), pickle.load(), yaml.load() ohne SafeLoader, verify=False

## Code-Qualität

- Leere `except:` Blöcke
- TODO / FIXME / HACK / XXX Kommentare
- Funktionen > 50 Zeilen
- Fehlende Return-Type-Hints
- print() in Produktionscode
- Auskommentierter Code

## Style

- Trailing Whitespace (auto-fixable)
- Tabs statt Spaces (auto-fixable)
- BOM-Marker (auto-fixable)
- Fehlende Newline am EOF (auto-fixable)

## Cron-Job

Der Cron `auto-code-review-60m` läuft alle 60 Minuten und prüft `--diff HEAD~1`
im OpenAmer-Repo.

## Integration

```bash
# Als Git-Pre-Push-Hook
echo 'python scripts/auto-code-review.py --quiet --repo "$PWD"' >> .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

## Exit-Code-Logik

- `exit 0` = sauber
- `exit 1` = Warnungen (Quality/Style Issues vorhanden)
- `exit 2` = Security Issues gefunden → sofort handeln
