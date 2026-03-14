"""Tests for the new factorized helpers in handlers/common.py.

Covers:
    - cb_auth_required  (authorized + unauthorized paths)
    - safe_delete_file  (existing file, missing file, None/empty path)
    - auth_required     (authorized + unauthorized paths)
    - handle_api_error  (no error, generic error, timeout error)
"""
import sys
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure src/ is on the path so imports work without installation
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from handlers.common import cb_auth_required, safe_delete_file, auth_required, handle_api_error
from telegram.ext import ConversationHandler


# ---------------------------------------------------------------------------
# Helpers to build minimal Telegram mock objects
# ---------------------------------------------------------------------------

def _make_context(allowed_user_ids=None):
    """Build a minimal CallbackContext mock."""
    ctx = MagicMock()
    ctx.bot_data = {"allowed_user_ids": allowed_user_ids or set()}
    return ctx


def _make_message_update(user_id: str):
    """Build a minimal Update mock for message-based handlers."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    return update


def _make_callback_update(user_id: str):
    """Build a minimal Update mock for callback query handlers."""
    update = MagicMock()
    update.callback_query.from_user.id = user_id
    update.callback_query.answer = AsyncMock()
    return update


# ---------------------------------------------------------------------------
# cb_auth_required
# ---------------------------------------------------------------------------

class TestCbAuthRequired:
    @pytest.mark.asyncio
    async def test_allows_authorized_user(self):
        allowed = {"42"}
        ctx = _make_context(allowed)
        update = _make_callback_update("42")

        @cb_auth_required
        async def handler(update, context):
            return "ok"

        result = await handler(update, ctx)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_blocks_unauthorized_user(self):
        ctx = _make_context({"99"})  # user 42 is NOT in the list
        update = _make_callback_update("42")

        @cb_auth_required
        async def handler(update, context):
            return "ok"

        result = await handler(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_unauthorized_calls_query_answer(self):
        ctx = _make_context(set())
        update = _make_callback_update("42")

        @cb_auth_required
        async def handler(update, context):
            return "ok"

        await handler(update, ctx)
        update.callback_query.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_allowlist_blocks_all(self):
        ctx = _make_context(set())
        update = _make_callback_update("1")

        @cb_auth_required
        async def handler(update, context):
            return "reached"

        result = await handler(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        @cb_auth_required
        async def my_handler(update, context):
            pass

        assert my_handler.__name__ == "my_handler"

    @pytest.mark.asyncio
    async def test_authorized_user_receives_context_args(self):
        """Authorized handler should receive update and context unmodified."""
        ctx = _make_context({"5"})
        update = _make_callback_update("5")
        received = {}

        @cb_auth_required
        async def handler(update, context):
            received["update"] = update
            received["context"] = context

        await handler(update, ctx)
        assert received["update"] is update
        assert received["context"] is ctx


# ---------------------------------------------------------------------------
# auth_required
# ---------------------------------------------------------------------------

class TestAuthRequired:
    @pytest.mark.asyncio
    async def test_allows_authorized_user(self):
        ctx = _make_context({"7"})
        update = _make_message_update("7")

        @auth_required
        async def handler(update, context):
            return "ok"

        result = await handler(update, ctx)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_blocks_unauthorized_user(self):
        ctx = _make_context({"99"})
        update = _make_message_update("1")

        @auth_required
        async def handler(update, context):
            return "reached"

        result = await handler(update, ctx)
        assert result is None  # auth_required returns None on denial

    @pytest.mark.asyncio
    async def test_unauthorized_replies_with_message(self):
        ctx = _make_context(set())
        update = _make_message_update("1")

        @auth_required
        async def handler(update, context):
            pass

        await handler(update, ctx)
        update.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        @auth_required
        async def my_cmd(update, context):
            pass

        assert my_cmd.__name__ == "my_cmd"


# ---------------------------------------------------------------------------
# safe_delete_file
# ---------------------------------------------------------------------------

class TestSafeDeleteFile:
    def test_deletes_existing_file(self, tmp_path):
        f = tmp_path / "chart.png"
        f.write_bytes(b"data")
        safe_delete_file(str(f))
        assert not f.exists()

    def test_does_not_raise_for_missing_file(self):
        safe_delete_file("/tmp/nonexistent_robbi_test_xyz.png")  # must not raise

    def test_does_not_raise_for_none(self):
        safe_delete_file(None)  # must not raise

    def test_does_not_raise_for_empty_string(self):
        safe_delete_file("")  # must not raise

    def test_logs_deletion(self, tmp_path, caplog):
        import logging
        f = tmp_path / "tmp.png"
        f.write_bytes(b"x")
        with caplog.at_level(logging.INFO):
            safe_delete_file(str(f))
        assert any("deleted" in record.message.lower() for record in caplog.records)

    def test_no_error_logged_for_missing_file(self, caplog):
        import logging
        with caplog.at_level(logging.ERROR):
            safe_delete_file("/tmp/totally_absent_robbi_xyz.png")
        assert not caplog.records


# ---------------------------------------------------------------------------
# handle_api_error
# ---------------------------------------------------------------------------

class TestHandleApiError:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_error(self):
        update = _make_message_update("1")
        update.message.reply_photo = AsyncMock()
        result = await handle_api_error(update, {"result": [{"balance": "100"}]})
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_on_generic_error(self):
        update = _make_message_update("1")
        update.message.reply_photo = AsyncMock()
        result = await handle_api_error(update, {"error": "Some API error"})
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_on_timeout_error(self):
        update = _make_message_update("1")
        update.message.reply_photo = AsyncMock()
        result = await handle_api_error(update, {"error": "Request timed out"})
        assert result is True

    @pytest.mark.asyncio
    async def test_sends_photo_on_generic_error(self):
        update = _make_message_update("1")
        update.message.reply_photo = AsyncMock()
        await handle_api_error(update, {"error": "Connection refused"})
        update.message.reply_photo.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sends_photo_on_timeout_error(self):
        update = _make_message_update("1")
        update.message.reply_photo = AsyncMock()
        await handle_api_error(update, {"error": "timed out"})
        update.message.reply_photo.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_dict_returns_false(self):
        update = _make_message_update("1")
        update.message.reply_photo = AsyncMock()
        result = await handle_api_error(update, {})
        assert result is False
