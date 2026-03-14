"""Tests for src/handlers/system.py."""
import threading
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from handlers.system import (
    _get_git_commit_hash,
    _calculate_uptime,
    _is_recent,
    hi,
    temperature,
    perf,
)


# ---------------------------------------------------------------------------
# _get_git_commit_hash
# ---------------------------------------------------------------------------

class TestGetGitCommitHash:
    def test_success_returns_short_hash(self):
        with patch('handlers.system.subprocess.check_output', return_value='abc1234\n'):
            result = _get_git_commit_hash()
        assert result == 'abc1234'

    def test_failure_returns_unknown(self):
        with patch('handlers.system.subprocess.check_output', side_effect=Exception("not a git repo")):
            result = _get_git_commit_hash()
        assert result == 'unknown'


# ---------------------------------------------------------------------------
# hi handler
# ---------------------------------------------------------------------------

class TestHiHandler:
    async def test_sends_greeting_and_photo(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.system._get_git_commit_hash', return_value='abc1234'):
            await hi(update, context)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert 'abc1234' in text
        update.message.reply_photo.assert_called_once()

    async def test_unauthorized_user_blocked(self, unauthorized_update_context):
        update, context = unauthorized_update_context
        await hi(update, context)
        update.message.reply_photo.assert_not_called()


# ---------------------------------------------------------------------------
# temperature handler
# ---------------------------------------------------------------------------

_FULL_STATS = {
    "cpu_percent": 27.5,
    "cpu_cores": [{"core": 0, "percent": 25.0}, {"core": 1, "percent": 30.0}],
    "ram_percent": 60.0,
    "ram_available_gb": 4.0,
    "ram_total_gb": 8.0,
    "temperature_details": [
        {"sensor": "coretemp", "label": "Core 0", "current": 55.0}
    ],
    "temperature_avg": 55.0,
}


class TestTemperatureHandler:
    async def test_happy_path_sends_formatted_stats(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.system.get_system_stats', return_value=_FULL_STATS):
            await temperature(update, context)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "CPU Usage" in text
        assert "RAM Usage" in text

    async def test_temperature_details_included(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.system.get_system_stats', return_value=_FULL_STATS):
            await temperature(update, context)
        text = update.message.reply_text.call_args[0][0]
        assert "Temperatures" in text
        assert "55.0" in text

    async def test_stats_without_temperature_details(self, authorized_update_context):
        update, context = authorized_update_context
        stats_no_temp = {k: v for k, v in _FULL_STATS.items()
                         if k not in ('temperature_details', 'temperature_avg')}
        with patch('handlers.system.get_system_stats', return_value=stats_no_temp):
            await temperature(update, context)
        text = update.message.reply_text.call_args[0][0]
        assert "CPU Usage" in text

    async def test_error_in_stats_sends_error_message(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.system.get_system_stats', return_value={"error": "psutil not installed"}):
            await temperature(update, context)
        text = update.message.reply_text.call_args[0][0]
        assert "Error" in text

    async def test_exception_sends_error_message(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.system.get_system_stats', side_effect=Exception("boom")):
            await temperature(update, context)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "Error" in text

    async def test_unauthorized_user_blocked(self, unauthorized_update_context):
        update, context = unauthorized_update_context
        with patch('handlers.system.get_system_stats') as mock_stats:
            await temperature(update, context)
        mock_stats.assert_not_called()


# ---------------------------------------------------------------------------
# _calculate_uptime
# ---------------------------------------------------------------------------

class TestCalculateUptime:
    def _key(self, dt: datetime) -> str:
        return f"{dt.year}/{dt.month:02d}/{dt.day:02d}-{dt.hour:02d}:{dt.minute:02d}"

    def test_empty_history_returns_zero(self):
        assert _calculate_uptime({}) == 0.0

    def test_full_24_entries_returns_100(self):
        now = datetime.now()
        history = {}
        for i in range(24):
            dt = now - timedelta(hours=i)
            history[self._key(dt)] = {"balance": 1.0}
        result = _calculate_uptime(history)
        assert result == 100.0

    def test_12_entries_returns_50(self):
        now = datetime.now()
        history = {}
        for i in range(12):
            dt = now - timedelta(hours=i)
            history[self._key(dt)] = {"balance": 1.0}
        result = _calculate_uptime(history)
        assert result == pytest.approx(50.0, abs=0.1)

    def test_capped_at_100(self):
        now = datetime.now()
        history = {}
        for i in range(30):
            dt = now - timedelta(hours=i)
            history[self._key(dt)] = {"balance": 1.0}
        result = _calculate_uptime(history)
        assert result <= 100.0

    def test_old_entries_ignored(self):
        now = datetime.now()
        old = now - timedelta(hours=48)
        history = {self._key(old): {"balance": 1.0}}
        result = _calculate_uptime(history)
        assert result == 0.0


# ---------------------------------------------------------------------------
# _is_recent
# ---------------------------------------------------------------------------

class TestIsRecent:
    def _key(self, dt: datetime) -> str:
        return f"{dt.year}/{dt.month:02d}/{dt.day:02d}-{dt.hour:02d}:{dt.minute:02d}"

    def test_new_format_in_range_returns_true(self):
        now = datetime.now()
        cutoff = now - timedelta(hours=24)
        recent = now - timedelta(hours=1)
        assert _is_recent(self._key(recent), cutoff, now) is True

    def test_new_format_out_of_range_returns_false(self):
        now = datetime.now()
        cutoff = now - timedelta(hours=24)
        old = now - timedelta(hours=25)
        assert _is_recent(self._key(old), cutoff, now) is False

    def test_legacy_format_in_range(self):
        now = datetime.now()
        cutoff = now - timedelta(hours=24)
        recent = now - timedelta(hours=2)
        legacy_key = f"{recent.day:02d}/{recent.month:02d}-{recent.hour:02d}:{recent.minute:02d}"
        assert _is_recent(legacy_key, cutoff, now) is True

    def test_invalid_format_returns_false(self):
        now = datetime.now()
        cutoff = now - timedelta(hours=24)
        assert _is_recent("not-a-date", cutoff, now) is False


# ---------------------------------------------------------------------------
# perf handler
# ---------------------------------------------------------------------------

class TestPerfHandler:
    async def test_happy_path_sends_formatted_string(self, authorized_update_context):
        update, context = authorized_update_context
        context.bot_data['balance_history'] = {}
        with patch('handlers.system.measure_rpc_latency', return_value={"latency_ms": 123.4, "status": "ok"}):
            await perf(update, context)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "123.4" in text
        assert "Uptime" in text

    async def test_rpc_error_sends_error_message(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.system.measure_rpc_latency', return_value={"error": "connection failed"}):
            await perf(update, context)
        text = update.message.reply_text.call_args[0][0]
        assert "Error" in text

    async def test_exception_sends_error_message(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.system.measure_rpc_latency', side_effect=Exception("crash")):
            await perf(update, context)
        text = update.message.reply_text.call_args[0][0]
        assert "Error" in text

    async def test_unauthorized_user_blocked(self, unauthorized_update_context):
        update, context = unauthorized_update_context
        with patch('handlers.system.measure_rpc_latency') as mock_rpc:
            await perf(update, context)
        mock_rpc.assert_not_called()
