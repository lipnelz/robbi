import json
import logging
import os
from datetime import datetime, timedelta


NODE_STATUS_HISTORY_FILE = 'config/node_status_history.json'
NODE_STATUS_RETENTION = timedelta(days=7)


def load_node_status_history() -> dict[str, bool]:
    """Load persisted results of scheduled node checks."""
    if not os.path.exists(NODE_STATUS_HISTORY_FILE):
        return {}
    try:
        with open(NODE_STATUS_HISTORY_FILE, 'r', encoding='utf-8') as history_file:
            history = json.load(history_file)
        if not isinstance(history, dict):
            raise ValueError("Node status history must be a JSON object.")
        return {
            timestamp: is_up
            for timestamp, is_up in history.items()
            if isinstance(timestamp, str) and isinstance(is_up, bool)
        }
    except (json.JSONDecodeError, OSError, ValueError) as error:
        logging.error("Error loading node status history: %s", error)
        return {}


def record_node_status(is_up: bool, checked_at: datetime = None) -> None:
    """Persist one scheduled node check, retaining at most seven days."""
    checked_at = checked_at or datetime.now()
    if checked_at.tzinfo is not None:
        checked_at = checked_at.astimezone().replace(tzinfo=None)
    cutoff = checked_at - NODE_STATUS_RETENTION
    history = load_node_status_history()
    retained_history = {}
    for timestamp, was_up in history.items():
        try:
            recorded_at = datetime.fromisoformat(timestamp)
        except ValueError:
            continue
        if recorded_at.tzinfo is not None:
            recorded_at = recorded_at.astimezone().replace(tzinfo=None)
        if cutoff <= recorded_at <= checked_at:
            retained_history[timestamp] = was_up

    retained_history[checked_at.isoformat(timespec='seconds')] = bool(is_up)
    temporary_path = f'{NODE_STATUS_HISTORY_FILE}.tmp'
    try:
        os.makedirs(os.path.dirname(NODE_STATUS_HISTORY_FILE), exist_ok=True)
        with open(temporary_path, 'w', encoding='utf-8') as history_file:
            json.dump(retained_history, history_file, indent=2)
        os.replace(temporary_path, NODE_STATUS_HISTORY_FILE)
    except OSError as error:
        logging.error("Error saving node status history: %s", error)
        try:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
        except OSError as cleanup_error:
            logging.error("Error removing temporary node status history: %s", cleanup_error)
