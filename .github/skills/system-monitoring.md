# Skill : Surveillance du système

## Description

Ce skill expose trois commandes pour surveiller l'état de la machine hébergeant le bot et le nœud Massa : `/hi` pour une salutation avec version, `/temperature` pour les métriques système détaillées, et `/perf` pour la performance du nœud (latence RPC et uptime).

## Commandes

```
/hi
/temperature
/perf
```

---

## Sous-skills

### 1. Salutation — `/hi`

- Envoie un message de bienvenue avec la version courante du bot :
  ```
  Hey dude! (version: a1b2c3d)
  ```
- Récupère le hash court du commit git courant via `subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'])`
- En cas d'échec de la commande git → affiche `unknown` comme version
- Envoie une image de mascotte (`BUDDY_FILE_NAME` défini dans `config.py`)

---

### 2. Statistiques système — `/temperature`

#### Collecte des données (`services/system_monitor.py`)
- Appelle `get_system_stats(logger)` qui utilise la bibliothèque `psutil`
- Retourne un dict contenant :

| Clé | Type | Description |
|-----|------|-------------|
| `temperature_details` | list | Détails par capteur : `sensor`, `label`, `current` (°C) |
| `temperature_avg` | float | Température CPU moyenne (°C) |
| `cpu_percent` | float | Utilisation CPU globale (%) |
| `cpu_cores` | list | Utilisation par cœur : `core`, `percent` |
| `ram_percent` | float | Utilisation RAM (%) |
| `ram_available_gb` | float | RAM disponible (Go) |
| `ram_total_gb` | float | RAM totale (Go) |

> **Note** : `temperature_details` et `temperature_avg` ne sont disponibles que sur Linux (via `psutil.sensors_temperatures()`). Sur les systèmes sans capteurs, ces clés sont absentes.

#### Format de la réponse bot
```
🌡️ System Status
-----------
🌡️ Temperatures:
  coretemp Physical id 0: 45.0°C
  coretemp Core 0: 43.0°C
  ...
  Average: 44.5°C
-----------
CPU Usage Global: 12.3%
-----------
CPU Cores:
  Core 0: 10.5%
  Core 1: 14.1%
  ...
-----------
RAM Usage: 67.2%
RAM Available: 5.2 GB / 15.6 GB
```

---

### 3. Performance du nœud — `/perf`

#### 3a. Latence RPC (`services/massa_rpc.py`)
- Appelle `measure_rpc_latency(logger, massa_node_address)`
- Effectue une requête JSON-RPC minimaliste et mesure le temps de réponse
- Retourne `{"latency_ms": 42}` ou `{"error": "..."}` en cas d'échec

#### 3b. Calcul de l'uptime (24h)
- Fonction `_calculate_uptime(balance_history)` dans `handlers/system.py`
- Compte les entrées de `balance_history` présentes dans la fenêtre des dernières 24 heures
- Hypothèse : 1 entrée par heure = 24 entrées → 100% d'uptime
- `uptime = min((entrées_24h / 24) * 100, 100.0)`, arrondi à 1 décimale

#### 3c. Parsing des clés temporelles
- Fonction `_is_recent(key, cutoff, now)` — supporte deux formats :
  - Format actuel : `YYYY/MM/DD-HH:MM`
  - Format legacy : `DD/MM-HH:MM` (rétrocompatibilité avec les anciennes données)
- Si la date reconstruite semble dans le futur (à cause de l'absence d'année), recule d'un an

#### Format de la réponse bot
```
⚡ Node Performance
-----------
RPC Latency: 42 ms
Uptime (24h): 95.8%
```

---

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `src/handlers/system.py` | Handlers `/hi`, `/temperature`, `/perf`, calcul uptime |
| `src/services/system_monitor.py` | Collecte des métriques système via psutil |
| `src/services/massa_rpc.py` | Mesure de la latence RPC |
| `src/config.py` | Constante `BUDDY_FILE_NAME` |

## Configuration requise

| Clé `topology.json` | Description |
|---------------------|-------------|
| `massa_node_address` | Adresse Massa pour la mesure de latence RPC |

## Gestion des erreurs

- Échec `get_system_stats` → message d'erreur avec le détail
- Échec `measure_rpc_latency` → message d'erreur avec le détail
- Absence de capteurs de température → section température omise du message
