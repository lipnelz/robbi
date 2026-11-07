"""Tests for src/services/massa_rpc.py."""
import json
import logging
import pytest
from unittest.mock import MagicMock, patch

from services.massa_rpc import (
    DEFAULT_MASSA_RPC_URL,
    get_addresses,
    get_node_status,
    measure_rpc_latency,
)


class TestGetAddresses:
    def test_default_rpc_url_uses_massa_api_v2_port(self):
        assert DEFAULT_MASSA_RPC_URL == 'http://massa:33035'

    def test_calls_safe_request_with_correct_post_body(self):
        logger = MagicMock(spec=logging.Logger)
        expected_result = {"result": [{"final_balance": "100"}]}
        with patch('services.massa_rpc.safe_request', return_value=expected_result) as mock_req:
            result = get_addresses(logger, 'AU1test_address')

        mock_req.assert_called_once()
        call_args = mock_req.call_args
        # positional: logger, method, url
        assert call_args[0][1] == 'post'
        assert call_args[0][2] == DEFAULT_MASSA_RPC_URL
        # The data kwarg should be valid JSON containing the address
        data_str = call_args[1]['data']
        data = json.loads(data_str)
        assert data['method'] == 'get_addresses'
        assert 'AU1test_address' in data['params'][0]
        assert result == expected_result

    def test_uses_configured_rpc_url(self):
        logger = MagicMock(spec=logging.Logger)
        rpc_url = 'http://massa-node:33034/api/v2'
        with patch('services.massa_rpc.safe_request') as mock_req:
            get_addresses(logger, 'AU1test_address', rpc_url)

        assert mock_req.call_args[0][2] == rpc_url

    def test_returns_error_dict_on_failure(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.massa_rpc.safe_request', return_value={"error": "timeout"}):
            result = get_addresses(logger, 'AU1test')
        assert "error" in result


class TestGetNodeStatus:
    def test_calls_get_status_on_configured_endpoint(self):
        logger = MagicMock(spec=logging.Logger)
        rpc_url = 'http://massa-node:33034/api/v2'
        expected = {"result": {"current_cycle": 42}}
        with patch('services.massa_rpc.safe_request', return_value=expected) as mock_request:
            result = get_node_status(logger, rpc_url)

        assert result == expected
        args, kwargs = mock_request.call_args
        assert args == (logger, 'post', rpc_url)
        request = json.loads(kwargs['data'])
        assert request['method'] == 'get_status'
        assert request['params'] == []


class TestMeasureRpcLatency:
    def test_happy_path_returns_latency_and_ok_status(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.massa_rpc.get_addresses', return_value={"result": [{}]}):
            with patch('services.massa_rpc.time.time', side_effect=[1000.0, 1000.5]):
                result = measure_rpc_latency(logger, 'AU1test')
        assert "latency_ms" in result
        assert result["status"] == "ok"
        assert result["latency_ms"] == pytest.approx(500.0, abs=1)

    def test_passes_configured_rpc_url_to_address_request(self):
        logger = MagicMock(spec=logging.Logger)
        rpc_url = 'http://massa-node:33034/api/v2'
        with patch('services.massa_rpc.get_addresses', return_value={"result": [{}]}) as mock_get, \
             patch('services.massa_rpc.time.time', side_effect=[1000.0, 1000.5]):
            measure_rpc_latency(logger, 'AU1test', rpc_url)

        mock_get.assert_called_once_with(logger, 'AU1test', rpc_url)

    def test_when_get_addresses_returns_error(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.massa_rpc.get_addresses', return_value={"error": "connection error"}):
            with patch('services.massa_rpc.time.time', side_effect=[1000.0, 1000.2]):
                result = measure_rpc_latency(logger, 'AU1test')
        assert "error" in result
        assert "latency_ms" in result

    def test_when_exception_thrown(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.massa_rpc.get_addresses', side_effect=RuntimeError("boom")):
            result = measure_rpc_latency(logger, 'AU1test')
        assert "error" in result
        assert "boom" in result["error"]
        logger.error.assert_called_once()

    def test_none_logger_uses_root_logger(self):
        with patch('services.massa_rpc.get_addresses', return_value={"result": [{}]}):
            with patch('services.massa_rpc.time.time', side_effect=[0.0, 0.1]):
                result = measure_rpc_latency(None, 'AU1test')
        assert result["status"] == "ok"

    def test_none_logger_on_exception(self):
        with patch('services.massa_rpc.get_addresses', side_effect=Exception("fail")):
            result = measure_rpc_latency(None, 'AU1test')
        assert "error" in result
