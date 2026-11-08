"""Additional tests covering error paths and formatting helpers."""
import json
import subprocess
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from handlers import deployment, node_status as node_status_handler, scheduler
from services import massa_deployment, massa_version, node_status


# --- services.massa_version ---------------------------------------------------

def test_update_massa_version_cleans_up_temp_file_on_write_error(tmp_path):
    dockerfile = tmp_path / 'Dockerfile'
    dockerfile.write_text('ARG MASSA_VERSION=MAIN.5.1\n', encoding='utf-8')

    with patch('services.massa_version.os.chown', side_effect=PermissionError('denied')):
        with pytest.raises(PermissionError):
            massa_version.update_massa_version('MAIN.5.2', str(dockerfile))

    assert dockerfile.read_text(encoding='utf-8') == 'ARG MASSA_VERSION=MAIN.5.1\n'
    assert [p.name for p in tmp_path.iterdir()] == ['Dockerfile']


def test_update_massa_version_tolerates_missing_temp_file_on_error(tmp_path):
    dockerfile = tmp_path / 'Dockerfile'
    dockerfile.write_text('ARG MASSA_VERSION=MAIN.5.1\n', encoding='utf-8')

    with patch('services.massa_version.os.chown', side_effect=PermissionError('denied')), \
            patch('services.massa_version.os.unlink', side_effect=FileNotFoundError):
        with pytest.raises(PermissionError):
            massa_version.update_massa_version('MAIN.5.2', str(dockerfile))


# --- services.massa_deployment ------------------------------------------------

def test_rebuild_massa_requires_project_directory(tmp_path, monkeypatch):
    monkeypatch.setenv('MASSA_COMPOSE_PROJECT_DIR', str(tmp_path / 'missing'))
    monkeypatch.setenv('MASSA_COMPOSE_FILE', str(tmp_path / 'docker-compose.yml'))

    with pytest.raises(FileNotFoundError, match='project directory'):
        massa_deployment.rebuild_massa()


def test_rebuild_massa_requires_compose_file(tmp_path, monkeypatch):
    monkeypatch.setenv('MASSA_COMPOSE_PROJECT_DIR', str(tmp_path))
    monkeypatch.setenv('MASSA_COMPOSE_FILE', str(tmp_path / 'docker-compose.yml'))

    with pytest.raises(FileNotFoundError, match='Compose file'):
        massa_deployment.rebuild_massa()


# --- services.node_status -----------------------------------------------------

@pytest.fixture
def history_file(tmp_path, monkeypatch):
    path = tmp_path / 'config' / 'node_status_history.json'
    monkeypatch.setattr('services.node_status.NODE_STATUS_HISTORY_FILE', str(path))
    return path


def test_load_node_status_history_missing_file(history_file):
    assert node_status.load_node_status_history() == {}


def test_load_node_status_history_rejects_non_object(history_file):
    history_file.parent.mkdir()
    history_file.write_text('[1, 2]', encoding='utf-8')

    assert node_status.load_node_status_history() == {}


def test_load_node_status_history_filters_invalid_entries(history_file):
    history_file.parent.mkdir()
    history_file.write_text(json.dumps({'a': True, 'b': 'yes', 'c': 1}), encoding='utf-8')

    assert node_status.load_node_status_history() == {'a': True}


def test_record_node_status_handles_aware_datetimes_and_bad_timestamps(history_file):
    history_file.parent.mkdir()
    now = datetime.now(timezone.utc)
    history_file.write_text(json.dumps({
        'not-a-date': True,
        now.isoformat(): False,
    }), encoding='utf-8')

    node_status.record_node_status(True, now)

    stored = node_status.load_node_status_history()
    assert 'not-a-date' not in stored
    assert list(stored.values()).count(True) == 1


def test_record_node_status_logs_save_error_and_removes_temp(history_file):
    with patch('services.node_status.json.dump', side_effect=OSError('disk full')):
        node_status.record_node_status(True, datetime(2026, 1, 1))

    assert not history_file.exists()
    assert not history_file.with_name(history_file.name + '.tmp').exists()


def test_record_node_status_logs_cleanup_error(history_file):
    with patch('services.node_status.json.dump', side_effect=OSError('disk full')), \
            patch('services.node_status.os.remove', side_effect=OSError('busy')):
        node_status.record_node_status(True, datetime(2026, 1, 1))


# --- handlers.deployment ------------------------------------------------------

