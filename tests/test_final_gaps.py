"""Final targeted tests to cover the last remaining uncovered lines."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from telegram.ext import ConversationHandler

from services.history import filter_since_midnight, filter_last_24h
from handlers.system import _is_recent
from handlers.node import hist


# ---------------------------------------------------------------------------
# history.py lines 100 and 136 – legacy year rollback branch
# (when parsed date with current year > now + 1h → rollback to previous year)
# ---------------------------------------------------------------------------

class TestHistoryLegacyYearRollback:
    """Cover the `dt = dt.replace(year=current_year - 1)` branches."""

    def test_filter_since_midnight_legacy_year_rollback(self):
        """
        Provide a legacy DD/MM-HH:MM key that, when assigned the current year,
        would be more than 1 hour in the future (e.g. New Year's Eve entry run
        on January 1). The function should roll it back to the previous year.
        """
        # Fake "now" = January 1 of year 2025 at 00:30
        fake_now = datetime(2025, 1, 1, 0, 30, 0)
        # A legacy key for Dec 31 at 23:00 – with year 2025 that's in the future
        legacy_key = "31/12-23:00"

        with patch('services.history.datetime') as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.strptime.side_effect = lambda s, fmt: datetime.strptime(s, fmt)
            result = filter_since_midnight({legacy_key: {"balance": 1.0}})

        # The date Dec 31, 2024 is before midnight of Jan 1, 2025, so it's filtered out
        assert result == {}

    def test_filter_last_24h_legacy_year_rollback(self):
        """
        Same scenario for filter_last_24h: legacy key from Dec 31 when
        now is Jan 1 should be rolled back to previous year and included
        if within 24h.
        """
        # Fake "now" = January 1, 2025 at 01:00
        fake_now = datetime(2025, 1, 1, 1, 0, 0)
        # Dec 31 at 12:00 is 13 hours before now → within 24h
        legacy_key = "31/12-12:00"

        with patch('services.history.datetime') as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.strptime.side_effect = lambda s, fmt: datetime.strptime(s, fmt)
            result = filter_last_24h({legacy_key: {"balance": 2.0}})

        assert legacy_key in result

    def test_filter_since_midnight_legacy_year_rollback_recent(self):
        """
        Dec 31 at 23:30 when now is Jan 1 at 00:30 – date is within today window? No,
        because midnight is Jan 1 00:00. But the year-rollback is still exercised.
        """
        fake_now = datetime(2025, 1, 1, 2, 0, 0)
        # Dec 31 at 23:00 would with year=2025 be Dec 31, 2025 (future) → roll to 2024
        legacy_key = "31/12-23:00"

        with patch('services.history.datetime') as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.strptime.side_effect = lambda s, fmt: datetime.strptime(s, fmt)
            result = filter_since_midnight({legacy_key: {"balance": 3.0}})

        # Dec 31, 2024 23:00 is before midnight Jan 1, 2025 → filtered out
        assert result == {}


# ---------------------------------------------------------------------------
# handlers/system.py line 115 – _is_recent legacy year rollback
# ---------------------------------------------------------------------------

class TestIsRecentLegacyYearRollback:
    def test_legacy_key_in_future_gets_rolled_back(self):
        """
        A legacy key that with current year appears > 1h in the future
        should be rolled back to previous year (line 115).
        """
        now = datetime(2025, 1, 1, 0, 30, 0)
        cutoff = now - timedelta(hours=24)
        # "31/12-23:00" with year=2025 is Dec 31, 2025 → future → roll back to 2024
        # Dec 31, 2024 23:00 is < 2 hours before now → within cutoff
        legacy_key = "31/12-23:00"
        result = _is_recent(legacy_key, cutoff, now)
        assert result is True  # within 24h after rollback


# ---------------------------------------------------------------------------
# handlers/node.py lines 288-291 – outer exception handler in hist
# ---------------------------------------------------------------------------

class TestHistOuterException:
    def _make_context(self, history=None):
        import threading
        ctx = MagicMock()
        ctx.bot_data = {
            'allowed_user_ids': {'123'},
            'balance_history': history or {"2024/01/01-10:00": {"balance": 100.0}},
            'balance_lock': threading.Lock(),
        }
        return ctx

    def _make_update(self):
        update = MagicMock()
        update.effective_user.id = 123
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.message.reply_photo = AsyncMock()
        return update

    async def test_outer_exception_when_reply_text_raises_immediately(self, tmp_path, monkeypatch):
        """
        Cover lines 288-291: The outer except in hist() is triggered when
        `reply_text` raises on the first call (the 'Do you also want...' message).
        Subsequent call (from outer except error handler) returns normally.
        """
        monkeypatch.chdir(tmp_path)
        update = self._make_update()
        context = self._make_context()

        fake_image = tmp_path / "balance_history.png"
        fake_image.write_bytes(b"PNG")

        # First call raises, second call (from outer except) succeeds
        update.message.reply_text.side_effect = [
            RuntimeError("network send failed"),  # "Do you also want..." → raises
            None,                                 # "Error retrieving..." → succeeds
        ]

        with patch('handlers.node.create_balance_history_plot', return_value=str(fake_image)), \
             patch('handlers.node.create_resources_plot', return_value=""), \
             patch('builtins.open', mock_open(read_data=b"PNG")):
            result = await hist(update, context)

        assert result == ConversationHandler.END

    async def test_outer_exception_when_keyboard_markup_raises(self, tmp_path, monkeypatch):
        """
        Cover lines 288-291: InlineKeyboardMarkup raises → outer except catches it.
        """
        monkeypatch.chdir(tmp_path)
        update = self._make_update()
        context = self._make_context()

        fake_image = tmp_path / "balance_history.png"
        fake_image.write_bytes(b"PNG")

        with patch('handlers.node.create_balance_history_plot', return_value=str(fake_image)), \
             patch('handlers.node.create_resources_plot', return_value=""), \
             patch('handlers.node.InlineKeyboardMarkup', side_effect=RuntimeError("markup error")), \
             patch('builtins.open', mock_open(read_data=b"PNG")):
            result = await hist(update, context)

        assert result == ConversationHandler.END
        # Should have called reply_text with error message
        texts = [c[0][0] for c in update.message.reply_text.call_args_list]
        assert any("Error" in t or "error" in t for t in texts)
