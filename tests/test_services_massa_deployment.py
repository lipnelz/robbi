import subprocess
from unittest.mock import patch

import pytest

from services.massa_deployment import rebuild_massa


def test_rebuild_massa_runs_compose_for_massa_only(tmp_path, monkeypatch):
    compose_file = tmp_path / 'docker-compose.yml'
    compose_file.write_text('services: {}', encoding='utf-8')
    monkeypatch.setenv('MASSA_COMPOSE_PROJECT_DIR', str(tmp_path))
    monkeypatch.setenv('MASSA_COMPOSE_FILE', str(compose_file))

    with patch(
        'services.massa_deployment.subprocess.run',
        return_value=subprocess.CompletedProcess([], 0, stdout='', stderr=''),
    ) as run:
        result = rebuild_massa()

    assert result.returncode == 0
    run.assert_called_once_with(
        [
            'docker-compose',
            '--project-directory', str(tmp_path),
            '-f', str(compose_file),
            'up', '-d', '--build', '--force-recreate', 'massa',
        ],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )


def test_rebuild_massa_requires_compose_project(tmp_path, monkeypatch):
    monkeypatch.setenv('MASSA_COMPOSE_PROJECT_DIR', str(tmp_path / 'missing'))
    monkeypatch.setenv('MASSA_COMPOSE_FILE', str(tmp_path / 'docker-compose.yml'))

    with pytest.raises(FileNotFoundError, match='project directory'):
        rebuild_massa()
