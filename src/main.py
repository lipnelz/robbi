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
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes
from telegram.request import HTTPXRequest
from jrequests import get_addresses, get_bitcoin_price, get_mas_instant, get_mas_daily
from apscheduler.schedulers.background import BackgroundScheduler


JOB_SCHED_NAME = 'periodic_node_ping'
LOG_FILE_NAME = 'bot_activity.log'
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
        try:
            # Get new data
            json_data = get_addresses(logging, massa_node_address)
            if "error" in json_data:
                error_message = json_data["error"]
                if "timed out" in error_message:
                    logging.error("Timeout occurred while trying to get the status.")
                    for user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=user_id, photo=('media/' + TIMEOUT_NAME))
                else:
                    logging.error(f"Error while getting the status: {error_message}")
                    for user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=user_id, photo=('media/' + TIMEOUT_FIRE_NAME))
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
            if os.path.exists(image_path):
                try:
                    # Send the image via Telegram with a timeout
                    await update.message.reply_photo(photo=image_path)
                except Exception as e:
                    logging.error(f"Error while send image : {e}")
                    await update.message.reply_text("Error while send image.")
                finally:
                    # Delete the image file after sending
                    os.remove(image_path)
                    print(f"{image_path} has been deleted.")
            else:
                logging.error("Image file was not created successfully.")
                await update.message.reply_text("Image file was not created successfully.")
        except Exception as e:
                logging.error(f"Error in node /node : {e}")
                await update.message.reply_text("Arf !")
                await update.message.reply_photo(photo=('media/' + PAT_FILE_NAME))

async def flush(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /flush command.')

    if user_id in allowed_user_ids and os.path.exists(LOG_FILE_NAME):
        try:
            with open(LOG_FILE_NAME, 'w'):
                pass
            message = f"{LOG_FILE_NAME} has been cleared and balance history cleared"
            print(message)
            # Clear the balance_history dictionary after sending the message
            balance_history.clear()
            await update.message.reply_text(message)
        except IOError as e:
            logging.error(f"Error clearing the log file: {e}")
            await update.message.reply_text("An error occurred while clearing the log file.")
    elif not os.path.exists(LOG_FILE_NAME):
        logging.warning(f"Log file {LOG_FILE_NAME} does not exist.")
        await update.message.reply_text(f"Log file {LOG_FILE_NAME} does not exist.")

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
                    for user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=user_id, photo=('media/' + TIMEOUT_NAME))
                else:
                    logging.error(f"Error while getting the status: {error_message}")
                    for user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=user_id, photo=('media/' + TIMEOUT_FIRE_NAME))
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
                    for user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=user_id, photo=('media/' + TIMEOUT_NAME))
                else:
                    logging.error(f"Error while getting the status: {error_message}")
                    for user_id in allowed_user_ids:
                        await update.message.reply_photo(chat_id=user_id, photo=('media/' + TIMEOUT_FIRE_NAME))
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

async def hist(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /hist command.')

    tmp_string = "History" + "\n" + "\n".join(
        f"{time_key}: {balance}" for time_key, balance in balance_history.items()
    )
    logging.info(f"History: {tmp_string}")
    try:
        await update.message.reply_text(tmp_string if user_id in allowed_user_ids else '')
    except Exception as error:
        logging.info(f"Error while getting history: {error}")


HANDLERS = [(cmd['cmd_txt'], globals()[cmd['cmd_txt']]) for cmd in COMMANDS_LIST]

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
                with open('media/' + TIMEOUT_NAME, "rb") as photo:
                    for user_id in allowed_user_ids:
                        await application.bot.send_photo(
                            chat_id=user_id,
                            photo=photo,
                            caption="Timeout occurred while trying to get the status."
                        )
            else:
                logging.error(f"Error while getting the status: {error_message}.")
                with open('media/' + TIMEOUT_FIRE_NAME, "rb") as photo:
                    for user_id in allowed_user_ids:
                        await application.bot.send_photo(
                            chat_id=user_id,
                            photo=photo,
                            caption=f"Error while getting the status: {error_message}."
                        )

        # Extract useful data using the function
        data = extract_address_data(json_data)
        logging.info(data)

        if not data or len(data) < 6:
            logging.error("Invalid data.")
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
                f"{time_key}: {balance}" for time_key, balance in balance_history.items()
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

    # Create the Request object with 10-second timeouts
    req = HTTPXRequest(connect_timeout=10, read_timeout=10, write_timeout=10)

    # Create the Application using the HTTPXRequest object
    application = Application.builder()\
        .token(bot_token)\
        .post_init(post_init)\
        .request(req)\
        .build()

    # Populate with commands in handlers
    for cmd_txt, handler_func in HANDLERS:
        application.add_handler(CommandHandler(cmd_txt, handler_func))

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