---
name: crypto-prices
description: Retrieves and displays real-time cryptocurrency prices for Bitcoin and Massa via external APIs. Use when implementing crypto price commands, adding BTC or MAS price lookups, integrating API-Ninjas or MEXC endpoints, or building Telegram bot price alerts.
---

# Cryptocurrency Prices

## Workflow

1. **Receive command** - `/btc` for Bitcoin or `/mas` for Massa/USDT
2. **Call external API** - API-Ninjas for BTC, MEXC for MAS (both via `http_client.py` with retry)
3. **Format response** - price, 24h change, high/low, volume
4. **Handle errors** - on failure, send error message + cry image

## Commands

| Command | API | Authentication | Data returned |
|---|---|---|---|
| `/btc` | API-Ninjas `/v1/cryptoprice?symbol=BTCUSDT` | `X-Api-Key` header (`ninja_api_key` in `topology.json`) | price, 24h change, high/low, volume |
| `/mas` | MEXC `/api/v3/avgPrice` + `/api/v3/ticker/24hr` | none (public endpoints) | price, 24h change, high/low, volume |

## Implementation Details

### Bitcoin (`/btc`)

- `get_bitcoin_price(logger, ninja_key)` in `services/price_api.py`
- GET request with retry via `http_client.py`
- Returns: `price`, `24h_price_change`, `24h_price_change_percent`, `24h_high`, `24h_low`, `24h_volume`
- On error: returns `{"error": "..."}`

### Massa (`/mas`)

- `get_mas_instant(logger)` + `get_mas_daily(logger)` in `services/price_api.py`
- Both calls run in parallel via `asyncio.gather()` to minimize latency
- On error: checks both responses sequentially, bails on first error

## Error Recovery

- HTTP failure: `http_client.py` retries with exponential backoff
- API error response: handler sends "Nooooo" message + cry image (`BTC_CRY_NAME` or `MAS_CRY_NAME` from `config.py`)
- Timeout: handled by retry logic in `http_client.py`

## Required Configuration

| Key (`topology.json`) | Purpose |
|---|---|
| `ninja_api_key` | API key for API-Ninjas (Bitcoin price) |

## Related Files

| File | Role |
|---|---|
| `src/handlers/price.py` | `/btc` and `/mas` command handlers |
| `src/services/price_api.py` | API-Ninjas and MEXC API calls |
| `src/services/http_client.py` | HTTP client with retry + backoff |
| `src/config.py` | `BTC_CRY_NAME`, `MAS_CRY_NAME` image constants |
