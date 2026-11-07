"""Tests for persisted scheduled Massa node check results."""
import json
from datetime import datetime, timedelta

from services.node_status import load_node_status_history, record_node_status


def test_record_node_status_persists_check_and_prunes_old_entries(tmp_path, monkeypatch):
    history_file = tmp_path / 'config' / 'node_status_history.json'
    monkeypatch.setattr('services.node_status.NODE_STATUS_HISTORY_FILE', str(history_file))
    now = datetime(2026, 11, 7, 9, 0)
    history_file.parent.mkdir()
    history_file.write_text(json.dumps({
        (now - timedelta(days=8)).isoformat(): True,
        (now - timedelta(hours=1)).isoformat(): True,
    }), encoding='utf-8')

    record_node_status(False, now)

    assert load_node_status_history() == {
        (now - timedelta(hours=1)).isoformat(): True,
        now.isoformat(): False,
    }


def test_load_node_status_history_returns_empty_for_invalid_json(tmp_path, monkeypatch):
    history_file = tmp_path / 'node_status_history.json'
    history_file.write_text('{invalid', encoding='utf-8')
    monkeypatch.setattr('services.node_status.NODE_STATUS_HISTORY_FILE', str(history_file))

    assert load_node_status_history() == {}
