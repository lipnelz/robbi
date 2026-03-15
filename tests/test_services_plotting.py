"""Tests for src/services/plotting.py using mocked matplotlib and tmp_path."""
import math
import pytest
from unittest.mock import patch, MagicMock

import matplotlib
matplotlib.use('Agg')

from services.plotting import (
    create_png_plot,
    create_resources_plot,
    create_balance_history_plot,
    PNG_FILE_NAME,
    RESOURCES_PLOT_FILE_NAME,
    BALANCE_HISTORY_PLOT_FILE_NAME,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plt_mock():
    """Return a MagicMock for matplotlib.pyplot with twinx support."""
    mock_plt = MagicMock()
    fig_mock = MagicMock()
    ax1_mock = MagicMock()
    ax2_mock = MagicMock()
    ax1_mock.twinx.return_value = ax2_mock
    ax1_mock.get_legend_handles_labels.return_value = ([], [])
    ax2_mock.get_legend_handles_labels.return_value = ([], [])
    mock_plt.subplots.return_value = (fig_mock, ax1_mock)
    mock_plt.figure.return_value = fig_mock
    return mock_plt, fig_mock, ax1_mock, ax2_mock


# ---------------------------------------------------------------------------
# create_png_plot
# ---------------------------------------------------------------------------

class TestCreatePngPlot:
    def test_creates_and_returns_filename(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cycles = [1, 2, 3]
        nok = [0, 1, 0]
        ok = [5, 4, 6]
        result = create_png_plot(cycles, nok, ok)
        assert result.endswith(PNG_FILE_NAME)
        assert (tmp_path / result).exists()

    def test_closes_figure_on_success(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_plt, fig, _, _ = _make_plt_mock()
        with patch('services.plotting.plt', mock_plt):
            create_png_plot([1], [0], [1])
        mock_plt.close.assert_called_once_with(fig)

    def test_closes_figure_on_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_plt, fig, _, _ = _make_plt_mock()
        mock_plt.plot.side_effect = RuntimeError("plot error")
        with patch('services.plotting.plt', mock_plt):
            with pytest.raises(RuntimeError):
                create_png_plot([1], [0], [1])
        mock_plt.close.assert_called_with(fig)


# ---------------------------------------------------------------------------
# create_resources_plot
# ---------------------------------------------------------------------------

class TestCreateResourcesPlot:
    def test_empty_dict_returns_empty_string(self):
        assert create_resources_plot({}) == ""

    def test_no_temp_or_ram_data_returns_empty_string(self):
        # legacy string entries have no temp/ram
        history = {"01/01-10:00": "Balance: 5.0"}
        assert create_resources_plot(history) == ""

    def test_temperature_only_returns_filename(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        history = {
            "2024/01/01-10:00": {"balance": 1.0, "temperature_avg": 55.0},
            "2024/01/01-11:00": {"balance": 1.5, "temperature_avg": 57.0},
        }
        result = create_resources_plot(history)
        assert result.endswith(RESOURCES_PLOT_FILE_NAME)
        assert (tmp_path / result).exists()

    def test_ram_only_returns_filename(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        history = {
            "2024/01/01-10:00": {"balance": 1.0, "ram_percent": 60.0},
            "2024/01/01-11:00": {"balance": 1.5, "ram_percent": 65.0},
        }
        result = create_resources_plot(history)
        assert result.endswith(RESOURCES_PLOT_FILE_NAME)
        assert (tmp_path / result).exists()

    def test_both_temperature_and_ram_returns_filename(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        history = {
            "2024/01/01-10:00": {"balance": 1.0, "temperature_avg": 50.0, "ram_percent": 70.0},
            "2024/01/01-11:00": {"balance": 2.0, "temperature_avg": 52.0, "ram_percent": 72.0},
        }
        result = create_resources_plot(history)
        assert result.endswith(RESOURCES_PLOT_FILE_NAME)
        assert (tmp_path / result).exists()

    def test_closes_figure_on_success(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_plt, fig, ax1, _ = _make_plt_mock()
        history = {"2024/01/01-10:00": {"temperature_avg": 50.0}}
        with patch('services.plotting.plt', mock_plt):
            create_resources_plot(history)
        mock_plt.close.assert_called_with(fig)


# ---------------------------------------------------------------------------
# create_balance_history_plot
# ---------------------------------------------------------------------------

class TestCreateBalanceHistoryPlot:
    def test_empty_dict_returns_empty_string(self):
        assert create_balance_history_plot({}) == ""

    def test_with_data_returns_filename(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        history = {
            "2024/01/01-10:00": {"balance": 100.0},
            "2024/01/01-11:00": {"balance": 105.0},
        }
        result = create_balance_history_plot(history)
        assert result.endswith(BALANCE_HISTORY_PLOT_FILE_NAME)
        assert (tmp_path / result).exists()

    def test_closes_figure_on_success(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_plt, fig, _, _ = _make_plt_mock()
        history = {"2024/01/01-10:00": {"balance": 50.0}}
        with patch('services.plotting.plt', mock_plt):
            create_balance_history_plot(history)
        mock_plt.close.assert_called_with(fig)

    def test_with_legacy_string_values(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        history = {
            "01/01-10:00": "Balance: 200.0",
            "01/01-11:00": "Balance: 210.0",
        }
        result = create_balance_history_plot(history)
        assert result.endswith(BALANCE_HISTORY_PLOT_FILE_NAME)
        assert (tmp_path / result).exists()
