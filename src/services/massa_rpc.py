import json
import time
import logging
from services.http_client import safe_request


def get_addresses(logger, address: str) -> dict:
    """
    Print the address info from a given address

    :param logger: The logger instance
    :param address: The address to querry.
    :return: json dict with all info
    """
    url = 'https://mainnet.massa.net/api/v2'
    headers = {'Content-Type': 'application/json'}
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "get_addresses",
        "params": [[address]]
    }
    return safe_request(logger, 'post', url, headers=headers, data=json.dumps(data))


def measure_rpc_latency(logger, address: str) -> dict:
    """
    Measure RPC latency and check node connectivity.

    :param logger: The logger instance
    :param address: The Massa address to query
    :return: dict with latency_ms and node status
    """
    if logger is None:
        logger = logging.getLogger()

    try:
        start = time.time()
        result = get_addresses(logger, address)
        latency_ms = (time.time() - start) * 1000

        if "error" in result:
            return {"error": result["error"], "latency_ms": round(latency_ms, 2)}
        return {"latency_ms": round(latency_ms, 2), "status": "ok"}
    except Exception as e:
        logger.error(f"Error measuring RPC latency: {e}")
        return {"error": str(e)}
