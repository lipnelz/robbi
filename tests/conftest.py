"""Shared pytest fixtures for handler and integration tests."""
import threading
import pytest
from unittest.mock import AsyncMock, MagicMock

import matplotlib
matplotlib.use('Agg')  # non-interactive backend – must be set before any pyplot import


@pytest.fixture
def mock_update():
    update = MagicMock()
    update.effective_user.id = 123
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.bot_data = {
        'allowed_user_ids': {'123'},
        'massa_node_address': 'AU1some_address',
        'ninja_key': 'fake_key',
        'balance_history': {},
        'balance_lock': threading.Lock(),
    }
    return context


@pytest.fixture
def authorized_update_context(mock_update, mock_context):
    return mock_update, mock_context


@pytest.fixture
def unauthorized_update_context(mock_context):
    update = MagicMock()
    update.effective_user.id = 999  # not in allowed list
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    return update, mock_context
