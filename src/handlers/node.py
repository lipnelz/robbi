import os
import logging
import asyncio
from datetime import datetime
import discord
from discord.ext import commands
from jrequests import get_addresses, start_docker_node, stop_docker_node, exec_massa_client
from handlers.common import auth_required, handle_api_error
from services.history import save_balance_history
from services.plotting import create_png_plot, create_balance_history_plot
from config import (
    LOG_FILE_NAME,
    PAT_FILE_NAME,
)


def extract_address_data(json_data: dict):
    """
    Extract useful JSON response data from get_address.

    :param json_data: Input JSON data to parse.
    :return: Tuple composed of final_balance, final_roll_count, cycles, ok_counts, nok_counts and active_rolls.
    """
    if "result" in json_data and len(json_data["result"]) > 0:
        result = json_data["result"][0]
        final_balance = result["final_balance"]
        final_roll_count = result["final_roll_count"]
        cycles = [info["cycle"] for info in result["cycle_infos"]]
        ok_counts = [info["ok_count"] for info in result["cycle_infos"]]
        nok_counts = [info["nok_count"] for info in result["cycle_infos"]]
        active_rolls = [info["active_rolls"] for info in result["cycle_infos"]]
        return final_balance, final_roll_count, cycles, ok_counts, nok_counts, active_rolls
    return "", 0, [], [], [], []


# ---------------------------------------------------------------------------
# Docker flow Views
# ---------------------------------------------------------------------------

class DockerMenuView(discord.ui.View):
    """Initial docker management menu: Start / Stop / Massa Client."""

    def __init__(self, bot: commands.Bot, timeout: int = 120) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) in getattr(self.bot, 'allowed_user_ids', set())

    @discord.ui.button(label="▶️ Start", style=discord.ButtonStyle.green)
    async def docker_start(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        view = DockerStartConfirmView(self.bot)
        await interaction.response.edit_message(
            content="⚠️  Are you sure you want to start the node container?",
            view=view
        )

    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.red)
    async def docker_stop(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        view = DockerStopConfirmView(self.bot)
        await interaction.response.edit_message(
            content="⚠️  Are you sure you want to stop the node container?",
            view=view
        )

    @discord.ui.button(label="💻 Massa Client", style=discord.ButtonStyle.blurple)
    async def docker_massa(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        view = MassaMenuView(self.bot)
        await interaction.response.edit_message(
            content="💻 Massa Client\nChoose an action:",
            view=view
        )


class DockerStartConfirmView(discord.ui.View):
    """Confirmation dialog for starting the Docker container."""

    def __init__(self, bot: commands.Bot, timeout: int = 60) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) in getattr(self.bot, 'allowed_user_ids', set())

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.defer()
        container_name = self.bot.docker_container_name
        if not container_name:
            await interaction.edit_original_response(
                content="❌ Error: Docker container name not configured.", view=None
            )
            return
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, start_docker_node, logging, container_name)
        await interaction.edit_original_response(content=result['message'], view=None)
        logging.info(f"User {interaction.user.id} executed docker start: {result['status']}")

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Action cancelled.", view=None)


class DockerStopConfirmView(discord.ui.View):
    """Confirmation dialog for stopping the Docker container."""

    def __init__(self, bot: commands.Bot, timeout: int = 60) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) in getattr(self.bot, 'allowed_user_ids', set())

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.defer()
        container_name = self.bot.docker_container_name
        if not container_name:
            await interaction.edit_original_response(
                content="❌ Error: Docker container name not configured.", view=None
            )
            return
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, stop_docker_node, logging, container_name)
        await interaction.edit_original_response(content=result['message'], view=None)
        logging.info(f"User {interaction.user.id} executed docker stop: {result['status']}")

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Action cancelled.", view=None)


