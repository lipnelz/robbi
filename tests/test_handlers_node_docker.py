"""Additional tests for node.py – docker handlers, hist_confirm, and edge-cases."""
import threading
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from telegram.ext import ConversationHandler

from handlers.node import (
    docker,
    docker_start,
    docker_stop,
    docker_restart,
    docker_start_confirm,
    docker_stop_confirm,
    docker_restart_confirm,
    docker_cancel,
    docker_massa,
    massa_wallet_info,
    massa_buy_rolls_ask,
    massa_buy_rolls_input,
    massa_buy_rolls_confirm,
    massa_sell_rolls_ask,
    massa_sell_rolls_input,
    massa_sell_rolls_confirm,
    massa_back,
    hist_confirm_yes,
    hist_confirm_no,
)
from config import (
    DOCKER_MENU_STATE,
    DOCKER_START_CONFIRM_STATE,
    DOCKER_STOP_CONFIRM_STATE,
    DOCKER_RESTART_CONFIRM_STATE,
    DOCKER_MASSA_MENU_STATE,
    DOCKER_BUYROLLS_INPUT_STATE,
    DOCKER_BUYROLLS_CONFIRM_STATE,
    DOCKER_SELLROLLS_INPUT_STATE,
    DOCKER_SELLROLLS_CONFIRM_STATE,
    HIST_CONFIRM_STATE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_query_update(user_id="123"):
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.from_user.id = int(user_id)
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message = AsyncMock()
    update.callback_query.message.reply_text = AsyncMock()
    return update


def _make_context(extra=None):
    ctx = MagicMock()
    ctx.bot_data = {
        'allowed_user_ids': {'123'},
        'balance_history': {},
        'balance_lock': threading.Lock(),
        'node_container_name': 'massa-node',
        'robbi_container_name': 'robbi-container',
        'massa_client_password': 'secret',
        'massa_wallet_address': 'AU1wallet',
        'massa_buy_rolls_fee': 0.01,
    }
    ctx.user_data = {}
    if extra:
        ctx.bot_data.update(extra)
    return ctx


# ---------------------------------------------------------------------------
# docker handler
# ---------------------------------------------------------------------------

class TestDockerHandler:
    async def test_authorized_shows_docker_menu(self):
        update, context = MagicMock(), _make_context()
        update.effective_user.id = 123
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        result = await docker(update, context)
        assert result == DOCKER_MENU_STATE
        update.message.reply_text.assert_called_once()

    async def test_unauthorized_returns_end(self):
        update = MagicMock()
        update.effective_user.id = 999
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        context = _make_context()
        result = await docker(update, context)
        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# docker_start / docker_stop / docker_restart
# ---------------------------------------------------------------------------

class TestDockerStartStop:
    async def test_docker_start_authorized(self):
        update = _make_query_update("123")
        context = _make_context()
        result = await docker_start(update, context)
        assert result == DOCKER_START_CONFIRM_STATE
        update.callback_query.edit_message_text.assert_called_once()

    async def test_docker_start_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await docker_start(update, context)
        assert result == ConversationHandler.END
        update.callback_query.answer.assert_called_once()

    async def test_docker_stop_authorized(self):
        update = _make_query_update("123")
        context = _make_context()
        result = await docker_stop(update, context)
        assert result == DOCKER_STOP_CONFIRM_STATE
        update.callback_query.edit_message_text.assert_called_once()

    async def test_docker_stop_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await docker_stop(update, context)
        assert result == ConversationHandler.END

    async def test_docker_restart_authorized(self):
        update = _make_query_update("123")
        context = _make_context()
        result = await docker_restart(update, context)
        assert result == DOCKER_RESTART_CONFIRM_STATE
        update.callback_query.edit_message_text.assert_called_once()

    async def test_docker_restart_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await docker_restart(update, context)
        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# docker_start_confirm / docker_stop_confirm / docker_restart_confirm
# ---------------------------------------------------------------------------

class TestDockerStartStopConfirm:
    async def test_start_confirm_happy_path(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.start_docker_node', return_value={"status": "ok", "message": "started"}):
            result = await docker_start_confirm(update, context)
        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_called()

    async def test_start_confirm_error_status(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.start_docker_node', return_value={"status": "error", "message": "failed"}):
            result = await docker_start_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_start_confirm_no_container_name(self):
        update = _make_query_update("123")
        context = _make_context()
        context.bot_data['node_container_name'] = ''
        result = await docker_start_confirm(update, context)
        assert result == ConversationHandler.END
        text = update.callback_query.edit_message_text.call_args[1]['text']
        assert "Error" in text

    async def test_start_confirm_exception(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.start_docker_node', side_effect=Exception("crash")):
            result = await docker_start_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_start_confirm_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await docker_start_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_stop_confirm_happy_path(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.stop_docker_node', return_value={"status": "ok", "message": "stopped"}):
            result = await docker_stop_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_stop_confirm_error_status(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.stop_docker_node', return_value={"status": "error", "message": "fail"}):
            result = await docker_stop_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_stop_confirm_no_container_name(self):
        update = _make_query_update("123")
        context = _make_context()
        context.bot_data['node_container_name'] = ''
        result = await docker_stop_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_stop_confirm_exception(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.stop_docker_node', side_effect=Exception("crash")):
            result = await docker_stop_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_stop_confirm_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await docker_stop_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_restart_confirm_happy_path(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.asyncio.sleep', new_callable=AsyncMock) as mock_sleep, \
             patch('handlers.node.restart_bot', return_value={"status": "ok", "message": "restarted"}):
            result = await docker_restart_confirm(update, context)
        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_called_once_with(text="Ok")
        mock_sleep.assert_awaited_once_with(1)

    async def test_restart_confirm_error_status(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.asyncio.sleep', new_callable=AsyncMock) as mock_sleep, \
             patch('handlers.node.restart_bot', return_value={"status": "error", "message": "failed"}):
            result = await docker_restart_confirm(update, context)
        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_called_once_with(text="Ok")
        mock_sleep.assert_awaited_once_with(1)

    async def test_restart_confirm_exception(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.asyncio.sleep', new_callable=AsyncMock), \
             patch('handlers.node.restart_bot', side_effect=Exception("crash")):
            result = await docker_restart_confirm(update, context)
        assert result == ConversationHandler.END
        # First "Ok", then fallback error message in exception handler.
        assert update.callback_query.edit_message_text.call_count == 2

    async def test_restart_confirm_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await docker_restart_confirm(update, context)
        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# docker_cancel / docker_massa / massa_back
# ---------------------------------------------------------------------------

class TestDockerCancelMassaBack:
    async def test_docker_cancel_authorized(self):
        update = _make_query_update("123")
        context = _make_context()
        result = await docker_cancel(update, context)
        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_called_once()

    async def test_docker_cancel_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await docker_cancel(update, context)
        assert result == ConversationHandler.END

    async def test_docker_cancel_exception(self):
        update = _make_query_update("123")
        context = _make_context()
        update.callback_query.edit_message_text.side_effect = Exception("network error")
        result = await docker_cancel(update, context)
        assert result == ConversationHandler.END

    async def test_docker_massa_authorized(self):
        update = _make_query_update("123")
        context = _make_context()
        result = await docker_massa(update, context)
        assert result == DOCKER_MASSA_MENU_STATE
        update.callback_query.edit_message_text.assert_called_once()

    async def test_docker_massa_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await docker_massa(update, context)
        assert result == ConversationHandler.END

    async def test_massa_back_authorized(self):
        update = _make_query_update("123")
        context = _make_context()
        result = await massa_back(update, context)
        assert result == DOCKER_MENU_STATE
        update.callback_query.edit_message_text.assert_called_once()

    async def test_massa_back_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await massa_back(update, context)
        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# massa_wallet_info
# ---------------------------------------------------------------------------

class TestMassaWalletInfo:
    async def test_happy_path_ok(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.exec_massa_client', return_value={"status": "ok", "output": "wallet data"}):
            result = await massa_wallet_info(update, context)
        assert result == ConversationHandler.END
        text = update.callback_query.edit_message_text.call_args[1]['text']
        assert "wallet data" in text

    async def test_happy_path_no_output(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.exec_massa_client', return_value={"status": "ok", "output": ""}):
            result = await massa_wallet_info(update, context)
        assert result == ConversationHandler.END

    async def test_error_status(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.exec_massa_client', return_value={"status": "error", "message": "failed"}):
            result = await massa_wallet_info(update, context)
        assert result == ConversationHandler.END

    async def test_missing_config(self):
        update = _make_query_update("123")
        context = _make_context()
        context.bot_data['node_container_name'] = ''
        result = await massa_wallet_info(update, context)
        assert result == ConversationHandler.END

    async def test_exception(self):
        update = _make_query_update("123")
        context = _make_context()
        with patch('handlers.node.exec_massa_client', side_effect=Exception("crash")):
            result = await massa_wallet_info(update, context)
        assert result == ConversationHandler.END

    async def test_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await massa_wallet_info(update, context)
        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# massa_buy_rolls_ask / massa_buy_rolls_input / massa_buy_rolls_confirm
# ---------------------------------------------------------------------------

class TestMassaBuyRolls:
    def _make_text_update(self, text, user_id="123"):
        update = MagicMock()
        update.effective_user.id = int(user_id)
        update.message = AsyncMock()
        update.message.text = text
        update.message.reply_text = AsyncMock()
        return update

    async def test_ask_authorized(self):
        update = _make_query_update("123")
        context = _make_context()
        result = await massa_buy_rolls_ask(update, context)
        assert result == DOCKER_BUYROLLS_INPUT_STATE

    async def test_ask_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await massa_buy_rolls_ask(update, context)
        assert result == ConversationHandler.END

    async def test_input_valid_number(self):
        update = self._make_text_update("5", "123")
        context = _make_context()
        result = await massa_buy_rolls_input(update, context)
        assert result == DOCKER_BUYROLLS_CONFIRM_STATE
        assert context.user_data['buy_rolls_count'] == 5

    async def test_input_invalid_not_a_number(self):
        update = self._make_text_update("abc", "123")
        context = _make_context()
        result = await massa_buy_rolls_input(update, context)
        assert result == DOCKER_BUYROLLS_INPUT_STATE
        update.message.reply_text.assert_called_once()

    async def test_input_zero_rejected(self):
        update = self._make_text_update("0", "123")
        context = _make_context()
        result = await massa_buy_rolls_input(update, context)
        assert result == DOCKER_BUYROLLS_INPUT_STATE

    async def test_input_negative_rejected(self):
        update = self._make_text_update("-1", "123")
        context = _make_context()
        result = await massa_buy_rolls_input(update, context)
        assert result == DOCKER_BUYROLLS_INPUT_STATE

    async def test_input_unauthorized(self):
        update = self._make_text_update("5", "999")
        context = _make_context()
        result = await massa_buy_rolls_input(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_happy_path(self):
        update = _make_query_update("123")
        context = _make_context()
        context.user_data['buy_rolls_count'] = 3
        with patch('handlers.node.exec_massa_client', return_value={"status": "ok", "output": "done"}):
            result = await massa_buy_rolls_confirm(update, context)
        assert result == ConversationHandler.END
        assert 'buy_rolls_count' not in context.user_data

    async def test_confirm_error_result(self):
        update = _make_query_update("123")
        context = _make_context()
        context.user_data['buy_rolls_count'] = 3
        with patch('handlers.node.exec_massa_client', return_value={"status": "error", "message": "fail"}):
            result = await massa_buy_rolls_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_missing_config(self):
        update = _make_query_update("123")
        context = _make_context()
        context.bot_data['node_container_name'] = ''
        context.user_data['buy_rolls_count'] = 3
        result = await massa_buy_rolls_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_zero_roll_count(self):
        update = _make_query_update("123")
        context = _make_context()
        context.user_data['buy_rolls_count'] = 0
        result = await massa_buy_rolls_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_exception(self):
        update = _make_query_update("123")
        context = _make_context()
        context.user_data['buy_rolls_count'] = 2
        with patch('handlers.node.exec_massa_client', side_effect=Exception("crash")):
            result = await massa_buy_rolls_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await massa_buy_rolls_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_no_output_uses_fallback(self):
        update = _make_query_update("123")
        context = _make_context()
        context.user_data['buy_rolls_count'] = 1
        with patch('handlers.node.exec_massa_client', return_value={"status": "ok", "output": ""}):
            result = await massa_buy_rolls_confirm(update, context)
        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# massa_sell_rolls_ask / massa_sell_rolls_input / massa_sell_rolls_confirm
# ---------------------------------------------------------------------------

class TestMassaSellRolls:
    def _make_text_update(self, text, user_id="123"):
        update = MagicMock()
        update.effective_user.id = int(user_id)
        update.message = AsyncMock()
        update.message.text = text
        update.message.reply_text = AsyncMock()
        return update

    async def test_ask_authorized(self):
        update = _make_query_update("123")
        context = _make_context()
        result = await massa_sell_rolls_ask(update, context)
        assert result == DOCKER_SELLROLLS_INPUT_STATE

    async def test_ask_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await massa_sell_rolls_ask(update, context)
        assert result == ConversationHandler.END

    async def test_input_valid_number(self):
        update = self._make_text_update("2", "123")
        context = _make_context()
        result = await massa_sell_rolls_input(update, context)
        assert result == DOCKER_SELLROLLS_CONFIRM_STATE
        assert context.user_data['sell_rolls_count'] == 2

    async def test_input_invalid(self):
        update = self._make_text_update("nope", "123")
        context = _make_context()
        result = await massa_sell_rolls_input(update, context)
        assert result == DOCKER_SELLROLLS_INPUT_STATE

    async def test_input_zero_rejected(self):
        update = self._make_text_update("0", "123")
        context = _make_context()
        result = await massa_sell_rolls_input(update, context)
        assert result == DOCKER_SELLROLLS_INPUT_STATE

    async def test_input_unauthorized(self):
        update = self._make_text_update("5", "999")
        context = _make_context()
        result = await massa_sell_rolls_input(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_happy_path(self):
        update = _make_query_update("123")
        context = _make_context()
        context.user_data['sell_rolls_count'] = 2
        with patch('handlers.node.exec_massa_client', return_value={"status": "ok", "output": "sold"}):
            result = await massa_sell_rolls_confirm(update, context)
        assert result == ConversationHandler.END
        assert 'sell_rolls_count' not in context.user_data

    async def test_confirm_error_result(self):
        update = _make_query_update("123")
        context = _make_context()
        context.user_data['sell_rolls_count'] = 2
        with patch('handlers.node.exec_massa_client', return_value={"status": "error", "message": "fail"}):
            result = await massa_sell_rolls_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_missing_config(self):
        update = _make_query_update("123")
        context = _make_context()
        context.bot_data['node_container_name'] = ''
        context.user_data['sell_rolls_count'] = 2
        result = await massa_sell_rolls_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_zero_roll_count(self):
        update = _make_query_update("123")
        context = _make_context()
        context.user_data['sell_rolls_count'] = 0
        result = await massa_sell_rolls_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_exception(self):
        update = _make_query_update("123")
        context = _make_context()
        context.user_data['sell_rolls_count'] = 1
        with patch('handlers.node.exec_massa_client', side_effect=Exception("crash")):
            result = await massa_sell_rolls_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await massa_sell_rolls_confirm(update, context)
        assert result == ConversationHandler.END

    async def test_confirm_no_output_uses_fallback(self):
        update = _make_query_update("123")
        context = _make_context()
        context.user_data['sell_rolls_count'] = 1
        with patch('handlers.node.exec_massa_client', return_value={"status": "ok", "output": ""}):
            result = await massa_sell_rolls_confirm(update, context)
        assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# hist_confirm_yes / hist_confirm_no
# ---------------------------------------------------------------------------

class TestHistConfirmYesNo:
    async def test_hist_confirm_yes_authorized(self):
        update = _make_query_update("123")
        context = _make_context()
        context.bot_data['balance_history'] = {
            "2024/01/01-10:00": {"balance": 100.0, "temperature_avg": 55.0, "ram_percent": 60.0}
        }
        result = await hist_confirm_yes(update, context)
        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_called()

    async def test_hist_confirm_yes_empty_history(self):
        update = _make_query_update("123")
        context = _make_context()
        context.bot_data['balance_history'] = {}
        result = await hist_confirm_yes(update, context)
        assert result == ConversationHandler.END
        update.callback_query.answer.assert_called()

    async def test_hist_confirm_yes_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await hist_confirm_yes(update, context)
        assert result == ConversationHandler.END

    async def test_hist_confirm_yes_exception(self):
        update = _make_query_update("123")
        context = _make_context()
        context.bot_data['balance_history'] = {"k": {"balance": 1.0}}
        update.callback_query.edit_message_text.side_effect = Exception("network")
        result = await hist_confirm_yes(update, context)
        assert result == ConversationHandler.END

    async def test_hist_confirm_no_authorized(self):
        update = _make_query_update("123")
        context = _make_context()
        result = await hist_confirm_no(update, context)
        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_called()

    async def test_hist_confirm_no_unauthorized(self):
        update = _make_query_update("999")
        context = _make_context()
        result = await hist_confirm_no(update, context)
        assert result == ConversationHandler.END

    async def test_hist_confirm_no_exception(self):
        update = _make_query_update("123")
        context = _make_context()
        update.callback_query.edit_message_text.side_effect = Exception("network")
        result = await hist_confirm_no(update, context)
        assert result == ConversationHandler.END
        update.callback_query.answer.assert_called()