async def test_massa_version_read_error_is_reported(authorized_update_context):
    update, context = authorized_update_context
    context.args = []
    with patch('handlers.deployment.read_massa_version', side_effect=OSError('nope')):
        await deployment.massa_version(update, context)

    assert 'Impossible de lire' in update.message.reply_text.call_args.args[0]


async def test_massa_version_rejects_too_many_arguments(authorized_update_context):
    update, context = authorized_update_context
    context.args = ['a', 'b']

    await deployment.massa_version(update, context)

    assert 'Usage' in update.message.reply_text.call_args.args[0]


async def test_massa_version_update_error_is_reported(authorized_update_context):
    update, context = authorized_update_context
    context.args = ['bad version']
    with patch('handlers.deployment.update_massa_version', side_effect=ValueError('invalide')):
        await deployment.massa_version(update, context)

    assert 'non modifiée' in update.message.reply_text.call_args.args[0]
    context.application.create_task.assert_not_called()


async def test_rebuild_reports_failure_details():
    message = AsyncMock()
    result = subprocess.CompletedProcess([], 2, stdout='', stderr='boom')
    with patch('handlers.deployment.rebuild_massa', return_value=result):
        await deployment._rebuild_massa_and_report(message, 'MAIN.5.2')

    text = message.reply_text.call_args.args[0]
    assert 'code 2' in text and 'boom' in text


async def test_rebuild_reports_exception():
    message = AsyncMock()
    with patch('handlers.deployment.rebuild_massa', side_effect=FileNotFoundError('x')):
        await deployment._rebuild_massa_and_report(message, 'MAIN.5.2')

    assert 'Impossible de reconstruire' in message.reply_text.call_args.args[0]


async def test_rebuild_survives_telegram_reply_failure():
    message = AsyncMock()
    message.reply_text.side_effect = RuntimeError('telegram down')
    result = subprocess.CompletedProcess([], 0, stdout='', stderr='')
    with patch('handlers.deployment.rebuild_massa', return_value=result):
        await deployment._rebuild_massa_and_report(message, 'MAIN.5.2')


# --- handlers.node_status -----------------------------------------------------

@pytest.mark.parametrize('slot, expected', [
    (None, 'indisponible'),
    ({'period': 1}, 'indisponible'),
    ({'thread': 1}, 'indisponible'),
    ({'period': 12, 'thread': 3}, 'période 12, thread 3'),
])
def test_slot_text(slot, expected):
    assert node_status_handler._slot_text(slot) == expected


def test_container_state_lines_exited_with_error_and_health():
    lines = node_status_handler._container_state_lines({
        'status': 'ok',
        'state': 'exited',
        'health': 'unhealthy',
        'exit_code': 137,
        'error': 'OOM',
    })

    assert any('non sain' in line for line in lines)
    assert 'Code de sortie : 137' in lines
    assert 'Erreur Docker : OOM' in lines


def test_container_state_lines_unavailable():
    lines = node_status_handler._container_state_lines({'status': 'error', 'message': 'no docker'})

    assert 'no docker' in lines[0]


