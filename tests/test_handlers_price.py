"""Tests for src/handlers/price.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.price import btc, mas


_BTC_DATA = {
    "price": "50000.00",
    "24h_price_change": "500.00",
    "24h_price_change_percent": "1.00",
    "24h_high": "51000.00",
    "24h_low": "49000.00",
    "24h_volume": "1000.00",
}

_MAS_INSTANT = {"price": "0.00500"}
_MAS_DAILY = {
    "symbol": "MASUSDT",
    "volume": "123456.789",
    "priceChangePercent": "0.500000",
    "priceChange": "0.000025",
    "highPrice": "0.005500",
    "lowPrice": "0.004500",
}


class TestBtcHandler:
    async def test_happy_path_sends_formatted_price(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.price.get_bitcoin_price', return_value=_BTC_DATA):
            await btc(update, context)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "50000.00" in text
        assert "24h" in text

    async def test_api_error_calls_handle_api_error(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.price.get_bitcoin_price', return_value={"error": "timed out"}):
            with patch('handlers.price.handle_api_error', new_callable=AsyncMock, return_value=True):
                await btc(update, context)
        update.message.reply_text.assert_not_called()

    async def test_exception_sends_error_messages(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.price.get_bitcoin_price', side_effect=Exception("crash")):
            await btc(update, context)
        # Should call reply_text with "Nooooo" and reply_photo with btc_cry image
        assert update.message.reply_text.called
        assert update.message.reply_photo.called

    async def test_unauthorized_user_blocked(self, unauthorized_update_context):
        update, context = unauthorized_update_context
        with patch('handlers.price.get_bitcoin_price') as mock_get:
            await btc(update, context)
        mock_get.assert_not_called()

    async def test_malformed_data_triggers_exception_handler(self, authorized_update_context):
        """If the response is missing keys, float() will fail → exception handler runs."""
        update, context = authorized_update_context
        with patch('handlers.price.get_bitcoin_price', return_value={"price": "not-a-float"}):
            await btc(update, context)
        # Exception path sends "Nooooo"
        texts = [call[0][0] for call in update.message.reply_text.call_args_list]
        assert any("Nooooo" in t for t in texts)


class TestMasHandler:
    async def test_happy_path_sends_formatted_string(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.price.get_mas_instant', return_value=_MAS_INSTANT):
            with patch('handlers.price.get_mas_daily', return_value=_MAS_DAILY):
                await mas(update, context)
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "MASUSDT" in text
        assert "0.00500" in text

    async def test_api_error_from_instant_price(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.price.get_mas_instant', return_value={"error": "timed out"}):
            with patch('handlers.price.get_mas_daily', return_value=_MAS_DAILY):
                with patch('handlers.price.handle_api_error', new_callable=AsyncMock, return_value=True) as mock_err:
                    await mas(update, context)
        mock_err.assert_called()

    async def test_api_error_from_daily_price(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.price.get_mas_instant', return_value=_MAS_INSTANT):
            with patch('handlers.price.get_mas_daily', return_value={"error": "connection error"}):
                with patch('handlers.price.handle_api_error', new_callable=AsyncMock, return_value=True) as mock_err:
                    await mas(update, context)
        mock_err.assert_called()

    async def test_exception_sends_error_and_photo(self, authorized_update_context):
        update, context = authorized_update_context
        with patch('handlers.price.get_mas_instant', side_effect=Exception("boom")):
            await mas(update, context)
        assert update.message.reply_text.called
        assert update.message.reply_photo.called

    async def test_unauthorized_user_blocked(self, unauthorized_update_context):
        update, context = unauthorized_update_context
        with patch('handlers.price.get_mas_instant') as mock_get:
            await mas(update, context)
        mock_get.assert_not_called()
