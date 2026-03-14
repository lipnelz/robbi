# Skill : Surveillance du nœud Massa

## Description

Ce skill permet de consulter l'état en temps réel du nœud Massa blockchain via la commande `/node`. Il interroge l'API JSON-RPC du nœud, affiche un résumé textuel et génère un graphique de validation.

## Commande

```
/node
```

## Sous-skills

### 1. Interrogation JSON-RPC

- Appelle `get_addresses(logger, massa_node_address)` depuis `services/massa_rpc.py`
- Envoie une requête POST à l'endpoint JSON-RPC du nœud Massa
- Gère les erreurs réseau (timeout, connexion refusée) et retourne un dict `{"error": "..."}` en cas d'échec

### 2. Extraction des données du nœud

- Fonction `extract_address_data(json_data)` dans `handlers/node.py`
- Extrait depuis la réponse JSON :
  - `final_balance` — solde courant du portefeuille (MAS)
  - `final_roll_count` — nombre de rolls détenus
  - `cycles` — liste des cycles de validation récents
  - `ok_counts` — nombre de validations réussies par cycle
  - `nok_counts` — nombre de validations échouées par cycle
  - `active_rolls` — rolls actifs par cycle
- Retourne `None` si le nœud est injoignable ou si les données sont invalides

### 3. Affichage du statut textuel

- Compose et envoie un message texte récapitulatif :
  ```
  Node status:
  Final Balance: <balance>
  Final Roll Count: <rolls>
  OK Counts: [...]
  NOK Counts: [...]
  Active Rolls: [...]
  ```

### 4. Enregistrement du snapshot de solde

- Appelle `make_time_key()` pour horodater l'entrée au format `YYYY/MM/DD-HH:MM`
- Appelle `build_balance_entry(balance, system_stats)` pour construire une entrée contenant :
  - le solde
  - la température CPU moyenne
  - l'utilisation RAM
- Écrit dans `balance_history` (protégé par un `threading.Lock`) puis sauvegarde via `save_balance_history()`

### 5. Génération du graphique de validation

- Appelle `create_png_plot(cycles, ok_counts, nok_counts, active_rolls)` depuis `services/plotting.py`
- Génère un graphique matplotlib (`plot.png`) affichant OK/NOK/ActiveRolls par cycle
- Envoie l'image en réponse, puis la supprime avec `safe_delete_file()`

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `src/handlers/node.py` | Handler `/node`, extraction des données |
| `src/services/massa_rpc.py` | Appel JSON-RPC Massa |
| `src/services/plotting.py` | Génération du graphique de validation |
| `src/services/history.py` | Snapshot horodaté du solde |
| `src/services/system_monitor.py` | Statistiques système pour le snapshot |

## Configuration requise

| Clé `topology.json` | Description |
|---------------------|-------------|
| `massa_node_address` | Adresse du portefeuille Massa pour le monitoring |

## Gestion des erreurs

- Timeout ou nœud injoignable → image d'erreur envoyée à l'utilisateur
- Données invalides → message texte d'erreur
- Échec de la génération du graphique → message d'erreur sans image
