import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from jrequests import get_addresses, start_docker_node, stop_docker_node, exec_massa_client
from handlers.common import auth_required, handle_api_error
from services.history import save_balance_history, get_entry_balance, get_entry_temperature, get_entry_ram
from services.plotting import create_png_plot, create_balance_history_plot, create_resources_plot
from config import (
    LOG_FILE_NAME, FLUSH_CONFIRM_STATE, HIST_CONFIRM_STATE,
    DOCKER_MENU_STATE, DOCKER_START_CONFIRM_STATE, DOCKER_STOP_CONFIRM_STATE,
    DOCKER_MASSA_MENU_STATE, DOCKER_BUYROLLS_INPUT_STATE, DOCKER_BUYROLLS_CONFIRM_STATE,
    DOCKER_SELLROLLS_INPUT_STATE, DOCKER_SELLROLLS_CONFIRM_STATE,
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
    """Handle /hist command: send balance and resources history charts, then ask for text summary.
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
    resources_path = None
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

        # Send the balance chart image to the user
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

        # Generate and send the resources (temperature + RAM) chart when data is available
        try:
            resources_path = create_resources_plot(balance_history)
            if resources_path and os.path.exists(resources_path):
                with open(resources_path, 'rb') as resources_file:
                    await update.message.reply_photo(photo=resources_file)
        except Exception as e:
            logging.error(f"Error creating or sending resources plot: {e}")
            # Non-fatal: continue without the resources chart

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
        # Always clean up the temporary chart images
        for path in (image_path, resources_path):
            if path:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        logging.info(f"{path} has been deleted.")
                except Exception as e:
                    logging.error(f"Error deleting image file {path}: {e}")


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
        def _format_entry(time_key: str, value) -> str:
            line = f"{time_key}: Balance {get_entry_balance(value):.2f}"
            temp = get_entry_temperature(value)
            ram = get_entry_ram(value)
            if temp is not None:
                line += f", Temp {temp:.1f}°C"
            if ram is not None:
                line += f", RAM {ram:.1f}%"
            return line

        tmp_string = "History\n" + "\n".join(
            _format_entry(time_key, value) for time_key, value in balance_history.items()
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


async def docker(update: Update, context: CallbackContext) -> int:
    """Handle /docker command: show menu with Start/Stop options.
    This is a ConversationHandler entry point (cannot use @auth_required).
    """
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /docker command.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    # Manual auth check (ConversationHandler requires returning a state)
    if user_id not in allowed_user_ids:
        await update.message.reply_text("Access denied. You are not authorized.")
        return ConversationHandler.END

    # Present inline keyboard: Start, Stop or Massa Client
    keyboard = [
        [
            InlineKeyboardButton("▶️ Start", callback_data='docker_start'),
            InlineKeyboardButton("⏹️ Stop", callback_data='docker_stop')
        ],
        [
            InlineKeyboardButton("💻 Massa Client", callback_data='docker_massa')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🐳 Docker Node Management\n"
        "What do you want to do?",
        reply_markup=reply_markup
    )

    return DOCKER_MENU_STATE


async def docker_start(update: Update, context: CallbackContext) -> int:
    """Callback for docker 'Start': ask for confirmation."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} selected Start in docker menu.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data='docker_start_confirm'),
            InlineKeyboardButton("No", callback_data='docker_cancel')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="⚠️  Are you sure you want to start the node container?",
        reply_markup=reply_markup
    )
    await query.answer()

    return DOCKER_START_CONFIRM_STATE


async def docker_stop(update: Update, context: CallbackContext) -> int:
    """Callback for docker 'Stop': ask for confirmation."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} selected Stop in docker menu.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data='docker_stop_confirm'),
            InlineKeyboardButton("No", callback_data='docker_cancel')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="⚠️  Are you sure you want to stop the node container?",
        reply_markup=reply_markup
    )
    await query.answer()

    return DOCKER_STOP_CONFIRM_STATE


async def docker_start_confirm(update: Update, context: CallbackContext) -> int:
    """Callback for docker start confirmation: execute docker start command."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} confirmed docker start.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    try:
        # Get container name from bot_data (must be set in main.py from topology.json)
        container_name = context.bot_data.get('docker_container_name')
        if not container_name:
            await query.edit_message_text(text="❌ Error: Docker container name not configured.")
            await query.answer()
            return ConversationHandler.END

        # Execute the docker start command
        result = start_docker_node(logging, container_name)

        if result['status'] == 'ok':
            await query.edit_message_text(text=result['message'])
            logging.info(f"User {user_id} successfully started the docker container.")
        else:
            await query.edit_message_text(text=result['message'])

        await query.answer()
    except Exception as e:
        logging.error(f"Error executing docker start: {e}")
        await query.edit_message_text(text="❌ Error executing docker start command.")
        await query.answer()

    return ConversationHandler.END


