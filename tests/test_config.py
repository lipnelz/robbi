"""Tests for src/config.py – type and value assertions for every constant."""
import config


def test_scheduler_constant():
    assert isinstance(config.JOB_SCHED_NAME, str)
    assert config.JOB_SCHED_NAME == 'periodic_node_ping'


def test_log_file_name():
    assert isinstance(config.LOG_FILE_NAME, str)
    assert config.LOG_FILE_NAME == 'bot_activity.log'


def test_conversation_state_integers():
    states = [
        config.FLUSH_CONFIRM_STATE,
        config.HIST_CONFIRM_STATE,
        config.DOCKER_MENU_STATE,
        config.DOCKER_START_CONFIRM_STATE,
        config.DOCKER_STOP_CONFIRM_STATE,
        config.DOCKER_MASSA_MENU_STATE,
        config.DOCKER_BUYROLLS_INPUT_STATE,
        config.DOCKER_BUYROLLS_CONFIRM_STATE,
        config.DOCKER_SELLROLLS_INPUT_STATE,
        config.DOCKER_SELLROLLS_CONFIRM_STATE,
        config.DOCKER_UPDATE_CONFIRM_STATE,
    ]
    for s in states:
        assert isinstance(s, int), f"Expected int, got {type(s)} for state {s}"
    # Values must be distinct
    assert len(set(states)) == len(states)


def test_conversation_state_values():
    assert config.FLUSH_CONFIRM_STATE == 1
    assert config.HIST_CONFIRM_STATE == 2
    assert config.DOCKER_MENU_STATE == 3
    assert config.DOCKER_START_CONFIRM_STATE == 4
    assert config.DOCKER_STOP_CONFIRM_STATE == 5
    assert config.DOCKER_MASSA_MENU_STATE == 6
    assert config.DOCKER_BUYROLLS_INPUT_STATE == 7
    assert config.DOCKER_BUYROLLS_CONFIRM_STATE == 8
    assert config.DOCKER_SELLROLLS_INPUT_STATE == 9
    assert config.DOCKER_SELLROLLS_CONFIRM_STATE == 10
    assert config.DOCKER_UPDATE_CONFIRM_STATE == 11


def test_media_file_names():
    media_constants = [
        config.BUDDY_FILE_NAME,
        config.PAT_FILE_NAME,
        config.BTC_CRY_NAME,
        config.MAS_CRY_NAME,
        config.TIMEOUT_NAME,
        config.TIMEOUT_FIRE_NAME,
    ]
    for name in media_constants:
        assert isinstance(name, str)
        assert len(name) > 0


def test_node_status_messages():
    assert isinstance(config.NODE_IS_DOWN, str)
    assert isinstance(config.NODE_IS_UP, str)
    assert 'down' in config.NODE_IS_DOWN.lower()
    assert 'up' in config.NODE_IS_UP.lower()


def test_commands_list_structure():
    assert isinstance(config.COMMANDS_LIST, list)
    assert len(config.COMMANDS_LIST) > 0
    for cmd in config.COMMANDS_LIST:
        assert isinstance(cmd, dict)
        assert 'id' in cmd
        assert 'cmd_txt' in cmd
        assert 'cmd_desc' in cmd
        assert isinstance(cmd['id'], int)
        assert isinstance(cmd['cmd_txt'], str)
        assert isinstance(cmd['cmd_desc'], str)


def test_commands_list_has_expected_commands():
    cmd_texts = {c['cmd_txt'] for c in config.COMMANDS_LIST}
    expected = {'hi', 'node', 'btc', 'mas', 'hist', 'flush', 'temperature', 'perf', 'docker'}
    assert expected.issubset(cmd_texts)
