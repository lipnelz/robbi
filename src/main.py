import os
import json
import logging
import plotly.graph_objs as go
import plotly.io as pio
from typing import Tuple, List
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
from jrequests import get_addresses, get_bitcoin_price, get_mas_intant, get_mas_daily


LOG_FILE_NAME = 'bot_activity.log'
PNG_FILE_NAME = 'plot.png'
BUDDY_FILE_NAME = 'Buddy_christ.jpg'
PAT_FILE_NAME = 'patrick.gif'

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

def extract_data(json_data: dict) -> Tuple[str, int, List[int], List[int], List[int]]:
    """
    Extract useful JSON response data.

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
        return final_balance, final_roll_count, cycles, ok_counts, nok_counts
    return "", 0, [], [], []

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
        final_balance, final_roll_count, cycles, ok_counts, nok_counts = extract_data(json_data)
        formatted_string = (
            f"Final Balance: {final_balance}\n"
            f"Final Roll Count: {final_roll_count}\n"
            f"OK Counts: {ok_counts}\n"
            f"NOK Counts: {nok_counts}"
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
            f"Price: {float(data['price']):.2f}\n"
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

def main():
    global allowed_user_ids
    global massa_node_address
    global ninja_key

    try:
        # Open 'topology.json' file
        with open('topology.json', 'r', encoding='utf-8') as file:
            tmp_json = json.load(file)
            token = tmp_json.get('telegram_bot_token')
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

    # Use of ApplicationBuilder to create app
    application = ApplicationBuilder().token(token).build()
    # Use of handler for /hello or /hi command
    application.add_handler(CommandHandler("hello", hello))
    application.add_handler(CommandHandler("hi", hello))
    # Use of handler for /node command
    application.add_handler(CommandHandler("node", massa_node))
    # Use of handler for /btc command
    application.add_handler(CommandHandler("btc", bitcoin))
    # Use of handler for /mas command
    application.add_handler(CommandHandler("mas", mas))
    # Use of handler for /flush, /clean command
    application.add_handler(CommandHandler("flush", remove_logs))
    application.add_handler(CommandHandler("clean", remove_logs))
    # Start bot
    application.run_polling()

if __name__ == '__main__':
    main()
