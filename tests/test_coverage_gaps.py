"""Additional targeted tests to cover remaining uncovered lines."""
import os
import threading
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, mock_open, call
from telegram.ext import ConversationHandler

from handlers.node import node, flush_confirm_yes, flush_confirm_no, hist
from handlers.scheduler import periodic_node_ping
from config import FLUSH_CONFIRM_STATE, HIST_CONFIRM_STATE


# ---------------------------------------------------------------------------
# node handler – image send and cleanup paths
# ---------------------------------------------------------------------------

_VALID_JSON = {
    "result": [{
        "final_balance": "1000.00",
        "final_roll_count": 5,
        "cycle_infos": [
            {"cycle": 100, "ok_count": 10, "nok_count": 0, "active_rolls": 5},
        ]
    }]
}


def _authorized_update():
    update = MagicMock()
    update.effective_user.id = 123
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    return update


def _authorized_context():
    ctx = MagicMock()
    ctx.bot_data = {
        'allowed_user_ids': {'123'},
        'massa_node_address': 'AU1addr',
        'balance_history': {},
        'balance_lock': threading.Lock(),
    }
    return ctx


class TestNodeHandlerImagePaths:
    async def test_image_exists_and_sent_successfully(self, tmp_path, monkeypatch):
        """Cover lines 93-95: image file exists and is opened/sent."""
        monkeypatch.chdir(tmp_path)
        update = _authorized_update()
        context = _authorized_context()

        # Create the actual file so os.path.exists returns True
        plot_file = tmp_path / "plot.png"
        plot_file.write_bytes(b"PNG")

        with patch('handlers.node.get_addresses', return_value=_VALID_JSON), \
             patch('handlers.node.handle_api_error', new_callable=AsyncMock, return_value=False), \
             patch('handlers.node.get_system_stats', return_value={"ram_percent": 50.0}), \
             patch('handlers.node.save_balance_history'), \
             patch('handlers.node.create_png_plot', return_value=str(plot_file)):
            await node(update, context)

        update.message.reply_photo.assert_called()

    async def test_image_open_raises_oserror(self, tmp_path, monkeypatch):
        """Cover lines 96-98: FileNotFoundError/OSError when opening image."""
        monkeypatch.chdir(tmp_path)
        update = _authorized_update()
        context = _authorized_context()
        plot_path = str(tmp_path / "plot.png")

        real_open = open

        def _mock_open(path, mode='r', **kwargs):
            if 'plot.png' in str(path) and mode == 'rb':
                raise OSError("permission denied")
            return real_open(path, mode, **kwargs)

        with patch('handlers.node.get_addresses', return_value=_VALID_JSON), \
             patch('handlers.node.handle_api_error', new_callable=AsyncMock, return_value=False), \
             patch('handlers.node.get_system_stats', return_value={}), \
             patch('handlers.node.save_balance_history'), \
             patch('handlers.node.create_png_plot', return_value=plot_path), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', side_effect=_mock_open):
            await node(update, context)

        # Should have replied with error text
        texts = [c[0][0] for c in update.message.reply_text.call_args_list]
        assert any("Error" in t or "error" in t for t in texts)

    async def test_cleanup_in_finally_when_remove_raises(self, tmp_path, monkeypatch):
        """Cover lines 111-114: os.remove raises in finally block."""
        monkeypatch.chdir(tmp_path)
        update = _authorized_update()
        context = _authorized_context()
        plot_path = str(tmp_path / "plot.png")
        (tmp_path / "plot.png").write_bytes(b"PNG")

        with patch('handlers.node.get_addresses', return_value=_VALID_JSON), \
             patch('handlers.node.handle_api_error', new_callable=AsyncMock, return_value=False), \
             patch('handlers.node.get_system_stats', return_value={}), \
             patch('handlers.node.save_balance_history'), \
             patch('handlers.node.create_png_plot', return_value=plot_path), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove', side_effect=OSError("cannot delete")):
            await node(update, context)

        # Should complete without raising


# ---------------------------------------------------------------------------
# flush_confirm_yes / flush_confirm_no – IOError paths
# ---------------------------------------------------------------------------