class MassaMenuView(discord.ui.View):
    """Massa Client sub-menu: Wallet Info / Buy Rolls / Sell Rolls / Back."""

    def __init__(self, bot: commands.Bot, timeout: int = 120) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) in getattr(self.bot, 'allowed_user_ids', set())

    @discord.ui.button(label="💰 Wallet Info", style=discord.ButtonStyle.blurple, row=0)
    async def wallet_info(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.defer()
        container_name = self.bot.docker_container_name
        password = self.bot.massa_client_password
        if not container_name or not password:
            await interaction.edit_original_response(
                content="❌ Error: Docker or Massa client not configured.", view=None
            )
            return
        await interaction.edit_original_response(content="⏳ Executing wallet_info...", view=None)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, exec_massa_client, logging, container_name, password, 'wallet_info'
        )
        if result['status'] == 'ok':
            output = result['output'] or 'No output returned.'
            await interaction.edit_original_response(content=f"💰 Wallet Info:\n\n{output}")
        else:
            await interaction.edit_original_response(content=result['message'])

    @discord.ui.button(label="🎲 Buy Rolls", style=discord.ButtonStyle.green, row=1)
    async def buy_rolls(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.send_modal(BuyRollsModal(self.bot))

    @discord.ui.button(label="💸 Sell Rolls", style=discord.ButtonStyle.red, row=1)
    async def sell_rolls(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.send_modal(SellRollsModal(self.bot))

    @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        view = DockerMenuView(self.bot)
        await interaction.response.edit_message(
            content="🐳 Docker Node Management\nWhat do you want to do?",
            view=view
        )


# ---------------------------------------------------------------------------
# Rolls Modals
# ---------------------------------------------------------------------------

class BuyRollsModal(discord.ui.Modal, title="Buy Rolls"):
    """Modal for the number of rolls to buy."""

    roll_count_input = discord.ui.TextInput(
        label="Number of rolls",
        placeholder="e.g. 1, 5, 10",
        min_length=1,
        max_length=10,
    )

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            count = int(self.roll_count_input.value.strip())
            if count <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid number. Please provide a positive integer.", ephemeral=True
            )
            return

        wallet_address = self.bot.massa_wallet_address or 'N/A'
        fee = self.bot.massa_buy_rolls_fee
        view = BuyRollsConfirmView(self.bot, count)
        await interaction.response.send_message(
            f"⚠️  Confirm buy_rolls:\n\n"
            f"Address: {wallet_address}\n"
            f"Rolls: {count}\n"
            f"Fee: {fee}\n\n"
            f"Proceed?",
            view=view
        )


class BuyRollsConfirmView(discord.ui.View):
    """Confirmation dialog for buying rolls."""

    def __init__(self, bot: commands.Bot, roll_count: int, timeout: int = 60) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.roll_count = roll_count

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) in getattr(self.bot, 'allowed_user_ids', set())

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.defer()
        container_name = self.bot.docker_container_name
        password = self.bot.massa_client_password
        wallet_address = self.bot.massa_wallet_address
        fee = self.bot.massa_buy_rolls_fee
        if not all([container_name, password, wallet_address]) or self.roll_count <= 0:
            await interaction.edit_original_response(
                content="❌ Error: Missing configuration or invalid roll count.", view=None
            )
            return
        command = f"buy_rolls {wallet_address} {self.roll_count} {fee}"
        await interaction.edit_original_response(
            content=f"⏳ Executing buy_rolls ({self.roll_count} rolls)...", view=None
        )
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, exec_massa_client, logging, container_name, password, command
        )
        if result['status'] == 'ok':
            output = result['output'] or 'Command executed (no output).'
            await interaction.edit_original_response(content=f"✅ buy_rolls executed:\n\n{output}")
            logging.info(f"User {interaction.user.id} bought {self.roll_count} rolls.")
        else:
            await interaction.edit_original_response(content=result['message'])

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Action cancelled.", view=None)


class SellRollsModal(discord.ui.Modal, title="Sell Rolls"):
    """Modal for the number of rolls to sell."""

    roll_count_input = discord.ui.TextInput(
        label="Number of rolls",
        placeholder="e.g. 1, 5, 10",
        min_length=1,
        max_length=10,
    )

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            count = int(self.roll_count_input.value.strip())
            if count <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid number. Please provide a positive integer.", ephemeral=True
            )
            return

        wallet_address = self.bot.massa_wallet_address or 'N/A'
        fee = self.bot.massa_buy_rolls_fee
        view = SellRollsConfirmView(self.bot, count)
        await interaction.response.send_message(
            f"⚠️  Confirm sell_rolls:\n\n"
            f"Address: {wallet_address}\n"
            f"Rolls: {count}\n"
            f"Fee: {fee}\n\n"
            f"Proceed?",
            view=view
        )


