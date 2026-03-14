"""Tests for src/handlers/scheduler.py."""
import asyncio
import threading
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from handlers.scheduler import periodic_node_ping, run_coroutine_in_loop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_application(user_ids=None, balance_history=None, address='AU1test'):
    """Build a minimal mock Application object."""
    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()
    app.bot.send_photo = AsyncMock()
    lock = threading.Lock()
    app.bot_data = {
        'allowed_user_ids': user_ids if user_ids is not None else {'111'},
        'balance_history': balance_history if balance_history is not None else {},
        'massa_node_address': address,
        'balance_lock': lock,
    }
    return app


_VALID_JSON = {
    "result": [{
        "final_balance": "1000.00",
        "final_roll_count": 5,
        "cycle_infos": [
            {"cycle": 100, "ok_count": 10, "nok_count": 0, "active_rolls": 5},
        ]
    }]
}

_DOWN_JSON = {
    "result": [{
        "final_balance": "0.00",
        "final_roll_count": 0,  # roll_count == 0 → node_is_up = False
        "cycle_infos": [
            {"cycle": 100, "ok_count": 0, "nok_count": 5, "active_rolls": 0},
        ]
    }]
}


class TestPeriodicNodePing:
    async def test_happy_path_node_up(self):
        app = _make_application()
        with patch('handlers.scheduler.get_addresses', return_value=_VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'):
            await periodic_node_ping(app)
        # Node is up → should NOT call send_message with NODE_IS_DOWN
        for send_call in app.bot.send_message.call_args_list:
            assert "down" not in send_call[1].get('text', '').lower()

    async def test_node_down_sends_node_is_down(self):
        app = _make_application()
        with patch('handlers.scheduler.get_addresses', return_value=_DOWN_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'):
            await periodic_node_ping(app)
        # Should send NODE_IS_DOWN message
        app.bot.send_message.assert_called()
        texts = [c[1]['text'] for c in app.bot.send_message.call_args_list]
        assert any("down" in t.lower() for t in texts)

    async def test_api_error_timeout_sends_photo(self):
        app = _make_application()
        with patch('handlers.scheduler.get_addresses', return_value={"error": "Request timed out."}), \
             patch('builtins.open', mock_open(read_data=b"PNG")):
            await periodic_node_ping(app)
        app.bot.send_photo.assert_called()

    async def test_api_error_other_sends_photo(self):
        app = _make_application()
        with patch('handlers.scheduler.get_addresses', return_value={"error": "Connection error."}), \
             patch('builtins.open', mock_open(read_data=b"PNG")):
            await periodic_node_ping(app)
        app.bot.send_photo.assert_called()

    async def test_extract_address_data_returns_none_sends_ping_failed(self):
        app = _make_application()
        with patch('handlers.scheduler.get_addresses', return_value={"result": []}), \
             patch('handlers.scheduler.get_system_stats', return_value={}):
            await periodic_node_ping(app)
        app.bot.send_message.assert_called()
        texts = [c[1]['text'] for c in app.bot.send_message.call_args_list]
        assert any("invalid" in t.lower() or "failed" in t.lower() for t in texts)

    async def test_at_report_hour_sends_detailed_report(self):
        """At hour 7, 12, or 21 with node up, a detailed text report is sent."""
        app = _make_application(
            balance_history={"2024/01/01-06:00": {"balance": 900.0}}
        )
        report_time = datetime(2024, 1, 1, 7, 0, 0)
        with patch('handlers.scheduler.get_addresses', return_value=_VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'), \
             patch('handlers.scheduler.datetime') as mock_dt:
            mock_dt.now.return_value = report_time
            await periodic_node_ping(app)
        # The detailed report message should have been sent
        app.bot.send_message.assert_called()

    async def test_exception_is_handled_gracefully(self):
        app = _make_application()
        with patch('handlers.scheduler.get_addresses', side_effect=Exception("unexpected crash")):
            # Must not raise
            await periodic_node_ping(app)

    async def test_no_lock_in_bot_data(self):
        """If balance_lock is not set, the code should fall back to direct assignment."""
        app = _make_application()
        del app.bot_data['balance_lock']
        with patch('handlers.scheduler.get_addresses', return_value=_VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'):
            await periodic_node_ping(app)
        # Should have added an entry to balance_history
        assert len(app.bot_data['balance_history']) > 0

    async def test_photo_send_ioerror_is_handled(self):
        """If open() raises FileNotFoundError when sending the error photo, it should be logged."""
        app = _make_application()
        with patch('handlers.scheduler.get_addresses', return_value={"error": "timed out"}), \
             patch('builtins.open', side_effect=FileNotFoundError("file not found")):
            # Must not raise
            await periodic_node_ping(app)


# ---------------------------------------------------------------------------
# run_coroutine_in_loop
# ---------------------------------------------------------------------------

class TestRunCoroutineInLoop:
    def test_with_running_loop_uses_run_coroutine_threadsafe(self):
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        mock_future = MagicMock()
        mock_loop.run_coroutine_threadsafe = MagicMock()

        with patch('handlers.scheduler.asyncio.run_coroutine_threadsafe', return_value=mock_future) as mock_rcts:
            async def dummy_coro(app):
                pass

            run_coroutine_in_loop(dummy_coro, MagicMock(), mock_loop)

        mock_rcts.assert_called_once()
        mock_future.add_done_callback.assert_called_once()

    def test_with_idle_loop_uses_run_until_complete(self):
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False

        async def dummy_coro(app):
            return "done"

        run_coroutine_in_loop(dummy_coro, MagicMock(), mock_loop)
        mock_loop.run_until_complete.assert_called_once()

    def test_with_exception_logs_error(self):
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        mock_loop.run_until_complete.side_effect = RuntimeError("loop error")

        async def dummy_coro(app):
            pass

        # Must not raise
        run_coroutine_in_loop(dummy_coro, MagicMock(), mock_loop)

    def test_done_callback_logs_exception(self):
        """The _log_future_exception callback should log when the future has an exception."""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        mock_future = MagicMock()
        mock_future.exception.return_value = RuntimeError("coro failed")

        captured_callback = []

        def fake_add_done_callback(cb):
            captured_callback.append(cb)

        mock_future.add_done_callback = fake_add_done_callback

        with patch('handlers.scheduler.asyncio.run_coroutine_threadsafe', return_value=mock_future):
            async def dummy_coro(app):
                pass

            run_coroutine_in_loop(dummy_coro, MagicMock(), mock_loop)

        # Invoke the captured callback with a mock future that has an exception
        assert len(captured_callback) == 1
        captured_callback[0](mock_future)  # Should log but not raise

    def test_done_callback_no_exception(self):
        """The callback should be silent when the future completed without error."""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        mock_future = MagicMock()
        mock_future.exception.return_value = None

        captured_callback = []
        mock_future.add_done_callback = lambda cb: captured_callback.append(cb)

        with patch('handlers.scheduler.asyncio.run_coroutine_threadsafe', return_value=mock_future):
            async def dummy_coro(app):
                pass

            run_coroutine_in_loop(dummy_coro, MagicMock(), mock_loop)

        assert len(captured_callback) == 1
        captured_callback[0](mock_future)  # Must not raise