class TestFlushConfirmIOErrors:
    def _make_query_update(self, user_id="123"):
        update = MagicMock()
        update.callback_query = AsyncMock()
        update.callback_query.from_user.id = int(user_id)
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        return update

    def _make_context(self):
        ctx = MagicMock()
        ctx.bot_data = {
            'allowed_user_ids': {'123'},
            'balance_history': {"key": "val"},
            'balance_lock': threading.Lock(),
        }
        return ctx

    async def test_flush_yes_ioerror_on_open(self):
        """Cover lines 181-184: IOError when opening log file in flush_confirm_yes."""
        update = self._make_query_update("123")
        context = self._make_context()
        with patch('builtins.open', side_effect=IOError("read-only filesystem")):
            result = await flush_confirm_yes(update, context)
        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_called()
        text = update.callback_query.edit_message_text.call_args[1]['text']
        assert "error" in text.lower() or "Error" in text

    async def test_flush_no_ioerror_on_open(self):
        """Cover lines 208-211: IOError when opening log file in flush_confirm_no."""
        update = self._make_query_update("123")
        context = self._make_context()
        with patch('builtins.open', side_effect=IOError("read-only")):
            result = await flush_confirm_no(update, context)
        assert result == ConversationHandler.END
        update.callback_query.edit_message_text.assert_called()
        text = update.callback_query.edit_message_text.call_args[1]['text']
        assert "error" in text.lower() or "Error" in text


# ---------------------------------------------------------------------------
# hist handler – image send error paths and cleanup
# ---------------------------------------------------------------------------

class TestHistHandlerEdgeCases:
    def _make_context(self, history=None):
        ctx = MagicMock()
        ctx.bot_data = {
            'allowed_user_ids': {'123'},
            'balance_history': history or {"2024/01/01-10:00": {"balance": 100.0}},
            'balance_lock': threading.Lock(),
        }
        return ctx

    async def test_image_send_raises_oserror(self, tmp_path, monkeypatch):
        """Cover lines 254-257: OSError when opening history image."""
        monkeypatch.chdir(tmp_path)
        update = _authorized_update()
        context = self._make_context()

        fake_image = tmp_path / "balance_history.png"
        fake_image.write_bytes(b"PNG")

        real_open = open

        def _mock_open(path, mode='r', **kwargs):
            if 'balance_history.png' in str(path) and mode == 'rb':
                raise OSError("disk error")
            return real_open(path, mode, **kwargs)

        with patch('handlers.node.create_balance_history_plot', return_value=str(fake_image)), \
             patch('builtins.open', side_effect=_mock_open):
            result = await hist(update, context)

        assert result == ConversationHandler.END
        texts = [c[0][0] for c in update.message.reply_text.call_args_list]
        assert any("Error" in t or "error" in t for t in texts)

    async def test_image_send_raises_generic_exception(self, tmp_path, monkeypatch):
        """Cover lines 258-261: Generic exception when opening history image."""
        monkeypatch.chdir(tmp_path)
        update = _authorized_update()
        context = self._make_context()

        fake_image = tmp_path / "balance_history.png"
        fake_image.write_bytes(b"PNG")

        real_open = open

        def _mock_open(path, mode='r', **kwargs):
            if 'balance_history.png' in str(path) and mode == 'rb':
                raise RuntimeError("generic error")
            return real_open(path, mode, **kwargs)

        with patch('handlers.node.create_balance_history_plot', return_value=str(fake_image)), \
             patch('builtins.open', side_effect=_mock_open):
            result = await hist(update, context)

        assert result == ConversationHandler.END

    async def test_resources_plot_exception_is_non_fatal(self, tmp_path, monkeypatch):
        """Cover lines 269-270: Exception in resources plot is non-fatal."""
        monkeypatch.chdir(tmp_path)
        update = _authorized_update()
        context = self._make_context()

        fake_image = tmp_path / "balance_history.png"
        fake_image.write_bytes(b"PNG")

        with patch('handlers.node.create_balance_history_plot', return_value=str(fake_image)), \
             patch('handlers.node.create_resources_plot', side_effect=Exception("plot error")), \
             patch('builtins.open', mock_open(read_data=b"PNG")):
            result = await hist(update, context)

        # Should continue and return HIST_CONFIRM_STATE despite resources plot error
        assert result == HIST_CONFIRM_STATE

    async def test_outer_exception_returns_end(self, tmp_path, monkeypatch):
        """Cover lines 288-291: Outer exception handler in hist."""
        monkeypatch.chdir(tmp_path)
        update = _authorized_update()
        context = self._make_context()

        with patch('handlers.node.create_balance_history_plot', side_effect=Exception("unexpected")):
            result = await hist(update, context)

        assert result == ConversationHandler.END
        texts = [c[0][0] for c in update.message.reply_text.call_args_list]
        assert any("Error" in t or "error" in t for t in texts)

    async def test_finally_cleanup_raises_for_resources_path(self, tmp_path, monkeypatch):
        """Cover lines 300-301: Exception when deleting resources image in finally."""
        monkeypatch.chdir(tmp_path)
        update = _authorized_update()
        context = self._make_context()

        fake_image = tmp_path / "balance_history.png"
        fake_image.write_bytes(b"PNG")
        fake_resources = tmp_path / "resources_history.png"
        fake_resources.write_bytes(b"PNG")

        orig_exists = os.path.exists
        orig_remove = os.remove

        def mock_remove(path):
            raise OSError("cannot delete")

        with patch('handlers.node.create_balance_history_plot', return_value=str(fake_image)), \
             patch('handlers.node.create_resources_plot', return_value=str(fake_resources)), \
             patch('builtins.open', mock_open(read_data=b"PNG")), \
             patch('os.remove', side_effect=mock_remove):
            result = await hist(update, context)

        # Should complete without raising
        assert result == HIST_CONFIRM_STATE


