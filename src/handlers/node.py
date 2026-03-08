import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from jrequests import get_addresses
from handlers.common import auth_required, handle_api_error
from services.history import save_balance_history
from services.plotting import create_png_plot, create_balance_history_plot
from config import (
    LOG_FILE_NAME, FLUSH_CONFIRM_STATE, HIST_CONFIRM_STATE,
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


@auth_required
async def node(update: Update, context: CallbackContext) -> None:
    """Handle /node command: fetch Massa node status, send stats and validation chart."""
    logging.info(f'User {update.effective_user.id} used the /node command.')
    balance_history = context.bot_data['balance_history']
    massa_node_address = context.bot_data['massa_node_address']

    image_path = None
    try:
        # Fetch node data via JSON-RPC
        json_data = get_addresses(logging, massa_node_address)
        if await handle_api_error(update, json_data):
            return

        # Parse the response into individual fields
        data = extract_address_data(json_data)
        if not data or len(data) < 6:
            logging.error("Node unreachable or no data available")
            await update.message.reply_text("Node unreachable or no data available.")
            return

        # Send a text summary of the node status
        formatted_string = (
            f"Final Balance: {data[0]}\n"
            f"Final Roll Count: {data[1]}\n"
            f"OK Counts: {data[3]}\n"
            f"NOK Counts: {data[4]}\n"
            f"Active Rolls: {data[5]}"
        )
        await update.message.reply_text('Node status: ' + formatted_string)

        # Record current balance snapshot with timestamp
        now = datetime.now()
        time_key = f"{now.year}/{now.month:02d}/{now.day:02d}-{now.hour:02d}:{now.minute:02d}"
        lock = context.bot_data['balance_lock']
        with lock:
            balance_history[time_key] = f"Balance: {float(data[0]):.2f}"
            save_balance_history(balance_history)

        # Generate and send a validation chart (OK/NOK counts per cycle)
        image_path = create_png_plot(data[2], data[4], data[3])
        if image_path and os.path.exists(image_path):
            try:
                with open(image_path, 'rb') as image_file:
                    await update.message.reply_photo(photo=image_file)
            except (FileNotFoundError, OSError) as e:
                logging.error(f"Error while send image : {e}")
                await update.message.reply_text("Error while send image.")
        else:
            logging.error("Image file was not created successfully.")
            await update.message.reply_text("Image file was not created successfully.")
    except Exception as e:
        logging.error(f"Error in /node : {e}")
        await update.message.reply_text("Arf !")
        await update.message.reply_photo(photo=f'media/{PAT_FILE_NAME}')
    finally:
        # Always clean up the temporary chart image
        if image_path:
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
                    logging.info(f"{image_path} has been deleted.")
            except Exception as e:
                logging.error(f"Error deleting image file {image_path}: {e}")


async def flush(update: Update, context: CallbackContext) -> int:
    """Handle /flush command: ask for confirmation before clearing logs.
    This is a ConversationHandler entry point (cannot use @auth_required).
    """
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /flush command.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    # Manual auth check (ConversationHandler requires returning a state)
    if user_id not in allowed_user_ids:
        await update.message.reply_text("Access denied. You are not authorized.")
        return ConversationHandler.END

    # Abort if log file does not exist
    if not os.path.exists(LOG_FILE_NAME):
        logging.warning(f"Log file {LOG_FILE_NAME} does not exist.")
        await update.message.reply_text(f"Log file {LOG_FILE_NAME} does not exist.")
        return ConversationHandler.END

    # Present inline keyboard: flush logs only, or logs + balance history
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data='flush_yes'),
            InlineKeyboardButton("No", callback_data='flush_no')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Do you want to clear the balance history as well?\n"
        "Yes: Clear both logs and balance history\n"
        "No: Clear only the log file",
        reply_markup=reply_markup
    )

    return FLUSH_CONFIRM_STATE


