"""Tests for the new factorized helpers in services/history.py.

Covers:
    - make_time_key
    - build_balance_entry
    - format_history_entry
"""
import sys
import os
import pytest
from datetime import datetime

# Ensure src/ is on the path so imports work without installation
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.history import make_time_key, build_balance_entry, format_history_entry


# ---------------------------------------------------------------------------
# make_time_key
# ---------------------------------------------------------------------------

class TestMakeTimeKey:
    def test_formats_datetime_correctly(self):
        dt = datetime(2025, 3, 14, 7, 5)
        assert make_time_key(dt) == "2025/03/14-07:05"

    def test_zero_pads_month_day_hour_minute(self):
        dt = datetime(2025, 1, 2, 3, 4)
        assert make_time_key(dt) == "2025/01/02-03:04"

    def test_end_of_year(self):
        dt = datetime(2024, 12, 31, 23, 59)
        assert make_time_key(dt) == "2024/12/31-23:59"

    def test_default_uses_current_time(self):
        before = datetime.now()
        key = make_time_key()
        after = datetime.now()
        # Key must be parseable back to a datetime
        dt = datetime.strptime(key, "%Y/%m/%d-%H:%M")
        # The key's datetime must lie within [before, after] (minute precision)
        assert dt.year == before.year
        assert dt.month == before.month
        assert dt.day == before.day
        assert dt.hour == before.hour

    def test_returns_string(self):
        assert isinstance(make_time_key(datetime(2025, 6, 15, 12, 0)), str)


# ---------------------------------------------------------------------------
# build_balance_entry
# ---------------------------------------------------------------------------

class TestBuildBalanceEntry:
    def test_balance_only_when_stats_empty(self):
        entry = build_balance_entry(1234.56, {})
        assert entry == {"balance": 1234.56}

    def test_includes_temperature_when_present(self):
        entry = build_balance_entry(100.0, {"temperature_avg": 42.5})
        assert entry == {"balance": 100.0, "temperature_avg": 42.5}

    def test_includes_ram_when_present(self):
        entry = build_balance_entry(100.0, {"ram_percent": 63.2})
        assert entry == {"balance": 100.0, "ram_percent": 63.2}

    def test_includes_both_temperature_and_ram(self):
        entry = build_balance_entry(500.0, {"temperature_avg": 55.0, "ram_percent": 80.1})
        assert entry == {"balance": 500.0, "temperature_avg": 55.0, "ram_percent": 80.1}

    def test_excludes_temperature_when_none(self):
        entry = build_balance_entry(100.0, {"temperature_avg": None, "ram_percent": 50.0})
        assert "temperature_avg" not in entry
        assert entry["ram_percent"] == 50.0

    def test_excludes_ram_when_none(self):
        entry = build_balance_entry(100.0, {"temperature_avg": 40.0, "ram_percent": None})
        assert "ram_percent" not in entry
        assert entry["temperature_avg"] == 40.0

    def test_ignores_unrelated_stats_keys(self):
        entry = build_balance_entry(200.0, {"cpu_percent": 10.0, "other": "ignored"})
        assert entry == {"balance": 200.0}

    def test_balance_stored_as_float(self):
        entry = build_balance_entry(0.0, {})
        assert isinstance(entry["balance"], float)

    def test_zero_balance(self):
        entry = build_balance_entry(0.0, {})
        assert entry["balance"] == 0.0


# ---------------------------------------------------------------------------
# format_history_entry
# ---------------------------------------------------------------------------

class TestFormatHistoryEntry:
    def test_dict_entry_with_all_fields(self):
        value = {"balance": 1234.56, "temperature_avg": 42.1, "ram_percent": 63.5}
        result = format_history_entry("2025/03/14-07:05", value)
        assert result == "2025/03/14-07:05: Balance 1234.56, Temp 42.1°C, RAM 63.5%"

    def test_dict_entry_balance_only(self):
        value = {"balance": 500.0}
        result = format_history_entry("2025/03/14-08:00", value)
        assert result == "2025/03/14-08:00: Balance 500.00"

    def test_dict_entry_with_temperature_no_ram(self):
        value = {"balance": 200.0, "temperature_avg": 55.0}
        result = format_history_entry("2025/03/14-09:00", value)
        assert result == "2025/03/14-09:00: Balance 200.00, Temp 55.0°C"

    def test_dict_entry_with_ram_no_temperature(self):
        value = {"balance": 300.0, "ram_percent": 75.3}
        result = format_history_entry("2025/03/14-10:00", value)
        assert result == "2025/03/14-10:00: Balance 300.00, RAM 75.3%"

    def test_legacy_string_entry(self):
        # Legacy format: "Balance: 1234.56"
        result = format_history_entry("14/03-07:05", "Balance: 1234.56")
        assert result == "14/03-07:05: Balance 1234.56"

    def test_zero_balance(self):
        value = {"balance": 0.0}
        result = format_history_entry("2025/01/01-00:00", value)
        assert result == "2025/01/01-00:00: Balance 0.00"

    def test_balance_rounds_to_two_decimals(self):
        value = {"balance": 1234.5678}
        result = format_history_entry("2025/03/14-07:05", value)
        assert "Balance 1234.57" in result

    def test_temperature_rounds_to_one_decimal(self):
        value = {"balance": 100.0, "temperature_avg": 42.16}
        result = format_history_entry("2025/03/14-07:05", value)
        assert "Temp 42.2°C" in result

    def test_ram_rounds_to_one_decimal(self):
        value = {"balance": 100.0, "ram_percent": 63.16}
        result = format_history_entry("2025/03/14-07:05", value)
        assert "RAM 63.2%" in result

    def test_returns_string(self):
        result = format_history_entry("2025/03/14-07:05", {"balance": 1.0})
        assert isinstance(result, str)
