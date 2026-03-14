"""Tests for src/handlers/common.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.common import auth_required, handle_api_error
from config import TIMEOUT_NAME, TIMEOUT_FIRE_NAME


# ---------------------------------------------------------------------------
# auth_required decorator
# ---------------------------------------------------------------------------

class TestAuthRequired:
    async def test_allows_authorized_user(self, authorized_update_context):
        update, context = authorized_update_context

        called = []

        @auth_required
        async def dummy_handler(u, c):
            called.append(True)

        await dummy_handler(update, context)
        assert called == [True]

    async def test_blocks_unauthorized_user(self, unauthorized_update_context):
        update, context = unauthorized_update_context

        called = []

        @auth_required
        async def dummy_handler(u, c):
            called.append(True)

        await dummy_handler(update, context)
        assert called == []
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "not authorized" in text.lower()

    async def test_decorator_preserves_function_name(self):
        @auth_required
        async def my_handler(u, c):
            pass

        assert my_handler.__name__ == 'my_handler'


# ---------------------------------------------------------------------------
# handle_api_error
# ---------------------------------------------------------------------------

class TestHandleApiError:
    def _make_update(self):
        update = MagicMock()
        update.message = AsyncMock()
        update.message.reply_photo = AsyncMock()
        return update

    async def test_returns_false_when_no_error_key(self):
        update = self._make_update()
        result = await handle_api_error(update, {"price": "50000"})
        assert result is False
        update.message.reply_photo.assert_not_called()

    async def test_handles_timeout_error_sends_timeout_image(self):
        update = self._make_update()
        result = await handle_api_error(update, {"error": "Request timed out. The server took too long."})
        assert result is True
        update.message.reply_photo.assert_called_once()
        call_args = update.message.reply_photo.call_args
        assert TIMEOUT_NAME in call_args[1]['photo']

    async def test_handles_other_error_sends_fire_image(self):
        update = self._make_update()
        result = await handle_api_error(update, {"error": "Connection error. Unable to reach the server."})
        assert result is True
        update.message.reply_photo.assert_called_once()
        call_args = update.message.reply_photo.call_args
        assert TIMEOUT_FIRE_NAME in call_args[1]['photo']

    async def test_returns_true_for_any_error(self):
        update = self._make_update()
        result = await handle_api_error(update, {"error": "Some arbitrary error"})
        assert result is True
