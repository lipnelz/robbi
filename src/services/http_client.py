import logging
import requests


def safe_request(logger, method: str, url: str, **kwargs) -> dict:
    """Wrapper around requests that handles common HTTP errors consistently.

    :param logger: The logger instance.
    :param method: HTTP method ('get' or 'post').
    :param url: The URL to request.
    :param kwargs: Extra arguments forwarded to requests.request.
    :return: Parsed JSON response or an error dict.
    """
    if logger is None:
        logger = logging.getLogger()
    try:
        response = requests.request(method, url, timeout=20, **kwargs)
        if response.status_code == requests.codes.ok:
            return response.json()
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