class SellRollsConfirmView(discord.ui.View):
    """Confirmation dialog for selling rolls."""

    def __init__(self, bot: commands.Bot, roll_count: int, timeout: int = 60) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.roll_count = roll_count

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) in getattr(self.bot, 'allowed_user_ids', set())

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.defer()
        container_name = self.bot.docker_container_name
        password = self.bot.massa_client_password
        wallet_address = self.bot.massa_wallet_address
        fee = self.bot.massa_buy_rolls_fee
        if not all([container_name, password, wallet_address]) or self.roll_count <= 0:
            await interaction.edit_original_response(
                content="❌ Error: Missing configuration or invalid roll count.", view=None
            )
            return
        command = f"sell_rolls {wallet_address} {self.roll_count} {fee}"
        await interaction.edit_original_response(
            content=f"⏳ Executing sell_rolls ({self.roll_count} rolls)...", view=None
        )
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, exec_massa_client, logging, container_name, password, command
        )
        if result['status'] == 'ok':
            output = result['output'] or 'Command executed (no output).'
            await interaction.edit_original_response(content=f"✅ sell_rolls executed:\n\n{output}")
            logging.info(f"User {interaction.user.id} sold {self.roll_count} rolls.")
        else:
            await interaction.edit_original_response(content=result['message'])

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Action cancelled.", view=None)


# ---------------------------------------------------------------------------
# Flush Views
# ---------------------------------------------------------------------------

class FlushView(discord.ui.View):
    """Confirmation dialog for /flush: clear both logs and balance history, or logs only."""

    def __init__(self, bot: commands.Bot, timeout: int = 60) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) in getattr(self.bot, 'allowed_user_ids', set())

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def flush_yes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Clear both the log file and balance history."""
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        try:
            with open(LOG_FILE_NAME, 'w'):
                pass
            with self.bot.balance_lock:
                self.bot.balance_history.clear()
                save_balance_history(self.bot.balance_history)
            message = "✓ Log file and balance history have been cleared."
            logging.info(message)
            await interaction.response.edit_message(content=message, view=None)
        except IOError as e:
            logging.error(f"Error clearing the log file: {e}")
            await interaction.response.edit_message(
                content="An error occurred while clearing the log file.", view=None
            )

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def flush_no(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Clear only the log file, keeping balance history."""
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        try:
            with open(LOG_FILE_NAME, 'w'):
                pass
            message = "✓ Log file has been cleared (balance history preserved)."
            logging.info(message)
            await interaction.response.edit_message(content=message, view=None)
        except IOError as e:
            logging.error(f"Error clearing the log file: {e}")
            await interaction.response.edit_message(
                content="An error occurred while clearing the log file.", view=None
            )


# ---------------------------------------------------------------------------
# Hist View
# ---------------------------------------------------------------------------

class HistView(discord.ui.View):
    """Ask whether the user also wants balance history as plain text."""

    def __init__(self, bot: commands.Bot, timeout: int = 60) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) in getattr(self.bot, 'allowed_user_ids', set())

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def hist_yes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Send the full balance history as a text message."""
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        balance_history = self.bot.balance_history
        if not balance_history:
            await interaction.response.edit_message(
                content="Balance history is empty.", view=None
            )
            return
        tmp_string = "History\n" + "\n".join(
            f"{time_key}: {balance}" for time_key, balance in balance_history.items()
        )
        await interaction.response.edit_message(content="✓ Sending balance history...", view=None)
        await interaction.followup.send(tmp_string)
        logging.info(f"Sent balance history to user {interaction.user.id}")

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def hist_no(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Dismiss without sending text history."""
        if not self._is_authorized(interaction):
            await interaction.response.send_message("Access denied.", ephemeral=True)
            return
        await interaction.response.edit_message(content="✓ Done.", view=None)


# ---------------------------------------------------------------------------
# Command registration
# ---------------------------------------------------------------------------

