import logging
import functools
from telegram import Update
from telegram.ext import CallbackContext
from config import TIMEOUT_NAME, TIMEOUT_FIRE_NAME


def auth_required(func):
    """Decorator to restrict handler access to allowed users only.
    Reads the whitelist from context.bot_data['allowed_user_ids'].
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = str(update.effective_user.id)
        allowed_user_ids = context.bot_data.get('allowed_user_ids', set())
        # Reject unauthorized users before reaching the handler
        if user_id not in allowed_user_ids:
            await update.message.reply_text("You are not authorized to use this bot.")
            return
        # User is authorized, proceed to the actual handler
        return await func(update, context, *args, **kwargs)
    return wrapper


async def handle_api_error(update: Update, error_data: dict) -> bool:
    """Handle API error responses uniformly.
    Sends an appropriate error photo depending on error type.
    Returns True if an error was handled, False otherwise.
    """
    if "error" not in error_data:
        return False
    error_message = error_data["error"]
    # Send a timeout-specific or generic error image
    if "timed out" in error_message:
        logging.error("Timeout occurred while trying to get the status.")
        await update.message.reply_photo(photo=f'media/{TIMEOUT_NAME}')
    else:
        logging.error(f"Error while getting the status: {error_message}")
        await update.message.reply_photo(photo=f'media/{TIMEOUT_FIRE_NAME}')
    return True
