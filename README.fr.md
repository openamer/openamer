# OpenAmer Agent

**OpenAmer est l'agent qui ne casse pas — et qui s'améliore de façon démontrable à l'usage.**

Il tourne sur votre propre machine, vous retrouve dans les canaux que vous utilisez déjà, et s'améliore à mesure que vous l'utilisez. Deux choses le distinguent :

1. **Il ne casse pas.** L'auto-mise à jour est durcie contre les modes de défaillance qui laissent d'autres agents à moitié installés — verrous de fichiers, installations interrompues, marqueurs de récupération obsolètes. L'agent vérifie avant d'affirmer et signale de vraies erreurs au lieu d'inventer des résultats.
2. **Il s'améliore de façon démontrable à l'usage.** La mémoire persiste entre les sessions, les compétences sont distillées à partir de tâches difficiles et affinées à la réutilisation, et l'essaim A2A partage des connaissances curées, signées et sans fuite entre les nœuds. Un apprentissage que vous pouvez observer, pas un slogan.

Utilisez n'importe quel modèle — OpenRouter, OpenAI, votre propre endpoint et [bien d'autres](https://github.com/openamer/openamer/blob/main/website/docs/integrations/providers). Changez avec `openamer model` — sans modification de code, sans verrouillage.

## Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| **Ne casse pas** | Auto-mise à jour durcie qui survit aux verrous de fichiers, aux installations interrompues et aux marqueurs de récupération obsolètes. L'agent vérifie avant d'affirmer et signale de vraies erreurs au lieu d'inventer des résultats. |
| **S'améliore de façon démontrable** | La mémoire persiste entre les sessions, les compétences sont distillées à partir de tâches difficiles et affinées à la réutilisation, et l'essaim A2A partage des connaissances curées, signées et sans fuite entre les nœuds. |
| **Une vraie interface terminal** | TUI complet avec édition multiligne, autocomplétion des commandes slash, historique de conversation, interruption-et-redirection et sortie d'outils en streaming en direct. |
| **Vit là où vous vivez** | Telegram, Discord, Slack, WhatsApp, Signal et CLI — une passerelle, une conversation qui vous suit sur chaque canal. Les mémos vocaux sont transcrits automatiquement. |
| **Automatisations planifiées** | Planificateur cron intégré avec livraison sur n'importe quelle plateforme. Décrivez un rapport quotidien, une sauvegarde nocturne ou un audit hebdomadaire en langage naturel et il s'exécute sans surveillance. |
| **Délègue et parallélise** | Lancez des sous-agents isolés pour des flux de travail parallèles, ou écrivez des scripts Python qui appellent des outils via RPC pour réduire des pipelines multi-étapes en un seul tour. |
| **Tourne partout, pas seulement sur votre portable** | Six backends de terminal — local, Docker, SSH, Singularity, Modal et Daytona. Daytona et Modal ajoutent une persistance serverless, pour que l'environnement de votre agent hiberne au repos et se réveille à la demande — presque sans coût entre les sessions. |
| **Privé par défaut** | Les numéros de téléphone, mots de passe, e-mails et numéros de carte sont expurgés avant tout stockage. Le système d'exploitation, le matériel et le modèle de votre nœud restent dans votre propre prompt système. |
| **Prêt pour la recherche** | Génération de trajectoires par lots et compression de trajectoires pour entraîner la prochaine génération de modèles appelant des outils. |

## Installation rapide

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.sh | bash
```

### Windows (natif, PowerShell)

```powershell
iex (irm https://raw.githubusercontent.com/openamer/openamer/main/scripts/install.ps1)
```

L'installateur s'occupe de tout : uv, Python 3.11, Node.js, ripgrep, ffmpeg et un Git Bash portable.

## Démarrage

```bash
openamer              # CLI interactif — démarrer une conversation
openamer model        # Choisir le fournisseur et le modèle de LLM
openamer tools        # Configurer les outils activés
openamer gateway      # Démarrer la passerelle de messagerie (Telegram, Discord, …)
openamer setup        # Exécuter l'assistant de configuration complet
openamer update       # Mettre à jour vers la dernière version
openamer doctor       # Diagnostiquer les problèmes
```

## Mise à jour

OpenAmer se maintient à jour automatiquement. À chaque lancement, il vérifie en arrière-plan si une version plus récente est disponible — si oui, le bandeau de bienvenue affiche `⚠ N commits de retard — exécutez 'openamer update'` directement dans le chat.

```bash
openamer update
```

## Documentation

La documentation complète se trouve dans **[OpenAmer Docs](https://github.com/openamer/openamer/blob/main/website/docs/)**.

## Communauté

- 💬 [Discord](https://discord.gg/openamer)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/openamer/openamer/issues)

## Licence

Apache License 2.0 — voir [LICENSE](LICENSE).
