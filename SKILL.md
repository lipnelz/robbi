# SKILL.md — T800 Agent Skills

This file documents the technical skills and knowledge areas used by the **T800** agent to maintain and improve the Robbi codebase.

---

## 🐍 Python Development

- Python 3.12+ idiomatic code (type hints, async/await, decorators, dataclasses)
- `asyncio` and `async`/`await` patterns for non-blocking I/O
- Functional patterns: `functools.wraps`, higher-order functions, decorators
- Exception handling with specific error types and structured logging
- Module-level logging via `logging.basicConfig` configured in `config.py`

---

## 🤖 Telegram Bot (python-telegram-bot)

- Handler registration: `CommandHandler`, `CallbackQueryHandler`, `ConversationHandler`, `MessageHandler`
- Shared state via `application.bot_data` — no global variables
- `auth_required` and `cb_auth_required` decorators for user whitelisting
- `ConversationHandler` multi-step flows (flush, hist, docker menus) with integer state constants
- Inline keyboards (`InlineKeyboardMarkup`, `InlineKeyboardButton`) for interactive menus
- Sending photos with `reply_photo` and temporary file cleanup via `safe_delete_file`

---

## ⛓️ Massa Blockchain Node Monitoring

- JSON-RPC calls to the Massa node (`get_addresses`, `get_graph_interval`)
- Balance extraction, roll count, OK/NOK block counts
- RPC latency measurement and uptime percentage (last 24 h)
- Periodic node ping via APScheduler (every 60 min) — alerts on node down/up transitions

---

## 💹 Crypto Price APIs

- **API-Ninjas** integration for real-time Bitcoin price (USD, 24 h change, high/low, volume)
- **MEXC REST API** for Massa/USDT price data
- Error handling for timeouts and API failures with user-facing error images

---

## 🖥️ System Monitoring

- `psutil` for per-core CPU usage, RAM, and per-sensor temperature readings
- `subprocess` for collecting additional system diagnostics
- Graceful fallback when sensors are unavailable

---

## 🐳 Docker Management

- Python Docker SDK (socket-based — no CLI dependency)
- Start / stop the Massa node container
- `exec_run` for Massa client commands: `wallet_info`, `buy_rolls`, `sell_rolls`
- Docker socket mounted via `volumes: /var/run/docker.sock:/var/run/docker.sock`

---

## 📊 Data Visualization

- `matplotlib` chart generation (non-interactive `Agg` backend for headless/Docker use)
- Balance history chart (balance, temperature, RAM over time)
- Node validation chart (OK/NOK block counts)
- Temporary PNG cleanup after sending to the user

---

## 📅 Scheduling

- `APScheduler` for periodic background jobs (node ping every 60 min)
- Scheduled Telegram reports at 07:00, 12:00, and 21:00 with 24 h balance delta

---

## 💾 Data Persistence

- Balance history stored in `config/balance_history.json` (survives Docker restarts)
- Load / save / filter helpers in `services/history.py`
- Threading lock (`balance_lock`) guards concurrent history updates

---

## 🧪 Testing

- `pytest` with `asyncio_mode=auto` (see `pytest.ini`)
- `AsyncMock` / `MagicMock` for Telegram `Update` and `CallbackContext` fixtures
- Service-level unit tests with patched external dependencies (`requests`, `psutil`, Docker SDK, `subprocess`, `datetime`, filesystem)
- ≥ 90 % branch coverage enforced in CI (`.github/workflows/tests.yml`)
- Run the full suite: `python -m pytest` from the repository root

---

## 🏗️ Architecture & Code Quality

- Handlers import only from `services/` — clean separation of concerns
- `handle_api_error` centralises error photo dispatch
- `safe_delete_file` centralises temporary file cleanup
- All configuration loaded from `topology.json` at startup; no hard-coded credentials
- Handler module layout: `common.py`, `node.py`, `price.py`, `system.py`, `scheduler.py`
- Service module layout: `docker_manager.py`, `history.py`, `http_client.py`, `massa_rpc.py`, `plotting.py`, `price_api.py`, `system_monitor.py`
