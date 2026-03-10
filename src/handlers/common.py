import logging
import functools
import discord
from config import TIMEOUT_NAME, TIMEOUT_FIRE_NAME


def auth_required(func):
    """Decorator to restrict slash command handler access to allowed users only.
    Reads the whitelist from interaction.client.allowed_user_ids.
    """
    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        user_id = str(interaction.user.id)
        bot = interaction.client
        allowed_user_ids = getattr(bot, 'allowed_user_ids', set())
        if user_id not in allowed_user_ids:
            await interaction.response.send_message(
                "You are not authorized to use this bot.", ephemeral=True
            )
            return
        return await func(interaction, *args, **kwargs)
    return wrapper


async def handle_api_error(interaction: discord.Interaction, error_data: dict) -> bool:
    """Handle API error responses uniformly.
    Sends an appropriate error file depending on error type.
    Returns True if an error was handled, False otherwise.
    Assumes the interaction response has already been deferred (uses followup).
    """
    if "error" not in error_data:
        return False
    error_message = error_data["error"]
    if "timed out" in error_message:
        logging.error("Timeout occurred while trying to get the status.")
        await interaction.followup.send(file=discord.File(f'media/{TIMEOUT_NAME}'))
    else:
        logging.error(f"Error while getting the status: {error_message}")
        await interaction.followup.send(file=discord.File(f'media/{TIMEOUT_FIRE_NAME}'))
    return True