def setup_node_commands(bot: commands.Bot) -> None:
    """Register /node, /flush, /hist and /docker slash commands on the bot's application command tree."""

    @bot.tree.command(name='node', description='Get node results')
    @auth_required
    async def node(interaction: discord.Interaction) -> None:
        """Handle /node command: fetch Massa node status, send stats and validation chart."""
        logging.info(f'User {interaction.user.id} used the /node command.')
        await interaction.response.defer()
        balance_history = interaction.client.balance_history
        massa_node_address = interaction.client.massa_node_address

        image_path = None
        try:
            loop = asyncio.get_running_loop()
            json_data = await loop.run_in_executor(None, get_addresses, logging, massa_node_address)
            if await handle_api_error(interaction, json_data):
                return

            data = extract_address_data(json_data)
            if not data or len(data) < 6:
                logging.error("Node unreachable or no data available")
                await interaction.followup.send("Node unreachable or no data available.")
                return

            formatted_string = (
                f"Final Balance: {data[0]}\n"
                f"Final Roll Count: {data[1]}\n"
                f"OK Counts: {data[3]}\n"
                f"NOK Counts: {data[4]}\n"
                f"Active Rolls: {data[5]}"
            )
            await interaction.followup.send('Node status: ' + formatted_string)

            now = datetime.now()
            time_key = f"{now.year}/{now.month:02d}/{now.day:02d}-{now.hour:02d}:{now.minute:02d}"
            lock = interaction.client.balance_lock
            with lock:
                balance_history[time_key] = f"Balance: {float(data[0]):.2f}"
                save_balance_history(balance_history)

            image_path = create_png_plot(data[2], data[4], data[3])
            if image_path and os.path.exists(image_path):
                try:
                    await interaction.followup.send(file=discord.File(image_path))
                except (FileNotFoundError, OSError) as e:
                    logging.error(f"Error while send image : {e}")
                    await interaction.followup.send("Error while send image.")
            else:
                logging.error("Image file was not created successfully.")
                await interaction.followup.send("Image file was not created successfully.")
        except Exception as e:
            logging.error(f"Error in /node : {e}")
            await interaction.followup.send("Arf !")
            await interaction.followup.send(file=discord.File(f'media/{PAT_FILE_NAME}'))
        finally:
            if image_path:
                try:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        logging.info(f"{image_path} has been deleted.")
                except Exception as e:
                    logging.error(f"Error deleting image file {image_path}: {e}")

    @bot.tree.command(name='flush', description='Flush local logs')
    @auth_required
    async def flush(interaction: discord.Interaction) -> None:
        """Handle /flush command: ask for confirmation before clearing logs."""
        user_id = str(interaction.user.id)
        logging.info(f'User {user_id} used the /flush command.')

        if not os.path.exists(LOG_FILE_NAME):
            logging.warning(f"Log file {LOG_FILE_NAME} does not exist.")
            await interaction.response.send_message(
                f"Log file {LOG_FILE_NAME} does not exist.", ephemeral=True
            )
            return

        view = FlushView(interaction.client)
        await interaction.response.send_message(
            "Do you want to clear the balance history as well?\n"
            "Yes: Clear both logs and balance history\n"
            "No: Clear only the log file",
            view=view
        )

    @bot.tree.command(name='hist', description='Get node balance history')
    @auth_required
    async def hist(interaction: discord.Interaction) -> None:
        """Handle /hist command: send balance history chart, then ask for text summary."""
        user_id = str(interaction.user.id)
        logging.info(f'User {user_id} used the /hist command.')
        await interaction.response.defer()
        balance_history = interaction.client.balance_history

        if not balance_history:
            await interaction.followup.send("No balance history available.")
            return

        image_path = None
        try:
            try:
                image_path = create_balance_history_plot(balance_history)
            except Exception as e:
                logging.error(f"Error creating balance history plot: {e}")
                await interaction.followup.send("Error creating history graph.")
                return

            if not image_path or not os.path.exists(image_path):
                logging.error("History image file was not created successfully.")
                await interaction.followup.send("Error creating history image.")
                return

            try:
                await interaction.followup.send(file=discord.File(image_path))
            except (FileNotFoundError, OSError) as e:
                logging.error(f"Error while sending history image : {e}")
                await interaction.followup.send("Error while sending history image.")
                return

            view = HistView(interaction.client)
            await interaction.followup.send(
                "Do you also want to receive the balance history as text?",
                view=view
            )
        except Exception as error:
            logging.error(f"Error in /hist command: {error}")
            await interaction.followup.send("Error retrieving balance history.")
        finally:
            if image_path:
                try:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        logging.info(f"{image_path} has been deleted.")
                except Exception as e:
                    logging.error(f"Error deleting image file {image_path}: {e}")

    @bot.tree.command(name='docker', description='Manage Docker node container (start/stop)')
    @auth_required
    async def docker(interaction: discord.Interaction) -> None:
        """Handle /docker command: show menu with Start/Stop/Massa Client options."""
        user_id = str(interaction.user.id)
        logging.info(f'User {user_id} used the /docker command.')
        view = DockerMenuView(interaction.client)
        await interaction.response.send_message(
            "🐳 Docker Node Management\nWhat do you want to do?",
            view=view
        )

