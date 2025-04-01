import requests
import json
import logging

def get_status(logger, address: str) -> dict:
    """
    Print the status from a given address

    :param logger: The logger instance
    :param address: The address to querry.
    :return: json string encoded due to 'None' value returned by remote server
    """
    # Define API and URL
    url = 'https://mainnet.massa.net/api/v2'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "get_status",
         "params": []
    }

    if logger is None:
        logger = logging.getLogger()
    try:
        # Send POST request
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
        # Check response status
        if response.status_code == requests.codes.ok:
            cleaned_response = json.dumps(response.json(), indent=4).rstrip('None\n').strip()
            data = json.loads(cleaned_response)
            print(data)
            return data
        else:
            logger.error(f"Error: {response.status_code}")
    except requests.Timeout:
        logger.error("Request timed out. The server took too long to respond.")
        return {"error": "Request timed out. The server took too long to respond."}
    except requests.ConnectionError:
        logger.error("Failed to establish a connection to the server.")
        return {"error": "Connection error. Unable to reach the server."}
    except requests.RequestException as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

def get_addresses(logger, address: str) -> dict:
    """
    Print the address info from a given address

    :param logger: The logger instance
    :param address: The address to querry.
    :return: json dict with all info
    """
    # Define API and URL
    url = 'https://mainnet.massa.net/api/v2'
    headers = {
        'Content-Type': 'application/json'
    }
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "get_addresses",
         "params": [[address]]
    }

    if logger is None:
        logger = logging.getLogger()

    try:
        # Send POST request
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
        # Check response status
        if response.status_code == requests.codes.ok:
            # Parse JSON
            response_json = response.json()
            print(json.dumps(response_json, indent=4))
            return response_json
        else:
            logger.error(f"Error: {response.status_code}")
            return {"error": "Status code not handled."}
    except requests.Timeout:
        logger.error("Request timed out. The server took too long to respond.")
        return {"error": "Request timed out. The server took too long to respond."}
    except requests.ConnectionError:
        logger.error("Failed to establish a connection to the server.")
        return {"error": "Connection error. Unable to reach the server."}
    except requests.RequestException as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

def get_bitcoin_price(logger, api_key: str) -> dict:
    """
    Get bitcoin price

    :param logger: The logger instance
    :param api_key: Ninja api key as string
    :return: json string encoded with btc price
    """
    # CoinDesk API URL
    url = 'https://api.api-ninjas.com/v1/bitcoin'
    headers = {
        'X-Api-Key': api_key
    }
    # Use the provided logger or default to the logging module's root logger
    if logger is None:
        logger = logging.getLogger()

    try:
        response = requests.get(url, headers, timeout=10)
        if response.status_code == requests.codes.ok:
            return response.json()
        else:
            logger.error(f"Error retrieving Bitcoin price: {response.status_code}")
            return {"error": "Status code not handled."}
    except requests.Timeout:
        logger.error("Request timed out. The server took too long to respond.")
        return {"error": "Request timed out. The server took too long to respond."}
    except requests.ConnectionError:
        logger.error("Failed to establish a connection to the server.")
        return {"error": "Connection error. Unable to reach the server."}
    except requests.RequestException as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

def get_mas_instant(logger) -> dict:
    """
    Current MAS Average Price

    :param logger: The logger instance
    :return: json string encoded MAS/USDT current price
    """
    url = 'https://api.mexc.com/api/v3/avgPrice?symbol=MASUSDT'
    if logger is None:
        logger = logging.getLogger()
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == requests.codes.ok:
            return response.json()
        else:
            logger.error(f"Error retrieving MAS price: {response.status_code}")
            return {"error": "Status code not handled."}
    except requests.Timeout:
        logger.error("Request timed out. The server took too long to respond.")
        return {"error": "Request timed out. The server took too long to respond."}
    except requests.ConnectionError:
        logger.error("Failed to establish a connection to the server.")
        return {"error": "Connection error. Unable to reach the server."}
    except requests.RequestException as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

def get_mas_daily(logger) -> dict:
    """
    Get 24hr Ticker MAS Price Change Statistics

    :param logger: The logger instance
    :param api_key: Ninja api key as string
    :return: json with MAS/USDT info on a period of 24hr
    """
    url = 'https://api.mexc.com/api/v3/ticker/24hr?symbol=MASUSDT'

    if logger is None:
        logger = logging.getLogger()
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == requests.codes.ok:
            return response.json()
        else:
            logger.error(f"Error retrieving 24hr MAS info: {response.status_code}")
            return {"error": "Status code not handled."}
    except requests.Timeout:
        logger.error("Request timed out. The server took too long to respond.")
        return {"error": "Request timed out. The server took too long to respond."}
    except requests.ConnectionError:
        logger.error("Failed to establish a connection to the server.")
        return {"error": "Connection error. Unable to reach the server."}
    except requests.RequestException as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {"error": f"Unexpected error: {str(e)}"}
