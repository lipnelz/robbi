import logging
import asyncio
from telegram import Update
from telegram.ext import CallbackContext
from services.price_api import get_bitcoin_price, get_mas_instant, get_mas_daily
from handlers.common import auth_required, handle_api_error
from config import BTC_CRY_NAME, MAS_CRY_NAME


@auth_required
async def btc(update: Update, context: CallbackContext) -> None:
    """Handle /btc command: fetch and display current Bitcoin price from API-Ninjas."""
    logging.info(f'User {update.effective_user.id} used the /btc command.')
    ninja_key = context.bot_data['ninja_key']

    try:
        # Fetch BTC price data from API-Ninjas
        data = get_bitcoin_price(logging, ninja_key)
        if await handle_api_error(update, data):
            return

        # Format price with 24h statistics
        formatted_string = (
            f"Price: {float(data['price']):.2f} $\n"
            f"24h Price Change: {float(data['24h_price_change']):.2f}\n"
            f"24h Price Change Percent: {float(data['24h_price_change_percent']):.2f}%\n"
            f"24h High: {float(data['24h_high']):.2f}\n"
            f"24h Low: {float(data['24h_low']):.2f}\n"
            f"24h Volume: {float(data['24h_volume']):.2f}"
        )
        await update.message.reply_text(formatted_string)
    except Exception as e:
        logging.error(f"Error when /btc : {e}")
        await update.message.reply_text("Nooooo")
        await update.message.reply_photo(photo=f'media/{BTC_CRY_NAME}')


@auth_required
async def mas(update: Update, context: CallbackContext) -> None:
    """Handle /mas command: fetch and display MAS/USDT price from MEXC."""
    logging.info(f'User {update.effective_user.id} used the /mas command.')

    try:
        # Fetch both instant price and 24h statistics from MEXC in parallel
        loop = asyncio.get_running_loop()
        current_avg_price, ticker_price_change_stats = await asyncio.gather(
            loop.run_in_executor(None, get_mas_instant, logging),
            loop.run_in_executor(None, get_mas_daily, logging),
        )

        # Check both responses for errors (bail on first error)
        for resp in (current_avg_price, ticker_price_change_stats):
            if await handle_api_error(update, resp):
                return

        # Format price with 24h statistics
        formatted_string = (
            f"{ticker_price_change_stats['symbol']}\n"
            f"-----------\n"
            f"Price: {float(current_avg_price['price']):.5f} USDT\n"
            f"24h Volume: {float(ticker_price_change_stats['volume']):.6f}\n"
            f"-----------\n"
            f"Price Change %: {float(ticker_price_change_stats['priceChangePercent']):.6f}%\n"
            f"Price Change: {float(ticker_price_change_stats['priceChange']):.6f}\n"
            f"24h High: {float(ticker_price_change_stats['highPrice']):.6f}\n"
            f"24h Low: {float(ticker_price_change_stats['lowPrice']):.6f}\n"
        )
        await update.message.reply_text(formatted_string)
    except Exception as e:
        logging.error(f"Error when /mas : {e}")
        await update.message.reply_text("Nooooo")
        await update.message.reply_photo(photo=f'media/{MAS_CRY_NAME}')
