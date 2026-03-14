"""Additional tests to cover scheduler.py run_async_func and remaining gaps."""
import asyncio
import logging
import threading
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from handlers.scheduler import run_async_func, periodic_node_ping


class TestRunAsyncFunc:
    def test_run_async_func_creates_new_event_loop_when_none_running(self):
        """When no event loop is running, run_async_func creates a new one."""
        mock_app = MagicMock()
        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        mock_scheduler.get_job.return_value = None

        with patch('handlers.scheduler.asyncio.get_running_loop', side_effect=RuntimeError("no loop")), \
             patch('handlers.scheduler.asyncio.new_event_loop', return_value=MagicMock()), \
             patch('handlers.scheduler.asyncio.set_event_loop'), \
             patch('handlers.scheduler.BackgroundScheduler', return_value=mock_scheduler):
            run_async_func(mock_app)

        mock_scheduler.add_job.assert_called_once()
        mock_scheduler.start.assert_called_once()

    def test_run_async_func_reuses_existing_loop(self):
        """When a loop is already running, run_async_func reuses it."""
        mock_app = MagicMock()
        mock_loop = MagicMock()
        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        mock_scheduler.get_job.return_value = None

        with patch('handlers.scheduler.asyncio.get_running_loop', return_value=mock_loop), \
             patch('handlers.scheduler.BackgroundScheduler', return_value=mock_scheduler):
            run_async_func(mock_app)

        mock_scheduler.add_job.assert_called_once()

    def test_run_async_func_removes_existing_job(self):
        """If a job with the same ID already exists, it should be removed first."""
        mock_app = MagicMock()
        mock_scheduler = MagicMock()
        mock_scheduler.running = True  # already running
        mock_scheduler.get_job.return_value = MagicMock()  # job exists

        with patch('handlers.scheduler.asyncio.get_running_loop', side_effect=RuntimeError), \
             patch('handlers.scheduler.asyncio.new_event_loop', return_value=MagicMock()), \
             patch('handlers.scheduler.asyncio.set_event_loop'), \
             patch('handlers.scheduler.BackgroundScheduler', return_value=mock_scheduler):
            run_async_func(mock_app)

        mock_scheduler.remove_job.assert_called_once()
        # Scheduler is already running, so start() is NOT called again
        mock_scheduler.start.assert_not_called()

    def test_run_async_func_handles_exception(self):
        """An exception inside run_async_func should be caught and logged."""
        mock_app = MagicMock()
        with patch('handlers.scheduler.asyncio.get_running_loop', side_effect=RuntimeError("bad")), \
             patch('handlers.scheduler.asyncio.new_event_loop', side_effect=OSError("no loop")):
            # Must not raise
            run_async_func(mock_app)


class TestPeriodicNodePingReportHours:
    """Edge-cases around balance history reporting at hours 7, 12, 21."""

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

    async def test_report_at_hour_12_with_empty_balance_history(self):
        """At report hour with empty history, should still send NODE_IS_UP."""
        from datetime import datetime
        app = self._make_app(balance_history={})

        report_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch('handlers.scheduler.get_addresses', return_value=self._VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'), \
             patch('handlers.scheduler.datetime') as mock_dt:
            mock_dt.now.return_value = report_time
            await periodic_node_ping(app)
        # Sends the NODE_IS_UP text to all users
        app.bot.send_message.assert_called()

    async def test_report_at_hour_21_with_history(self):
        """At hour 21 with balance history, detailed report is sent."""
        from datetime import datetime, timedelta
        now = datetime(2024, 6, 15, 21, 0, 0)
        earlier = now - timedelta(hours=3)
        key = f"{earlier.year}/{earlier.month:02d}/{earlier.day:02d}-{earlier.hour:02d}:{earlier.minute:02d}"
        app = self._make_app(balance_history={key: {"balance": 900.0, "temperature_avg": 55.0}})

        with patch('handlers.scheduler.get_addresses', return_value=self._VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={"ram_percent": 60.0}), \
             patch('handlers.scheduler.save_balance_history'), \
             patch('handlers.scheduler.datetime') as mock_dt:
            mock_dt.now.return_value = now
            await periodic_node_ping(app)

        app.bot.send_message.assert_called()

    async def test_non_report_hour_sends_no_message_when_node_up(self):
        """At a non-report hour (e.g. hour 3), no message should be sent if node is up."""
        from datetime import datetime
        app = self._make_app()
        report_time = datetime(2024, 1, 1, 3, 0, 0)

        with patch('handlers.scheduler.get_addresses', return_value=self._VALID_JSON), \
             patch('handlers.scheduler.get_system_stats', return_value={}), \
             patch('handlers.scheduler.save_balance_history'), \
             patch('handlers.scheduler.datetime') as mock_dt:
            mock_dt.now.return_value = report_time
            await periodic_node_ping(app)

        app.bot.send_message.assert_not_called()
