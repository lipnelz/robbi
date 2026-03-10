# Robbi — Discord bot for Massa node monitoring

Robbi is a Discord bot that monitors a [Massa](https://massa.net/) blockchain node, tracks balance history, and provides crypto price data and system stats.

## Features

- **Massa node monitoring** — Periodically checks node status every 60 minutes and alerts when the node goes down
- **Balance history** — Persisted to JSON file (`config/balance_history.json`), survives Docker restarts. Periodic reports show last 24h of data
- **Crypto price tracking** — Real-time Bitcoin (API-Ninjas) and Massa/USDT (MEXC) prices
- **System monitoring** — Per-core CPU usage, RAM, and per-sensor temperature details
- **Node performance** — RPC latency measurement and uptime percentage (last 24h)
- **Docker management** — Start/stop the Massa node container and execute Massa client commands (wallet_info, buy_rolls, sell_rolls) via interactive button menus, using the Docker SDK (socket-based, no CLI needed)
- **User authentication** — All commands restricted to whitelisted user via `auth_required` decorator
- **Interactive confirmations** — Discord UI buttons and modals for operations (`/flush`, `/hist`, `/docker`)

## Project Structure

```
src/
├── main.py                  # Entry point: config, RobbiBot setup, command registration
├── config.py                # Constants, logging config, command list
├── jrequests.py             # External API calls (Massa JSON-RPC, API-Ninjas, MEXC, Docker SDK)
├── Dockerfile
├── entrypoint.sh
├── handlers/
│   ├── common.py            # auth_required decorator, handle_api_error helper
│   ├── node.py              # /node, /flush, /hist, /docker commands + Discord Views/Modals
│   ├── price.py             # /btc, /mas commands
│   ├── system.py            # /hi, /temperature, /perf commands
│   └── scheduler.py         # Periodic node ping (APScheduler), DM notifications
├── services/
│   ├── history.py           # Balance history load/save/filter (JSON persistence)
│   └── plotting.py          # Chart generation (matplotlib)
└── media/                   # Images used in bot responses
```

Shared state (`allowed_user_ids`, `massa_node_address`, `ninja_key`, `balance_history`, `docker_container_name`, etc.) is stored as attributes on the `RobbiBot` instance and accessed via `interaction.client` in all handlers — no global variables.

## Configuration

The `topology.json` file (placed at the repository root) provides all configuration:

```json
{
    "discord_bot_token": "YOUR_API_KEY",
    "user_white_list": {
        "admin": "YOUR_USER_ID"
    },
    "massa_node_address": "YOUR_MASSA_ADDRESS",
    "ninja_api_key": "YOUR_NINJA_API_KEY",
    "docker_container_name": "massa-container",
    "massa_client_password": "YOUR_MASSA_CLIENT_PASSWORD",
    "massa_wallet_address": "YOUR_MASSA_WALLET_ADDRESS",
    "massa_buy_rolls_fee": 0.01
}
```

| Key | Description |
|-----|-------------|
| `discord_bot_token` | Discord bot token from the [Developer Portal](https://discord.com/developers/applications) |
| `user_white_list.admin` | Discord user ID (snowflake) authorized to use the bot |
| `massa_node_address` | Massa wallet address for node monitoring |
| `ninja_api_key` | API-Ninjas key for Bitcoin price |
| `docker_container_name` | Name of the Docker container running the Massa node (default: `massa-container`) |
| `massa_client_password` | Password for `./massa-client -p` |
| `massa_wallet_address` | Wallet address used for buy_rolls / sell_rolls commands |
| `massa_buy_rolls_fee` | Fee for buy/sell rolls transactions (default: `0.01`) |

## Commands

All commands are Discord slash commands and require authentication via `topology.json` whitelist.

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

The `/docker` command opens a multi-level interactive button menu:

```
🐳 Docker Node Management
  ├── ▶️ Start       → Confirmation → Start the node container
  ├── ⏹️ Stop        → Confirmation → Stop the node container
  └── 💻 Massa Client
        ├── 💰 Wallet Info   → Execute wallet_info
        ├── 🎲 Buy Rolls     → Modal (roll count input) → Confirmation → Execute buy_rolls
        ├── 💸 Sell Rolls    → Modal (roll count input) → Confirmation → Execute sell_rolls
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
- A Discord application/bot created via the [Discord Developer Portal](https://discord.com/developers/applications)
  - Enable the **applications.commands** (slash commands) OAuth2 scope
- A Massa node with accessible JSON-RPC API
- API keys:
  - [API-Ninjas](https://www.api-ninjas.com/) — Bitcoin price
  - [MEXC](https://mexcdevelop.github.io/apidocs/spot_v3_en/) — Massa price

### Python Dependencies

```bash
pip install -r requirements.txt
```

Key packages: `discord.py`, `requests`, `matplotlib`, `apscheduler`, `psutil`, `docker`

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
- **Scheduled reports** — At 7:00, 12:00, and 21:00 (if node is up), sends a detailed status DM including:
  - Balance comparison: first recorded vs current value
  - Change amount and percentage (📈/📉 indicators)
  - Last 24h balance history
- **Graph cleanup** — Charts are deleted after being sent to the user
- **Error handling** — API timeouts and errors are logged and reported with appropriate feedback images

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Access denied" message | Verify your Discord user ID in `topology.json` |
| Slash commands not appearing | Wait a few minutes after first startup for Discord to sync commands globally |
| No node data | Check Massa node is running and JSON-RPC endpoint is reachable |
| Missing temperature data | Sensor may not be available on your system (non-critical) |
| Graph generation fails | `pip install --upgrade matplotlib` |
| Docker commands fail with "No such file or directory" | Ensure `docker` Python package is installed (not the CLI) and the socket is mounted |

## External Links

- [Discord Developer Portal](https://discord.com/developers/applications)
- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [API-Ninjas Documentation](https://www.api-ninjas.com/)
- [Massa JSON-RPC API](https://docs.massa.net/docs/build/api/jsonrpc)
- [MEXC API Documentation](https://mexcdevelop.github.io/apidocs/spot_v3_en/)