async def flush_confirm_yes(update: Update, context: CallbackContext) -> int:
    """Callback for flush 'Yes': clear both log file and balance history."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} confirmed flush with balance history clear.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    try:
        # Truncate the log file
        with open(LOG_FILE_NAME, 'w'):
            pass
        # Clear the in-memory balance history and persist the empty state
        balance_history = context.bot_data['balance_history']
        lock = context.bot_data['balance_lock']
        with lock:
            balance_history.clear()
            save_balance_history(balance_history)

        message = "✓ Log file and balance history have been cleared."
        logging.info(message)
        await query.edit_message_text(text=message)
        await query.answer()
    except IOError as e:
        logging.error(f"Error clearing the log file: {e}")
        await query.edit_message_text(text="An error occurred while clearing the log file.")
        await query.answer()

    return ConversationHandler.END


async def flush_confirm_no(update: Update, context: CallbackContext) -> int:
    """Callback for flush 'No': clear only the log file, keep balance history."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} confirmed flush without balance history clear.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    try:
        # Truncate the log file only
        with open(LOG_FILE_NAME, 'w'):
            pass
        message = "✓ Log file has been cleared (balance history preserved)."
        logging.info(message)
        await query.edit_message_text(text=message)
        await query.answer()
    except IOError as e:
        logging.error(f"Error clearing the log file: {e}")
        await query.edit_message_text(text="An error occurred while clearing the log file.")
        await query.answer()

    return ConversationHandler.END


async def hist(update: Update, context: CallbackContext) -> int:
    """Handle /hist command: send balance history chart, then ask for text summary.
    This is a ConversationHandler entry point (cannot use @auth_required).
    """
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /hist command.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())
    balance_history = context.bot_data['balance_history']

    # Manual auth check (ConversationHandler requires returning a state)
    if user_id not in allowed_user_ids:
        await update.message.reply_text("Access denied. You are not authorized.")
        return ConversationHandler.END

    if not balance_history:
        await update.message.reply_text("No balance history available.")
        return ConversationHandler.END

    image_path = None
    try:
        # Generate a balance-over-time chart
        try:
            image_path = create_balance_history_plot(balance_history)
        except Exception as e:
            logging.error(f"Error creating balance history plot: {e}")
            await update.message.reply_text("Error creating history graph.")
            return ConversationHandler.END

        if not image_path or not os.path.exists(image_path):
            logging.error("History image file was not created successfully.")
            await update.message.reply_text("Error creating history image.")
            return ConversationHandler.END

        # Send the chart image to the user
        try:
            with open(image_path, 'rb') as image_file:
                await update.message.reply_photo(photo=image_file)
        except (FileNotFoundError, OSError) as e:
            logging.error(f"Error while sending history image : {e}")
            await update.message.reply_text("Error while sending history image.")
            return ConversationHandler.END
        except Exception as e:
            logging.error(f"Error while sending history image : {e}")
            await update.message.reply_text("Error sending history image.")
            return ConversationHandler.END

        # Ask if the user also wants the history as a text message
        keyboard = [
            [
                InlineKeyboardButton("Yes", callback_data='hist_yes'),
                InlineKeyboardButton("No", callback_data='hist_no')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Do you also want to receive the balance history as text?",
            reply_markup=reply_markup
        )

        return HIST_CONFIRM_STATE
    except Exception as error:
        logging.error(f"Error in /hist command: {error}")
        await update.message.reply_text("Error retrieving balance history.")
        return ConversationHandler.END
    finally:
        # Always clean up the temporary chart image
        if image_path:
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
                    logging.info(f"{image_path} has been deleted.")
            except Exception as e:
                logging.error(f"Error deleting image file {image_path}: {e}")


async def hist_confirm_yes(update: Update, context: CallbackContext) -> int:
    """Callback for hist 'Yes': send the full balance history as text."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} confirmed hist with text summary.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())
    balance_history = context.bot_data['balance_history']

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    try:
        if not balance_history:
            await query.answer("Balance history is empty.", show_alert=True)
            return ConversationHandler.END

        # Format all history entries as a single text message
        tmp_string = "History\n" + "\n".join(
            f"{time_key}: {balance}" for time_key, balance in balance_history.items()
        )

        await query.edit_message_text(text="✓ Sending balance history...")
        await query.message.reply_text(tmp_string)
        await query.answer()
        logging.info(f"Sent balance history to user {user_id}")
    except Exception as e:
        logging.error(f"Error sending balance history text: {e}")
        await query.answer("Error sending history text.", show_alert=True)

    return ConversationHandler.END


async def hist_confirm_no(update: Update, context: CallbackContext) -> int:
    """Callback for hist 'No': dismiss the prompt."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} declined hist text summary.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    try:
        await query.edit_message_text(text="✓ Done.")
        await query.answer()
    except Exception as e:
        logging.error(f"Error in hist_confirm_no: {e}")
        await query.answer()

    return ConversationHandler.END
