---
name: ab-test-engine
description: Use for A/B experiments on OpenAmer configs and skills.
---

# A/B Test Engine

CLI-Tool für automatische Experimente mit Skills + Configs in OpenAmer.

## Verzeichnisse

| Pfad | Zweck |
|------|-------|
| `~/.ab-tests/experiments/` | JSON-Experimentdefinitionen |
| `~/.ab-tests/results/` | Ergebnisdaten pro Experiment |
| `~/.ab-tests/metrics/` | Raw-Metrik-Snapshots |

## CLI-Befehle

```bash
python scripts/ab-test-engine.py --create <name> '<beschreibung>' --variant 'key=value[,key=value]'
python scripts/ab-test-engine.py --list
python scripts/ab-test-engine.py --status <name>
python scripts/ab-test-engine.py --conclude <name>
python scripts/ab-test-engine.py --collect
python scripts/ab-test-engine.py --analyze
python scripts/ab-test-engine.py --switch <name> --to variant|control
python scripts/ab-test-engine.py --restore <name>
```

## Workflow

### 1. Experiment anlegen
```bash
python scripts/ab-test-engine.py --create skill-loader-test "Vergleicht lazy vs eager Skill-Loader" --variant 'skill_loader=lazy,skill_cache_size=512'
```

### 2. Automatische Metrikerfassung
- `--collect` → alle 30 min (Cron-Job)
- Liest Cron-Exit-Codes, Dauer, RAM-Nutzung
- Bildet Composite Score aus Exit-Codes (60%), Dauer (30%), RAM (10%)

### 3. Statistische Analyse
```bash
python scripts/ab-test-engine.py --conclude skill-loader-test
```
- Welch's t-Test (ungleiche Varianzen)
- p-Wert + Cohen's d
- Winner-Empfehlung

### 4. Automation (Cron)

Im OpenAmer-Cron einrichten:

```yaml
- name: ab-test-collect
  schedule: "*/30 * * * *"
  command: python scripts/ab-test-engine.py --collect
  description: Sammelt A/B-Test-Metriken alle 30min

- name: ab-test-analyze
  schedule: "0 6 * * *"
  command: python scripts/ab-test-engine.py --analyze
  description: Analysiert abgelaufene A/B-Tests täglich 6 Uhr
```

## Fallstricke

- **Mindestens 3 Samples pro Gruppe** nötig für t-Test
- Bei < 2 Samples wird σ=0 gesetzt
- RAM-Messung ohne `psutil` ist ungenau (Fallback WMIC / fixed total)
- `--switch` verändert die aktive `config.yaml` direkt
- Cron-Log-Pfad: `$OPENAMER_HOME/cron/cron.log`
- Normalapproximation bei df > 100 für p-Wert
- Nutze `--restore` um Config auf Control-Zustand zurückzusetzen