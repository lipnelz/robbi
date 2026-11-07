from pathlib import Path

import pytest

from services.massa_version import read_massa_version, update_massa_version


def test_reads_massa_version_from_dockerfile(tmp_path):
    dockerfile = tmp_path / 'Dockerfile'
    dockerfile.write_text('FROM ubuntu\nARG MASSA_VERSION=MAIN.5.1\n', encoding='utf-8')

    assert read_massa_version(str(dockerfile)) == 'MAIN.5.1'


def test_updates_version_and_preserves_other_dockerfile_content(tmp_path):
    dockerfile = tmp_path / 'Dockerfile'
    original = 'FROM ubuntu:24.04\nARG MASSA_VERSION=MAIN.5.1\nRUN echo ready\n'
    dockerfile.write_text(original, encoding='utf-8')

    assert update_massa_version('MAIN.5.2', str(dockerfile)) == ('MAIN.5.1', 'MAIN.5.2')
    assert dockerfile.read_text(encoding='utf-8') == original.replace('MAIN.5.1', 'MAIN.5.2')
    assert read_massa_version(str(dockerfile)) == 'MAIN.5.2'


@pytest.mark.parametrize('version', ['', '../MAIN.5.2', 'MAIN 5.2', '$(touch bad)', 'MAIN/5.2'])
def test_rejects_invalid_version_without_modifying_file(tmp_path, version):
    dockerfile = tmp_path / 'Dockerfile'
    original = 'ARG MASSA_VERSION=MAIN.5.1\n'
    dockerfile.write_text(original, encoding='utf-8')

    with pytest.raises(ValueError):
        update_massa_version(version, str(dockerfile))

    assert dockerfile.read_text(encoding='utf-8') == original


def test_rejects_dockerfile_with_missing_or_duplicate_argument(tmp_path):
    dockerfile = tmp_path / 'Dockerfile'
    for content in (
        'FROM ubuntu\n',
        'ARG MASSA_VERSION=MAIN.5.1\nARG MASSA_VERSION=MAIN.5.2\n',
    ):
        dockerfile.write_text(content, encoding='utf-8')
        with pytest.raises(ValueError, match='exactement un'):
            update_massa_version('MAIN.5.3', str(dockerfile))


def test_preserves_file_permissions(tmp_path):
    dockerfile = tmp_path / 'Dockerfile'
    dockerfile.write_text('ARG MASSA_VERSION=MAIN.5.1\n', encoding='utf-8')
    dockerfile.chmod(0o640)

    update_massa_version('MAIN.5.2', str(dockerfile))

    assert dockerfile.stat().st_mode & 0o777 == 0o640


def test_preserves_file_owner(tmp_path):
    dockerfile = tmp_path / 'Dockerfile'
    dockerfile.write_text('ARG MASSA_VERSION=MAIN.5.1\n', encoding='utf-8')
    original_stat = dockerfile.stat()

    update_massa_version('MAIN.5.2', str(dockerfile))

    updated_stat = dockerfile.stat()
    assert (updated_stat.st_uid, updated_stat.st_gid) == (
        original_stat.st_uid,
        original_stat.st_gid,
    )
