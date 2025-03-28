import os
import json
import logging
import functools
import asyncio
import plotly.graph_objs as go
import plotly.io as pio
from datetime import datetime
from typing import Tuple, List
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, CallbackContext
from jrequests import get_addresses, get_bitcoin_price, get_mas_intant, get_mas_daily
from apscheduler.schedulers.background import BackgroundScheduler


LOG_FILE_NAME = 'bot_activity.log'
PNG_FILE_NAME = 'plot.png'
BUDDY_FILE_NAME = 'Buddy_christ.jpg'
PAT_FILE_NAME = 'patrick.gif'

# String constants
HI_CMD_TXT = 'hi'
HI_CMD_DESC_TXT = 'Say hi to Robbi'
NODE_CMD_TXT = 'node'
NODE_CMD_DESC_TXT = 'Get your node results'
BTC_CMD_TXT = 'btc'
BTC_CMD_DESC_TXT = 'Get BTC current price'
MAS_CMD_TXT = 'mas'
MAS_CMD_DESC_TXT = 'Get MAS current price'
FLUSH_CMD_TXT = 'flush'
FLUSH_CMD_DESC_TXT = 'Flush local logs'
NODE_IS_DOWN = 'Node is down'

COMMANDS_LIST = [
    {
        'id': 0,
        'cmd_txt': HI_CMD_TXT,
        'cmd_desc': HI_CMD_DESC_TXT
    },
    {
        'id': 1,
        'cmd_txt': NODE_CMD_TXT,
        'cmd_desc': NODE_CMD_DESC_TXT
    },
    {
        'id': 2,
        'cmd_txt': BTC_CMD_TXT,
        'cmd_desc': BTC_CMD_DESC_TXT
    },
    {
        'id': 3,
        'cmd_txt': MAS_CMD_TXT,
        'cmd_desc': MAS_CMD_DESC_TXT
    },
    {
        'id': 4,
        'cmd_txt': FLUSH_CMD_TXT,
        'cmd_desc': FLUSH_CMD_DESC_TXT
    }
]

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
prev_active_rolls = []
bot_token = ""

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

def create_png_pot(cycles: int, nok_counts: int, ok_counts: int) -> str:
        """
        Creates a line plot with markers for OK and NOK counts over multiple cycles,
        and saves the plot as a PNG image.

        :param cycles(int): A list or array of integers representing the cycles for which counts are recorded.
        :param nok_counts(int): A list or array of integers representing the NOK counts for each cycle.
        :param ok_counts(int): A list or array of integers representing the OK counts for each cycle.

        :return(str): The file path of the generated PNG image.
        """
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=cycles,
            y=nok_counts,
            mode='lines+markers',
            name='NOK Counts',
            line=dict(color='red')
        ))

        fig.add_trace(go.Scatter(
            x=cycles,
            y=ok_counts,
            mode='lines+markers',
            name='OK Counts',
            line=dict(color='blue')
        ))

        fig.update_layout(
            title='Validation per Cycle',
            xaxis_title='Cycle',
            yaxis_title='Count',
            xaxis=dict(tickformat='.0f')
        )

        # Save the plot as a PNG file
        image_path = PNG_FILE_NAME
        pio.write_image(fig, image_path)

        return image_path

