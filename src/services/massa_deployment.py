import os
import subprocess
import threading
from pathlib import Path


DEFAULT_COMPOSE_PROJECT_DIR = '/host-project'
DEFAULT_COMPOSE_FILE = '/host-project/docker-compose.yml'
_REBUILD_LOCK = threading.Lock()


def rebuild_massa() -> subprocess.CompletedProcess:
    """Rebuild and recreate Massa using the configured Docker Compose project."""
    project_dir = Path(os.environ.get(
        'MASSA_COMPOSE_PROJECT_DIR',
        DEFAULT_COMPOSE_PROJECT_DIR,
    ))
    compose_file = Path(os.environ.get('MASSA_COMPOSE_FILE', DEFAULT_COMPOSE_FILE))
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Compose project directory not found: {project_dir}")
    if not compose_file.is_file():
        raise FileNotFoundError(f"Compose file not found: {compose_file}")

    with _REBUILD_LOCK:
        return subprocess.run(
            [
                'docker-compose',
                '--project-directory', str(project_dir),
                '-f', str(compose_file),
                'up', '-d', '--build', '--force-recreate', 'massa',
            ],
            cwd=project_dir,
            capture_output=True,
            check=False,
            text=True,
        )