async def docker_stop_confirm(update: Update, context: CallbackContext) -> int:
    """Callback for docker stop confirmation: execute docker stop command."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} confirmed docker stop.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    try:
        # Get container name from bot_data (must be set in main.py from topology.json)
        container_name = context.bot_data.get('docker_container_name')
        if not container_name:
            await query.edit_message_text(text="❌ Error: Docker container name not configured.")
            await query.answer()
            return ConversationHandler.END

        # Execute the docker stop command
        result = stop_docker_node(logging, container_name)

        if result['status'] == 'ok':
            await query.edit_message_text(text=result['message'])
            logging.info(f"User {user_id} successfully stopped the docker container.")
        else:
            await query.edit_message_text(text=result['message'])

        await query.answer()
    except Exception as e:
        logging.error(f"Error executing docker stop: {e}")
        await query.edit_message_text(text="❌ Error executing docker stop command.")
        await query.answer()

    return ConversationHandler.END


async def docker_cancel(update: Update, context: CallbackContext) -> int:
    """Callback for docker cancel: dismiss the action."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} cancelled docker action.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    try:
        await query.edit_message_text(text="❌ Action cancelled.")
        await query.answer()
    except Exception as e:
        logging.error(f"Error in docker_cancel: {e}")
        await query.answer()

    return ConversationHandler.END


async def docker_massa(update: Update, context: CallbackContext) -> int:
    """Callback for docker 'Massa Client': show wallet_info / buy_rolls sub-menu."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} selected Massa Client in docker menu.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    keyboard = [
        [
            InlineKeyboardButton("💰 Wallet Info", callback_data='massa_wallet_info'),
        ],
        [
            InlineKeyboardButton("🎲 Buy Rolls", callback_data='massa_buy_rolls'),
            InlineKeyboardButton("💸 Sell Rolls", callback_data='massa_sell_rolls')
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data='massa_back')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="💻 Massa Client\n"
             "Choose an action:",
        reply_markup=reply_markup
    )
    await query.answer()

    return DOCKER_MASSA_MENU_STATE


async def massa_wallet_info(update: Update, context: CallbackContext) -> int:
    """Callback for 'Wallet Info': execute wallet_info via massa-client."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} requested wallet_info.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    try:
        container_name = context.bot_data.get('docker_container_name')
        password = context.bot_data.get('massa_client_password')
        if not container_name or not password:
            await query.edit_message_text(text="❌ Error: Docker or Massa client not configured.")
            await query.answer()
            return ConversationHandler.END

        await query.edit_message_text(text="⏳ Executing wallet_info...")
        await query.answer()

        result = exec_massa_client(logging, container_name, password, 'wallet_info')

        if result['status'] == 'ok':
            output = result['output'] or 'No output returned.'
            await query.edit_message_text(text=f"💰 Wallet Info:\n\n{output}")
        else:
            await query.edit_message_text(text=result['message'])
    except Exception as e:
        logging.error(f"Error executing wallet_info: {e}")
        await query.edit_message_text(text="❌ Error executing wallet_info.")

    return ConversationHandler.END


async def massa_buy_rolls_ask(update: Update, context: CallbackContext) -> int:
    """Callback for 'Buy Rolls': ask the user how many rolls to buy."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} selected Buy Rolls.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    await query.edit_message_text(
        text="🎲 Buy Rolls\n\n"
             "How many rolls do you want to buy?\n"
             "Send a number (e.g. 1, 5, 10) or /docker to cancel."
    )
    await query.answer()

    return DOCKER_BUYROLLS_INPUT_STATE


async def massa_sell_rolls_ask(update: Update, context: CallbackContext) -> int:
    """Callback for 'Sell Rolls': ask the user how many rolls to sell."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} selected Sell Rolls.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    await query.edit_message_text(
        text="💸 Sell Rolls\n\n"
             "How many rolls do you want to sell?\n"
             "Send a number (e.g. 1, 5, 10) or /docker to cancel."
    )
    await query.answer()

    return DOCKER_SELLROLLS_INPUT_STATE


async def massa_buy_rolls_input(update: Update, context: CallbackContext) -> int:
    """Handle text input for the number of rolls to buy."""
    user_id = str(update.effective_user.id)
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await update.message.reply_text("Access denied.")
        return ConversationHandler.END

    text = update.message.text.strip()

    # Validate input: must be a positive integer
    try:
        roll_count = int(text)
        if roll_count <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please send a positive integer (e.g. 1, 5, 10) or /docker to cancel."
        )
        return DOCKER_BUYROLLS_INPUT_STATE

    # Store roll count for the confirmation step
    context.user_data['buy_rolls_count'] = roll_count

    wallet_address = context.bot_data.get('massa_wallet_address', 'N/A')
    fee = context.bot_data.get('massa_buy_rolls_fee', 0.01)

    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data='buyrolls_confirm'),
            InlineKeyboardButton("No", callback_data='docker_cancel')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"⚠️  Confirm buy_rolls:\n\n"
        f"Address: {wallet_address}\n"
        f"Rolls: {roll_count}\n"
        f"Fee: {fee}\n\n"
        f"Proceed?",
        reply_markup=reply_markup
    )

    return DOCKER_BUYROLLS_CONFIRM_STATE


