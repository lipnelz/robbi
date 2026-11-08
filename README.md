# Robbi

Robbi is a private Telegram bot for monitoring a [Massa](https://massa.net/) node. It queries the node's JSON-RPC API, keeps a balance history, and provides monitoring, price-tracking, and Docker management commands.

## Features

- Monitor node status and activity through JSON-RPC.
- Check the node every 60 minutes, send alerts when checks fail, and send reports when checks run at 7 AM, 12 PM, and 9 PM (process-local time).
- Persist balance, average temperature, and memory usage history, with charts.
- Measure RPC latency and observed availability from scheduled checks (this is not continuous uptime monitoring).
- Fetch BTC prices from API-Ninjas and MAS/USDT prices from MEXC.
- Report CPU, memory, and temperature metrics visible from the bot container.
- Navigate commands using an interactive Telegram menu.
- Manage Docker containers and run `massa-client` commands when the Docker socket is accessible.
- Restrict access to the configured Telegram administrator ID.

## Telegram commands

All commands are restricted to the configured administrator. `/start` and `/menu` open the interactive menu.

| Command | Description |
|---|---|
| `/menu`, `/help` | Open the menu and help |
| `/hi` | Send a greeting |
| `/node` | Show balance, rolls, and validation results with a chart |
| `/status` | Check the Massa container state and node information via RPC |
| `/perf` | Show RPC latency and observed availability over the last 24 hours |
| `/temperature` | Show resource and temperature metrics visible from the container |
| `/btc` | Show Bitcoin price and 24-hour statistics |
| `/mas` | Show the MAS/USDT price and 24-hour statistics |
| `/hist` | Show charts and optionally send the balance history as text |
| `/flush` | Clear the log, with an option to also clear balance history |
| `/docker` | Open Docker actions and the `massa-client` menu |
| `/massa_version` | Show the configured Massa version |
| `/massa_version MAIN.5.2` | Change the version and request a Massa service rebuild |

The `/docker` menu can start or stop the Massa container, restart Robbi, show wallet information, and buy or sell rolls. Actions that change state require confirmation.

## Requirements

- Python 3.12 or later.
- A Telegram bot created with [BotFather](https://core.telegram.org/bots#botfather).
- A Massa node accessible through JSON-RPC.
- An [API-Ninjas](https://api-ninjas.com/) key for the `/btc` command.
- Docker and access to the Docker socket if `/docker` and `/status` need to manage or inspect containers.

The `/mas` command uses MEXC's public API and does not require an API key.

## Configuration

This repository does not include a configuration template. Create `topology.json` in the repository root (or in the process working directory):

```json
{
  "telegram_bot_token": "TOKEN_FROM_BOTFATHER",
  "user_white_list": {
    "admin": "TELEGRAM_USER_ID"
  },
  "massa_node_address": "MASSA_ADDRESS",
  "massa_node_rpc_url": "http://massa:33035",
  "ninja_api_key": "API_NINJAS_KEY",
  "node_container_name": "massa-container",
  "robbi_container_name": "robbi-container",
  "massa_client_password": "MASSA_CLIENT_PASSWORD",
  "massa_wallet_address": "WALLET_ADDRESS",
  "massa_buy_rolls_fee": 0.01
}
```

The first three fields (`telegram_bot_token`, `user_white_list.admin`, and `massa_node_address`) are required. The rest are optional: the default RPC URL is `http://massa:33035`, the default container names are `massa-container` and `robbi-container`, and the default roll transaction fee is `0.01`. The API-Ninjas key is required for `/btc`; the password and wallet address are needed for `massa-client` commands.

Keep `topology.json` private; Git ignores it. Set the RPC URL to an address reachable from the environment where Robbi runs.

## Install and run locally

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python src/main.py
```

The program reads `topology.json` from the current working directory. Run it from the repository root so that the `media/` assets and data paths also resolve correctly. The bot communicates with Telegram using polling.

## Docker deployment

This repository does not include a `Dockerfile` or a Docker Compose file; define the image and service in your deployment. The `entrypoint.sh` script expects the project under `/app`; it attempts to synchronize with `origin/main`, then runs `python src/main.py`. The bot must be able to read `/app/topology.json` and the repository assets.

To keep history when replacing the container, mount a volume at `/app/config`. To enable Docker commands, also mount the host socket:

```yaml
volumes:
  - ./robbi-config:/app/config
  - /var/run/docker.sock:/var/run/docker.sock
```

Access to the Docker socket gives the bot control over containers available on the host. Only enable it if you trust the runtime environment, and protect the bot with an administrator allowlist.

The `/massa_version` command requires additional configuration in the container environment:

| Variable | Default | Purpose |
|---|---|---|
| `MASSA_DOCKERFILE_PATH` | `/massa-build-context/Dockerfile` | Massa Dockerfile containing exactly one `ARG MASSA_VERSION=...` |
| `MASSA_COMPOSE_PROJECT_DIR` | `/host-project` | Compose project directory mounted in the container |
| `MASSA_COMPOSE_FILE` | `/host-project/docker-compose.yml` | Compose file to use |

The Robbi container must also have the `docker-compose` command available and the mounts required to edit the Dockerfile and rebuild the Compose `massa` service.

## Data and logs

Paths are relative to the process working directory:

- `bot_activity.log`: activity log.
- `config/balance_history.json`: balance and resource history.
- `config/node_status_history.json`: scheduled check results, retained for up to 7 days.
- Charts are temporary and deleted after they are sent.

For local runs, back up `config/` to preserve history. In a container, mount it as a persistent volume.

## Development and tests

```bash
python -m pip install pytest pytest-asyncio pytest-cov
python -m pip install -r requirements.txt
pytest
```

The test suite is in `tests/`. GitHub Actions runs the tests with a 97% coverage threshold and audits dependencies.

## Repository structure

```text
src/
├── main.py                 # Bot configuration and startup
├── config.py               # Commands, states, and logging
├── handlers/               # Telegram commands and menus
└── services/               # Massa RPC, Docker, history, prices, and metrics
tests/                      # Unit tests
media/                      # Images used in bot responses
entrypoint.sh               # Startup script intended for /app
requirements.txt            # Production Python dependencies
```
