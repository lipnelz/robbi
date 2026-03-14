"""Tests for src/services/massa_rpc.py."""
import json
import logging
import pytest
from unittest.mock import MagicMock, patch

from services.massa_rpc import get_addresses, measure_rpc_latency


class TestGetAddresses:
    def test_calls_safe_request_with_correct_post_body(self):
        logger = MagicMock(spec=logging.Logger)
        expected_result = {"result": [{"final_balance": "100"}]}
        with patch('services.massa_rpc.safe_request', return_value=expected_result) as mock_req:
            result = get_addresses(logger, 'AU1test_address')

        mock_req.assert_called_once()
        call_args = mock_req.call_args
        # positional: logger, method, url
        assert call_args[0][1] == 'post'
        assert 'massa.net' in call_args[0][2]
        # The data kwarg should be valid JSON containing the address
        data_str = call_args[1]['data']
        data = json.loads(data_str)
        assert data['method'] == 'get_addresses'
        assert 'AU1test_address' in data['params'][0]
        assert result == expected_result

    def test_returns_error_dict_on_failure(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.massa_rpc.safe_request', return_value={"error": "timeout"}):
            result = get_addresses(logger, 'AU1test')
        assert "error" in result


class TestMeasureRpcLatency:
    def test_happy_path_returns_latency_and_ok_status(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.massa_rpc.get_addresses', return_value={"result": [{}]}):
            with patch('services.massa_rpc.time.time', side_effect=[1000.0, 1000.5]):
                result = measure_rpc_latency(logger, 'AU1test')
        assert "latency_ms" in result
        assert result["status"] == "ok"
        assert result["latency_ms"] == pytest.approx(500.0, abs=1)

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