async def hello(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /hello command.')

    if user_id in allowed_user_ids:
        photo_path = 'media/' + BUDDY_FILE_NAME
        await update.message.reply_text('Hey dude!')
        await update.message.reply_photo(photo=photo_path)
    else:
        photo_path = 'media/' + PAT_FILE_NAME
        await update.message.reply_photo(photo=photo_path)

async def massa_node(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /node command.')

    if user_id in allowed_user_ids:
        # Get new data
        json_data = get_addresses(logging, massa_node_address)

        # Extract useful data using the function
        final_balance, final_roll_count, cycles, ok_counts, nok_counts, active_rolls = extract_address_data(json_data)
        formatted_string = (
            f"Final Balance: {final_balance}\n"
            f"Final Roll Count: {final_roll_count}\n"
            f"OK Counts: {ok_counts}\n"
            f"NOK Counts: {nok_counts}\n"
            f"Active Rolls: {active_rolls}"
        )
        print(formatted_string)
        await update.message.reply_text('Node status: ' + formatted_string)

        # Create graph from data and save to PNG_FILE_NAME
        image_path = create_png_pot(cycles, nok_counts, ok_counts)

        # Check if the image file was created successfully
        if os.path.exists(image_path):
            try:
                # Send the image via Telegram with a timeout
                await update.message.reply_photo(photo=image_path)
            finally:
                # Delete the image file after sending
                os.remove(image_path)
                print(f"{image_path} has been deleted.")
        else:
            logging.error("Image file was not created successfully.")

async def remove_logs(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /flush /clean command.')

    if user_id in allowed_user_ids:
        if os.path.exists(LOG_FILE_NAME):
            try:
                # Clear the log file at runtime
                with open(LOG_FILE_NAME, 'w'):
                    pass  # This will clear the file content
                message = f"{LOG_FILE_NAME} has been cleared."
                print(message)
                await update.message.reply_text(message)
            except IOError as e:
                logging.error(f"Error clearing the log file: {e}")
                await update.message.reply_text("An error occurred while clearing the log file.")
        else:
            logging.warning(f"Log file {LOG_FILE_NAME} does not exist.")
            await update.message.reply_text(f"Log file {LOG_FILE_NAME} does not exist.")

async def bitcoin(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /btc command.')

    if user_id in allowed_user_ids:
        data = get_bitcoin_price(logging, ninja_key)
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

async def mas(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /mas command.')

    if user_id in allowed_user_ids:
        current_avg_price = get_mas_intant(logging)
        ticker_price_change_stats = get_mas_daily(logging)
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

HANDLERS = [
    (COMMANDS_LIST[0]['cmd_txt'], hello),
    (COMMANDS_LIST[1]['cmd_txt'], massa_node),
    (COMMANDS_LIST[2]['cmd_txt'], bitcoin),
    (COMMANDS_LIST[3]['cmd_txt'], mas),
    (COMMANDS_LIST[4]['cmd_txt'], remove_logs)
]

async def post_init(application: Application) -> None:
    commands = [
        BotCommand(command=cmd['cmd_txt'], description=cmd['cmd_desc'])
        for cmd in COMMANDS_LIST
    ]
    await application.bot.set_my_commands(commands)

def run_async_func(application: Application) -> None:
    loop = asyncio.new_event_loop()
    scheduler = BackgroundScheduler()
    hour = datetime.now().hour

    if 22 <= hour < 6:
        # Use functools.partial to pass the bot instance correctly
        scheduler.add_job(functools.partial(run_coroutine_in_loop, periodic_node_ping(application), loop), 'interval', minutes=120)
    elif 6 <= hour < 22:
        scheduler.add_job(functools.partial(run_coroutine_in_loop, periodic_node_ping(application), loop), 'interval', minutes=60)
    else:
        logging.error(f'Should not happen {hour}')

    scheduler.start()

def run_coroutine_in_loop(coroutine, loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coroutine)

async def periodic_node_ping(application: Application) -> None:
    logging.info(f'Node ping')
    json_data = get_addresses(logging, massa_node_address)
    # Extract useful data using the function
    final_balance, final_roll_count, cycles, ok_counts, nok_counts, active_rolls = extract_address_data(json_data)
    logging.info((any(element != 0 for element in nok_counts) != 0))
    logging.info(active_rolls != prev_active_rolls)
    if((any(element != 0 for element in nok_counts) != 0) or (active_rolls != prev_active_rolls)):
        for user_id in allowed_user_ids:
            run_async_func(application) # Restart the scheduler
            await application.bot.send_message(chat_id=user_id, text=NODE_IS_DOWN)


def main():
    global allowed_user_ids
    global massa_node_address
    global ninja_key
    global bot_token
    global prev_active_rolls

    try:
        # Open 'topology.json' file
        with open('topology.json', 'r', encoding='utf-8') as file:
            tmp_json = json.load(file)
            bot_token = tmp_json.get('telegram_bot_token')
            # Update globals
            allowed_user_ids = {str(tmp_json.get('user_white_list', {}).get('admin'))}
            massa_node_address = tmp_json.get('massa_node_address')
            ninja_key = tmp_json.get('ninja_api_key')
    except FileNotFoundError:
        logging.error("The file 'topology.json' was not found.")
        return
    except json.JSONDecodeError:
        logging.error("Error decoding the JSON file.")
        return

    # Get node info at bot startup
    json_data = get_addresses(logging, massa_node_address)
    final_balance, final_roll_count, cycles, ok_counts, nok_counts, active_rolls = extract_address_data(json_data)
    prev_active_rolls = list(active_rolls)

    # Use of ApplicationBuilder to create app
    application = Application.builder().token(bot_token).post_init(post_init).build()

    # Populate with commands in handlers
    for cmd_txt, handler_func in HANDLERS:
        application.add_handler(CommandHandler(cmd_txt, handler_func))

    # Start the scheduler
    run_async_func(application)
    # Start bot
    application.run_polling()

if __name__ == '__main__':
    main()
