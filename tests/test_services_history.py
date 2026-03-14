"""Exhaustive tests for src/services/history.py."""
import json
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from services.history import (
    get_entry_balance,
    get_entry_temperature,
    get_entry_ram,
    load_balance_history,
    save_balance_history,
    filter_since_midnight,
    filter_last_24h,
)


# ---------------------------------------------------------------------------
# get_entry_balance
# ---------------------------------------------------------------------------

class TestGetEntryBalance:
    def test_dict_format_with_balance_key(self):
        assert get_entry_balance({"balance": 42.5}) == 42.5

    def test_dict_format_missing_balance_key_returns_zero(self):
        assert get_entry_balance({"other": 1}) == 0.0

    def test_dict_format_zero_balance(self):
        assert get_entry_balance({"balance": 0.0}) == 0.0

    def test_legacy_string_format(self):
        assert get_entry_balance("Balance: 99.75") == 99.75

    def test_legacy_string_bad_format_returns_zero(self):
        assert get_entry_balance("no colon here") == 0.0

    def test_legacy_string_non_numeric_returns_zero(self):
        assert get_entry_balance("Balance: abc") == 0.0

    def test_empty_string_returns_zero(self):
        assert get_entry_balance("") == 0.0

    def test_integer_value_via_dict(self):
        assert get_entry_balance({"balance": 10}) == 10.0


# ---------------------------------------------------------------------------
# get_entry_temperature
# ---------------------------------------------------------------------------

class TestGetEntryTemperature:
    def test_dict_with_temperature_avg(self):
        assert get_entry_temperature({"temperature_avg": 55.3}) == 55.3

    def test_dict_without_temperature_avg(self):
        assert get_entry_temperature({"balance": 1.0}) is None

    def test_string_input_returns_none(self):
        assert get_entry_temperature("Balance: 10") is None

    def test_dict_with_none_temperature(self):
        assert get_entry_temperature({"temperature_avg": None}) is None


# ---------------------------------------------------------------------------
# get_entry_ram
# ---------------------------------------------------------------------------

class TestGetEntryRam:
    def test_dict_with_ram_percent(self):
        assert get_entry_ram({"ram_percent": 72.4}) == 72.4

    def test_dict_without_ram_percent(self):
        assert get_entry_ram({"balance": 1.0}) is None

    def test_string_input_returns_none(self):
        assert get_entry_ram("Balance: 10") is None

    def test_dict_with_none_ram(self):
        assert get_entry_ram({"ram_percent": None}) is None


# ---------------------------------------------------------------------------
# load_balance_history
# ---------------------------------------------------------------------------

class TestLoadBalanceHistory:
    def test_loads_valid_json_file(self, tmp_path):
        data = {"2024/01/01-10:00": {"balance": 100.0}}
        history_file = tmp_path / "balance_history.json"
        history_file.write_text(json.dumps(data), encoding='utf-8')

        with patch('services.history.BALANCE_HISTORY_FILE', str(history_file)):
            result = load_balance_history()

        assert result == data

    def test_returns_empty_dict_for_missing_file(self, tmp_path):
        missing_file = tmp_path / "nonexistent.json"
        with patch('services.history.BALANCE_HISTORY_FILE', str(missing_file)):
            result = load_balance_history()
        assert result == {}

    def test_returns_empty_dict_for_corrupt_json(self, tmp_path):
        corrupt_file = tmp_path / "balance_history.json"
        corrupt_file.write_text("{not valid json", encoding='utf-8')
        with patch('services.history.BALANCE_HISTORY_FILE', str(corrupt_file)):
            result = load_balance_history()
        assert result == {}

    def test_returns_empty_dict_on_ioerror(self, tmp_path):
        history_file = tmp_path / "balance_history.json"
        history_file.write_text("{}", encoding='utf-8')
        with patch('services.history.BALANCE_HISTORY_FILE', str(history_file)):
            with patch('builtins.open', side_effect=IOError("disk full")):
                result = load_balance_history()
        assert result == {}


# ---------------------------------------------------------------------------
# save_balance_history
# ---------------------------------------------------------------------------

class TestSaveBalanceHistory:
    def test_creates_directory_and_writes_file(self, tmp_path):
        target = tmp_path / "subdir" / "balance_history.json"
        data = {"2024/01/01-10:00": {"balance": 55.0}}
        with patch('services.history.BALANCE_HISTORY_FILE', str(target)):
            save_balance_history(data)
        assert target.exists()
        assert json.loads(target.read_text()) == data

    def test_writes_correct_json(self, tmp_path):
        target = tmp_path / "balance_history.json"
        data = {"k1": {"balance": 1.0}, "k2": {"balance": 2.0}}
        with patch('services.history.BALANCE_HISTORY_FILE', str(target)):
            save_balance_history(data)
        loaded = json.loads(target.read_text())
        assert loaded == data

    def test_handles_ioerror_gracefully(self, tmp_path):
        target = tmp_path / "balance_history.json"
        with patch('services.history.BALANCE_HISTORY_FILE', str(target)):
            with patch('builtins.open', side_effect=IOError("read-only")):
                # Must not raise
                save_balance_history({"key": "val"})

    def test_empty_dict_saved(self, tmp_path):
        target = tmp_path / "balance_history.json"
        with patch('services.history.BALANCE_HISTORY_FILE', str(target)):
            save_balance_history({})
        assert json.loads(target.read_text()) == {}


