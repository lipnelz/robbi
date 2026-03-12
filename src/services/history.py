import os
import json
import logging
from datetime import datetime, timedelta


BALANCE_HISTORY_FILE = 'config/balance_history.json'


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
