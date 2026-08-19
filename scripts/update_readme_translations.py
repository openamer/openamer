"""Update all 7 language READMEs with new feature rows (self-modify, plugins search, brain data)."""

import os
import re

# New rows in each language, keyed by language code.
ROWS = {
    "de": (
        '| **Selbst-Modifikation mit Test-Gate** — Kern-Code, Skills oder Plugins ändern; bei Fehlschlag automatischer Rollback | `scripts/self_modify.py` + Skill |',
        '| **Plugin-Entdeckung** — GitHub nach Community-Plugins durchsuchen | `openamer plugins search` |',
        '| **Brain-Datensammlung** — Aktivität, Gedanken & Tools → lokaler Trainingsdatensatz | **automatisch** — Daemon startet mit jedem `openamer`-Aufruf, exportiert jede Sitzung innerhalb von 60s |',
    ),
    "es": (
        '| **Auto-modificación con compuerta de prueba** — modificar código central, skills o plugins; revertido automáticamente si falla | `scripts/self_modify.py` + Skill |',
        '| **Descubrimiento de plugins** — buscar plugins de la comunidad en GitHub | `openamer plugins search` |',
        '| **Recopilación de datos Brain** — actividad, pensamientos y herramientas → conjunto de datos de entrenamiento local | **automático** — el daemon se inicia con cada invocación de `openamer`, exporta cada sesión en 60s |',
    ),
    "fr": (
        "| **Auto-modification avec test gate** — modifier le code central, les skills ou les plugins ; restauration automatique en cas d'échec | `scripts/self_modify.py` + Skill |",
        "| **Découverte de plugins** — rechercher des plugins communautaires sur GitHub | `openamer plugins search` |",
        "| **Collecte de données Brain** — activité, pensées et outils → jeu de données d'entraînement local | **automatique** — le daemon démarre avec chaque invocation `openamer`, exporte chaque session en 60s |",
    ),
    "ja": (
        "| **テストゲート付き自己修正** — コアコード、スキル、プラグインを変更、失敗時に自動ロールバック | `scripts/self_modify.py` + Skill |",
        "| **プラグイン検出** — GitHubでコミュニティプラグインを検索 | `openamer plugins search` |",
        "| **Brainデータ収集** — アクティビティ、思考、ツール → ローカルトレーニングデータセット | **自動** — `openamer`起動時にデーモンが開始、各セッションを60秒以内にエクスポート |",
    ),
    "pt": (
        "| **Auto-modificação com gate de teste** — alterar código central, skills ou plugins; reversão automática se falhar | `scripts/self_modify.py` + Skill |",
        "| **Descoberta de plugins** — pesquisar plugins da comunidade no GitHub | `openamer plugins search` |",
        "| **Coleta de dados Brain** — atividade, pensamentos e ferramentas → conjunto de dados de treinamento local | **automática** — daemon inicia com cada invocação `openamer`, exporta cada sessão em 60s |",
    ),
    "ru": (
        "| **Само-модификация с тестовым шлюзом** — изменение core-кода, навыков или плагинов; автоматический откат при сбое | `scripts/self_modify.py` + Skill |",
        "| **Поиск плагинов** — поиск плагинов сообщества на GitHub | `openamer plugins search` |",
        "| **Сбор данных Brain** — активность, мысли и инструменты → локальный тренировочный набор данных | **автоматически** — демон запускается с каждым вызовом `openamer`, экспортирует каждую сессию в течение 60с |",
    ),
    "zh": (
        "| **带测试门的自我修改** — 修改核心代码、技能或插件；失败时自动回滚 | `scripts/self_modify.py` + Skill |",
        "| **插件发现** — 在GitHub上搜索社区插件 | `openamer plugins search` |",
        "| **Brain数据收集** — 活动、思考和工具 → 本地训练数据集 | **自动** — 守护进程随每次`openamer`调用启动，60秒内导出每个会话 |",
    ),
}

# Marker strings to find the insertion point (the last feature row before the "Research-ready" equivalent).
# Ordered by language; the first match wins.
MARKERS = {
    "de": "Forschungsbereit",
    "es": "Listo para investigación",
    "fr": "Prêt pour la recherche",
    "ja": "研究対応",
    "pt": "Pronto para pesquisa",
    "ru": "Готово к исследованиям",
    "zh": "研究就绪",
}

HERE = os.path.dirname(os.path.abspath(__file__))  # scripts/
ROOT = os.path.dirname(HERE)  # repo root (one level up from scripts/)

for code, rows in ROWS.items():
    path = os.path.join(ROOT, f"README.{code}.md")
    if not os.path.exists(path):
        print(f"  {path}: not found, skipping")
        continue

    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Find the "Research-ready" equivalent line.
    marker = MARKERS.get(code)
    if marker not in content:
        print(f"  README.{code}.md: marker '{marker}' not found, skipping")
        continue

    # Find the end of the research-ready line and insert the new rows after it.
    idx = content.index(marker)
    # Find the end of this table row (the \n after the line).
    eol = content.index("\n", idx)
    # Find the next \n (to insert after the full row).
    next_eol = content.index("\n", eol + 1)
    insert_pos = next_eol + 1

    new_rows = rows[0] + "\n" + rows[1] + "\n"
    content = content[:insert_pos] + "\n" + new_rows + content[insert_pos:]

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  README.{code}.md: updated (self-modify + plugins search added)")