async def massa_buy_rolls_confirm(update: Update, context: CallbackContext) -> int:
    """Callback for buy rolls confirmation: execute the buy_rolls command."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} confirmed buy_rolls.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    try:
        container_name = context.bot_data.get('docker_container_name')
        password = context.bot_data.get('massa_client_password')
        wallet_address = context.bot_data.get('massa_wallet_address')
        fee = context.bot_data.get('massa_buy_rolls_fee', 0.01)
        roll_count = context.user_data.get('buy_rolls_count', 0)

        if not all([container_name, password, wallet_address]) or roll_count <= 0:
            await query.edit_message_text(text="❌ Error: Missing configuration or invalid roll count.")
            await query.answer()
            return ConversationHandler.END

        command = f"buy_rolls {wallet_address} {roll_count} {fee}"

        await query.edit_message_text(text=f"⏳ Executing buy_rolls ({roll_count} rolls)...")
        await query.answer()

        result = exec_massa_client(logging, container_name, password, command)

        if result['status'] == 'ok':
            output = result['output'] or 'Command executed (no output).'
            await query.edit_message_text(
                text=f"✅ buy_rolls executed:\n\n{output}"
            )
            logging.info(f"User {user_id} bought {roll_count} rolls.")
        else:
            await query.edit_message_text(text=result['message'])
    except Exception as e:
        logging.error(f"Error executing buy_rolls: {e}")
        await query.edit_message_text(text="❌ Error executing buy_rolls.")

    # Clean up user_data
    context.user_data.pop('buy_rolls_count', None)
    return ConversationHandler.END


async def massa_sell_rolls_input(update: Update, context: CallbackContext) -> int:
    """Handle text input for the number of rolls to sell."""
    user_id = str(update.effective_user.id)
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await update.message.reply_text("Access denied.")
        return ConversationHandler.END

    text = update.message.text.strip()

    # Validate input: must be a positive integer
    try:
        roll_count = int(text)
        if roll_count <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please send a positive integer (e.g. 1, 5, 10) or /docker to cancel."
        )
        return DOCKER_SELLROLLS_INPUT_STATE

    # Store roll count for the confirmation step
    context.user_data['sell_rolls_count'] = roll_count

    wallet_address = context.bot_data.get('massa_wallet_address', 'N/A')
    fee = context.bot_data.get('massa_buy_rolls_fee', 0.01)

    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data='sellrolls_confirm'),
            InlineKeyboardButton("No", callback_data='docker_cancel')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"⚠️  Confirm sell_rolls:\n\n"
        f"Address: {wallet_address}\n"
        f"Rolls: {roll_count}\n"
        f"Fee: {fee}\n\n"
        f"Proceed?",
        reply_markup=reply_markup
    )

    return DOCKER_SELLROLLS_CONFIRM_STATE


async def massa_sell_rolls_confirm(update: Update, context: CallbackContext) -> int:
    """Callback for sell rolls confirmation: execute the sell_rolls command."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} confirmed sell_rolls.')
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    try:
        container_name = context.bot_data.get('docker_container_name')
        password = context.bot_data.get('massa_client_password')
        wallet_address = context.bot_data.get('massa_wallet_address')
        fee = context.bot_data.get('massa_buy_rolls_fee', 0.01)
        roll_count = context.user_data.get('sell_rolls_count', 0)

        if not all([container_name, password, wallet_address]) or roll_count <= 0:
            await query.edit_message_text(text="❌ Error: Missing configuration or invalid roll count.")
            await query.answer()
            return ConversationHandler.END

        command = f"sell_rolls {wallet_address} {roll_count} {fee}"

        await query.edit_message_text(text=f"⏳ Executing sell_rolls ({roll_count} rolls)...")
        await query.answer()

        result = exec_massa_client(logging, container_name, password, command)

        if result['status'] == 'ok':
            output = result['output'] or 'Command executed (no output).'
            await query.edit_message_text(
                text=f"✅ sell_rolls executed:\n\n{output}"
            )
            logging.info(f"User {user_id} sold {roll_count} rolls.")
        else:
            await query.edit_message_text(text=result['message'])
    except Exception as e:
        logging.error(f"Error executing sell_rolls: {e}")
        await query.edit_message_text(text="❌ Error executing sell_rolls.")

    # Clean up user_data
    context.user_data.pop('sell_rolls_count', None)
    return ConversationHandler.END


async def massa_back(update: Update, context: CallbackContext) -> int:
    """Callback to go back to the main docker menu."""
    query = update.callback_query
    user_id = str(query.from_user.id)
    allowed_user_ids = context.bot_data.get('allowed_user_ids', set())

    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END

    keyboard = [
        [
            InlineKeyboardButton("▶️ Start", callback_data='docker_start'),
            InlineKeyboardButton("⏹️ Stop", callback_data='docker_stop')
        ],
        [
            InlineKeyboardButton("💻 Massa Client", callback_data='docker_massa')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="🐳 Docker Node Management\n"
             "What do you want to do?",
        reply_markup=reply_markup
    )
    await query.answer()

    return DOCKER_MENU_STATE
