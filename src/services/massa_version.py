import os
import re
import tempfile
from pathlib import Path


_VERSION_ARGUMENT = re.compile(r'^ARG MASSA_VERSION=([^\r\n]+)$', re.MULTILINE)
_VALID_VERSION = re.compile(r'^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$')
DEFAULT_MASSA_DOCKERFILE = '/massa-build-context/Dockerfile'


def _read_dockerfile(dockerfile_path: str) -> tuple[Path, str, re.Match]:
    path = Path(dockerfile_path)
    content = path.read_text(encoding='utf-8')
    matches = list(_VERSION_ARGUMENT.finditer(content))
    if len(matches) != 1:
        raise ValueError("Le Dockerfile doit contenir exactement un ARG MASSA_VERSION.")
    return path, content, matches[0]


def read_massa_version(dockerfile_path: str = DEFAULT_MASSA_DOCKERFILE) -> str:
    """Read the default MASSA_VERSION build argument from the Dockerfile."""
    _, _, match = _read_dockerfile(dockerfile_path)
    return match.group(1).strip()


def update_massa_version(
    version: str,
    dockerfile_path: str = DEFAULT_MASSA_DOCKERFILE,
) -> tuple[str, str]:
    """Update MASSA_VERSION in the mounted Massa Dockerfile."""
    if not _VALID_VERSION.fullmatch(version):
        raise ValueError(
            "Version invalide. Utilisez uniquement des lettres, chiffres, points, "
            "tirets ou tirets bas (ex. MAIN.5.2)."
        )

    path, content, match = _read_dockerfile(dockerfile_path)
    previous_version = match.group(1).strip()
    updated_content = content[:match.start(1)] + version + content[match.end(1):]
    original_stat = path.stat()

    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f'.{path.name}.',
        suffix='.tmp',
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as dockerfile:
            dockerfile.write(updated_content)
            dockerfile.flush()
            os.fsync(dockerfile.fileno())
        os.chmod(temporary_path, original_stat.st_mode)
        os.chown(temporary_path, original_stat.st_uid, original_stat.st_gid)
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise

    return previous_version, version
