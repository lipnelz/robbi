"""Tests for src/services/system_monitor.py."""
import logging
import sys
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from services.system_monitor import get_system_stats


def _make_virtual_memory(percent=60.0, available=4 * 1024 ** 3, total=8 * 1024 ** 3):
    vm = MagicMock()
    vm.percent = percent
    vm.available = available
    vm.total = total
    return vm


def _make_temp_entry(label, current):
    entry = MagicMock()
    entry.label = label
    entry.current = current
    return entry


class TestGetSystemStats:
    def test_happy_path_returns_cpu_and_ram(self):
        logger = MagicMock(spec=logging.Logger)
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = [25.0, 30.0]
        mock_psutil.virtual_memory.return_value = _make_virtual_memory()
        mock_psutil.sensors_temperatures.return_value = {
            "coretemp": [_make_temp_entry("Core 0", 55.0), _make_temp_entry("Core 1", 60.0)]
        }

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            result = get_system_stats(logger)

        assert "cpu_percent" in result
        assert result["cpu_percent"] == pytest.approx(27.5, abs=0.1)
        assert "ram_percent" in result
        assert "temperature_avg" in result
        assert "temperature_details" in result
        assert len(result["temperature_details"]) == 2

    def test_no_temperature_sensors_returns_stats_without_temp(self):
        logger = MagicMock(spec=logging.Logger)
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = [50.0]
        mock_psutil.virtual_memory.return_value = _make_virtual_memory()
        mock_psutil.sensors_temperatures.return_value = {}

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            result = get_system_stats(logger)

        assert "cpu_percent" in result
        assert "temperature_avg" not in result
        assert "temperature_details" not in result

    def test_psutil_no_sensors_temperatures_attribute(self):
        logger = MagicMock(spec=logging.Logger)
        mock_psutil = MagicMock(spec=['cpu_percent', 'virtual_memory'])
        mock_psutil.cpu_percent.return_value = [40.0]
        mock_psutil.virtual_memory.return_value = _make_virtual_memory()

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            result = get_system_stats(logger)

        assert "cpu_percent" in result
        assert "temperature_avg" not in result

    def test_psutil_not_installed_returns_error(self):
        logger = MagicMock(spec=logging.Logger)
        # Remove psutil from sys.modules so ImportError is triggered
        with patch.dict('sys.modules', {'psutil': None}):
            result = get_system_stats(logger)
        assert "error" in result
        assert "psutil" in result["error"].lower()

    def test_none_logger_uses_root_logger(self):
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = [10.0]
        mock_psutil.virtual_memory.return_value = _make_virtual_memory()
        mock_psutil.sensors_temperatures.return_value = {}

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            result = get_system_stats(None)

        assert "cpu_percent" in result

    def test_none_logger_when_psutil_missing(self):
        with patch.dict('sys.modules', {'psutil': None}):
            result = get_system_stats(None)
        assert "error" in result

    def test_exception_in_main_block_returns_error_dict(self):
        logger = MagicMock(spec=logging.Logger)
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.side_effect = RuntimeError("cpu exploded")
        mock_psutil.virtual_memory.return_value = _make_virtual_memory()

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            result = get_system_stats(logger)

        assert "error" in result
        logger.error.assert_called()

    def test_temperature_collection_exception_logged_as_warning(self):
        logger = MagicMock(spec=logging.Logger)
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = [30.0]
        mock_psutil.virtual_memory.return_value = _make_virtual_memory()
        mock_psutil.sensors_temperatures.side_effect = OSError("no sensors")

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            result = get_system_stats(logger)

        assert "cpu_percent" in result
        assert "error" not in result
        logger.warning.assert_called()

    def test_sensor_with_empty_label_uses_fallback(self):
        logger = MagicMock(spec=logging.Logger)
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = [20.0]
        mock_psutil.virtual_memory.return_value = _make_virtual_memory()
        entry = _make_temp_entry("", 45.0)  # empty label
        mock_psutil.sensors_temperatures.return_value = {"coretemp": [entry]}

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            result = get_system_stats(logger)

        assert "temperature_details" in result
        # Label should have been replaced with "Sensor 0"
        assert result["temperature_details"][0]["label"].startswith("Sensor")

    def test_cpu_per_core_empty_returns_zero_overall(self):
        logger = MagicMock(spec=logging.Logger)
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = []
        mock_psutil.virtual_memory.return_value = _make_virtual_memory()
        mock_psutil.sensors_temperatures.return_value = {}

        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            result = get_system_stats(logger)

        assert result["cpu_percent"] == 0