# ---------------------------------------------------------------------------
# scheduler – cover remaining lines (temperature in entry, oldest_24h logic)
# ---------------------------------------------------------------------------

class TestSchedulerRemainingLines:
    def _make_app(self, balance_history=None):
        app = MagicMock()
        app.bot = AsyncMock()
        app.bot.send_message = AsyncMock()
        app.bot.send_photo = AsyncMock()
        lock = threading.Lock()
        app.bot_data = {
            'allowed_user_ids': {'111'},
            'balance_history': balance_history if balance_history is not None else {},
            'massa_node_address': 'AU1test',
            'balance_lock': lock,
        }
        return app

    _VALID_JSON = {
        "result": [{
            "final_balance": "1000.00",
            "final_roll_count": 5,
            "cycle_infos": [{"cycle": 100, "ok_count": 10, "nok_count": 0, "active_rolls": 5}]
        }]
    }

    async def test_temperature_avg_added_to_entry(self):
        """Cover line 156: temperature_avg set in entry."""
        app = self._make_app()
        with patch('handlers.scheduler.get_addresses', return_value=self._VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={"temperature_avg": 55.0, "ram_percent": 60.0}), \
             patch('handlers.scheduler.save_balance_history'):
            await periodic_node_ping(app)
        # Check that the entry has temperature_avg
        history = app.bot_data['balance_history']
        assert len(history) == 1
        entry = next(iter(history.values()))
        assert 'temperature_avg' in entry
        assert entry['temperature_avg'] == 55.0

    async def test_report_with_recent_history_covers_oldest_balance(self):
        """Cover lines 178-179, 201-202: recent_history not empty at report hour."""
        now = datetime.now()
        # Create a history entry from 2 hours ago (definitely within 24h)
        two_hours_ago = now - timedelta(hours=2)
        key = f"{two_hours_ago.year}/{two_hours_ago.month:02d}/{two_hours_ago.day:02d}-{two_hours_ago.hour:02d}:{two_hours_ago.minute:02d}"
        balance_history = {key: {"balance": 900.0}}
        app = self._make_app(balance_history=balance_history)

        # Patch datetime in scheduler to a report hour
        report_time = datetime(now.year, now.month, now.day, 7, 0, 0)
        with patch('handlers.scheduler.get_addresses', return_value=self._VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'), \
             patch('handlers.scheduler.datetime') as mock_dt:
            mock_dt.now.return_value = report_time
            # Also need to patch filter functions to return our history
            with patch('handlers.scheduler.filter_last_24h', return_value={key: {"balance": 900.0}}), \
                 patch('handlers.scheduler.filter_since_midnight', return_value={}):
                await periodic_node_ping(app)

        app.bot.send_message.assert_called()

    async def test_report_midnight_history_present(self):
        """Cover lines 186-187: midnight_history is not empty."""
        now = datetime.now()
        today_key = f"{now.year}/{now.month:02d}/{now.day:02d}-01:00"
        midnight_history = {today_key: {"balance": 800.0}}
        recent_history = {today_key: {"balance": 800.0}}
        app = self._make_app(balance_history={today_key: {"balance": 800.0}})

        report_time = datetime(now.year, now.month, now.day, 7, 0, 0)
        with patch('handlers.scheduler.get_addresses', return_value=self._VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'), \
             patch('handlers.scheduler.datetime') as mock_dt:
            mock_dt.now.return_value = report_time
            with patch('handlers.scheduler.filter_last_24h', return_value=recent_history), \
                 patch('handlers.scheduler.filter_since_midnight', return_value=midnight_history):
                await periodic_node_ping(app)

        app.bot.send_message.assert_called()

    async def test_report_no_midnight_but_oldest_24h_available(self):
        """Cover lines 188-190: midnight_history empty but oldest_24h_balance is not None."""
        now = datetime.now()
        yesterday = now - timedelta(hours=10)
        key = f"{yesterday.year}/{yesterday.month:02d}/{yesterday.day:02d}-{yesterday.hour:02d}:{yesterday.minute:02d}"
        recent_history = {key: {"balance": 950.0}}
        app = self._make_app(balance_history={key: {"balance": 950.0}})

        report_time = datetime(now.year, now.month, now.day, 7, 0, 0)
        with patch('handlers.scheduler.get_addresses', return_value=self._VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'), \
             patch('handlers.scheduler.datetime') as mock_dt:
            mock_dt.now.return_value = report_time
            # midnight_history is empty, recent_history has data
            with patch('handlers.scheduler.filter_last_24h', return_value=recent_history), \
                 patch('handlers.scheduler.filter_since_midnight', return_value={}):
                await periodic_node_ping(app)

        app.bot.send_message.assert_called()

    async def test_report_no_history_at_all_sends_node_is_up(self):
        """Cover line 239: empty balance_history at report hour → tmp_string = NODE_IS_UP."""
        app = self._make_app(balance_history={})

        report_time = datetime.now().replace(hour=7, minute=0, second=0)
        with patch('handlers.scheduler.get_addresses', return_value=self._VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'), \
             patch('handlers.scheduler.datetime') as mock_dt:
            mock_dt.now.return_value = report_time
            await periodic_node_ping(app)

        # NODE_IS_UP message should have been sent
        app.bot.send_message.assert_called()
        texts = [c[1]['text'] for c in app.bot.send_message.call_args_list]
        assert any("up" in t.lower() for t in texts)

    async def test_report_with_temperature_samples(self):
        """Cover temp_samples path: entries with temperature_avg in recent_history."""
        now = datetime.now()
        recent_key = f"{now.year}/{now.month:02d}/{now.day:02d}-02:00"
        recent_history = {recent_key: {"balance": 900.0, "temperature_avg": 55.0}}
        app = self._make_app(balance_history={recent_key: {"balance": 900.0, "temperature_avg": 55.0}})

        report_time = datetime(now.year, now.month, now.day, 7, 0, 0)
        with patch('handlers.scheduler.get_addresses', return_value=self._VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'), \
             patch('handlers.scheduler.datetime') as mock_dt:
            mock_dt.now.return_value = report_time
            with patch('handlers.scheduler.filter_last_24h', return_value=recent_history), \
                 patch('handlers.scheduler.filter_since_midnight', return_value={}):
                await periodic_node_ping(app)

        app.bot.send_message.assert_called()
        texts = [c[1]['text'] for c in app.bot.send_message.call_args_list]
        assert any("Temp" in t for t in texts)
