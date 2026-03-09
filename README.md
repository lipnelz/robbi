# Robbi — Telegram bot for Massa node monitoring

Robbi is a Telegram bot that monitors a [Massa](https://massa.net/) blockchain node, tracks balance history, and provides crypto price data and system stats.

## Features

- **Massa node monitoring** — Periodically checks node status every 60 minutes and alerts when the node goes down
- **Balance history** — Persisted to JSON file (`config/balance_history.json`), survives Docker restarts. Periodic reports show last 24h of data
- **Crypto price tracking** — Real-time Bitcoin (API-Ninjas) and Massa/USDT (MEXC) prices
- **System monitoring** — Per-core CPU usage, RAM, and per-sensor temperature details
- **Node performance** — RPC latency measurement and uptime percentage (last 24h)
- **Docker management** — Start/stop the Massa node container and execute Massa client commands (wallet_info, buy_rolls, sell_rolls) via interactive menus
- **User authentication** — All commands restricted to whitelisted user via `auth_required` decorator
- **Interactive confirmations** — Inline keyboard buttons for operations (`/flush`, `/hist`, `/docker`)

## Project Structure

```
src/
├── main.py                  # Entry point: config, bot_data setup, handler registration
├── config.py                # Constants, logging config, command list
├── jrequests.py             # External API calls (Massa JSON-RPC, API-Ninjas, MEXC, Docker)
├── Dockerfile
├── entrypoint.sh
├── handlers/
│   ├── common.py            # auth_required decorator, handle_api_error helper
│   ├── node.py              # /node, /flush, /hist, /docker commands
│   ├── price.py             # /btc, /mas commands
│   ├── system.py            # /hi, /temperature, /perf commands
│   └── scheduler.py         # Periodic node ping (APScheduler)
├── services/
│   ├── history.py           # Balance history load/save/filter (JSON persistence)
│   └── plotting.py          # Chart generation (matplotlib)
└── media/                   # Images used in bot responses
```

Shared state (`allowed_user_ids`, `massa_node_address`, `ninja_key`, `balance_history`, `docker_container_name`, etc.) is stored in `application.bot_data` and accessed via `context.bot_data` in handlers — no global variables.

## Configuration

The `topology.json` file (placed at the repository root) provides all configuration:

```json
{
    "telegram_bot_token": "YOUR_API_KEY",
    "user_white_list": {
        "admin": "YOUR_USER_ID"
    },
    "massa_node_address": "YOUR_MASSA_ADDRESS",
    "ninja_api_key": "YOUR_NINJA_API_KEY",
    "docker_container_name": "massa-node",
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
| `ninja_api_key` | API-Ninjas key for Bitcoin price |
| `docker_container_name` | Name of the Docker container running the Massa node (default: `massa-node`) |
| `massa_client_password` | Password for `./massa-client -p` |
| `massa_wallet_address` | Wallet address used for buy_rolls / sell_rolls commands |
| `massa_buy_rolls_fee` | Fee for buy/sell rolls transactions (default: `0.01`) |

## Commands

All commands require authentication via `topology.json` whitelist.

| Command | Description |
|---------|-------------|
| `/hi` | Greeting with a custom image |
| `/node` | Node status: balance, roll count, OK/NOK counts, active rolls + validation chart |
| `/btc` | Bitcoin price: USD price, 24h change, high/low, volume |
| `/mas` | Massa/USDT price from MEXC: price, change, high/low, volume |
| `/temperature` | System stats: per-sensor temperatures, per-core CPU usage, RAM |
| `/perf` | Node performance: RPC latency and uptime percentage (last 24h) |
| `/hist` | Balance history chart + optional text summary |
| `/flush` | Clear logs with confirmation dialog (option to also clear balance history) |
| `/docker` | Docker management menu (see below) |

### `/docker` — Interactive Menu

The `/docker` command opens a multi-level interactive menu:

```
🐳 Docker Node Management
  ├── ▶️ Start       → Confirmation → Start the node container
  ├── ⏹️ Stop        → Confirmation → Stop the node container
  └── 💻 Massa Client
        ├── 💰 Wallet Info   → Execute wallet_info
        ├── 🎲 Buy Rolls     → Input roll count → Confirmation → Execute buy_rolls
        ├── 💸 Sell Rolls     → Input roll count → Confirmation → Execute sell_rolls
        └── ⬅️ Back          → Return to main menu
```

> **Note:** For Docker commands to work, the bot container needs access to the Docker daemon.
> Mount the Docker socket in your `docker-compose.yml`:
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

Key packages: `python-telegram-bot`, `requests`, `matplotlib`, `apscheduler`, `psutil`

## How to Run

### Local

```bash
cd src
python main.py
```

### Docker (recommended)

With `docker-compose`, mount volumes for balance history persistence and Docker access:

```yaml
volumes:
  - ./docker-volumes/robbi:/app/config
  - /var/run/docker.sock:/var/run/docker.sock
```

```bash
docker compose up -d
```

Activity is logged to `bot_activity.log`.

## Generated Files

| File | Description | Lifecycle |
|------|-------------|-----------|
| `bot_activity.log` | Activity log | Persistent, clearable via `/flush` |
| `config/balance_history.json` | Balance snapshots | Persistent (Docker volume) |
| `plot.png` | Node validation chart | Temporary, deleted after sending |
| `balance_history.png` | Balance history chart | Temporary, deleted after sending |

## Notes on Operation

- **Periodic pings** — Every 60 minutes, the bot checks the Massa node and records the balance
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

## External Links

- [API-Ninjas Documentation](https://www.api-ninjas.com/)
- [Massa JSON-RPC API](https://docs.massa.net/docs/build/api/jsonrpc)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [MEXC API Documentation](https://mexcdevelop.github.io/apidocs/spot_v3_en/)
- [python-telegram-bot Documentation](https://python-telegram-bot.readthedocs.io/)