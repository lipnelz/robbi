# Skill: User Authentication

## Description

This skill controls access to all bot commands. Only users present in the whitelist defined in `topology.json` can use the bot's features. Authentication is implemented via Python decorators applied to handlers.

---

## Sub-skills

### 1. `@auth_required` Decorator (Command Handlers)

File: `src/handlers/common.py`

```python
@auth_required
async def node(update: Update, context: CallbackContext) -> None:
    ...
```

**How it works:**
1. Extracts `user_id = str(update.effective_user.id)`
2. Reads the whitelist from `context.bot_data['allowed_user_ids']` (a `set` of strings)
3. If the user **is not** in the list:
   - Sends "You are not authorized to use this bot."
   - Returns `None` without executing the decorated function
4. If the user **is** in the list: calls the handler function normally

**Commands covered:** `/node`, `/btc`, `/mas`, `/hi`, `/temperature`, `/perf`

---

### 2. `@cb_auth_required` Decorator (Callback Query Handlers)

File: `src/handlers/common.py`

```python
@cb_auth_required
async def flush_confirm_yes(update: Update, context: CallbackContext) -> int:
    ...
```

**Specificity:** Used for inline button callbacks (responses to interactive keyboards). Unlike `@auth_required`, it:
1. Extracts the `user_id` from `query.from_user.id` (not `update.effective_user.id`)
2. On denial: calls `query.answer("Access denied.", show_alert=True)` (popup alert)
3. Returns `ConversationHandler.END` to cleanly terminate the conversation

**Callbacks covered:** `flush_confirm_yes/no`, `hist_confirm_yes/no`, `docker_start/stop`, `docker_*_confirm`, `massa_*`

---

### 3. Manual Check in ConversationHandlers

ConversationHandler entry points cannot use `@auth_required` because they must return an integer (conversation state) rather than `None`.

```python
async def flush(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())
    if user_id not in allowed_user_ids:
        await update.message.reply_text("Access denied. You are not authorized.")
        return ConversationHandler.END
    ...
```

**Commands covered:** `/flush`, `/hist`, `/docker`

---

### 4. Whitelist Loading

File: `src/main.py`

At startup, the whitelist is built from `topology.json`:

```python
admin_id = config.get('user_white_list', {}).get('admin')
allowed_user_ids = {str(admin_id)}
```

- The value is a `set` of strings (Telegram IDs as strings)
- The set is stored in `application.bot_data['allowed_user_ids']`
- All handlers access it via `context.bot_data.get('allowed_user_ids', set())`
- Currently, only the `admin` role is supported (single authorized user)

---

### 5. API Error Handling (`handle_api_error`)

File: `src/handlers/common.py`

Although not directly related to authentication, this function secures external API responses:

```python
async def handle_api_error(update: Update, error_data: dict) -> bool
```

- Receives the dict returned by an API function
- If `"error"` is present in the dict:
  - Timeout → sends the `TIMEOUT_NAME` image
  - Other error → sends the `TIMEOUT_FIRE_NAME` image
  - Returns `True` (error handled, handler should stop)
- If no error → returns `False` (handler can continue)

---

## Related Files

| File | Role |
|------|------|
| `src/handlers/common.py` | `auth_required`, `cb_auth_required`, `handle_api_error` decorators |
| `src/main.py` | Loading `allowed_user_ids` from `topology.json` |

## Required Configuration

| `topology.json` Key | Description |
|---------------------|-------------|
| `user_white_list.admin` | Authorized administrator's Telegram ID |

## Example `topology.json`

```json
{
    "user_white_list": {
        "admin": "123456789"
    }
}
```

## Security

- User ID is always converted to `str` before comparison (avoids int/str type mismatches)
- Whitelist defaults to `set()` (no authorization if not configured)
- Verification is performed on every handler call (no session caching)
