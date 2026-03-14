import os
import json
import logging
from typing import Optional
from datetime import datetime, timedelta


BALANCE_HISTORY_FILE = 'config/balance_history.json'


def make_time_key(dt: datetime = None) -> str:
    """Return a ``YYYY/MM/DD-HH:MM`` time key suitable for balance history.

    :param dt: Datetime to format; defaults to now.
    :return: Formatted time key string.
    """
    if dt is None:
        dt = datetime.now()
    return f"{dt.year}/{dt.month:02d}/{dt.day:02d}-{dt.hour:02d}:{dt.minute:02d}"


def build_balance_entry(balance: float, system_stats: dict) -> dict:
    """Build a balance history entry dict from a balance and system stats.

    Includes ``temperature_avg`` and ``ram_percent`` when they are present
    in *system_stats*.

    :param balance: Current node balance.
    :param system_stats: Dict returned by ``get_system_stats``.
    :return: Entry dict ready to store in balance history.
    """
    entry: dict = {"balance": balance}
    temperature_avg = system_stats.get("temperature_avg")
    ram_percent = system_stats.get("ram_percent")
    if temperature_avg is not None:
        entry["temperature_avg"] = temperature_avg
    if ram_percent is not None:
        entry["ram_percent"] = ram_percent
    return entry


def format_history_entry(time_key: str, value) -> str:
    """Format a single history entry as a human-readable string.

    :param time_key: Timestamp key (e.g. ``"2025/03/14-07:00"``).
    :param value: History entry value (str or dict).
    :return: Formatted string like ``"2025/03/14-07:00: Balance 1234.56, Temp 42.0°C, RAM 63.5%"``.
    """
    line = f"{time_key}: Balance {get_entry_balance(value):.2f}"
    temp = get_entry_temperature(value)
    ram = get_entry_ram(value)
    if temp is not None:
        line += f", Temp {temp:.1f}°C"
    if ram is not None:
        line += f", RAM {ram:.1f}%"
    return line


def get_entry_balance(value) -> float:
    """Extract the balance from a history entry.

    Supports both the legacy string format ("Balance: X.XX") and the new
    dict format ({"balance": X.XX, ...}).

    :param value: A history entry value (str or dict).
    :return: The balance as a float, or 0.0 on parse failure.
    """
    if isinstance(value, dict):
        return float(value.get("balance", 0.0))
    try:
        return float(str(value).split(": ")[1])
    except (IndexError, ValueError):
        return 0.0


def get_entry_temperature(value) -> Optional[float]:
    """Extract the average CPU temperature from a history entry.

    Only available in the new dict format.  Returns None for legacy string
    entries or when the sensor was unavailable at recording time.

    :param value: A history entry value (str or dict).
    :return: Temperature in °C as a float, or None.
    """
    if isinstance(value, dict):
        return value.get("temperature_avg")
    return None


def get_entry_ram(value) -> Optional[float]:
    """Extract the RAM usage percentage from a history entry.

    Only available in the new dict format.  Returns None for legacy string
    entries.

    :param value: A history entry value (str or dict).
    :return: RAM usage as a float percentage, or None.
    """
    if isinstance(value, dict):
        return value.get("ram_percent")
    return None


def load_balance_history() -> dict:
    """Load balance history from the JSON file on disk.
    Returns an empty dict if the file does not exist or is corrupted.
    """
    if os.path.exists(BALANCE_HISTORY_FILE):
        try:
            with open(BALANCE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Error loading balance history: {e}")
    return {}


def save_balance_history(balance_history: dict) -> None:
    """Persist the balance history dict to the JSON file.
    Creates the parent directory if it does not exist.
    """
    try:
        # Ensure the config/ directory exists (first run or fresh container)
        os.makedirs(os.path.dirname(BALANCE_HISTORY_FILE), exist_ok=True)
        with open(BALANCE_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(balance_history, f, indent=2)
    except IOError as e:
        logging.error(f"Error saving balance history: {e}")


def filter_since_midnight(history: dict) -> dict:
    """Filter balance history to keep only entries recorded today after midnight.
    Returns entries from the current day (00:00:00 onwards) in chronological order.
    Keys are in "YYYY/MM/DD-HH:MM" format (with year).
    Legacy keys in "DD/MM-HH:MM" format are also supported.
    """
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    current_year = now.year

    entries = []
    for key, value in history.items():
        try:
            dt = datetime.strptime(key, "%Y/%m/%d-%H:%M")
        except ValueError:
            try:
                dt = datetime.strptime(key, "%d/%m-%H:%M").replace(year=current_year)
                if dt > now + timedelta(hours=1):
                    dt = dt.replace(year=current_year - 1)
            except ValueError:
                continue
        if dt >= midnight:
            entries.append((dt, key, value))

    entries.sort(key=lambda x: x[0])

    filtered = {}
    for _, key, value in entries:
        filtered[key] = value
    return filtered


def filter_last_24h(history: dict) -> dict:
    """Filter balance history to keep only one entry per hour from the last 24 hours.
    For each hour, the latest recorded entry is kept.
    Returns at most 24 entries in chronological order.
    Keys are in "YYYY/MM/DD-HH:MM" format (with year).
    Legacy keys in "DD/MM-HH:MM" format are also supported.
    """
    now = datetime.now()
    cutoff = now - timedelta(hours=24)
    current_year = now.year

    # Collect all entries within the last 24 hours with their parsed datetime
    entries = []
    for key, value in history.items():
        try:
            # Try new format first: YYYY/MM/DD-HH:MM
            dt = datetime.strptime(key, "%Y/%m/%d-%H:%M")
        except ValueError:
            try:
                # Fallback to legacy format: DD/MM-HH:MM
                dt = datetime.strptime(key, "%d/%m-%H:%M").replace(year=current_year)
                if dt > now + timedelta(hours=1):
                    dt = dt.replace(year=current_year - 1)
            except ValueError:
                continue
        if dt >= cutoff:
            entries.append((dt, key, value))

    # Sort chronologically
    entries.sort(key=lambda x: x[0])

    # Keep only the latest entry for each hour
    hourly = {}
    for dt, key, value in entries:
        hour_key = (dt.year, dt.month, dt.day, dt.hour)
        hourly[hour_key] = (dt, key, value)

    # Build result dict in chronological order, keeping only the last 24 entries
    sorted_entries = sorted(hourly.values(), key=lambda x: x[0])[-24:]
    filtered = {}
    for _, key, value in sorted_entries:
        filtered[key] = value
    return filtered