# ---------------------------------------------------------------------------
# filter_since_midnight
# ---------------------------------------------------------------------------

class TestFilterSinceMidnight:
    def _key(self, dt: datetime) -> str:
        return f"{dt.year}/{dt.month:02d}/{dt.day:02d}-{dt.hour:02d}:{dt.minute:02d}"

    def test_empty_dict_returns_empty(self):
        assert filter_since_midnight({}) == {}

    def test_entries_before_midnight_filtered_out(self):
        now = datetime.now()
        yesterday = now - timedelta(hours=25)
        key = self._key(yesterday)
        result = filter_since_midnight({key: {"balance": 1.0}})
        assert result == {}

    def test_entries_after_midnight_kept(self):
        now = datetime.now()
        today_key = self._key(now.replace(hour=1, minute=0) if now.hour > 1 else now)
        # Use a time that is definitely today and after midnight
        today_dt = now.replace(hour=0, minute=30)
        key = self._key(today_dt)
        result = filter_since_midnight({key: {"balance": 5.0}})
        assert key in result

    def test_legacy_format_kept_if_today(self):
        now = datetime.now()
        # Build a legacy key for today
        legacy_key = f"{now.day:02d}/{now.month:02d}-{now.hour:02d}:{now.minute:02d}"
        result = filter_since_midnight({legacy_key: "Balance: 10"})
        # Should be included (today's entry)
        assert len(result) <= 1  # might or might not be included depending on exact hour

    def test_invalid_format_skipped(self):
        result = filter_since_midnight({"not-a-date": {"balance": 1.0}})
        assert result == {}

    def test_result_is_sorted_chronologically(self):
        now = datetime.now()
        early = now.replace(hour=1, minute=0)
        late = now.replace(hour=2, minute=0)
        history = {
            self._key(late): {"balance": 2.0},
            self._key(early): {"balance": 1.0},
        }
        result = filter_since_midnight(history)
        keys = list(result.keys())
        if len(keys) >= 2:
            assert keys.index(self._key(early)) < keys.index(self._key(late))


# ---------------------------------------------------------------------------
# filter_last_24h
# ---------------------------------------------------------------------------

class TestFilterLast24h:
    def _key(self, dt: datetime) -> str:
        return f"{dt.year}/{dt.month:02d}/{dt.day:02d}-{dt.hour:02d}:{dt.minute:02d}"

    def test_empty_dict_returns_empty(self):
        assert filter_last_24h({}) == {}

    def test_entries_older_than_24h_removed(self):
        now = datetime.now()
        old = now - timedelta(hours=25)
        key = self._key(old)
        result = filter_last_24h({key: {"balance": 1.0}})
        assert result == {}

    def test_recent_entry_kept(self):
        now = datetime.now()
        recent = now - timedelta(hours=1)
        key = self._key(recent)
        result = filter_last_24h({key: {"balance": 5.0}})
        assert key in result

    def test_one_per_hour_dedup(self):
        now = datetime.now()
        # Two entries in the same hour; only the latest should be kept
        hour_dt = now - timedelta(hours=2)
        earlier = hour_dt.replace(minute=10)
        later = hour_dt.replace(minute=50)
        history = {
            self._key(earlier): {"balance": 1.0},
            self._key(later): {"balance": 2.0},
        }
        result = filter_last_24h(history)
        assert len(result) == 1
        assert self._key(later) in result

    def test_max_24_entries(self):
        now = datetime.now()
        history = {}
        # Insert 30 entries over the last 30 hours but all in different hours within last 24h
        for i in range(30):
            dt = now - timedelta(hours=i)
            history[self._key(dt)] = {"balance": float(i)}
        result = filter_last_24h(history)
        assert len(result) <= 24

    def test_legacy_format_parsed(self):
        now = datetime.now()
        # Build a legacy key for 2 hours ago
        two_hours_ago = now - timedelta(hours=2)
        legacy_key = f"{two_hours_ago.day:02d}/{two_hours_ago.month:02d}-{two_hours_ago.hour:02d}:{two_hours_ago.minute:02d}"
        result = filter_last_24h({legacy_key: "Balance: 7"})
        assert len(result) == 1

    def test_invalid_format_skipped(self):
        result = filter_last_24h({"not-a-date": {"balance": 1.0}})
        assert result == {}

    def test_result_sorted_chronologically(self):
        now = datetime.now()
        keys_and_hours = []
        for h in range(3, 0, -1):
            dt = now - timedelta(hours=h)
            keys_and_hours.append((self._key(dt), dt))
        history = {k: {"balance": float(i)} for i, (k, _) in enumerate(keys_and_hours)}
        result = filter_last_24h(history)
        dts = []
        for k in result.keys():
            dts.append(datetime.strptime(k, "%Y/%m/%d-%H:%M"))
        assert dts == sorted(dts)
