# Telegram bot for network status management

This project has for purpose to be able to run a telegram bot interaction script.

## Features

- **Massa node monitoring** : Periodically checks your Massa node status every 60 minutes and notifies when the node is down
- **Balance history tracking** : Tracks node balance over time with periodic snapshots (hourly at 7, 12, 21)
- **Crypto price tracking** : Real-time Bitcoin (via API-NINJA) and Massa (via MEXC) price monitoring
- **System monitoring** : Monitor your server's CPU, RAM usage and temperature
- **Activity logging** : All activity logged to `bot_activity.log`
- **User authentication** : Commands restricted to whitelisted users with proper feedback
- **Conversation handlers** : Interactive confirmations for destructive operations (flush/clear logs)
- **Highly customizable** : Support for custom API keys and command extensions

## How to configure

The `topology.json` file describes all the usefull configuration informations for Robbi.

```json
{
    "telegram_bot_token": "YOUR_API_KEY",
    "user_white_list": {
        "admin": "YOUR_USER_ID"
    },
    "massa_node_address": "YOUR_MASSA_ADDRESS",
    "ninja_api_key" : "YOUR_NINJA_API_KEY"
}
```

## Commands

**Note:** All commands require authentication via the whitelist in `topology.json`. Unauthorized users receive an explicit access denied message.

- **`/hi`** - Say hello to Robbi and get a friendly response with a custom image (authorized users only)

- **`/node`** - Get Massa node information:
  - Current balance and roll count
  - Validation stats (OK/NOK counts per cycle)
  - Active rolls
  - Visual chart of recent validation performance

- **`/btc`** - Get Bitcoin price data:
  - Current price in USD
  - 24h change (absolute and percentage)
  - 24h high/low prices
  - 24h trading volume

- **`/mas`** - Get Massa token price from MEXC:
  - Current price in USDT
  - Price change (absolute and percentage)
  - 24h high/low prices
  - 24h trading volume

- **`/temperature`** - Monitor your server:
  - CPU usage percentage
  - RAM usage and available memory
  - System temperature (if available)

- **`/hist`** - Get balance history:
  - Visual chart of balance over time
  - Option to receive text summary of all recorded snapshots
  - Useful for tracking balance trends

- **`/flush`** - Clear operational data with confirmation dialog:
  - Option 1: Clear both log files and balance history
  - Option 2: Clear only log files (preserve balance history)
  - Uses inline buttons for safe confirmation

## Requirements

- Python 3.8+
- A Telegram account and bot created via [BotFather](https://core.telegram.org/bots#botfather)
- A Massa node running with accessible JSON-RPC API
- API keys for:
  - [API-NINJA](https://www.api-ninjas.com/) (Bitcoin price)
  - [MEXC](https://mexcdevelop.github.io/apidocs/spot_v3_en/) (Massa price)

### Python Dependencies

```bash
pip install python-telegram-bot requests matplotlib apscheduler
```

Or from `requirements.txt`:
```bash
pip install -r requirements.txt
```

## How to Run

1. **Configure the bot:**
   - Ensure `topology.json` is properly set up with your API keys and user ID

2. **Start the bot:**
   ```bash
   cd src
   python main.py
   ```

3. **Monitor activity:**
   - Bot logs all activity to `bot_activity.log`
   - Check the log file for debugging and activity tracking

### Running in the Background

**Linux/macOS:**
```bash
nohup python src/main.py > bot.log 2>&1 &
```

**Docker:**
```bash
docker build -t robbi .
docker run -d --name robbi robbi
```

## Generated Files

During operation, the bot generates the following files:

- **`bot_activity.log`** - Complete activity log during bot runtime (timestamp, user, command, errors)
- **`plot.png`** - Temporary chart generated for `/node` command (cleaned up after sending)
- **`balance_history.png`** - Chart generated for `/hist` command (cleaned up after sending)

## Notes on Operation

- **Periodic pings:** Every 60 minutes, the bot automatically checks the Massa node status and stores the balance
- **Hourly reports:** At 7:00, 12:00, and 21:00 UTC (if node is up), the bot sends a balance comparison report
- **Graph generation:** Graphs are automatically cleaned up after being sent to prevent disk space issues
- **Error handling:** All API timeouts and errors are logged and reported to the user with helpful feedback

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Access denied" message | Check your user ID in `topology.json` matches your actual Telegram user ID |
| No node data received | Verify Massa node is running and JSON-RPC endpoint is accessible |
| Missing temperature data | Temperature sensor might not be available on your system (non-critical) |
| Graph generation fails | Ensure matplotlib is properly installed: `pip install --upgrade matplotlib` |

## External Links

- [API-NINJA Documentation](https://www.api-ninjas.com/)
- [Massa JSON-RPC API](https://docs.massa.net/docs/build/api/jsonrpc)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [MEXC API Documentation](https://mexcdevelop.github.io/apidocs/spot_v3_en/)
- [python-telegram-bot Documentation](https://python-telegram-bot.readthedocs.io/)