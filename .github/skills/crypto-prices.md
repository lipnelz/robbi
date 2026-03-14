# Skill : Prix des cryptomonnaies

## Description

Ce skill récupère et affiche les prix en temps réel de Bitcoin (BTC) et de Massa (MAS) via des API externes. Il expose deux commandes : `/btc` pour le prix du Bitcoin et `/mas` pour le prix Massa/USDT.

## Commandes

```
/btc
/mas
```

---

## Sous-skills

### 1. Prix Bitcoin — `/btc`

#### Source de données
- **API** : [API-Ninjas](https://www.api-ninjas.com/) — endpoint `/v1/cryptoprice?symbol=BTCUSDT`
- **Authentification** : Header `X-Api-Key: <ninja_api_key>`
- **Clé de configuration** : `ninja_api_key` dans `topology.json`

#### Fonction d'appel (`services/price_api.py`)
```python
get_bitcoin_price(logger, ninja_key) -> dict
```
- Effectue une requête GET avec retry (via `http_client.py`)
- Retourne les champs : `price`, `24h_price_change`, `24h_price_change_percent`, `24h_high`, `24h_low`, `24h_volume`
- En cas d'erreur réseau ou HTTP → retourne `{"error": "..."}`

#### Format de la réponse bot
```
Price: 65432.10 $
24h Price Change: +1234.56
24h Price Change Percent: +1.92%
24h High: 66000.00
24h Low: 64000.00
24h Volume: 12345678.90
```

#### Gestion d'erreur
- En cas d'erreur API → message "Nooooo" + image `BTC_CRY_NAME` (définie dans `config.py`)

---

### 2. Prix Massa — `/mas`

#### Sources de données
- **API instantanée** : MEXC — `GET /api/v3/avgPrice?symbol=MASUSDT`
- **API 24h** : MEXC — `GET /api/v3/ticker/24hr?symbol=MASUSDT`
- Pas d'authentification requise pour les endpoints publics MEXC

#### Fonctions d'appel (`services/price_api.py`)
```python
get_mas_instant(logger) -> dict   # Prix moyen actuel
get_mas_daily(logger) -> dict     # Statistiques 24h
```
- Les deux appels sont lancés **en parallèle** via `asyncio.gather()` pour minimiser la latence
- Retournent `{"error": "..."}` en cas d'échec réseau ou HTTP

#### Format de la réponse bot
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

#### Gestion d'erreur
- Vérifie les deux réponses API séquentiellement (bail on first error)
- En cas d'erreur → message "Nooooo" + image `MAS_CRY_NAME` (définie dans `config.py`)

---

### 3. Client HTTP sécurisé (`services/http_client.py`)

- Enveloppe commune utilisée par toutes les fonctions d'appel API
- Implémente une logique de retry avec backoff exponentiel
- Gère les timeouts de connexion et de lecture
- Retourne un dict avec le corps de la réponse ou `{"error": "..."}` en cas d'échec

---

## Fichiers concernés

| Fichier | Rôle |
|---------|------|
| `src/handlers/price.py` | Handlers `/btc` et `/mas` |
| `src/services/price_api.py` | Appels API-Ninjas et MEXC |
| `src/services/http_client.py` | Client HTTP avec retry |
| `src/config.py` | Constantes `BTC_CRY_NAME`, `MAS_CRY_NAME` |

## Configuration requise

| Clé `topology.json` | Description |
|---------------------|-------------|
| `ninja_api_key` | Clé API pour API-Ninjas (Bitcoin) |

## Liens externes

- [API-Ninjas — Crypto Price](https://www.api-ninjas.com/api/cryptoprice)
- [MEXC API — avgPrice](https://mexcdevelop.github.io/apidocs/spot_v3_en/#current-average-price)
- [MEXC API — 24hr Ticker](https://mexcdevelop.github.io/apidocs/spot_v3_en/#24hr-ticker-price-change-statistics)
