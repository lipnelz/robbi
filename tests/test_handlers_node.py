"""Tests for src/handlers/node.py."""
import os
import threading
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open, call
from telegram.ext import ConversationHandler

from handlers.node import (
    extract_address_data,
    node,
    flush,
    flush_confirm_yes,
    flush_confirm_no,
    hist,
)
from config import FLUSH_CONFIRM_STATE, HIST_CONFIRM_STATE


# ---------------------------------------------------------------------------
# extract_address_data
# ---------------------------------------------------------------------------

_VALID_JSON = {
    "result": [{
        "final_balance": "1000.00",
        "final_roll_count": 5,
        "cycle_infos": [
            {"cycle": 100, "ok_count": 10, "nok_count": 0, "active_rolls": 5},
            {"cycle": 101, "ok_count": 9,  "nok_count": 1, "active_rolls": 5},
        ]
    }]
}


class TestExtractAddressData:
    def test_valid_json_returns_tuple(self):
        result = extract_address_data(_VALID_JSON)
        assert result is not None
        balance, roll_count, cycles, ok_counts, nok_counts, active_rolls = result
        assert balance == "1000.00"
        assert roll_count == 5
        assert cycles == [100, 101]
        assert ok_counts == [10, 9]
        assert nok_counts == [0, 1]
        assert active_rolls == [5, 5]

    def test_no_result_key_returns_none(self):
        assert extract_address_data({}) is None

    def test_empty_result_list_returns_none(self):
        assert extract_address_data({"result": []}) is None

    def test_error_dict_returns_none(self):
        assert extract_address_data({"error": "timeout"}) is None


# ---------------------------------------------------------------------------
# node handler
# ---------------------------------------------------------------------------

def _make_stats():
    return {"cpu_percent": 10.0, "ram_percent": 50.0, "temperature_avg": 55.0}


