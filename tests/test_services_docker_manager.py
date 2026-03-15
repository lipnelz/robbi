"""Tests for src/services/docker_manager.py."""
import logging
import pytest
from unittest.mock import MagicMock, patch

from services.docker_manager import (
    _get_docker_client,
    _is_image_allowed,
    start_docker_node,
    stop_docker_node,
    exec_massa_client,
    update_docker_container_image,
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


class TestIsImageAllowed:
    def test_allow_all_when_list_empty(self):
        assert _is_image_allowed('ghcr.io/lipnelz/robbi:latest', None)
        assert _is_image_allowed('ghcr.io/lipnelz/robbi:latest', [])

    def test_exact_match_allowed(self):
        assert _is_image_allowed('ghcr.io/lipnelz/robbi:latest', ['ghcr.io/lipnelz/robbi:latest'])

    def test_repository_match_allowed(self):
        assert _is_image_allowed('ghcr.io/lipnelz/robbi:latest', ['ghcr.io/lipnelz/robbi'])

    def test_not_allowed(self):
        assert not _is_image_allowed('docker.io/library/python:3.12', ['ghcr.io/lipnelz/robbi'])


class TestUpdateDockerContainerImage:
    def _make_client_and_container(self):
        client = MagicMock()

        old_container = MagicMock()
        old_container.attrs = {
            'Config': {
                'Env': ['A=B'],
                'Cmd': ['python', 'src/main.py'],
                'Entrypoint': ['/app/entrypoint.sh'],
                'WorkingDir': '/app',
                'Labels': {'com.docker.compose.project': 'robbi'},
                'User': '',
            },
            'HostConfig': {
                'Binds': ['/var/run/docker.sock:/var/run/docker.sock'],
                'RestartPolicy': {'Name': 'unless-stopped'},
                'NetworkMode': 'bridge',
            },
            'NetworkSettings': {'Networks': {}},
        }
        old_container.image.tags = ['ghcr.io/lipnelz/robbi:old']

        new_container = MagicMock()

        client.containers.get.side_effect = [old_container, Exception('no stale candidate')]
        client.containers.create.return_value = new_container

        return client, old_container, new_container

    def test_happy_path(self):
        logger = MagicMock(spec=logging.Logger)
        client, old_container, new_container = self._make_client_and_container()

        with patch('services.docker_manager._get_docker_client', return_value=client):
            result = update_docker_container_image(
                logger,
                'robbi',
                'ghcr.io/lipnelz/robbi:latest',
                allowed_images=['ghcr.io/lipnelz/robbi'],
            )

        assert result['status'] == 'ok'
        client.images.pull.assert_called_once_with('ghcr.io/lipnelz/robbi:latest')
        old_container.stop.assert_called_once_with(timeout=30)
        old_container.remove.assert_called_once()
        new_container.rename.assert_called_once_with('robbi')

    def test_refused_by_allowlist(self):
        logger = MagicMock(spec=logging.Logger)
        result = update_docker_container_image(
            logger,
            'robbi',
            'docker.io/library/python:3.12',
            allowed_images=['ghcr.io/lipnelz/robbi'],
        )
        assert result['status'] == 'error'
        assert 'not allowed' in result['message']

    def test_missing_parameters(self):
        logger = MagicMock(spec=logging.Logger)
        result = update_docker_container_image(logger, '', '')
        assert result['status'] == 'error'

    def test_exception_returns_error(self):
        logger = MagicMock(spec=logging.Logger)
        with patch('services.docker_manager._get_docker_client', side_effect=RuntimeError('docker down')):
            result = update_docker_container_image(
                logger,
                'robbi',
                'ghcr.io/lipnelz/robbi:latest',
            )
        assert result['status'] == 'error'
