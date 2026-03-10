import logging
import asyncio
import discord
from discord.ext import commands
from jrequests import get_bitcoin_price, get_mas_instant, get_mas_daily
from handlers.common import auth_required, handle_api_error
from config import BTC_CRY_NAME, MAS_CRY_NAME


def setup_price_commands(bot: commands.Bot) -> None:
    """Register /btc and /mas slash commands on the bot's application command tree."""

    @bot.tree.command(name='btc', description='Get BTC current price')
    @auth_required
    async def btc(interaction: discord.Interaction) -> None:
        """Handle /btc command: fetch and display current Bitcoin price from API-Ninjas."""
        logging.info(f'User {interaction.user.id} used the /btc command.')
        await interaction.response.defer()
        ninja_key = interaction.client.ninja_key

        try:
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, get_bitcoin_price, logging, ninja_key)
            if await handle_api_error(interaction, data):
                return

            formatted_string = (
                f"Price: {float(data['price']):.2f} $\n"
                f"24h Price Change: {float(data['24h_price_change']):.2f}\n"
                f"24h Price Change Percent: {float(data['24h_price_change_percent']):.2f}%\n"
                f"24h High: {float(data['24h_high']):.2f}\n"
                f"24h Low: {float(data['24h_low']):.2f}\n"
                f"24h Volume: {float(data['24h_volume']):.2f}"
            )
            await interaction.followup.send(formatted_string)
        except Exception as e:
            logging.error(f"Error when /btc : {e}")
            await interaction.followup.send("Nooooo")
            await interaction.followup.send(file=discord.File(f'media/{BTC_CRY_NAME}'))

    @bot.tree.command(name='mas', description='Get MAS current price')
    @auth_required
    async def mas(interaction: discord.Interaction) -> None:
        """Handle /mas command: fetch and display MAS/USDT price from MEXC."""
        logging.info(f'User {interaction.user.id} used the /mas command.')
        await interaction.response.defer()

        try:
            loop = asyncio.get_running_loop()
            current_avg_price, ticker_price_change_stats = await asyncio.gather(
                loop.run_in_executor(None, get_mas_instant, logging),
                loop.run_in_executor(None, get_mas_daily, logging),
            )

            for resp in (current_avg_price, ticker_price_change_stats):
                if await handle_api_error(interaction, resp):
                    return

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
            await interaction.followup.send(formatted_string)
        except Exception as e:
            logging.error(f"Error when /mas : {e}")
            await interaction.followup.send("Nooooo")
            await interaction.followup.send(file=discord.File(f'media/{MAS_CRY_NAME}'))
