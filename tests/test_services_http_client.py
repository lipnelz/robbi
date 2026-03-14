"""Tests for src/services/http_client.py."""
import logging
import pytest
import requests
from unittest.mock import MagicMock, patch

from services.http_client import safe_request


class TestSafeRequest:
    def _make_logger(self):
        logger = MagicMock(spec=logging.Logger)
        return logger

    def test_200_ok_returns_json(self):
        logger = self._make_logger()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": "50000"}
        # requests.codes.ok == 200
        with patch('services.http_client.requests.request', return_value=mock_response) as mock_req:
            result = safe_request(logger, 'get', 'https://example.com/api')
        assert result == {"price": "50000"}
        mock_req.assert_called_once_with('get', 'https://example.com/api', timeout=20)

    def test_non_200_returns_error_dict(self):
        logger = self._make_logger()
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch('services.http_client.requests.request', return_value=mock_response):
            result = safe_request(logger, 'get', 'https://example.com/api')
        assert "error" in result
        logger.error.assert_called_once()

    def test_timeout_returns_error_dict(self):
        logger = self._make_logger()
        with patch('services.http_client.requests.request', side_effect=requests.Timeout):
            result = safe_request(logger, 'get', 'https://example.com/api')
        assert "error" in result
        assert "timed out" in result["error"].lower()
        logger.error.assert_called_once()

    def test_connection_error_returns_error_dict(self):
        logger = self._make_logger()
        with patch('services.http_client.requests.request', side_effect=requests.ConnectionError):
            result = safe_request(logger, 'get', 'https://example.com/api')
        assert "error" in result
        assert "connection" in result["error"].lower()
        logger.error.assert_called_once()

    def test_request_exception_returns_error_dict(self):
        logger = self._make_logger()
        with patch(
            'services.http_client.requests.request',
            side_effect=requests.RequestException("boom")
        ):
            result = safe_request(logger, 'get', 'https://example.com/api')
        assert "error" in result
        assert "Unexpected error" in result["error"]
        logger.error.assert_called_once()

    def test_none_logger_uses_root_logger(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        with patch('services.http_client.requests.request', return_value=mock_response):
            result = safe_request(None, 'get', 'https://example.com/api')
        assert result == {"ok": True}

    def test_none_logger_on_error_path(self):
        """None logger should not crash when a non-200 status is returned."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch('services.http_client.requests.request', return_value=mock_response):
            result = safe_request(None, 'get', 'https://example.com/api')
        assert "error" in result

    def test_post_method_forwarded(self):
        logger = self._make_logger()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        with patch('services.http_client.requests.request', return_value=mock_response) as mock_req:
            safe_request(logger, 'post', 'https://example.com/rpc', json={"key": "val"})
        mock_req.assert_called_once_with(
            'post', 'https://example.com/rpc', timeout=20, json={"key": "val"}
        )

    def test_kwargs_forwarded_to_request(self):
        logger = self._make_logger()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        with patch('services.http_client.requests.request', return_value=mock_response) as mock_req:
            safe_request(logger, 'get', 'https://example.com', headers={"X-Key": "abc"})
        mock_req.assert_called_once_with(
            'get', 'https://example.com', timeout=20, headers={"X-Key": "abc"}
        )
