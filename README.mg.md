# OpenAmer Agent

**Ilay agent AI mianatra hatrany — mianatra avy amin'ny traikefa, mamorona fahaizana, mahatadidy ny safidinao, ary miasa ho anao na aiza na aiza.**

Ampiasao izay modelina tianao — OpenRouter, OpenAI, DeepSeek, ary ny hafa. Mifindra amin'ny alalan'ny `openamer model` — tsy mila manova kaody.

## Ireo mampiavaka azy

- **Interface terminal tena izy — TUI feno misy autocomplete, tantara (history), ary fampisehoana mivantana ny vokatry ny fitaovana (streaming tool output)**
- **Ao amin'izay misy anao — Telegram, Discord, Slack, WhatsApp ary maro hafa avy amin'ny vavahady iray**
- **Mianatra miandalana — fitadidiana, fahaizana mivoatra hatrany, fampahatsiahivana avy amin'ny session teo aloha**
- **Manome andraikitra & mampifandanja — mamorona sub-agents hiasa miaraka (parallel)**
- **Automations voatondro fotoana — cron anaty ho an'ny tatitra isan'andro, backup, ary fanaraha-maso (audits)**
- **Mandeha na aiza na aiza — eo an-toerana, Docker, SSH, cloud, serverless**

## Fametrahana Haingana

Windows (PowerShell):
```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

Linux / macOS:
```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

## Fidirana voalohany

```bash
openamer              # Atombohy ny firesahana
openamer setup        # Ampidiro ny lakilen'ny API-nao sy ny mpanome serivisy (provider)
openamer model        # Safidio ny modelinao
openamer update       # Havaozy ho amin'ny dikan-teny farany
```

## Fanavaozana

Manao fanamarinana fanavaozana ho azy ny OpenAmer ary mampiseho fampitandrema ao amin'ny sora-pialonana (welcome banner). Alefaso ny `openamer update` mba hahazoana ny kinova farany — manao kopia fiarovana (backup) ny angon-drakitrao aloha izy.

## Fandraisana anjara

Sokafana ho an'ny rehetra ny fandraisana anjara — manokafana "issues", mandefa "pull requests", na miditra ao amin'ny vondrom-piarahamonina.

## Zakana

Apache License 2.0. Jereo ny {LICENSE}.
