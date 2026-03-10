import io
import sys
import json
import logging
import threading
import discord
from discord.ext import commands
from jrequests import get_addresses
from services.history import load_balance_history
from handlers.node import setup_node_commands
from handlers.price import setup_price_commands
from handlers.system import setup_system_commands
from handlers.scheduler import run_async_func


class RobbiBot(commands.Bot):
    """Discord bot with shared application state."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix='/', intents=intents)

        # Shared state — populated in main() before bot.run()
        self.allowed_user_ids: set = set()
        self.massa_node_address: str = ''
        self.ninja_key: str = ''
        self.balance_history: dict = {}
        self.balance_lock: threading.Lock = threading.Lock()
        self.docker_container_name: str = 'massa-container'
        self.massa_client_password: str = ''
        self.massa_wallet_address: str = ''
        self.massa_buy_rolls_fee: float = 0.01

    async def setup_hook(self) -> None:
        """Register slash commands and sync them with Discord after login."""
        setup_node_commands(self)
        setup_price_commands(self)
        setup_system_commands(self)
        await self.tree.sync()
        logging.info("Slash commands synced with Discord.")

    async def on_ready(self) -> None:
        logging.info(f"Bot {self.user} is ready and connected to Discord.")


def disable_prints() -> None:
    """Redirect stdout and stderr to suppress all print output."""
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()


def main():
    # Load bot configuration from topology.json
    try:
        with open('topology.json', 'r', encoding='utf-8') as file:
            config = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading topology.json: {e}")
        return

    # Extract credentials and settings from configuration
    bot_token = config.get('discord_bot_token')
    admin_id = config.get('user_white_list', {}).get('admin')
    if not bot_token or admin_id is None:
        logging.error("Missing required config: 'discord_bot_token' or 'user_white_list.admin'")
        return
    allowed_user_ids = {str(admin_id)}
    massa_node_address = config.get('massa_node_address')
    ninja_key = config.get('ninja_api_key')
    docker_container_name = config.get('docker_container_name', 'massa-container')
    massa_client_password = config.get('massa_client_password', '')
    massa_wallet_address = config.get('massa_wallet_address', '')
    massa_buy_rolls_fee = config.get('massa_buy_rolls_fee', 0.01)

    # Load persisted balance history from JSON file on disk
    balance_history = load_balance_history()

    disable_prints()  # Comment this line to enable prints (DEBUG purpose only)
    logging.info("Starting Discord bot...")

    # Perform an initial node health check at startup
    json_data = get_addresses(logging, massa_node_address)
    if "error" in json_data:
        error_message = json_data["error"]
        if "timed out" in error_message:
            logging.error("Timeout occurred while trying to get the status.")
        else:
            logging.error(f"Error while getting the status: {error_message}")

    # Build the Discord bot and populate shared state
    bot = RobbiBot()
    bot.allowed_user_ids = allowed_user_ids
    bot.massa_node_address = massa_node_address
    bot.ninja_key = ninja_key
    bot.balance_history = balance_history
    bot.docker_container_name = docker_container_name
    bot.massa_client_password = massa_client_password
    bot.massa_wallet_address = massa_wallet_address
    bot.massa_buy_rolls_fee = massa_buy_rolls_fee

    # Start the periodic scheduler (node ping every 60 min) and begin polling
    run_async_func(bot)
    bot.run(bot_token)

    logging.info("Bot stopped.")


if __name__ == '__main__':
    main()
