# Skill : Historique du solde

## Description

Ce skill gère la persistance, la visualisation et l'effacement de l'historique des soldes Massa. Il comprend deux commandes interactives : `/hist` pour consulter l'historique sous forme de graphiques et de texte, et `/flush` pour effacer les logs et/ou l'historique.

## Commandes

```
/hist
/flush
```

---

## Sous-skills

### 1. Persistance JSON de l'historique (`services/history.py`)

- L'historique est stocké dans `config/balance_history.json` (volume Docker monté)
- **`save_balance_history(balance_history)`** — sérialise et écrit le dict en JSON
- **`make_time_key(dt=None)`** — génère une clé temporelle au format `YYYY/MM/DD-HH:MM`
- **`build_balance_entry(balance, system_stats)`** — construit une entrée dict contenant :
  - `balance` — solde MAS (float)
  - `temperature` — température CPU moyenne (float ou `null`)
  - `ram_percent` — pourcentage d'utilisation RAM (float ou `null`)
- Toutes les écritures dans `balance_history` sont protégées par un `threading.Lock` (`balance_lock` dans `bot_data`)

### 2. Filtrage de l'historique

- **`filter_last_24h(balance_history)`** — retourne les entrées des dernières 24 heures (fenêtre glissante)
- **`filter_since_midnight(balance_history)`** — retourne les entrées depuis minuit du jour courant
- **`get_entry_balance(entry)`** — extrait le solde d'une entrée (compatible formats ancien et nouveau)
- **`get_entry_temperature(entry)`** — extrait la température d'une entrée (retourne `None` si absente)
- **`format_history_entry(timestamp, entry)`** — formate une ligne d'historique : `HH:MM | balance MAS | temp°C | ram%`

### 3. Commande `/hist` — Graphique et résumé

#### Étape 1 : Menu de confirmation
- Affiche un message avec un clavier inline :
  - **Graph only** → génère uniquement les graphiques
  - **Graph + Text** → génère les graphiques et envoie également un résumé textuel
  - **Cancel** → annule et termine la conversation

#### Étape 2 : Génération des graphiques
- **`create_balance_history_plot(balance_history)`** — graphique matplotlib du solde dans le temps (`balance_history.png`)
- **`create_resources_plot(balance_history)`** — graphique matplotlib de la température CPU et RAM (`resources_plot.png`)
- Les deux images sont envoyées en réponse puis supprimées avec `safe_delete_file()`

#### Étape 3 (optionnel) : Résumé textuel
- Liste toutes les entrées de l'historique formatées par `format_history_entry()`
- Gère la limite de 4096 caractères des messages Telegram (découpe en plusieurs messages si nécessaire)

### 4. Commande `/flush` — Effacement des logs

#### Étape 1 : Menu de confirmation
- Affiche un clavier inline :
  - **Logs only** → supprime uniquement `bot_activity.log`
  - **Logs + History** → supprime le log ET vide `balance_history.json`
  - **Cancel** → annule sans rien supprimer

#### Étape 2 : Exécution de l'effacement
- Efface le fichier `bot_activity.log` (chemin : `config/LOG_FILE_NAME`)
- Si « Logs + History » sélectionné : vide `balance_history` en mémoire et sur disque, puis recrée un fichier JSON vide

### 5. Formats de clés temporelles (rétrocompatibilité)

- Format actuel : `YYYY/MM/DD-HH:MM` (ex. `2024/03/15-14:30`)
- Format legacy : `DD/MM-HH:MM` (ex. `15/03-14:30`) — encore lisible par les filtres pour les anciennes données

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `src/handlers/node.py` | Handlers `/hist` et `/flush` (ConversationHandler) |
| `src/services/history.py` | Persistance, filtrage et formatage de l'historique |
| `src/services/plotting.py` | Génération des graphiques solde et ressources |
| `src/handlers/common.py` | `safe_delete_file()`, `cb_auth_required` |

## Fichiers générés

| Fichier | Description | Cycle de vie |
|---------|-------------|--------------|
| `config/balance_history.json` | Snapshots horodatés du solde | Persistant (volume Docker) |
| `balance_history.png` | Graphique du solde | Temporaire, supprimé après envoi |
| `resources_plot.png` | Graphique CPU / RAM | Temporaire, supprimé après envoi |
| `bot_activity.log` | Journal d'activité du bot | Persistant, effaçable via `/flush` |

## Gestion des erreurs

- Historique vide → message informatif sans graphique
- Échec de génération de graphique → message d'erreur
- Fichier log absent → ignore l'erreur silencieusement
