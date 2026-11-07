"""Tests for the /status command."""
from unittest.mock import patch

from handlers.node_status import _format_massa_status, node_status


_RUNNING_CONTAINER = {
    'status': 'ok',
    'state': 'running',
    'health': 'healthy',
    'started_at': '2026-11-07T09:00:00Z',
    'exit_code': 0,
    'error': None,
}

_NODE_STATUS = {
    'result': {
        'version': 'MAIN.5.1',
        'current_cycle': 123,
        'connected_nodes': {'peer-a': [], 'peer-b': []},
        'last_slot': {'period': 500, 'thread': 3},
        'next_slot': {'period': 500, 'thread': 4},
        'consensus_stats': {'final_block_count': 11, 'stale_block_count': 1},
        'execution_stats': {
            'final_executed_operations_count': 17,
            'final_cursor': {'period': 499, 'thread': 31},
            'active_cursor': {'period': 500, 'thread': 4},
        },
    }
}


def test_format_status_includes_current_activity():
    text = _format_massa_status(_NODE_STATUS)
    assert 'MAIN.5.1' in text
    assert 'Cycle courant : 123' in text
    assert 'Nœuds pairs connectés : 2' in text
    assert 'période 500, thread 3' in text
    assert '11 blocs finalisés' in text
    assert '17 opérations exécutées' in text


def test_format_status_rejects_invalid_rpc_response():
    try:
        _format_massa_status({'result': []})
    except ValueError as error:
        assert 'invalide' in str(error)
    else:
        raise AssertionError('Expected invalid RPC data to be rejected')


async def test_status_reports_running_node(authorized_update_context):
    update, context = authorized_update_context
    context.bot_data.update({
        'node_container_name': 'massa-container',
        'massa_node_rpc_url': 'http://massa:33034/api/v2',
    })
    with patch('handlers.node_status.get_container_status', return_value=_RUNNING_CONTAINER), \
         patch('handlers.node_status.get_node_status', return_value=_NODE_STATUS) as rpc_call:
        await node_status(update, context)

    rpc_call.assert_called_once()
    text = update.message.reply_text.call_args.args[0]
    assert 'Conteneur Massa : démarré' in text
    assert 'Healthcheck : sain' in text
    assert 'Cycle courant : 123' in text


async def test_status_reports_starting_node_when_rpc_is_unavailable(authorized_update_context):
    update, context = authorized_update_context
    with patch('handlers.node_status.get_container_status', return_value={
        **_RUNNING_CONTAINER, 'health': 'starting',
    }), patch('handlers.node_status.get_node_status', return_value={
        'error': 'Connection refused',
    }):
        await node_status(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert 'Healthcheck : vérification en cours' in text
    assert 'le nœud peut démarrer' in text


async def test_status_skips_rpc_for_stopped_container(authorized_update_context):
    update, context = authorized_update_context
    with patch('handlers.node_status.get_container_status', return_value={
        'status': 'ok', 'state': 'exited', 'exit_code': 1,
    }), patch('handlers.node_status.get_node_status') as rpc_call:
        await node_status(update, context)

    rpc_call.assert_not_called()
    text = update.message.reply_text.call_args.args[0]
    assert 'Conteneur Massa : arrêté' in text
    assert 'Code de sortie : 1' in text
    assert 'RPC : non interrogé' in text


async def test_status_still_checks_rpc_if_docker_is_unavailable(authorized_update_context):
    update, context = authorized_update_context
    with patch('handlers.node_status.get_container_status', return_value={
        'status': 'error', 'message': 'Docker unavailable',
    }), patch('handlers.node_status.get_node_status', return_value=_NODE_STATUS):
        await node_status(update, context)

    text = update.message.reply_text.call_args.args[0]
    assert 'Docker unavailable' in text
    assert 'RPC Massa : disponible' in text


async def test_unauthorized_user_cannot_check_status(unauthorized_update_context):
    update, context = unauthorized_update_context
    with patch('handlers.node_status.get_container_status') as docker_status, \
         patch('handlers.node_status.get_node_status') as rpc_status:
        await node_status(update, context)

    docker_status.assert_not_called()
    rpc_status.assert_not_called()
