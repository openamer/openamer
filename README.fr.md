# OpenAmer Agent

**L'agent IA auto-améliorant — apprendre de l'expérience, créer des compétences, se souvenir de vos préférences, et travailler pour vous n'importe où.**

**Traduire en français**

Veuillez utiliser le modèle de votre choix, tel que OpenRouter, OpenAI, DeepSeek, etc. Vous pouvez changer de modèle en utilisant la commande `openamer model`.

## **Fonctionnalités**

- ****Interface de terminal réelle — TUI complète avec autocomplétion, historique et sortie en streaming****
- **Vivez où vous habitez — Telegram, Discord, Slack, WhatsApp et plus d'un seul point d'accès**
- **Apprend sur le long terme — mémoire, compétences auto-améliorantes, rappel inter-sessions**
- **Déléguer & paralléliser — lancer des sous-agents pour un travail parallèle**
- **Automatisations planifiées — cron intégré pour les rapports quotidiens, les sauvegardes, les audits**
- **Exécute n'importe où — local, Docker, SSH, cloud, sans serveur.**

## Installation Rapide

Windows (PowerShell)
```powershell
iex (irm https://github.com/openamer/openamer/raw/main/scripts/install.ps1)
```

Linux / macOS :
```bash
curl -fsSL https://github.com/openamer/openamer/raw/main/scripts/install.sh | bash
```

## **Commencer**

```bash
openamer              # Commencez à discuter.
openamer setup        # **Établir vos clés API & fournisseur**

Pour utiliser les API, vous devez d'abord vous assurer d'avoir créé un compte auprès du fournisseur de l'API que vous souhaitez utiliser. Voici les étapes générales à suivre :

1. **Choisissez un fournisseur d'API** : recherchez un fournisseur d'API qui offre les fonctionnalités dont vous avez besoin. Certains fournisseurs populaires incluent [Google Cloud](https://cloud.google.com/), [Microsoft Azure](https://azure.microsoft.com/fr-fr/), [Amazon Web Services (AWS)](https://aws.amazon.com/fr/), etc.
2. **Créez un compte** : rendez-vous sur le site web du fournisseur d'API et créez un compte en suivant les instructions fournies. Vous devrez généralement fournir des informations personnelles, telles que votre nom, votre adresse e-mail et un mot de passe.
3. **Générez vos clés API** : une fois votre compte créé, vous devrez généralement générer des clés API pour accéder aux API. Ces clés sont généralement composées de deux parties : une clé API publique et une clé API privée. La clé API publique est utilisée pour identifier votre compte, tandis que la clé API privée est utilisée pour authentifier les requêtes.
4. **Configurez vos clés API** : une fois que vous avez généré vos clés API, vous devrez les configurer pour utiliser les API. Cela peut impliquer de copier et de coller les clés dans votre code, ou d'utiliser un gestionnaire de clés API pour les stocker de manière sécurisée.
5. **Testez vos clés API** : avant de les utiliser dans votre application
openamer model        # **Modèle de traduction**

Je propose trois options de modèles de traduction :

1. **Modèle de base** : Ce modèle est conçu pour traduire du texte simple et clair. Il est adapté pour les textes courts et les phrases simples.
2. **Modèle avancé** : Ce modèle est conçu pour traduire du texte plus complexe et technique. Il est adapté pour les textes longs et les phrases complexes.
3. **Modèle neural** : Ce modèle utilise des réseaux de neurones pour traduire du texte. Il est adapté pour les textes longs et les phrases complexes, et peut également apprendre des modèles linguistiques.

**Choisissez votre modèle de traduction :**

1. [Modèle de base](#modele-de-base)
2. [Modèle avancé](#modele-avance)
3. [Modèle neural](#modele-neural)
openamer update       # Mise à jour vers la dernière version.
```

## Mise à jour

OpenAmer vérifie automatiquement les mises à jour et affiche un avertissement dans le bandeau d'accueil. Exécutez openamer update pour obtenir la dernière version — elle sauvegarde d'abord vos données.

## **Contribuer**

Les contributions sont les bienvenues — ouvrez les problèmes, soumettez des demandes de tirage, ou rejoignez la communauté.

## Licence

Licence Apache 2.0. Voir {LICENSE}.
