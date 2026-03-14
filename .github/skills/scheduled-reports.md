# Skill : Rapports planifiés automatiques

## Description

Ce skill gère les vérifications périodiques du nœud Massa et l'envoi automatique de rapports de statut. Un job tourne toutes les 60 minutes pour contrôler l'état du nœud, enregistrer un snapshot du solde, et envoyer un rapport détaillé aux heures planifiées.

## Déclencheurs

- **Ping périodique** : toutes les 60 minutes (APScheduler, `interval`)
- **Rapports automatiques** : aux heures 7h, 12h et 21h si le nœud est actif

---

## Sous-skills

### 1. Initialisation du scheduler (`run_async_func`)

- Crée ou réutilise la boucle `asyncio` (compatible environnements avec boucle déjà active)
- Initialise un `BackgroundScheduler` (APScheduler)
- Supprime un éventuel job obsolète portant le même ID (`JOB_SCHED_NAME`)
- Enregistre `periodic_node_ping` avec un intervalle de 60 minutes
- Démarre le scheduler si ce n'est pas déjà le cas

### 2. Pont async/sync (`run_coroutine_in_loop`)

- Permet d'exécuter une coroutine `asyncio` depuis un thread synchrone (celui du scheduler)
- Si la boucle est active : utilise `asyncio.run_coroutine_threadsafe()` (thread-safe)
- Si la boucle est inactive : utilise `loop.run_until_complete()`
- Les exceptions non gérées dans la coroutine sont loguées via un callback `add_done_callback`

### 3. Ping périodique du nœud (`periodic_node_ping`)

#### 3a. Vérification du statut
- Appelle `get_addresses(logger, massa_node_address)` pour interroger le nœud
- En cas d'erreur :
  - Timeout → envoie une image dédiée `TIMEOUT_NAME` à tous les utilisateurs autorisés
  - Autre erreur → envoie une image d'erreur `TIMEOUT_FIRE_NAME`
  - Retour anticipé sans enregistrement de snapshot

#### 3b. Détermination de l'état du nœud
- Le nœud est considéré **inactif** si :
  - au moins un `nok_count` est non nul, **OU**
  - `final_roll_count == 0`
- Alerte immédiate (`NODE_IS_DOWN`) envoyée à tous les utilisateurs si le nœud est inactif

#### 3c. Enregistrement du snapshot
- Appelle `get_system_stats(logger)` pour collecter température CPU et RAM
- Crée la clé temporelle avec `make_time_key(now)`
- Construit l'entrée avec `build_balance_entry(balance, system_stats)`
- Écrit dans `balance_history` en utilisant `balance_lock` (thread-safe) et sauvegarde sur disque

### 4. Rapport de statut aux heures planifiées (7h, 12h, 21h)

Envoyé uniquement si le nœud est actif (`node_is_up == True`) et si `balance_history` n'est pas vide.

#### Composition du rapport

| Section | Contenu |
|---------|---------|
| **Indicateur** | `NODE_IS_UP` |
| **Comparaison de solde** | Premier solde depuis minuit (ou fenêtre 24h) vs solde courant |
| **Variation** | Montant et pourcentage avec indicateur 📈/📉 |
| **Température moyenne** | Moyenne CPU sur 24h glissantes (si données disponibles) |
| **Historique 24h** | Liste formatée de toutes les entrées des dernières 24 heures |

#### Logique de référence du solde

1. Priorité : premier enregistrement **depuis minuit** (`filter_since_midnight`)
2. Repli : première entrée de la **fenêtre glissante 24h** (`filter_last_24h`)
3. Dernier cas : solde à 0 si aucune donnée disponible

#### Calcul de la variation
```
balance_change = solde_courant - solde_reference_24h
change_percent = (balance_change / solde_reference_24h) * 100
```

### 5. Diffusion aux utilisateurs

- Parcourt `allowed_user_ids` (set stocké dans `application.bot_data`)
- Utilise `application.bot.send_message(chat_id=user_id, text=...)` pour chaque utilisateur autorisé
- Pour les erreurs avec image : utilise `application.bot.send_photo()` avec ouverture du fichier

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `src/handlers/scheduler.py` | Scheduler, ping périodique, rapports automatiques |
| `src/services/massa_rpc.py` | Interrogation JSON-RPC du nœud |
| `src/services/history.py` | Snapshots, filtrage 24h, formatage des entrées |
| `src/services/system_monitor.py` | Statistiques CPU/RAM pour les snapshots |
| `src/main.py` | Appel de `run_async_func()` au démarrage du bot |

## Configuration requise

| Clé `topology.json` | Description |
|---------------------|-------------|
| `massa_node_address` | Adresse Massa pour les requêtes JSON-RPC |
| `user_white_list` | Liste des utilisateurs à notifier |

## Constantes (`config.py`)

| Constante | Valeur | Description |
|-----------|--------|-------------|
| `JOB_SCHED_NAME` | `"node_ping_job"` | Identifiant du job APScheduler |
| `NODE_IS_UP` | `"✅ Node is up"` | Message de statut nœud actif |
| `NODE_IS_DOWN` | `"❌ Node is down"` | Message d'alerte nœud inactif |
| `TIMEOUT_NAME` | `"timeout.png"` | Image pour les timeouts |
| `TIMEOUT_FIRE_NAME` | `"timeout_fire.png"` | Image pour les erreurs critiques |
