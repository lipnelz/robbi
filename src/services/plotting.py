import matplotlib.pyplot as plt
from typing import List
from config import PNG_FILE_NAME


def create_png_plot(cycles: List[int], nok_counts: List[int], ok_counts: List[int]) -> str:
    """
    Creates a line plot with markers for OK and NOK counts over multiple cycles,
    and saves the plot as a PNG image.

    :param cycles: A list of integers representing the cycles.
    :param nok_counts: A list of integers representing the NOK counts for each cycle.
    :param ok_counts: A list of integers representing the OK counts for each cycle.
    :return: The file path of the generated PNG image.
    """
    plt.figure(figsize=(10, 6))
    plt.plot(cycles, nok_counts, marker='o', linestyle='-', color='red', label='NOK Counts')
    plt.plot(cycles, ok_counts, marker='o', linestyle='-', color='blue', label='OK Counts')
    plt.title('Validation per Cycle')
    plt.xlabel('Cycle')
    plt.ylabel('Count')
    plt.legend()
    plt.grid(True)
    plt.savefig(PNG_FILE_NAME)
    plt.close()
    return PNG_FILE_NAME


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
    balances = [float(balance.split(": ")[1]) for balance in balance_history.values()]

    # Create plot
    plt.figure(figsize=(12, 6))
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
    plt.close()
    return history_plot_name
