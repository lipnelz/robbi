# Skill : Gestion Docker du nœud Massa

## Description

Ce skill permet de contrôler le conteneur Docker du nœud Massa directement depuis le bot, via la commande interactive `/docker`. Il utilise le SDK Python Docker (communication par socket Unix), sans nécessiter le CLI Docker dans le conteneur du bot.

## Commande

```
/docker
```

---

## Architecture du menu interactif

```
/docker
└── 🐳 Docker Node Management
      ├── ▶️  Start  → ⚠️ Confirmation → Démarrage du conteneur
      ├── ⏹️  Stop   → ⚠️ Confirmation → Arrêt du conteneur
      └── 💻 Massa Client
            ├── 💰 Wallet Info   → Exécution de wallet_info
            ├── 🎲 Buy Rolls     → Saisie du nombre → ⚠️ Confirmation → Exécution de buy_rolls
            ├── 💸 Sell Rolls    → Saisie du nombre → ⚠️ Confirmation → Exécution de sell_rolls
            └── ⬅️  Back         → Retour au menu principal
```

---

## Sous-skills

### 1. Point d'entrée — `/docker`

- Vérification manuelle de l'authentification (ConversationHandler ne permet pas `@auth_required`)
- Affiche le menu principal avec un clavier inline (Start / Stop / Massa Client)
- Retourne l'état `DOCKER_MENU_STATE`

### 2. Démarrage du conteneur (`docker_start` → `docker_start_confirm`)

- **Étape 1** : Demande de confirmation : "⚠️ Are you sure you want to start the node container?"
  - **Yes** → passe à `DOCKER_START_CONFIRM_STATE`
  - **No** → annule et termine la conversation

- **Étape 2** : Exécution de `start_docker_node(logger, container_name)` :
  ```python
  client = docker.from_env()
  container = client.containers.get(container_name)
  container.start()
  ```
  - Succès → message "✅ Container '<name>' started."
  - Échec → message "❌ Error: <détail>"

### 3. Arrêt du conteneur (`docker_stop` → `docker_stop_confirm`)

- **Étape 1** : Demande de confirmation : "⚠️ Are you sure you want to stop the node container?"
  - **Yes** → passe à `DOCKER_STOP_CONFIRM_STATE`
  - **No** → annule et termine la conversation

- **Étape 2** : Exécution de `stop_docker_node(logger, container_name)` :
  ```python
  client = docker.from_env()
  container = client.containers.get(container_name)
  container.stop(timeout=30)
  ```
  - Succès → message "✅ Container '<name>' stopped."
  - Délai d'arrêt : 30 secondes (grace period)

### 4. Menu Massa Client (`docker_massa`)

Sous-menu accessible depuis le menu principal. Présente trois actions :

| Bouton | Commande massa-client | Description |
|--------|----------------------|-------------|
| 💰 Wallet Info | `wallet_info` | Affiche les informations du portefeuille |
| 🎲 Buy Rolls | `buy_rolls <count> <addr> <fee>` | Achète des rolls (avec saisie + confirmation) |
| 💸 Sell Rolls | `sell_rolls <count> <addr> <fee>` | Vend des rolls (avec saisie + confirmation) |

### 5. Wallet Info (`docker_massa_wallet_info`)

- Appelle directement `exec_massa_client(logger, container_name, password, "wallet_info")`
- Affiche la sortie brute de la commande dans le message bot
- Aucune confirmation requise

### 6. Buy Rolls / Sell Rolls (flux en 3 étapes)

**Étape 1 — Saisie du nombre de rolls** (état `DOCKER_BUYROLLS_INPUT_STATE` / `DOCKER_SELLROLLS_INPUT_STATE`)
- L'utilisateur envoie un message texte avec le nombre de rolls
- Validation : doit être un entier > 0
- Le nombre est stocké dans `context.user_data['rolls_count']`

**Étape 2 — Confirmation** (état `DOCKER_BUYROLLS_CONFIRM_STATE` / `DOCKER_SELLROLLS_CONFIRM_STATE`)
- Affiche "⚠️ Confirm: <action> <N> rolls?"
- **Yes** → exécution ; **No** → annulation

**Étape 3 — Exécution** via `exec_massa_client` :
```python
# Buy Rolls
cmd = f"buy_rolls {wallet_address} {rolls_count} {buy_rolls_fee}"

# Sell Rolls
cmd = f"sell_rolls {wallet_address} {rolls_count} {buy_rolls_fee}"
```

### 7. Exécution de commandes massa-client (`services/docker_manager.py`)

Fonction `exec_massa_client(logger, container_name, password, command)` :

```python
client = docker.from_env()
container = client.containers.get(container_name)
cmd = ['./massa-client', '-p', password, '-a'] + command.split()
exit_code, output = container.exec_run(cmd, workdir='/massa/massa-client')
```

- Décode la sortie en UTF-8 (erreurs remplacées)
- Envoie une commande `exit` après l'exécution pour fermer proprement la session
- Code de retour 0 → succès (`{"status": "ok", "output": ...}`)
- Code de retour non-nul → échec (`{"status": "error", "message": ...}`)

### 8. Annulation et navigation

- `docker_cancel` : annule l'action en cours, retourne au menu principal ou termine la conversation
- `docker_back` : retourne au menu Massa Client depuis un sous-menu
- Bouton "⬅️ Back" dans le menu Massa Client : retour au menu Docker principal

---

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `src/handlers/node.py` | Handlers du menu `/docker` et toutes les callbacks |
| `src/services/docker_manager.py` | Fonctions SDK Docker (start, stop, exec) |
| `src/config.py` | États de la conversation Docker (`DOCKER_*_STATE`) |

## Configuration requise

| Clé `topology.json` | Description |
|---------------------|-------------|
| `docker_container_name` | Nom du conteneur Docker (ex. `massa-container`) |
| `massa_client_password` | Mot de passe pour `./massa-client -p` |
| `massa_wallet_address` | Adresse du portefeuille pour buy/sell rolls |
| `massa_buy_rolls_fee` | Frais de transaction (ex. `0.01`) |

## Prérequis Docker

Le conteneur du bot doit avoir accès au socket Docker :

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

> Le package Python `docker` est requis (pas le CLI Docker).

## Gestion des erreurs

- Nom du conteneur non configuré → message d'erreur explicite
- Conteneur inexistant → propagation de l'exception Docker SDK
- Commande massa-client échouée → affichage de la sortie d'erreur
- Saisie invalide (rolls) → message de correction et nouvelle demande
