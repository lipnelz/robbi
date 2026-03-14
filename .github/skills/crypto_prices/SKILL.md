# Skill: Cryptocurrency Prices

## Description

This skill retrieves and displays real-time prices for Bitcoin (BTC) and Massa (MAS) via external APIs. It exposes two commands: `/btc` for the Bitcoin price and `/mas` for the Massa/USDT price.

## Commands

```
/btc
/mas
```

---

## Sub-skills

### 1. Bitcoin Price — `/btc`

#### Data Source
- **API**: [API-Ninjas](https://www.api-ninjas.com/) — endpoint `/v1/cryptoprice?symbol=BTCUSDT`
- **Authentication**: Header `X-Api-Key: <ninja_api_key>`
- **Configuration key**: `ninja_api_key` in `topology.json`

#### API Call Function (`services/price_api.py`)
```python
get_bitcoin_price(logger, ninja_key) -> dict
```
- Performs a GET request with retry (via `http_client.py`)
- Returns fields: `price`, `24h_price_change`, `24h_price_change_percent`, `24h_high`, `24h_low`, `24h_volume`
- On network or HTTP error → returns `{"error": "..."}`

#### Bot Response Format
```
Price: 65432.10 $
24h Price Change: +1234.56
24h Price Change Percent: +1.92%
24h High: 66000.00
24h Low: 64000.00
24h Volume: 12345678.90
```

#### Error Handling
- On API error → "Nooooo" message + `BTC_CRY_NAME` image (defined in `config.py`)

---

### 2. Massa Price — `/mas`

#### Data Sources
- **Instant API**: MEXC — `GET /api/v3/avgPrice?symbol=MASUSDT`
- **24h API**: MEXC — `GET /api/v3/ticker/24hr?symbol=MASUSDT`
- No authentication required for public MEXC endpoints

#### API Call Functions (`services/price_api.py`)
```python
get_mas_instant(logger) -> dict   # Current average price
get_mas_daily(logger) -> dict     # 24h statistics
```
- Both calls are launched **in parallel** via `asyncio.gather()` to minimize latency
- Return `{"error": "..."}` on network or HTTP failure

#### Bot Response Format
```
MASUSDT
-----------
Price: 0.00734 USDT
24h Volume: 1234567.890000
-----------
Price Change %: +0.123456%
Price Change: +0.000009
24h High: 0.007500
24h Low: 0.007100
```

#### Error Handling
- Checks both API responses sequentially (bail on first error)
- On error → "Nooooo" message + `MAS_CRY_NAME` image (defined in `config.py`)

---

### 3. Secure HTTP Client (`services/http_client.py`)

- Common wrapper used by all API call functions
- Implements retry logic with exponential backoff
- Handles connection and read timeouts
- Returns a dict with the response body or `{"error": "..."}` on failure

---

## Related Files

| File | Role |
|------|------|
| `src/handlers/price.py` | `/btc` and `/mas` handlers |
| `src/services/price_api.py` | API-Ninjas and MEXC API calls |
| `src/services/http_client.py` | HTTP client with retry |
| `src/config.py` | `BTC_CRY_NAME`, `MAS_CRY_NAME` constants |

## Required Configuration

| `topology.json` Key | Description |
|---------------------|-------------|
| `ninja_api_key` | API key for API-Ninjas (Bitcoin) |

## External Links

- [API-Ninjas — Crypto Price](https://www.api-ninjas.com/api/cryptoprice)
- [MEXC API — avgPrice](https://mexcdevelop.github.io/apidocs/spot_v3_en/#current-average-price)
- [MEXC API — 24hr Ticker](https://mexcdevelop.github.io/apidocs/spot_v3_en/#24hr-ticker-price-change-statistics)
