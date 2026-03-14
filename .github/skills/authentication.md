# Skill : Authentification des utilisateurs

## Description

Ce skill contrôle l'accès à toutes les commandes du bot. Seuls les utilisateurs présents dans la liste blanche définie dans `topology.json` peuvent utiliser les fonctionnalités du bot. L'authentification est implémentée via des décorateurs Python appliqués aux handlers.

---

## Sous-skills

### 1. Décorateur `@auth_required` (handlers de commandes)

Fichier : `src/handlers/common.py`

```python
@auth_required
async def node(update: Update, context: CallbackContext) -> None:
    ...
```

**Fonctionnement :**
1. Extrait `user_id = str(update.effective_user.id)`
2. Lit la liste blanche depuis `context.bot_data['allowed_user_ids']` (un `set` de strings)
3. Si l'utilisateur **n'est pas** dans la liste :
   - Envoie "You are not authorized to use this bot."
   - Retourne `None` sans exécuter la fonction décorée
4. Si l'utilisateur **est** dans la liste : appelle la fonction handler normalement

**Commandes concernées :** `/node`, `/btc`, `/mas`, `/hi`, `/temperature`, `/perf`

---

### 2. Décorateur `@cb_auth_required` (handlers de callback query)

Fichier : `src/handlers/common.py`

```python
@cb_auth_required
async def flush_confirm_yes(update: Update, context: CallbackContext) -> int:
    ...
```

**Spécificité :** Utilisé pour les callbacks des boutons inline (réponses aux claviers interactifs). Contrairement à `@auth_required`, il :
1. Extrait le `user_id` depuis `query.from_user.id` (et non `update.effective_user.id`)
2. En cas de refus : appelle `query.answer("Access denied.", show_alert=True)` (alerte popup)
3. Retourne `ConversationHandler.END` pour terminer proprement la conversation

**Callbacks concernées :** `flush_confirm_yes/no`, `hist_confirm_yes/no`, `docker_start/stop`, `docker_*_confirm`, `massa_*`

---

### 3. Vérification manuelle dans les ConversationHandlers

Les points d'entrée des `ConversationHandler` ne peuvent pas utiliser `@auth_required` car ils doivent retourner un entier (état de la conversation) et non `None`.

```python
async def flush(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())
    if user_id not in allowed_user_ids:
        await update.message.reply_text("Access denied. You are not authorized.")
        return ConversationHandler.END
    ...
```

**Commandes concernées :** `/flush`, `/hist`, `/docker`

---

### 4. Chargement de la liste blanche

Fichier : `src/main.py`

Au démarrage, la liste blanche est construite depuis `topology.json` :

```python
admin_id = config.get('user_white_list', {}).get('admin')
allowed_user_ids = {str(admin_id)}
```

- La valeur est un `set` de strings (IDs Telegram sous forme de chaîne)
- Le set est stocké dans `application.bot_data['allowed_user_ids']`
- Tous les handlers y accèdent via `context.bot_data.get('allowed_user_ids', set())`
- Actuellement, seul le rôle `admin` est supporté (un seul utilisateur autorisé)

---

### 5. Gestion des erreurs API (`handle_api_error`)

Fichier : `src/handlers/common.py`

Bien que non directement lié à l'authentification, cette fonction sécurise les réponses des APIs externes :

```python
async def handle_api_error(update: Update, error_data: dict) -> bool
```

- Reçoit le dict retourné par une fonction API
- Si `"error"` est présent dans le dict :
  - Timeout → envoie l'image `TIMEOUT_NAME`
  - Autre erreur → envoie l'image `TIMEOUT_FIRE_NAME`
  - Retourne `True` (erreur gérée, le handler doit s'arrêter)
- Si pas d'erreur → retourne `False` (le handler peut continuer)

---

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `src/handlers/common.py` | Décorateurs `auth_required`, `cb_auth_required`, `handle_api_error` |
| `src/main.py` | Chargement de `allowed_user_ids` depuis `topology.json` |

## Configuration requise

| Clé `topology.json` | Description |
|---------------------|-------------|
| `user_white_list.admin` | ID Telegram de l'administrateur autorisé |

## Exemple `topology.json`

```json
{
    "user_white_list": {
        "admin": "123456789"
    }
}
```

## Sécurité

- L'ID utilisateur est toujours converti en `str` avant comparaison (évite les erreurs de type int/str)
- La liste blanche est initialisée à `set()` par défaut (aucune autorisation si non configuré)
- La vérification s'effectue à chaque appel de handler (pas de cache de session)
