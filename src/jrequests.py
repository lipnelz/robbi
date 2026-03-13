"""Backward-compatibility facade.

All functions have been moved to dedicated service modules:
- services.massa_rpc: get_addresses, measure_rpc_latency
- services.price_api: get_bitcoin_price, get_mas_instant, get_mas_daily
- services.system_monitor: get_system_stats
- services.docker_manager: start_docker_node, stop_docker_node, exec_massa_client
"""
from services.massa_rpc import get_addresses, measure_rpc_latency  # noqa: F401
from services.price_api import get_bitcoin_price, get_mas_instant, get_mas_daily  # noqa: F401
from services.system_monitor import get_system_stats  # noqa: F401
from services.docker_manager import start_docker_node, stop_docker_node, exec_massa_client  # noqa: F401
