import math
import matplotlib.pyplot as plt
from typing import List

from services.history import get_entry_balance, get_entry_temperature, get_entry_ram


PNG_FILE_NAME = 'plot.png'
RESOURCES_PLOT_FILE_NAME = 'resources_history.png'


def create_png_plot(cycles: List[int], nok_counts: List[int], ok_counts: List[int]) -> str:
    """
    Creates a line plot with markers for OK and NOK counts over multiple cycles,
    and saves the plot as a PNG image.

    :param cycles: A list of integers representing the cycles.
    :param nok_counts: A list of integers representing the NOK counts for each cycle.
    :param ok_counts: A list of integers representing the OK counts for each cycle.
    :return: The file path of the generated PNG image.
    """
    fig = plt.figure(figsize=(10, 6))
    try:
        plt.plot(cycles, nok_counts, marker='o', linestyle='-', color='red', label='NOK Counts')
        plt.plot(cycles, ok_counts, marker='o', linestyle='-', color='blue', label='OK Counts')
        plt.title('Validation per Cycle')
        plt.xlabel('Cycle')
        plt.ylabel('Count')
        plt.legend()
        plt.grid(True)
        plt.savefig(PNG_FILE_NAME)
    finally:
        plt.close(fig)
    return PNG_FILE_NAME


def create_resources_plot(resource_history: dict) -> str:
    """
    Creates a two-panel line plot showing CPU temperature (°C) and RAM usage (%)
    over time from history entries, and saves it as a PNG image.

    Only entries that carry resource data (new dict format) are plotted.
    Returns an empty string when no resource data is available.

    :param resource_history: Dict with time keys and entry values (dict or str).
    :return: The file path of the generated PNG image, or empty string if no data.
    """
    if not resource_history:
        return ""

    timestamps = list(resource_history.keys())
    temperatures = [get_entry_temperature(v) for v in resource_history.values()]
    ram_percents = [get_entry_ram(v) for v in resource_history.values()]

    has_temperature = any(t is not None for t in temperatures)
    has_ram = any(r is not None for r in ram_percents)

    if not has_temperature and not has_ram:
        return ""

    # Replace None with NaN so matplotlib skips missing data points
    temp_values = [t if t is not None else math.nan for t in temperatures]
    ram_values = [r if r is not None else math.nan for r in ram_percents]

    n_panels = sum([has_temperature, has_ram])
    fig, axes = plt.subplots(n_panels, 1, figsize=(12, 4 * n_panels))
    if n_panels == 1:
        axes = [axes]

    try:
        idx = 0
        x = range(len(timestamps))

        if has_temperature:
            axes[idx].plot(
                x, temp_values, marker='o', linestyle='-',
                color='orange', linewidth=2, markersize=6, label='Temperature (°C)',
            )
            axes[idx].set_title('CPU Temperature Over Time')
            axes[idx].set_xlabel('Time')
            axes[idx].set_ylabel('Temperature (°C)')
            axes[idx].set_xticks(list(x))
            axes[idx].set_xticklabels(timestamps, rotation=45, ha='right')
            axes[idx].legend()
            axes[idx].grid(True, alpha=0.3)
            idx += 1

        if has_ram:
            axes[idx].plot(
                x, ram_values, marker='o', linestyle='-',
                color='purple', linewidth=2, markersize=6, label='RAM Usage (%)',
            )
            axes[idx].set_title('RAM Usage Over Time')
            axes[idx].set_xlabel('Time')
            axes[idx].set_ylabel('RAM (%)')
            axes[idx].set_xticks(list(x))
            axes[idx].set_xticklabels(timestamps, rotation=45, ha='right')
            axes[idx].legend()
            axes[idx].grid(True, alpha=0.3)

        plt.tight_layout()
        resources_plot_name = RESOURCES_PLOT_FILE_NAME
        plt.savefig(resources_plot_name)
    finally:
        plt.close(fig)

    return resources_plot_name


def create_balance_history_plot(balance_history: dict) -> str:
    """
    Creates a line plot of balance history over time and saves it as a PNG image.

    :param balance_history: Dict with time keys and balance string values.
    :return: The file path of the generated PNG image, or empty string if no data.
    """
    if not balance_history:
        return ""

    # Extract timestamps and balance values
    timestamps = list(balance_history.keys())
    balances = [get_entry_balance(v) for v in balance_history.values()]

    # Create plot
    fig = plt.figure(figsize=(12, 6))
    try:
        plt.plot(range(len(timestamps)), balances, marker='o', linestyle='-',
                 color='green', linewidth=2, markersize=8, label='Balance')
        plt.title('Balance History Over Time')
        plt.xlabel('Time')
        plt.ylabel('Balance')
        plt.xticks(range(len(timestamps)), timestamps, rotation=45, ha='right')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        # Save plot
        history_plot_name = 'balance_history.png'
        plt.savefig(history_plot_name)
    finally:
        plt.close(fig)
    return history_plot_name
