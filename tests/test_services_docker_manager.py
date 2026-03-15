"""Tests for src/services/docker_manager.py."""
import logging
import pytest
from unittest.mock import MagicMock, patch

from services.docker_manager import (
    _get_docker_client,
    restart_bot,
    start_docker_node,
    stop_docker_node,
    exec_massa_client,
)


class TestGetDockerClient:
    def test_calls_docker_from_env(self):
        mock_docker = MagicMock()
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        with patch.dict('sys.modules', {'docker': mock_docker}):
            client = _get_docker_client()
        mock_docker.from_env.assert_called_once()
        assert client is mock_client


class TestStartDockerNode:
    def _make_client(self):
        client = MagicMock()
        container = MagicMock()
        client.containers.get.return_value = container
        return client, container

    def test_happy_path_returns_ok_status(self):
        logger = MagicMock(spec=logging.Logger)
        client, container = self._make_client()
        with patch('services.docker_manager._get_docker_client', return_value=client):
            result = start_docker_node(logger, 'massa-node')
        assert result["status"] == "ok"
        assert "massa-node" in result["message"]
        container.start.assert_called_once()
        logger.info.assert_called()

    def test_exception_returns_error_status(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.docker_manager._get_docker_client', side_effect=Exception("no docker")):
            result = start_docker_node(logger, 'massa-node')
        assert result["status"] == "error"
        assert "no docker" in result["message"]
        logger.error.assert_called()

    def test_none_logger_uses_root_logger(self):
        client, container = self._make_client()
        with patch('services.docker_manager._get_docker_client', return_value=client):
            result = start_docker_node(None, 'massa-node')
        assert result["status"] == "ok"


class TestRestartBot:
    def test_happy_path_returns_ok_status(self):
        logger = MagicMock(spec=logging.Logger)
        context = MagicMock()
        context.bot_data = {'robbi_container_name': 'robbi-container'}
        client = MagicMock()
        container = MagicMock()
        client.containers.get.return_value = container

        with patch('services.docker_manager._get_docker_client', return_value=client):
            result = restart_bot(logger, context)

        assert result["status"] == "ok"
        assert "robbi-container" in result["message"]
        container.restart.assert_called_once()
        logger.info.assert_called()

    def test_missing_container_name_returns_error_status(self):
        logger = MagicMock(spec=logging.Logger)
        context = MagicMock()
        context.bot_data = {'robbi_container_name': ''}

        result = restart_bot(logger, context)

        assert result["status"] == "error"
        assert "not configured" in result["message"]
        logger.error.assert_called()

    def test_exception_returns_error_status(self):
        logger = MagicMock(spec=logging.Logger)
        context = MagicMock()
        context.bot_data = {'robbi_container_name': 'robbi-container'}

        with patch('services.docker_manager._get_docker_client', side_effect=RuntimeError("no docker")):
            result = restart_bot(logger, context)

        assert result["status"] == "error"
        assert "no docker" in result["message"]
        logger.error.assert_called()


class TestStopDockerNode:
    def _make_client(self):
        client = MagicMock()
        container = MagicMock()
        client.containers.get.return_value = container
        return client, container

    def test_happy_path_returns_ok_status(self):
        logger = MagicMock(spec=logging.Logger)
        client, container = self._make_client()
        with patch('services.docker_manager._get_docker_client', return_value=client):
            result = stop_docker_node(logger, 'massa-node')
        assert result["status"] == "ok"
        container.stop.assert_called_once_with(timeout=30)
        logger.info.assert_called()

    def test_exception_returns_error_status(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.docker_manager._get_docker_client', side_effect=RuntimeError("fail")):
            result = stop_docker_node(logger, 'massa-node')
        assert result["status"] == "error"
        logger.error.assert_called()

    def test_none_logger_uses_root_logger(self):
        client, container = self._make_client()
        with patch('services.docker_manager._get_docker_client', return_value=client):
            result = stop_docker_node(None, 'massa-container')
        assert result["status"] == "ok"


class TestExecMassaClient:
    def _make_client(self, exit_code=0, output=b"output text"):
        client = MagicMock()
        container = MagicMock()
        container.exec_run.return_value = (exit_code, output)
        client.containers.get.return_value = container
        return client, container

    def test_success_exit_code_zero(self):
        logger = MagicMock(spec=logging.Logger)
        client, container = self._make_client(exit_code=0, output=b"wallet info\n")
        with patch('services.docker_manager._get_docker_client', return_value=client):
            result = exec_massa_client(logger, 'massa-node', 'password', 'wallet_info')
        assert result["status"] == "ok"
        assert "wallet info" in result["output"]
        logger.info.assert_called()

    def test_failure_exit_code_nonzero(self):
        logger = MagicMock(spec=logging.Logger)
        client, container = self._make_client(exit_code=1, output=b"error occurred")
        with patch('services.docker_manager._get_docker_client', return_value=client):
            result = exec_massa_client(logger, 'massa-node', 'password', 'bad_cmd')
        assert result["status"] == "error"
        assert "error occurred" in result["message"]
        logger.error.assert_called()

    def test_exception_returns_error(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.docker_manager._get_docker_client', side_effect=Exception("no container")):
            result = exec_massa_client(logger, 'massa-node', 'password', 'wallet_info')
        assert result["status"] == "error"
        logger.error.assert_called()

    def test_none_logger_uses_root_logger(self):
        client, container = self._make_client(exit_code=0, output=b"ok")
        with patch('services.docker_manager._get_docker_client', return_value=client):
            result = exec_massa_client(None, 'massa-node', 'password', 'wallet_info')
        assert result["status"] == "ok"

    def test_exec_run_called_with_correct_command(self):
        logger = MagicMock(spec=logging.Logger)
        client, container = self._make_client(exit_code=0, output=b"result")
        with patch('services.docker_manager._get_docker_client', return_value=client):
            exec_massa_client(logger, 'massa-node', 'mypass', 'wallet_info extra')
        # First exec_run call builds the command list
        first_call_args = container.exec_run.call_args_list[0]
        cmd = first_call_args[0][0]
        assert './massa-client' in cmd
        assert 'mypass' in cmd
        assert 'wallet_info' in cmd
        assert 'extra' in cmd
