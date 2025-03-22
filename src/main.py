import json
import logging
from typing import Tuple, List
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
from jrequests import get_addresses, get_bitcoin_price, get_mas_intant, get_mas_daily

# Configure logging module
logging.basicConfig(
    filename='bot_activity.log',
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

async def hello(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /hello command.')

    if user_id in allowed_user_ids:
        photo_path = 'https://upload.wikimedia.org/wikipedia/en/thumb/9/93/Buddy_christ.jpg/300px-Buddy_christ.jpg'
        await update.message.reply_text('Hey dude!')
        await update.message.reply_photo(photo=photo_path)
    else:
        photo_path = 'https://media1.giphy.com/media/OPU6wzx8JrHna/giphy.gif?cid=6c09b952dldwktjvqrd7lflvvi4p89xcofc6u3z2u7el6pla&ep=v1_internal_gif_by_id&rid=giphy.gif&ct=g'
        await update.message.reply_photo(photo=photo_path)

async def massa_node(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    logging.info(f'User {user_id} used the /massa command.')

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
        await update.message.reply_text('Node status: ' + formatted_string)

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
    # Use of handler for /massa command
    application.add_handler(CommandHandler("massa", massa_node))
    # Use of handler for /btc command
    application.add_handler(CommandHandler("btc", bitcoin))
    # Use of handler for /mas command
    application.add_handler(CommandHandler("mas", mas))
    # Start bot
    application.run_polling()

if __name__ == '__main__':
    main()