class TestNodeHandler:
    async def test_happy_path_sends_reply_text_and_photo(self, authorized_update_context, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        update, context = authorized_update_context

        with patch('handlers.node.get_addresses', return_value=_VALID_JSON), \
             patch('handlers.node.handle_api_error', new_callable=AsyncMock, return_value=False), \
             patch('handlers.node.get_system_stats', return_value=_make_stats()), \
             patch('handlers.node.save_balance_history'), \
             patch('handlers.node.create_png_plot', return_value='plot.png'), \
             patch('os.path.exists', return_value=False):
            await node(update, context)

        update.message.reply_text.assert_called()

    async def test_api_error_triggers_handle_api_error(self, authorized_update_context):
        update, context = authorized_update_context

        with patch('handlers.node.get_addresses', return_value={"error": "timed out"}), \
             patch('handlers.node.handle_api_error', new_callable=AsyncMock, return_value=True) as mock_err:
            await node(update, context)

        mock_err.assert_called_once()

    async def test_extract_address_data_returns_none(self, authorized_update_context):
        update, context = authorized_update_context

        with patch('handlers.node.get_addresses', return_value={"result": []}), \
             patch('handlers.node.handle_api_error', new_callable=AsyncMock, return_value=False):
            await node(update, context)

        # Should reply with "unreachable"
        text = update.message.reply_text.call_args[0][0]
        assert "unreachable" in text.lower() or "no data" in text.lower()

    async def test_unauthorized_user_blocked(self, unauthorized_update_context):
        update, context = unauthorized_update_context
        with patch('handlers.node.get_addresses') as mock_get:
            await node(update, context)
        mock_get.assert_not_called()

    async def test_exception_sends_error_and_photo(self, authorized_update_context):
        update, context = authorized_update_context

        with patch('handlers.node.get_addresses', side_effect=Exception("boom")):
            await node(update, context)

        texts = [c[0][0] for c in update.message.reply_text.call_args_list]
        assert any("Arf" in t or "Error" in t for t in texts)
        update.message.reply_photo.assert_called()


# ---------------------------------------------------------------------------
# flush handler
# ---------------------------------------------------------------------------

class TestFlushHandler:
    async def test_unauthorized_user_returns_end(self, unauthorized_update_context):
        update, context = unauthorized_update_context
        result = await flush(update, context)
        assert result == ConversationHandler.END
        update.message.reply_text.assert_called_once()

    async def test_log_file_does_not_exist_returns_end(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('os.path.exists', return_value=False):
            result = await flush(update, context)
        assert result == ConversationHandler.END

    async def test_authorized_with_log_file_returns_flush_confirm_state(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('os.path.exists', return_value=True):
            result = await flush(update, context)
        assert result == FLUSH_CONFIRM_STATE
        update.message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# flush_confirm_yes
# ---------------------------------------------------------------------------

class TestFlushConfirmYes:
    def _make_query_update(self, user_id="123"):
        update = MagicMock()
        update.callback_query = AsyncMock()
        update.callback_query.from_user.id = int(user_id)
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        return update

    async def test_authorized_clears_log_and_history(self, mock_context):
        update = self._make_query_update("123")
        mock_context.bot_data['balance_history'] = {"key": "val"}

        with patch('builtins.open', mock_open()), \
             patch('handlers.node.save_balance_history'):
            result = await flush_confirm_yes(update, mock_context)

        assert result == ConversationHandler.END
        assert mock_context.bot_data['balance_history'] == {}
        update.callback_query.edit_message_text.assert_called_once()

    async def test_unauthorized_returns_end(self, mock_context):
        update = self._make_query_update("999")
        result = await flush_confirm_yes(update, mock_context)
        assert result == ConversationHandler.END
        update.callback_query.answer.assert_called_once()


# ---------------------------------------------------------------------------
# flush_confirm_no
# ---------------------------------------------------------------------------

class TestFlushConfirmNo:
    def _make_query_update(self, user_id="123"):
        update = MagicMock()
        update.callback_query = AsyncMock()
        update.callback_query.from_user.id = int(user_id)
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        return update

    async def test_authorized_clears_log_only(self, mock_context):
        update = self._make_query_update("123")
        mock_context.bot_data['balance_history'] = {"key": "val"}

        with patch('builtins.open', mock_open()):
            result = await flush_confirm_no(update, mock_context)

        assert result == ConversationHandler.END
        # Balance history must NOT be cleared
        assert mock_context.bot_data['balance_history'] == {"key": "val"}
        update.callback_query.edit_message_text.assert_called_once()

    async def test_unauthorized_returns_end(self, mock_context):
        update = self._make_query_update("999")
        result = await flush_confirm_no(update, mock_context)
        assert result == ConversationHandler.END
        update.callback_query.answer.assert_called_once()


# ---------------------------------------------------------------------------
# hist handler
# ---------------------------------------------------------------------------

class TestHistHandler:
    async def test_unauthorized_user_returns_end(self, unauthorized_update_context):
        update, context = unauthorized_update_context
        result = await hist(update, context)
        assert result == ConversationHandler.END
        update.message.reply_text.assert_called_once()

    async def test_empty_balance_history_returns_end(self, authorized_update_context):
        update, context = authorized_update_context
        context.bot_data['balance_history'] = {}
        result = await hist(update, context)
        assert result == ConversationHandler.END
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "no balance history" in text.lower()

    async def test_happy_path_returns_hist_confirm_state(self, authorized_update_context, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        update, context = authorized_update_context
        context.bot_data['balance_history'] = {
            "2024/01/01-10:00": {"balance": 100.0}
        }

        # Create a fake image file
        fake_image = tmp_path / "balance_history.png"
        fake_image.write_bytes(b"PNG")
        fake_resources = tmp_path / "resources_history.png"
        fake_resources.write_bytes(b"PNG")

        with patch('handlers.node.create_balance_history_plot', return_value=str(fake_image)), \
             patch('handlers.node.create_resources_plot', return_value=str(fake_resources)), \
             patch('builtins.open', mock_open(read_data=b"PNG")):
            result = await hist(update, context)

        assert result == HIST_CONFIRM_STATE

    async def test_plot_creation_error_returns_end(self, authorized_update_context):
        update, context = authorized_update_context
        context.bot_data['balance_history'] = {"2024/01/01-10:00": {"balance": 100.0}}

        with patch('handlers.node.create_balance_history_plot', side_effect=Exception("plot failed")):
            result = await hist(update, context)

        assert result == ConversationHandler.END

    async def test_image_not_created_returns_end(self, authorized_update_context):
        update, context = authorized_update_context
        context.bot_data['balance_history'] = {"2024/01/01-10:00": {"balance": 100.0}}

        with patch('handlers.node.create_balance_history_plot', return_value=""), \
             patch('os.path.exists', return_value=False):
            result = await hist(update, context)

        assert result == ConversationHandler.END
