import json
import time
import logging
from services.http_client import safe_request


DEFAULT_MASSA_RPC_URL = 'http://massa:33034/api/v2'


def get_addresses(logger, address: str, rpc_url: str = DEFAULT_MASSA_RPC_URL) -> dict:
    """
    Retrieve address information from the configured Massa node JSON-RPC endpoint.

    :param logger: The logger instance
    :param address: The address to query.
    :param rpc_url: The Massa node JSON-RPC endpoint.
    :return: json dict with all info
    """
    headers = {'Content-Type': 'application/json'}
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "get_addresses",
        "params": [[address]]
    }
    return safe_request(logger, 'post', rpc_url, headers=headers, data=json.dumps(data))


def get_node_status(logger, rpc_url: str = DEFAULT_MASSA_RPC_URL) -> dict:
    """Fetch runtime, peer, and consensus information from the Massa node."""
    headers = {'Content-Type': 'application/json'}
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "get_status",
        "params": []
    }
    return safe_request(logger, 'post', rpc_url, headers=headers, data=json.dumps(data))


def measure_rpc_latency(logger, address: str, rpc_url: str = DEFAULT_MASSA_RPC_URL) -> dict:
    """
    Measure RPC latency and check node connectivity.

    :param logger: The logger instance
    :param address: The Massa address to query
    :param rpc_url: The Massa node JSON-RPC endpoint.
    :return: dict with latency_ms and node status
    """
    if logger is None:
        logger = logging.getLogger()

    try:
        start = time.time()
        result = get_addresses(logger, address, rpc_url)
        latency_ms = (time.time() - start) * 1000

        if "error" in result:
            return {"error": result["error"], "latency_ms": round(latency_ms, 2)}
        return {"latency_ms": round(latency_ms, 2), "status": "ok"}
    except Exception as e:
        logger.error(f"Error measuring RPC latency: {e}")
        return {"error": str(e)}
