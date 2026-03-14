"""Tests for src/jrequests.py backward-compatibility facade."""
import inspect
import pytest

import jrequests


class TestJrequestsFacade:
    def test_get_addresses_is_callable(self):
        assert callable(jrequests.get_addresses)

    def test_measure_rpc_latency_is_callable(self):
        assert callable(jrequests.measure_rpc_latency)

    def test_get_bitcoin_price_is_callable(self):
        assert callable(jrequests.get_bitcoin_price)

    def test_get_mas_instant_is_callable(self):
        assert callable(jrequests.get_mas_instant)

    def test_get_mas_daily_is_callable(self):
        assert callable(jrequests.get_mas_daily)

    def test_get_system_stats_is_callable(self):
        assert callable(jrequests.get_system_stats)

    def test_start_docker_node_is_callable(self):
        assert callable(jrequests.start_docker_node)

    def test_stop_docker_node_is_callable(self):
        assert callable(jrequests.stop_docker_node)

    def test_exec_massa_client_is_callable(self):
        assert callable(jrequests.exec_massa_client)

    def test_all_symbols_are_functions(self):
        symbols = [
            jrequests.get_addresses,
            jrequests.measure_rpc_latency,
            jrequests.get_bitcoin_price,
            jrequests.get_mas_instant,
            jrequests.get_mas_daily,
            jrequests.get_system_stats,
            jrequests.start_docker_node,
            jrequests.stop_docker_node,
            jrequests.exec_massa_client,
        ]
        for sym in symbols:
            assert callable(sym), f"{sym} should be callable"

    def test_get_addresses_points_to_massa_rpc(self):
        from services.massa_rpc import get_addresses
        assert jrequests.get_addresses is get_addresses

    def test_get_bitcoin_price_points_to_price_api(self):
        from services.price_api import get_bitcoin_price
        assert jrequests.get_bitcoin_price is get_bitcoin_price

    def test_get_system_stats_points_to_system_monitor(self):
        from services.system_monitor import get_system_stats
        assert jrequests.get_system_stats is get_system_stats

    def test_start_docker_node_points_to_docker_manager(self):
        from services.docker_manager import start_docker_node
        assert jrequests.start_docker_node is start_docker_node
