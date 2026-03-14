# Skill: Docker Management for the Massa Node

## Description

This skill allows controlling the Massa node's Docker container directly from the bot, via the interactive `/docker` command. It uses the Python Docker SDK (Unix socket communication), without requiring the Docker CLI inside the bot's container.

## Command

```
/docker
```

---

## Interactive Menu Architecture

```
/docker
└── 🐳 Docker Node Management
      ├── ▶️  Start  → ⚠️ Confirmation → Start container
      ├── ⏹️  Stop   → ⚠️ Confirmation → Stop container
      └── 💻 Massa Client
            ├── 💰 Wallet Info   → Execute wallet_info
            ├── 🎲 Buy Rolls     → Enter amount → ⚠️ Confirmation → Execute buy_rolls
            ├── 💸 Sell Rolls    → Enter amount → ⚠️ Confirmation → Execute sell_rolls
            └── ⬅️  Back         → Return to main menu
```

---

## Sub-skills

### 1. Entry Point — `/docker`

- Manual authentication check (ConversationHandler does not support `@auth_required`)
- Displays the main menu with an inline keyboard (Start / Stop / Massa Client)
- Returns `DOCKER_MENU_STATE`

### 2. Start Container (`docker_start` → `docker_start_confirm`)

- **Step 1**: Confirmation prompt: "⚠️ Are you sure you want to start the node container?"
  - **Yes** → proceeds to `DOCKER_START_CONFIRM_STATE`
  - **No** → cancels and ends the conversation

- **Step 2**: Executes `start_docker_node(logger, container_name)`:
  ```python
  client = docker.from_env()
  container = client.containers.get(container_name)
  container.start()
  ```
  - Success → message "✅ Container '<name>' started."
  - Failure → message "❌ Error: <details>"

### 3. Stop Container (`docker_stop` → `docker_stop_confirm`)

- **Step 1**: Confirmation prompt: "⚠️ Are you sure you want to stop the node container?"
  - **Yes** → proceeds to `DOCKER_STOP_CONFIRM_STATE`
  - **No** → cancels and ends the conversation

- **Step 2**: Executes `stop_docker_node(logger, container_name)`:
  ```python
  client = docker.from_env()
  container = client.containers.get(container_name)
  container.stop(timeout=30)
  ```
  - Success → message "✅ Container '<name>' stopped."
  - Stop timeout: 30 seconds (grace period)

### 4. Massa Client Menu (`docker_massa`)

Sub-menu accessible from the main menu. Presents three actions:

| Button | massa-client Command | Description |
|--------|---------------------|-------------|
| 💰 Wallet Info | `wallet_info` | Displays wallet information |
| 🎲 Buy Rolls | `buy_rolls <count> <addr> <fee>` | Buys rolls (with input + confirmation) |
| 💸 Sell Rolls | `sell_rolls <count> <addr> <fee>` | Sells rolls (with input + confirmation) |

### 5. Wallet Info (`docker_massa_wallet_info`)

- Directly calls `exec_massa_client(logger, container_name, password, "wallet_info")`
- Displays the raw command output in the bot message
- No confirmation required

### 6. Buy Rolls / Sell Rolls (3-step flow)

**Step 1 — Enter number of rolls** (state `DOCKER_BUYROLLS_INPUT_STATE` / `DOCKER_SELLROLLS_INPUT_STATE`)
- The user sends a text message with the number of rolls
- Validation: must be an integer > 0
- The number is stored in `context.user_data['rolls_count']`

**Step 2 — Confirmation** (state `DOCKER_BUYROLLS_CONFIRM_STATE` / `DOCKER_SELLROLLS_CONFIRM_STATE`)
- Displays "⚠️ Confirm: <action> <N> rolls?"
- **Yes** → execution; **No** → cancellation

**Step 3 — Execution** via `exec_massa_client`:
```python
# Buy Rolls
cmd = f"buy_rolls {wallet_address} {rolls_count} {buy_rolls_fee}"

# Sell Rolls
cmd = f"sell_rolls {wallet_address} {rolls_count} {buy_rolls_fee}"
```

### 7. Massa-client Command Execution (`services/docker_manager.py`)

Function `exec_massa_client(logger, container_name, password, command)`:

```python
client = docker.from_env()
container = client.containers.get(container_name)
cmd = ['./massa-client', '-p', password, '-a'] + command.split()
exit_code, output = container.exec_run(cmd, workdir='/massa/massa-client')
```

- Decodes output as UTF-8 (errors replaced)
- Sends an `exit` command after execution to cleanly close the session
- Exit code 0 → success (`{"status": "ok", "output": ...}`)
- Non-zero exit code → failure (`{"status": "error", "message": ...}`)

### 8. Cancellation and Navigation

- `docker_cancel`: cancels the current action, returns to the main menu or ends the conversation
- `docker_back`: returns to the Massa Client menu from a sub-menu
- "⬅️ Back" button in the Massa Client menu: returns to the Docker main menu

---

## Related Files

| File | Role |
|------|------|
| `src/handlers/node.py` | `/docker` menu handlers and all callbacks |
| `src/services/docker_manager.py` | Docker SDK functions (start, stop, exec) |
| `src/config.py` | Docker conversation states (`DOCKER_*_STATE`) |

## Required Configuration

| `topology.json` Key | Description |
|---------------------|-------------|
| `docker_container_name` | Docker container name (e.g. `massa-container`) |
| `massa_client_password` | Password for `./massa-client -p` |
| `massa_wallet_address` | Wallet address for buy/sell rolls |
| `massa_buy_rolls_fee` | Transaction fee (e.g. `0.01`) |

## Docker Prerequisites

The bot's container must have access to the Docker socket:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

> The Python `docker` package is required (not the Docker CLI).

## Error Handling

- Container name not configured → explicit error message
- Non-existent container → Docker SDK exception propagated
- Failed massa-client command → error output displayed
- Invalid input (rolls) → correction message and new prompt
