"""Tests for the unified /menu navigation."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram.ext import ConversationHandler

import handlers.menu as menu_module
from config import DOCKER_MENU_STATE


def _cb_update(data, user_id=123):
    update = MagicMock()
    query = MagicMock()
    query.data = data
    query.from_user.id = user_id
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = 42
    query.message.delete = AsyncMock()
    query.get_bot.return_value.send_message = AsyncMock()
    update.callback_query = query
    return update, query


def _callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def _ctx(mock_context):
    mock_context.bot.send_message = AsyncMock()
    mock_context.bot.send_photo = AsyncMock()
    mock_context.args = None
    return mock_context


class TestMenuCommands:
    async def test_menu_shows_main_keyboard(self, mock_update, mock_context):
        await menu_module.menu(mock_update, mock_context)
        markup = mock_update.message.reply_text.call_args.kwargs['reply_markup']
        assert {'menu_monitoring', 'menu_crypto', 'menu_docker', 'menu_data',
                'menu_summary', 'menu_help'} == set(_callbacks(markup))

    async def test_menu_rejects_unauthorized(self, mock_update, mock_context):
        mock_update.effective_user.id = 999
        mock_context.bot.send_message = AsyncMock()
        await menu_module.menu(mock_update, mock_context)
        assert 'not authorized' in mock_update.message.reply_text.call_args.args[0]

    async def test_start_installs_persistent_button(self, mock_update, mock_context):
        await menu_module.start(mock_update, mock_context)
        assert mock_update.message.reply_text.call_count == 2
        first = mock_update.message.reply_text.call_args_list[0].kwargs['reply_markup']
        assert first.keyboard[0][0].text == menu_module.MENU_BUTTON_LABEL


class TestMenuNavigation:
    @pytest.mark.parametrize('func,expected', [
        (menu_module.menu_monitoring, 'menu_run_node'),
        (menu_module.menu_crypto, 'menu_run_btc'),
        (menu_module.menu_data, 'menu_hist'),
        (menu_module.menu_help, 'menu_home'),
    ])
    async def test_submenus(self, func, expected, mock_context):
        update, query = _cb_update('x')
        await func(update, mock_context)
        markup = query.edit_message_text.call_args.kwargs['reply_markup']
        assert expected in _callbacks(markup)

    async def test_home_ends_conversation(self, mock_context):
        update, query = _cb_update('menu_home')
        assert await menu_module.menu_home(update, mock_context) == ConversationHandler.END

    async def test_docker_enters_docker_state(self, mock_context):
        update, query = _cb_update('menu_docker')
        assert await menu_module.menu_docker(update, mock_context) == DOCKER_MENU_STATE
        assert 'docker_start' in _callbacks(query.edit_message_text.call_args.kwargs['reply_markup'])

    async def test_unauthorized_callback_denied(self, mock_context):
        mock_context.bot.send_message = AsyncMock()
        update, query = _cb_update('menu_home', user_id=999)
        assert await menu_module.menu_home(update, mock_context) == ConversationHandler.END
        query.edit_message_text.assert_not_called()

    async def test_help_lists_commands(self):
        text = menu_module._build_help_text()
        assert '/menu' in text and '/docker' in text

    async def test_expired_alerts(self, mock_context):
        update, query = _cb_update('docker_stop')
        await menu_module.menu_expired(update, mock_context)
        assert query.answer.call_args.kwargs['show_alert'] is True


class TestMenuRun:
    async def test_text_result_edits_in_place(self, mock_context):
        async def fake(update, context):
            await update.message.reply_text('price 1')
        update, query = _cb_update('menu_run_btc')
        with patch.dict(menu_module._ACTIONS, {'btc': (fake, 'menu_crypto', ('🟣 MAS', 'menu_run_mas'))}):
            await menu_module.menu_run(update, _ctx(mock_context))
        calls = query.edit_message_text.call_args_list
        assert calls[0].kwargs['text'] == menu_module._LOADING_TEXT
        assert calls[-1].kwargs['text'] == 'price 1'
        nav = _callbacks(calls[-1].kwargs['reply_markup'])
        assert nav == ['menu_run_btc', 'menu_run_mas', 'menu_crypto', 'menu_home']
        query.message.delete.assert_not_called()

    async def test_photo_result_sends_footer(self, mock_context):
        async def fake(update, context):
            await update.message.reply_text('before')
            await update.message.reply_photo(photo='img')
            await update.message.reply_text('after')
        update, query = _cb_update('menu_run_node')
        ctx = _ctx(mock_context)
        with patch.dict(menu_module._ACTIONS, {'node': (fake, 'menu_monitoring', None)}):
            await menu_module.menu_run(update, ctx)
        ctx.bot.send_message.assert_called_once_with(chat_id=42, text='before')
        ctx.bot.send_photo.assert_called_once_with(chat_id=42, photo='img')
        query.message.delete.assert_called_once()
        footer = query.get_bot.return_value.send_message.call_args.kwargs
        assert footer['text'] == 'after'

    async def test_handler_error_is_reported(self, mock_context):
        async def boom(update, context):
            raise RuntimeError('x')
        update, query = _cb_update('menu_run_perf')
        with patch.dict(menu_module._ACTIONS, {'perf': (boom, 'menu_monitoring', None)}):
            await menu_module.menu_run(update, _ctx(mock_context))
        assert 'error' in query.edit_message_text.call_args.kwargs['text']

    async def test_unknown_action_shows_main_menu(self, mock_context):
        update, query = _cb_update('menu_run_nope')
        await menu_module.menu_run(update, _ctx(mock_context))
        assert query.edit_message_text.call_args.kwargs['text'] == menu_module._MAIN_TEXT

    async def test_handler_sees_clicking_user_and_empty_args(self, mock_context):
        seen = {}
        async def fake(update, context):
            seen['user'] = update.effective_user.id
            seen['args'] = context.args
            await update.message.reply_text('ok')
        update, query = _cb_update('menu_run_hi')
        with patch.dict(menu_module._ACTIONS, {'hi': (fake, 'menu_monitoring', None)}):
            await menu_module.menu_run(update, _ctx(mock_context))
        assert seen == {'user': 123, 'args': []}

    async def test_summary_combines_outputs(self, mock_context):
        def make(label):
            async def fake(update, context):
                await update.message.reply_text(label)
            return fake
        update, query = _cb_update('menu_summary')
        with patch.object(menu_module, '_SUMMARY_HANDLERS', (make('A'), make('B'))):
            await menu_module.menu_summary(update, _ctx(mock_context))
        assert query.edit_message_text.call_args.kwargs['text'] == 'A\n\nB'


class TestMenuDataEntries:
    async def test_hist_runs_handler_and_returns_state(self, mock_context):
        update, query = _cb_update('menu_hist')
        entry = AsyncMock(return_value=2)
        with patch.object(menu_module, 'hist', entry):
            assert await menu_module.menu_hist(update, mock_context) == 2
        proxy = entry.call_args.args[0]
        assert proxy.effective_user.id == 123 and proxy.message is query.message

    async def test_flush_runs_handler_and_returns_state(self, mock_context):
        update, query = _cb_update('menu_flush')
        entry = AsyncMock(return_value=1)
        with patch.object(menu_module, 'flush', entry):
            assert await menu_module.menu_flush(update, mock_context) == 1