async def test_node_status_reports_rpc_error(authorized_update_context):
    update, context = authorized_update_context
    with patch('handlers.node_status.get_container_status',
               return_value={'status': 'ok', 'state': 'exited', 'exit_code': 1}), \
            patch('handlers.node_status.get_node_status', return_value={'error': 'refused'}):
        await node_status_handler.node_status(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert 'non interrogé' in text


async def test_node_status_reports_rpc_error_when_container_running(authorized_update_context):
    update, context = authorized_update_context
    with patch('handlers.node_status.get_container_status',
               return_value={'status': 'error', 'message': 'x'}), \
            patch('handlers.node_status.get_node_status', return_value={'error': 'refused'}):
        await node_status_handler.node_status(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert 'indisponible' in text and 'refused' in text


async def test_node_status_handles_unexpected_exception(authorized_update_context):
    update, context = authorized_update_context
    with patch('handlers.node_status.get_container_status', side_effect=RuntimeError('boom')):
        await node_status_handler.node_status(update, context)

    assert 'boom' in update.message.reply_text.call_args.args[0]


async def test_node_status_handles_invalid_response(authorized_update_context):
    update, context = authorized_update_context
    with patch('handlers.node_status.get_container_status', side_effect=KeyError('k')):
        await node_status_handler.node_status(update, context)

    assert 'interpréter' in update.message.reply_text.call_args.args[0]


async def test_node_status_survives_bootstrap_failure(authorized_update_context):
    update, context = authorized_update_context
    with patch('handlers.node_status.get_container_status',
               return_value={'status': 'ok', 'state': 'running'}), \
            patch('services.docker_manager._get_docker_client', side_effect=RuntimeError('no')), \
            patch('handlers.node_status.get_node_status', return_value={'error': 'refused'}):
        await node_status_handler.node_status(update, context)

    assert 'refused' in update.message.reply_text.call_args.args[0]


# --- handlers.scheduler -------------------------------------------------------

def test_stop_async_func_logs_scheduler_shutdown_error():
    application = MagicMock()
    sched = MagicMock()
    sched.running = True
    sched.shutdown.side_effect = RuntimeError('boom')
    application.bot_data = {'scheduler': sched}

    scheduler.stop_async_func(application)

    sched.shutdown.assert_called_once()


def test_stop_async_func_logs_loop_close_error():
    application = MagicMock()
    loop = MagicMock()
    loop.is_running.return_value = False
    loop.is_closed.return_value = False
    loop.close.side_effect = RuntimeError('boom')
    application.bot_data = {'scheduler_loop': loop, 'scheduler_owns_loop': True}

    scheduler.stop_async_func(application)

    loop.close.assert_called_once()


# --- services.docker_manager / bootstrap_monitor / main / node handlers ---------

def test_close_docker_client_handles_none_and_close_error():
    from services.docker_manager import _close_docker_client

    _close_docker_client(None, MagicMock())
    client = MagicMock()
    client.close.side_effect = RuntimeError('boom')
    logger = MagicMock()

    _close_docker_client(client, logger)

    logger.warning.assert_called_once()


def test_get_container_status_without_container_name():
    from services.docker_manager import get_container_status

    assert get_container_status(None, '')['status'] == 'error'


def test_get_bootstrap_status_returns_unknown_when_logs_unreadable():
    from services.bootstrap_monitor import get_bootstrap_status

    container = MagicMock()
    container.logs.side_effect = RuntimeError('no logs')

    assert get_bootstrap_status(container, None)['state'] == 'unknown'


def test_get_bootstrap_status_extracts_last_error():
    from services.bootstrap_monitor import get_bootstrap_status

    logs = (
        '2026-01-01T10:00:00 INFO bootstrap::client: Start bootstrapping from 1.2.3.4:31245\n'
        '2026-01-01T10:00:05 WARN bootstrap::client: Error: connection refused\n'
    )
    container = MagicMock()
    container.logs.return_value = logs.encode()

    info = get_bootstrap_status(container, None)

    assert info['state'] == 'bootstrapping'
    assert info['current_server'] == '1.2.3.4:31245'
    assert info['error'] == 'connection refused'


def test_get_bootstrap_status_survives_unparsable_start_time():
    from services.bootstrap_monitor import get_bootstrap_status

    container = MagicMock()
    container.logs.return_value = b'2026-13-45T99:99:99 INFO something\n'

    assert get_bootstrap_status(container, None)['time_elapsed'] is None


def test_format_bootstrap_status_truncates_long_errors():
    from services.bootstrap_monitor import format_bootstrap_status

    text = format_bootstrap_status({
        'state': 'bootstrapping',
        'progress_pct': 40,
        'current_server': '1.2.3.4',
        'time_elapsed': 125,
        'retry_in_seconds': 120,
        'error': 'x' * 100,
    })

    assert '...' in text
    assert '2m 5s' in text
    assert 'Nouvelle tentative dans: 2m' in text


def test_main_missing_massa_node_address_returns_early():
    from unittest.mock import mock_open
    import main as main_module

    config = {'telegram_bot_token': 't', 'user_white_list': {'admin': '1'}}
    with patch('builtins.open', mock_open(read_data=json.dumps(config))), \
            patch('main.logging.error') as log_error:
        main_module.main()

    assert 'massa_node_address' in log_error.call_args.args[0]


async def test_stop_docker_report_handles_stop_error_and_edit_failure():
    from handlers.node import _stop_docker_node_and_report

    query = AsyncMock()
    query.edit_message_text.side_effect = RuntimeError('telegram down')
    with patch('handlers.node.stop_docker_node', side_effect=RuntimeError('boom')):
        await _stop_docker_node_and_report(query, '123', 'massa')

    query.edit_message_text.assert_awaited_once()
