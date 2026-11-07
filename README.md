# Robbi — Telegram bot for Massa node monitoring

Robbi is a Telegram bot that monitors a [Massa](https://massa.net/) blockchain node, tracks balance history, and provides crypto price data and system stats.

## Features

- **Massa node monitoring** — Periodically checks node status every 60 minutes and alerts when the node goes down
- **Balance history** — Persisted to JSON file (`config/balance_history.json`), survives Docker restarts. Records balance, CPU temperature, and RAM usage per snapshot
- **Scheduled reports** — Automatic status reports at 7 AM, 12 PM, and 9 PM with 24h balance change, average temperature, and history data
- **Crypto price tracking** — Real-time Bitcoin (API-Ninjas) and Massa/USDT (MEXC) prices
- **System monitoring** — Container-visible CPU/RAM and available per-sensor temperature details (not guaranteed to represent the host)
- **Node performance** — RPC latency and observed availability across scheduled checks in the last 24h (not continuous uptime); reports include the successful/total check count
- **Docker management** — Start/stop the Massa node container, execute Massa client commands (wallet_info, buy_rolls, sell_rolls), and support bot-container restart helpers via the Docker SDK (socket-based, no CLI needed)
- **User authentication** — All commands restricted to whitelisted user via `auth_required` decorator
- **Interactive confirmations** — Inline keyboard buttons for operations (`/flush`, `/hist`, `/docker`)

## Project Structure

```
src/
├── main.py                         # Entry point: config, bot_data setup, handler registration
├── config.py                       # Constants, conversation states, logging config, command list
├── jrequests.py                    # Backward-compatibility facade (re-exports from services/)
├── Dockerfile
├── entrypoint.sh
├── handlers/
│   ├── common.py                   # auth_required decorator, handle_api_error helper
│   ├── node.py                     # /node, /flush, /hist, /docker commands
│   ├── price.py                    # /btc, /mas commands
│   ├── system.py                   # /hi, /temperature, /perf commands
│   └── scheduler.py                # Periodic node ping (APScheduler, every 60 min)
├── services/
│   ├── docker_manager.py           # Docker SDK wrapper (start/stop/restart, exec massa-client)
│   ├── history.py                  # Balance history load/save/filter (JSON persistence)
│   ├── http_client.py              # Safe HTTP request wrapper with retry logic
│   ├── massa_rpc.py                # Massa blockchain JSON-RPC calls
│   ├── plotting.py                 # Chart generation (matplotlib) — validation, resources, balance
│   ├── price_api.py                # External price API wrappers (API-Ninjas, MEXC)
│   └── system_monitor.py           # System stats via psutil (CPU, RAM, temperatures)
└── media/                          # Images used in bot responses
tests/                              # pytest test suite (unit tests for all modules)
topology_template.json              # Configuration template — copy to topology.json and fill in values
```

Shared state (`allowed_user_ids`, `massa_node_address`, `ninja_key`, `balance_history`, `node_container_name`, `robbi_container_name`, etc.) is stored in `application.bot_data` and accessed via `context.bot_data` in handlers — no global variables. A threading lock protects concurrent history updates.

## Configuration

A `topology_template.json` file is provided at the repository root. Copy it to `topology.json` and fill in your values:

```bash
cp topology_template.json topology.json
```

The `topology.json` file provides all configuration:

```json
{
    "telegram_bot_token": "YOUR_API_KEY",
    "user_white_list": {
        "admin": "YOUR_USER_ID"
    },
    "massa_node_address": "YOUR_MASSA_ADDRESS",
    "massa_node_rpc_url": "http://massa:33035",
    "ninja_api_key": "YOUR_NINJA_API_KEY",
    "node_container_name": "massa-container",
    "robbi_container_name": "robbi-container",
    "massa_client_password": "YOUR_MASSA_CLIENT_PASSWORD",
    "massa_wallet_address": "YOUR_MASSA_WALLET_ADDRESS",
    "massa_buy_rolls_fee": 0.01
}
```

| Key | Description |
|-----|-------------|
| `telegram_bot_token` | Telegram bot token from BotFather |
| `user_white_list.admin` | Telegram user ID authorized to use the bot |
| `massa_node_address` | Massa wallet address for node monitoring |
| `massa_node_rpc_url` | JSON-RPC endpoint of the Massa node (defaults to `http://massa:33035` for the Docker Compose service) |
| `ninja_api_key` | API-Ninjas key for Bitcoin price |
| `node_container_name` | Name of the Docker container running the Massa node (default: `massa-container`) |
| `robbi_container_name` | Name of the Docker container running Robbi itself (default: `robbi-container`) |
| `massa_client_password` | Password for `./massa-client -p` |
| `massa_wallet_address` | Wallet address used for buy_rolls / sell_rolls commands |
| `massa_buy_rolls_fee` | Fee for buy/sell rolls transactions (default: `0.01`) |

## Commands

All commands require authentication via `topology.json` whitelist.

Node status, scheduled checks, and `/perf` use `massa_node_rpc_url` to query the Massa node's own JSON-RPC API. In Docker Compose, the default URL uses the `massa` service name on the shared network; for a different deployment, set this key to that node's reachable `/api/v2` URL.

| Command | Description |
|---------|-------------|
| `/hi` | Greeting with a custom image and current git commit hash |
| `/node` | Node status: balance, roll count, OK/NOK counts, active rolls + validation chart |
| `/status` | Massa container state, healthcheck, JSON-RPC availability, cycle, peers, slots and recent activity |
| `/btc` | Bitcoin price: USD price, 24h change, high/low, volume |
| `/mas` | Massa/USDT price from MEXC: price, change, high/low, volume |
| `/temperature` | System stats: per-sensor temperatures, per-core CPU usage, RAM |
| `/perf` | Node performance: RPC latency and observed availability across scheduled checks in the last 24h |
| `/hist` | Balance history chart (balance, temperature, RAM) + optional text summary |
| `/flush` | Clear logs with confirmation dialog (option to also clear balance history) |
| `/docker` | Docker management menu (see below) |
| `/massa_version` | Affiche la version Massa configurée; `/massa_version MAIN.5.2` la modifie dans le Dockerfile |

`/massa_version` modifie le Dockerfile Massa monté, puis lance en arrière-plan `docker-compose up -d --build --force-recreate massa`. Robbi confirme immédiatement la demande et envoie un second message avec le résultat du rebuild. Le service Compose doit monter le dossier du projet au même chemin absolu dans le conteneur Robbi et fournir `MASSA_COMPOSE_PROJECT_DIR` et `MASSA_COMPOSE_FILE`; le Dockerfile Robbi doit embarquer le binaire Docker Compose v2.

### `/docker` — Interactive Menu

The `/docker` command opens a multi-level interactive menu:

```
🐳 Docker Node Management
  ├── ▶️ Start       → Confirmation → Start the node container
  ├── ⏹️ Stop        → Confirmation → Stop the node container
  ├── 🔁 Restart Bot → Confirmation → Send "Ok" → Wait 1s → Restart the Robbi bot container
  └── 💻 Massa Client
        ├── 💰 Wallet Info   → Execute wallet_info
        ├── 🎲 Buy Rolls     → Input roll count → Confirmation → Execute buy_rolls
        ├── 💸 Sell Rolls    → Input roll count → Confirmation → Execute sell_rolls
        └── ⬅️ Back          → Return to main menu
```

> **Note:** Docker commands use the Python Docker SDK which communicates directly via the Docker socket.
> The bot container does **not** need the `docker` CLI installed — only the socket mount:
> ```yaml
> volumes:
>   - /var/run/docker.sock:/var/run/docker.sock
> ```

## Requirements

- Python 3.12+
- A Telegram bot created via [BotFather](https://core.telegram.org/bots#botfather)
- A Massa node with accessible JSON-RPC API
- API keys:
  - [API-Ninjas](https://www.api-ninjas.com/) — Bitcoin price
  - [MEXC](https://mexcdevelop.github.io/apidocs/spot_v3_en/) — Massa price

### Python Dependencies

```bash
pip install -r requirements.txt
```

Key packages: `python-telegram-bot`, `requests`, `matplotlib`, `apscheduler`, `psutil`, `tzlocal`, `docker`

## How to Run

### Local

```bash
cp topology_template.json src/topology.json  # or place topology.json in the working directory
cd src
python main.py
```

### Docker (recommended)

The `Dockerfile` (located in `src/`) clones the repository from GitHub and expects `topology.json` to be present in the `src/` build context:

At container startup, `entrypoint.sh` attempts `git pull origin main` before launching `python src/main.py`.
If the pull fails (network/auth), the bot still starts with the local code already present in the image.
The Massa container runs the node in the foreground and its healthcheck probes the local JSON-RPC `get_status` method. Robbi's healthcheck verifies that its PID 1 is the bot entrypoint process.

```bash
cp topology_template.json src/topology.json
docker build -t robbi ./src
docker run -d \
  -v ./docker-volumes/robbi:/app/config \
  -v /var/run/docker.sock:/var/run/docker.sock \
  robbi
```

Or with `docker-compose`, mount volumes for balance history persistence and Docker access:

```yaml
volumes:
  - ./docker-volumes/robbi:/app/config
  - /var/run/docker.sock:/var/run/docker.sock
```

```bash
docker compose up -d
```

Activity is logged to `bot_activity.log`.

## Tests

The project has a full unit test suite under `tests/`. Run with:

```bash
pytest
```

Configuration is in `pytest.ini`. A detailed description of all tests is available in [`test_plan.md`](test_plan.md).

CI runs tests automatically on every push via GitHub Actions (`.github/workflows/tests.yml`). Commit messages are also linted via `.github/workflows/commitlint.yml`.

## Generated Files

| File | Description | Lifecycle |
|------|-------------|-----------|
| `bot_activity.log` | Activity log | Persistent, clearable via `/flush` |
| `config/balance_history.json` | Balance snapshots | Persistent (Docker volume) |
| `config/node_status_history.json` | Scheduled node check results, retained for 7 days | Persistent (Docker volume) |
| `*_plot.png` / `*_balance_history.png` / `*_resources_history.png` | Generated charts with unique filenames (validation, balance history, resources) | Temporary, deleted after sending |

## Notes on Operation

- **Periodic pings** — Every 60 minutes, the bot checks the Massa node and records the balance
- **Availability metric** — `/perf` reports the percentage of successful scheduled checks in the last 24 hours; it is sampled availability, not continuous uptime
- **Container metrics** — CPU, RAM, and temperatures are collected from the bot container's view and may not describe the Docker host; CPU temperature may be unavailable
- **Scheduled reports** — At 7:00, 12:00, and 21:00 (if node is up), sends a detailed status report including:
  - Balance comparison: first recorded vs current value
  - Change amount and percentage (📈/📉 indicators)
  - Last 24h balance history
- **Graph cleanup** — Charts are deleted after being sent to the user
- **Error handling** — API timeouts and errors are logged and reported with appropriate feedback images

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Access denied" message | Verify your Telegram user ID in `topology.json` |
| No node data | Check Massa node is running and JSON-RPC endpoint is reachable |
| Missing temperature data | Sensor may not be available on your system (non-critical) |
| Graph generation fails | `pip install --upgrade matplotlib` |
| Docker commands fail with "No such file or directory" | Ensure `docker` Python package is installed (not the CLI) and the socket is mounted |

## External Links

- [API-Ninjas Documentation](https://www.api-ninjas.com/)
- [Massa JSON-RPC API](https://docs.massa.net/docs/build/api/jsonrpc)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [MEXC API Documentation](https://mexcdevelop.github.io/apidocs/spot_v3_en/)
- [python-telegram-bot Documentation](https://python-telegram-bot.readthedocs.io/)