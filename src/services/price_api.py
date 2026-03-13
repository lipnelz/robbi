from services.http_client import safe_request


def get_bitcoin_price(logger, api_key: str) -> dict:
    """
    Get bitcoin price

    :param logger: The logger instance
    :param api_key: Ninja api key as string
    :return: json string encoded with btc price
    """
    url = 'https://api.api-ninjas.com/v1/bitcoin'
    headers = {'X-Api-Key': api_key}
    return safe_request(logger, 'get', url, headers=headers)


def get_mas_instant(logger) -> dict:
    """
    Current MAS Average Price

    :param logger: The logger instance
    :return: json string encoded MAS/USDT current price
    """
    return safe_request(logger, 'get', 'https://api.mexc.com/api/v3/avgPrice?symbol=MASUSDT')


def get_mas_daily(logger) -> dict:
    """
    Get 24hr Ticker MAS Price Change Statistics

    :param logger: The logger instance
    :return: json with MAS/USDT info on a period of 24hr
    """
    return safe_request(logger, 'get', 'https://api.mexc.com/api/v3/ticker/24hr?symbol=MASUSDT')
