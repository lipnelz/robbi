# SKILL.md — Compétences du bot Robbi

Ce fichier répertorie les compétences (skills) du bot Robbi. Chaque skill est documenté en détail dans un fichier dédié dans le répertoire [`.github/skills/`](.github/skills/).

## Liste des skills

| Skill | Commandes | Description |
|-------|-----------|-------------|
| [Surveillance du nœud Massa](.github/skills/node-monitoring.md) | `/node` | Statut temps réel du nœud, solde, rolls, graphique de validation |
| [Historique du solde](.github/skills/balance-history.md) | `/hist`, `/flush` | Persistance JSON, graphiques, effacement des logs |
| [Rapports planifiés](.github/skills/scheduled-reports.md) | *(automatique)* | Ping toutes les 60 min, rapports à 7h/12h/21h |
| [Prix des cryptomonnaies](.github/skills/crypto-prices.md) | `/btc`, `/mas` | Prix Bitcoin (API-Ninjas) et Massa/USDT (MEXC) |
| [Surveillance du système](.github/skills/system-monitoring.md) | `/hi`, `/temperature`, `/perf` | Métriques CPU/RAM/température, latence RPC, uptime |
| [Gestion Docker](.github/skills/docker-management.md) | `/docker` | Menu interactif : start/stop nœud, wallet_info, buy/sell rolls |
| [Authentification](.github/skills/authentication.md) | *(transversal)* | Décorateurs `@auth_required`, liste blanche `topology.json` |
