from unittest.mock import patch

from handlers.deployment import massa_version


async def test_massa_version_without_argument_reports_current_version(
    authorized_update_context,
    monkeypatch,
):
    update, context = authorized_update_context
    context.args = []
    monkeypatch.setenv('MASSA_DOCKERFILE_PATH', '/mounted/Massa.Dockerfile')
    with patch('handlers.deployment.read_massa_version', return_value='MAIN.5.1') as read_version:
        await massa_version(update, context)

    read_version.assert_called_once_with('/mounted/Massa.Dockerfile')
    assert 'MAIN.5.1' in update.message.reply_text.call_args.args[0]
    assert '/massa_version MAIN.5.2' in update.message.reply_text.call_args.args[0]


async def test_massa_version_updates_argument_and_explains_rebuild(
    authorized_update_context,
    monkeypatch,
):
    update, context = authorized_update_context
    context.args = ['MAIN.5.2']
    monkeypatch.setenv('MASSA_DOCKERFILE_PATH', '/mounted/Massa.Dockerfile')
    with patch(
        'handlers.deployment.update_massa_version',
        return_value=('MAIN.5.1', 'MAIN.5.2'),
    ) as update_version:
        await massa_version(update, context)

    update_version.assert_called_once_with('MAIN.5.2', '/mounted/Massa.Dockerfile')
    message = update.message.reply_text.call_args.args[0]
    assert 'MAIN.5.1 → MAIN.5.2' in message
    assert 'docker-compose up -d --build massa' in message


async def test_massa_version_rejects_extra_arguments(authorized_update_context):
    update, context = authorized_update_context
    context.args = ['MAIN.5.2', 'unexpected']
    with patch('handlers.deployment.update_massa_version') as update_version:
        await massa_version(update, context)

    update_version.assert_not_called()
    assert 'Usage' in update.message.reply_text.call_args.args[0]


async def test_massa_version_reports_invalid_version(authorized_update_context):
    update, context = authorized_update_context
    context.args = ['../../unsafe']
    with patch(
        'handlers.deployment.update_massa_version',
        side_effect=ValueError('Version invalide.'),
    ):
        await massa_version(update, context)

    assert 'non modifiée' in update.message.reply_text.call_args.args[0]


async def test_unauthorized_user_cannot_update_massa_version(unauthorized_update_context):
    update, context = unauthorized_update_context
    context.args = ['MAIN.5.2']
    with patch('handlers.deployment.update_massa_version') as update_version:
        await massa_version(update, context)

    update_version.assert_not_called()
