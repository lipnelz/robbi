import os
import io
import sys
import json
import logging
import functools
import asyncio
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Tuple, List
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.request import HTTPXRequest
from jrequests import get_addresses, get_bitcoin_price, get_mas_instant, get_mas_daily, get_system_stats
from apscheduler.schedulers.background import BackgroundScheduler


JOB_SCHED_NAME = 'periodic_node_ping'
LOG_FILE_NAME = 'bot_activity.log'
FLUSH_CONFIRM_STATE = 1
HIST_CONFIRM_STATE = 2
PNG_FILE_NAME = 'plot.png'
BUDDY_FILE_NAME = 'Buddy_christ.jpg'
PAT_FILE_NAME = 'patrick.gif'
BTC_CRY_NAME = "btc_cry.png"
MAS_CRY_NAME = "mas_cry.png"
TIMEOUT_NAME = "timeout.png"
TIMEOUT_FIRE_NAME = "timeout_fire.png"

COMMANDS_LIST = [
    {'id': 0, 'cmd_txt': 'hi', 'cmd_desc': 'Say hi to Robbi'},
    {'id': 1, 'cmd_txt': 'node', 'cmd_desc': 'Get node results'},
    {'id': 2, 'cmd_txt': 'btc', 'cmd_desc': 'Get BTC current price'},
    {'id': 3, 'cmd_txt': 'mas', 'cmd_desc': 'Get MAS current price'},
    {'id': 4, 'cmd_txt': 'hist', 'cmd_desc': 'Get node balance history'},
    {'id': 5, 'cmd_txt': 'flush', 'cmd_desc': 'Flush local logs'},
    {'id': 6, 'cmd_txt': 'temperature', 'cmd_desc': 'Get system temperature, CPU and RAM'},
]

NODE_IS_DOWN = 'Node is down'
NODE_IS_UP = 'Node is up and running'

