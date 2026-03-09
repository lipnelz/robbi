import requests
import json
import logging


def _safe_request(logger, method: str, url: str, **kwargs) -> dict:
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
    return _safe_request(logger, 'post', url, headers=headers, data=json.dumps(data))


def get_bitcoin_price(logger, api_key: str) -> dict:
    """
    Get bitcoin price

    :param logger: The logger instance
    :param api_key: Ninja api key as string
    :return: json string encoded with btc price
    """
    url = 'https://api.api-ninjas.com/v1/bitcoin'
    headers = {'X-Api-Key': api_key}
    return _safe_request(logger, 'get', url, headers=headers)


def get_mas_instant(logger) -> dict:
    """
    Current MAS Average Price

    :param logger: The logger instance
    :return: json string encoded MAS/USDT current price
    """
    return _safe_request(logger, 'get', 'https://api.mexc.com/api/v3/avgPrice?symbol=MASUSDT')


def get_mas_daily(logger) -> dict:
    """
    Get 24hr Ticker MAS Price Change Statistics

    :param logger: The logger instance
    :param api_key: Ninja api key as string
    :return: json with MAS/USDT info on a period of 24hr
    """
    return _safe_request(logger, 'get', 'https://api.mexc.com/api/v3/ticker/24hr?symbol=MASUSDT')

def get_system_stats(logger) -> dict:
    """
    Get system statistics (CPU, RAM, Temperature)

    :param logger: The logger instance
    :return: json dict with system stats
    """
    try:
        import psutil
    except ImportError:
        if logger is None:
            logger = logging.getLogger()
        logger.error("psutil not installed")
        return {"error": "psutil library not installed"}

    if logger is None:
        logger = logging.getLogger()

    try:
        # Get overall CPU and per-core CPU usage
        cpu_overall = psutil.cpu_percent(interval=1)
        cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
        
        stats = {
            "cpu_percent": cpu_overall,
            "cpu_cores": [{"core": i, "percent": percent} for i, percent in enumerate(cpu_per_core)],
            "ram_percent": psutil.virtual_memory().percent,
            "ram_available_gb": round(psutil.virtual_memory().available / (1024 ** 3), 2),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2)
        }

        # Try to get temperature (Linux only)
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    temperature_details = []
                    for sensor_type, entries in temps.items():
                        for entry in entries:
                            temperature_details.append({
                                "sensor": sensor_type,
                                "label": entry.label or f"Sensor {len(temperature_details)}",
                                "current": round(entry.current, 1)
                            })
                    if temperature_details:
                        stats["temperature_details"] = temperature_details
                        all_temps = [t["current"] for t in temperature_details]
                        stats["temperature_avg"] = round(sum(all_temps) / len(all_temps), 1)
        except Exception as e:
            logger.warning(f"Could not retrieve temperature: {e}")

        return stats
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {"error": f"Unexpected error: {str(e)}"}


def measure_rpc_latency(logger, address: str) -> dict:
    """
    Measure RPC latency and check node connectivity.
    
    :param logger: The logger instance
    :param address: The Massa address to query
    :return: dict with latency_ms and node status
    """
    import time
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


def _get_docker_client():
    """Create a Docker client connected via the mounted socket."""
    import docker
    return docker.from_env()


def start_docker_node(logger, container_name: str) -> dict:
    """
    Start a Docker container running the Massa node.
    
    :param logger: The logger instance
    :param container_name: Name of the Docker container (e.g., 'massa-node')
    :return: dict with status and message
    """
    if logger is None:
        logger = logging.getLogger()
    
    try:
        client = _get_docker_client()
        container = client.containers.get(container_name)
        container.start()
        logger.info(f"Docker container '{container_name}' started successfully.")
        return {"status": "ok", "message": f"✅ Container '{container_name}' started."}
    except Exception as e:
        logger.error(f"Error starting Docker container: {e}")
        return {"status": "error", "message": f"❌ Error: {str(e)}"}


def stop_docker_node(logger, container_name: str) -> dict:
    """
    Stop a Docker container running the Massa node.
    
    :param logger: The logger instance
    :param container_name: Name of the Docker container (e.g., 'massa-container')
    :return: dict with status and message
    """
    if logger is None:
        logger = logging.getLogger()
    
    try:
        client = _get_docker_client()
        container = client.containers.get(container_name)
        container.stop(timeout=30)
        logger.info(f"Docker container '{container_name}' stopped successfully.")
        return {"status": "ok", "message": f"✅ Container '{container_name}' stopped."}
    except Exception as e:
        logger.error(f"Error stopping Docker container: {e}")
        return {"status": "error", "message": f"❌ Error: {str(e)}"}


def exec_massa_client(logger, container_name: str, password: str, command: str) -> dict:
    """
    Execute a command via massa-client inside a Docker container.
    
    :param logger: The logger instance
    :param container_name: Name of the Docker container
    :param password: Massa client password
    :param command: The massa-client command to execute (e.g. 'wallet_info')
    :return: dict with status, message/output
    """
    if logger is None:
        logger = logging.getLogger()
    
    try:
        client = _get_docker_client()
        container = client.containers.get(container_name)
        cmd = ['./massa-client', '-p', password, '-a', command]
        exit_code, output = container.exec_run(cmd, workdir='/massa/massa-client')
        decoded = output.decode('utf-8', errors='replace').strip()
        if exit_code == 0:
            logger.info(f"massa-client command '{command}' executed successfully.")
            return {"status": "ok", "output": decoded}
        else:
            logger.error(f"massa-client command failed: {decoded}")
            return {"status": "error", "message": f"❌ Command failed:\n{decoded}"}
    except Exception as e:
        logger.error(f"Error executing massa-client: {e}")
        return {"status": "error", "message": f"❌ Error: {str(e)}"}
