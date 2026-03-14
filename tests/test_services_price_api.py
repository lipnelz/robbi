"""Tests for src/services/price_api.py."""
import logging
import pytest
from unittest.mock import MagicMock, patch

from services.price_api import get_bitcoin_price, get_mas_instant, get_mas_daily


class TestGetBitcoinPrice:
    def test_calls_safe_request_with_correct_url_and_headers(self):
        logger = MagicMock(spec=logging.Logger)
        api_key = 'my_ninja_key'
        mock_result = {"price": "50000"}
        with patch('services.price_api.safe_request', return_value=mock_result) as mock_req:
            result = get_bitcoin_price(logger, api_key)

        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][1] == 'get'
        assert 'bitcoin' in call_args[0][2]
        assert call_args[1]['headers']['X-Api-Key'] == api_key
        assert result == mock_result

    def test_returns_error_on_failure(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.price_api.safe_request', return_value={"error": "timeout"}):
            result = get_bitcoin_price(logger, 'key')
        assert "error" in result


class TestGetMasInstant:
    def test_calls_safe_request_with_correct_url(self):
        logger = MagicMock(spec=logging.Logger)
        mock_result = {"price": "0.005"}
        with patch('services.price_api.safe_request', return_value=mock_result) as mock_req:
            result = get_mas_instant(logger)

        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][1] == 'get'
        assert 'MASUSDT' in call_args[0][2]
        assert result == mock_result

    def test_returns_error_on_failure(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.price_api.safe_request', return_value={"error": "fail"}):
            result = get_mas_instant(logger)
        assert "error" in result


class TestGetMasDaily:
    def test_calls_safe_request_with_correct_url(self):
        logger = MagicMock(spec=logging.Logger)
        mock_result = {"symbol": "MASUSDT", "volume": "1234"}
        with patch('services.price_api.safe_request', return_value=mock_result) as mock_req:
            result = get_mas_daily(logger)

        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][1] == 'get'
        assert 'MASUSDT' in call_args[0][2]
        assert '24hr' in call_args[0][2]
        assert result == mock_result

    def test_returns_error_on_failure(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.price_api.safe_request', return_value={"error": "fail"}):
            result = get_mas_daily(logger)
        assert "error" in result