# Configure logging module
logging.basicConfig(
    filename=LOG_FILE_NAME,
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Globals shared among callbacks
allowed_user_ids = set()
massa_node_address = ""
ninja_key = ""
bot_token = ""
balance_history = {}

def disable_prints() -> None:
    # Redirect stdout to a string stream to suppress print statements
    sys.stdout = io.StringIO()
    # Redirect stderr to a string stream to suppress error messages
    sys.stderr = io.StringIO()

def extract_address_data(json_data: dict) -> Tuple[str, int, List[int], List[int], List[int], List[int]]:
    """
    Extract useful JSON response data from get_address.

    :param json_data: Input JSON data to parse.
    :return: Tuple composed of final_balance, final_roll_count, cycles, ok_counts and nok_counts.
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

def create_png_plot(cycles: List[int], nok_counts: List[int], ok_counts: List[int]) -> str:
        """
        Creates a line plot with markers for OK and NOK counts over multiple cycles,
        and saves the plot as a PNG image.

        :param cycles(int): A list or array of integers representing the cycles for which counts are recorded.
        :param nok_counts(int): A list or array of integers representing the NOK counts for each cycle.
        :param ok_counts(int): A list or array of integers representing the OK counts for each cycle.

        :return(str): The file path of the generated PNG image.
        """
        plt.figure(figsize=(10, 6))
        plt.plot(cycles, nok_counts, marker='o', linestyle='-', color='red', label='NOK Counts')
        plt.plot(cycles, ok_counts, marker='o', linestyle='-', color='blue', label='OK Counts')
        plt.title('Validation per Cycle')
        plt.xlabel('Cycle')
        plt.ylabel('Count')
        plt.legend()
        plt.grid(True)
        plt.savefig(PNG_FILE_NAME)
        plt.close()
        return PNG_FILE_NAME

def create_balance_history_plot() -> str:
        """
        Creates a line plot of balance history over time and saves it as a PNG image.

        :return(str): The file path of the generated PNG image.
        """
        if not balance_history:
            return ""
        
        # Extract timestamps and balance values
        timestamps = list(balance_history.keys())
        balances = []
        
        for balance_str in balance_history.values():
            # Extract numeric value from "Balance: 123.45" format
            balance_value = float(balance_str.split(": ")[1])
            balances.append(balance_value)
        
        # Create plot
        plt.figure(figsize=(12, 6))
        plt.plot(range(len(timestamps)), balances, marker='o', linestyle='-', 
                 color='green', linewidth=2, markersize=8, label='Balance')
        plt.title('Balance History Over Time')
        plt.xlabel('Time')
        plt.ylabel('Balance')
        plt.xticks(range(len(timestamps)), timestamps, rotation=45, ha='right')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Save plot
        history_plot_name = 'balance_history.png'
        plt.savefig(history_plot_name)
        plt.close()
        return history_plot_name

async def hi(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /hi command.')

    photo_path = 'media/' + (BUDDY_FILE_NAME if user_id in allowed_user_ids else PAT_FILE_NAME)
    await update.message.reply_text('Hey dude!' if user_id in allowed_user_ids else '')
    await update.message.reply_photo(photo=photo_path)

async def node(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /node command.')

    if user_id in allowed_user_ids:
        image_path = None
        try:
            # Get new data
            json_data = get_addresses(logging, massa_node_address)
            if "error" in json_data:
                error_message = json_data["error"]
                if "timed out" in error_message:
                    logging.error("Timeout occurred while trying to get the status.")
                    for notify_user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=notify_user_id, photo=('media/' + TIMEOUT_NAME))
                else:
                    logging.error(f"Error while getting the status: {error_message}")
                    for notify_user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=notify_user_id, photo=('media/' + TIMEOUT_FIRE_NAME))
                return

            # Extract useful data using the function
            data = extract_address_data(json_data)
            if not data or len(data) < 6:  # Check if extract has returned empty data
                logging.error(f"Node unreachable or no data available")
                await update.message.reply_text("Node unreachable or no data available.")
                return

            formatted_string = (
                f"Final Balance: {data[0]}\n"
                f"Final Roll Count: {data[1]}\n"
                f"OK Counts: {data[3]}\n"
                f"NOK Counts: {data[4]}\n"
                f"Active Rolls: {data[5]}"
            )
            print(formatted_string)
            await update.message.reply_text('Node status: ' + formatted_string)

            # Get the current hour and minute
            now = datetime.now()
            hour, minute, day, month = now.hour, now.minute, now.day, now.month
            # Add data to balance_history with the key day/month-hour:minute
            time_key = f"{day:02d}/{month:02d}-{hour:02d}:{minute:02d}"
            balance_history[time_key] = f"Balance: {float(data[0]):.2f}"

            # Create graph from data and save to PNG_FILE_NAME
            image_path = create_png_plot(data[2], data[4], data[3])
            # Check if the image file was created successfully
            if image_path and os.path.exists(image_path):
                try:
                    # Send the image via Telegram with a timeout
                    with open(image_path, 'rb') as image_file:
                        await update.message.reply_photo(photo=image_file)
                except (FileNotFoundError, OSError) as e:
                    logging.error(f"Error while send image : {e}")
                    await update.message.reply_text("Error while send image.")
            else:
                logging.error("Image file was not created successfully.")
                await update.message.reply_text("Image file was not created successfully.")
        except Exception as e:
            logging.error(f"Error in node /node : {e}")
            await update.message.reply_text("Arf !")
            await update.message.reply_photo(photo=('media/' + PAT_FILE_NAME))
        finally:
            # Always cleanup the image file
            if image_path:
                try:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        logging.info(f"{image_path} has been deleted.")
                except Exception as e:
                    logging.error(f"Error deleting image file {image_path}: {e}")

async def flush(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /flush command.')

    if user_id not in allowed_user_ids:
        await update.message.reply_text("Access denied. You are not authorized.")
        return ConversationHandler.END

    if not os.path.exists(LOG_FILE_NAME):
        logging.warning(f"Log file {LOG_FILE_NAME} does not exist.")
        await update.message.reply_text(f"Log file {LOG_FILE_NAME} does not exist.")
        return ConversationHandler.END

    # Create inline buttons for yes/no confirmation
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
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} confirmed flush with balance history clear.')
    
    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END
    
    try:
        # Clear log file
        with open(LOG_FILE_NAME, 'w'):
            pass
        # Clear balance history
        balance_history.clear()
        
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
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} confirmed flush without balance history clear.')
    
    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END
    
    try:
        # Clear log file only
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

async def btc(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /btc command.')

    if user_id in allowed_user_ids:
        try:
            data = get_bitcoin_price(logging, ninja_key)
            if "error" in data:
                error_message = data["error"]
                if "timed out" in error_message:
                    logging.error("Timeout occurred while trying to get the status.")
                    for notify_user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=notify_user_id, photo=('media/' + TIMEOUT_NAME))
                else:
                    logging.error(f"Error while getting the status: {error_message}")
                    for notify_user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=notify_user_id, photo=('media/' + TIMEOUT_FIRE_NAME))
                return

            formatted_string = (
                f"Price: {float(data['price']):.2f} $\n"
                f"24h Price Change: {float(data['24h_price_change']):.2f}\n"
                f"24h Price Change Percent: {float(data['24h_price_change_percent']):.2f}%\n"
                f"24h High: {float(data['24h_high']):.2f}\n"
                f"24h Low: {float(data['24h_low']):.2f}\n"
                f"24h Volume: {float(data['24h_volume']):.2f}"
            )
            print(formatted_string)
            await update.message.reply_text(formatted_string)
        except Exception as e:
            logging.error(f"Error when /btc : {e}")
            await update.message.reply_text("Nooooo")
            await update.message.reply_photo(photo=('media/' + BTC_CRY_NAME))

async def mas(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /mas command.')

    if user_id in allowed_user_ids:
        try:
            current_avg_price = get_mas_instant(logging)
            ticker_price_change_stats = get_mas_daily(logging)
            if "error" in current_avg_price or "error" in ticker_price_change_stats:
                error_message = current_avg_price["error"] if "error" in current_avg_price else ticker_price_change_stats["error"]
                if "timed out" in error_message:
                    logging.error("Timeout occurred while trying to get the status.")
                    for notify_user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=notify_user_id, photo=('media/' + TIMEOUT_NAME))
                else:
                    logging.error(f"Error while getting the status: {error_message}")
                    for notify_user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=notify_user_id, photo=('media/' + TIMEOUT_FIRE_NAME))
                return

            formatted_string = (
                f"{ticker_price_change_stats['symbol']}\n"
                f"-----------\n"
                f"Price: {float(current_avg_price['price']):.5f} USDT\n"
                f"24h Volume: {float(ticker_price_change_stats['volume']):.6f}\n"
                f"-----------\n"
                f"Price Change: {float(ticker_price_change_stats['priceChangePercent']):.6f}%\n"
                f"Price Change: {float(ticker_price_change_stats['priceChange']):.6f}\n"
                f"24h High: {float(ticker_price_change_stats['highPrice']):.6f}\n"
                f"24h Low: {float(ticker_price_change_stats['lowPrice']):.6f}\n"
            )
            print(formatted_string)
            await update.message.reply_text(formatted_string)
        except Exception as e:
            logging.error(f"Error when /mas : {e}")
            await update.message.reply_text("Nooooo")
            await update.message.reply_photo(photo=('media/' + MAS_CRY_NAME))

async def temperature(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /temperature command.')

    if user_id in allowed_user_ids:
        try:
            stats = get_system_stats(logging)
            if "error" in stats:
                error_message = stats["error"]
                logging.error(f"Error while getting system stats: {error_message}")
                await update.message.reply_text(f"Error: {error_message}")
                return

            formatted_string = (
                f"🌡️ System Status\n"
                f"-----------\n"
            )
            
            if "temperature_celsius" in stats:
                formatted_string += f"Temperature: {stats['temperature_celsius']}°C\n"
            
            formatted_string += (
                f"CPU Usage: {stats['cpu_percent']}%\n"
                f"RAM Usage: {stats['ram_percent']}%\n"
                f"RAM Available: {stats['ram_available_gb']} GB / {stats['ram_total_gb']} GB"
            )
            
            print(formatted_string)
            await update.message.reply_text(formatted_string)
        except Exception as e:
            logging.error(f"Error when /temperature : {e}")
            await update.message.reply_text("Error retrieving system stats")

async def hist(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /hist command.')

    if user_id not in allowed_user_ids:
        await update.message.reply_text("Access denied. You are not authorized.")
        return ConversationHandler.END

    if not balance_history:
        await update.message.reply_text("No balance history available.")
        return ConversationHandler.END

    image_path = None
    try:
        # Generate balance history plot
        try:
            image_path = create_balance_history_plot()
        except Exception as e:
            logging.error(f"Error creating balance history plot: {e}")
            await update.message.reply_text("Error creating history graph.")
            return ConversationHandler.END
        
        if not image_path or not os.path.exists(image_path):
            logging.error("History image file was not created successfully.")
            await update.message.reply_text("Error creating history image.")
            return ConversationHandler.END
        
        try:
            # Send the image via Telegram
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
        
        # After sending the image, ask if user wants text summary
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
        # Always cleanup the image file
        if image_path:
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
                    logging.info(f"{image_path} has been deleted.")
            except Exception as e:
                logging.error(f"Error deleting image file {image_path}: {e}")

async def hist_confirm_yes(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} confirmed hist with text summary.')
    
    if user_id not in allowed_user_ids:
        await query.answer("Access denied.", show_alert=True)
        return ConversationHandler.END
    
    try:
        if not balance_history:
            await query.answer("Balance history is empty.", show_alert=True)
            return ConversationHandler.END
        
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
    query = update.callback_query
    user_id = str(query.from_user.id)
    logging.info(f'User {user_id} declined hist text summary.')
    
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

HANDLERS = [(cmd['cmd_txt'], globals()[cmd['cmd_txt']]) for cmd in COMMANDS_LIST if cmd['cmd_txt'] not in ('flush', 'hist')]

async def post_init(application: Application) -> None:
    commands = [BotCommand(command=cmd['cmd_txt'], description=cmd['cmd_desc']) for cmd in COMMANDS_LIST]
    await application.bot.set_my_commands(commands)

def run_async_func(application: Application) -> None:
    try:
        try:
            loop = asyncio.get_running_loop()
            logging.info("Use the same event loop.")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            logging.info("Create a new event loop.")

        scheduler = BackgroundScheduler()

        if scheduler.get_job(JOB_SCHED_NAME):
            scheduler.remove_job(JOB_SCHED_NAME)
            logging.info(f"Previous job {JOB_SCHED_NAME} removed.")

        logging.info(f"Add periodic job {JOB_SCHED_NAME}.")
        scheduler.add_job(
            functools.partial(run_coroutine_in_loop, periodic_node_ping, application, loop),
            'interval',
            minutes=60,
            id=JOB_SCHED_NAME,
            name=JOB_SCHED_NAME
        )

        # Start scheduler if not already running
        if not scheduler.running:
            scheduler.start()
            logging.info("Scheduler started.")
    except Exception as e:
        logging.error(f"Error in run_async_func: {e}")

def run_coroutine_in_loop(coroutine, application, loop) -> None:
    try:
        # Check if loop is already running
        if loop.is_running():
            logging.info("Event loop already running, scheduling coroutine.")
            asyncio.ensure_future(coroutine(application), loop=loop)
        else:
            logging.info("Running coroutine in a new loop.")
            loop.run_until_complete(coroutine(application))
    except Exception as e:
        logging.error(f"Error in run_coroutine_in_loop: {e}")

async def periodic_node_ping(application: Application) -> None:
    logging.info(f'Node ping beginning...')
    try:
        json_data = get_addresses(logging, massa_node_address)
        if "error" in json_data:
            error_message = json_data["error"]
            if "timed out" in error_message:
                logging.error("Timeout occurred while trying to get the status.")
                photo_path = 'media/' + TIMEOUT_NAME
                for user_id in allowed_user_ids:
                    try:
                        with open(photo_path, "rb") as photo:
                            await application.bot.send_photo(
                                chat_id=user_id,
                                photo=photo,
                                caption="Timeout occurred while trying to get the status."
                            )
                    except (FileNotFoundError, OSError) as e:
                        logging.error(f"Error sending timeout photo to {user_id}: {e}")
            else:
                logging.error(f"Error while getting the status: {error_message}.")
                photo_path = 'media/' + TIMEOUT_FIRE_NAME
                for user_id in allowed_user_ids:
                    try:
                        with open(photo_path, "rb") as photo:
                            await application.bot.send_photo(
                                chat_id=user_id,
                                photo=photo,
                                caption=f"Error while getting the status: {error_message}."
                            )
                    except (FileNotFoundError, OSError) as e:
                        logging.error(f"Error sending fire photo to {user_id}: {e}")

        # Extract useful data using the function
        data = extract_address_data(json_data)
        logging.info(data)

        if not data or len(data) < 6:
            logging.error("Invalid data.")
            for user_id in allowed_user_ids:
                await application.bot.send_message(chat_id=user_id, text="Ping failed, invalid data.")
            return

        logging.info(f"Extracted data: {data}")

        # if nok count set contains a value (data[4]) or roll count is 0 (data[1])
        if any(data[4]) or data[1] == 0:
            for user_id in allowed_user_ids:
                await application.bot.send_message(chat_id=user_id, text=NODE_IS_DOWN)
            logging.info(f"Node is down.")
        else:
            logging.info(f"Node is up.")

        now = datetime.now()
        hour, minute, day, month = now.hour, now.minute, now.day, now.month
        # Add data to balance_history with the key day/month-hour:minute
        time_key = f"{day:02d}/{month:02d}-{hour:02d}:{minute:02d}"
        balance_history[time_key] = f"Balance: {float(data[0]):.2f}"

        # If the node is up and hour is 7, 12 or 21 then send a message
        if hour == 7 or hour == 12 or hour == 21:
            tmp_string = NODE_IS_UP + "\n" + "\n".join(
                f"{timestamp}: {balance}" for timestamp, balance in balance_history.items()
            )
            for user_id in allowed_user_ids:
                await application.bot.send_message(chat_id=user_id, text=tmp_string)

    except Exception as e:
        logging.error(f"Error in periodic_node_ping: {e}")

async def error_handler(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(f"Error handler catch: {context.error}")


def main():
    global allowed_user_ids
    global massa_node_address
    global ninja_key
    global bot_token
    global balance_history

    try:
        # Open 'topology.json' file
        with open('topology.json', 'r', encoding='utf-8') as file:
            tmp_json = json.load(file)
            bot_token = tmp_json.get('telegram_bot_token')
            # Update globals
            allowed_user_ids = {str(tmp_json.get('user_white_list', {}).get('admin'))}
            massa_node_address = tmp_json.get('massa_node_address')
            ninja_key = tmp_json.get('ninja_api_key')
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading topology.json: {e}")
        return

    disable_prints() # Comment this line to enable prints DEBUG purpose only
    logging.info("Starting bot...")

    # Get node info at bot startup
    json_data = get_addresses(logging, massa_node_address)
    if "error" in json_data:
        error_message = json_data["error"]
        if "timed out" in error_message:
            logging.error("Timeout occurred while trying to get the status.")
        else:
            logging.error(f"Error while getting the status: {error_message}")

    # Create the Request object with 20-second timeouts
    req = HTTPXRequest(connect_timeout=20, read_timeout=20, write_timeout=20)

    # Create the Application using the HTTPXRequest object
    application = Application.builder()\
        .token(bot_token)\
        .post_init(post_init)\
        .request(req)\
        .build()

    # Populate with commands in handlers
    for cmd_txt, handler_func in HANDLERS:
        application.add_handler(CommandHandler(cmd_txt, handler_func))

    # Add ConversationHandler for /flush command
    flush_handler = ConversationHandler(
        entry_points=[CommandHandler('flush', flush)],
        states={
            FLUSH_CONFIRM_STATE: [
                CallbackQueryHandler(flush_confirm_yes, pattern='^flush_yes$'),
                CallbackQueryHandler(flush_confirm_no, pattern='^flush_no$')
            ]
        },
        fallbacks=[CommandHandler('flush', flush)]
    )
    application.add_handler(flush_handler)

    # Add ConversationHandler for /hist command
    hist_handler = ConversationHandler(
        entry_points=[CommandHandler('hist', hist)],
        states={
            HIST_CONFIRM_STATE: [
                CallbackQueryHandler(hist_confirm_yes, pattern='^hist_yes$'),
                CallbackQueryHandler(hist_confirm_no, pattern='^hist_no$')
            ]
        },
        fallbacks=[CommandHandler('hist', hist)]
    )
    application.add_handler(hist_handler)

    application.add_error_handler(error_handler)

    # Start the scheduler
    run_async_func(application)
    # Start bot
    application.run_polling()

    # Should never happen
    logging.info("Bot stopped.")
    print("Bot stopped.")

if __name__ == '__main__':
    main()