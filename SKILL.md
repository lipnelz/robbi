# SKILL.md — Robbi Bot Skills

This file lists the skills of the Robbi bot. Each skill is documented in detail in a dedicated file under the [`.github/skills/`](.github/skills/) directory.

## Skills List

| Skill | Commands | Description |
|-------|----------|-------------|
| [Massa Node Monitoring](.github/skills/node-monitoring) | `/node` | Real-time node status, balance, rolls, validation chart |
| [Balance History](.github/skills/balance-history) | `/hist`, `/flush` | JSON persistence, charts, log clearing |
| [Scheduled Reports](.github/skills/scheduled-reports) | *(automatic)* | Ping every 60 min, reports at 7am/12pm/9pm |
| [Cryptocurrency Prices](.github/skills/crypto-prices) | `/btc`, `/mas` | Bitcoin price (API-Ninjas) and Massa/USDT (MEXC) |
| [System Monitoring](.github/skills/system-monitoring) | `/hi`, `/temperature`, `/perf` | CPU/RAM/temperature metrics, RPC latency, uptime |
| [Docker Management](.github/skills/docker-management) | `/docker` | Interactive menu: start/stop node, wallet_info, buy/sell rolls |
| [Authentication](.github/skills/authentication) | *(cross-cutting)* | `@auth_required` decorators, `topology.json` whitelist |
