import io
import sys
import json
import logging
import threading
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.request import HTTPXRequest
from jrequests import get_addresses
from services.history import load_balance_history
from config import (
    FLUSH_CONFIRM_STATE, HIST_CONFIRM_STATE, COMMANDS_LIST,
    DOCKER_MENU_STATE, DOCKER_START_CONFIRM_STATE, DOCKER_STOP_CONFIRM_STATE,
)
from handlers.node import node, flush, flush_confirm_yes, flush_confirm_no, hist, hist_confirm_yes, hist_confirm_no, docker, docker_start, docker_stop, docker_start_confirm, docker_stop_confirm, docker_cancel
from handlers.price import btc, mas
from handlers.system import hi, temperature, perf
from handlers.scheduler import run_async_func


# Map command names to handler functions
HANDLER_MAP = {
    'hi': hi,
    'node': node,
    'btc': btc,
    'mas': mas,
    'temperature': temperature,
    'perf': perf,
}


def disable_prints() -> None:
    """Redirect stdout and stderr to suppress all print output."""
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()


async def post_init(application: Application) -> None:
    """Register bot commands with Telegram after startup."""
    commands = [BotCommand(command=cmd['cmd_txt'], description=cmd['cmd_desc']) for cmd in COMMANDS_LIST]
    await application.bot.set_my_commands(commands)


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(f"Error handler catch: {context.error}")


def main():
    # Load bot configuration from topology.json
    try:
        with open('topology.json', 'r', encoding='utf-8') as file:
            config = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading topology.json: {e}")
        return

    # Extract credentials and settings from configuration
    bot_token = config.get('telegram_bot_token')
    admin_id = config.get('user_white_list', {}).get('admin')
    if not bot_token or admin_id is None:
        logging.error("Missing required config: 'telegram_bot_token' or 'user_white_list.admin'")
        return
    allowed_user_ids = {str(admin_id)}
    massa_node_address = config.get('massa_node_address')
    ninja_key = config.get('ninja_api_key')
    docker_container_name = config.get('docker_container_name', 'massa-node')

    # Load persisted balance history from JSON file on disk
    balance_history = load_balance_history()

    disable_prints()  # Comment this line to enable prints (DEBUG purpose only)
    logging.info("Starting bot...")

    # Perform an initial node health check at startup
    json_data = get_addresses(logging, massa_node_address)
    if "error" in json_data:
        error_message = json_data["error"]
        if "timed out" in error_message:
            logging.error("Timeout occurred while trying to get the status.")
        else:
            logging.error(f"Error while getting the status: {error_message}")

    # Build the Telegram Application with custom HTTP timeouts
    req = HTTPXRequest(connect_timeout=20, read_timeout=20, write_timeout=20)
    application = Application.builder()\
        .token(bot_token)\
        .post_init(post_init)\
        .request(req)\
        .build()

    # Store shared state in bot_data, accessible via context.bot_data in all handlers.
    # This replaces global variables and allows handlers to share mutable state.
    application.bot_data['allowed_user_ids'] = allowed_user_ids
    application.bot_data['massa_node_address'] = massa_node_address
    application.bot_data['ninja_key'] = ninja_key
    application.bot_data['balance_history'] = balance_history
    application.bot_data['balance_lock'] = threading.Lock()
    application.bot_data['docker_container_name'] = docker_container_name

    # Register simple command handlers (one function per command)
    for cmd in COMMANDS_LIST:
        cmd_txt = cmd['cmd_txt']
        if cmd_txt in HANDLER_MAP:
            application.add_handler(CommandHandler(cmd_txt, HANDLER_MAP[cmd_txt]))

    # Register /flush as a ConversationHandler with inline keyboard confirmation
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

    # Register /hist as a ConversationHandler with inline keyboard confirmation
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

    # Register /docker as a ConversationHandler with menu and inline keyboard confirmation
    docker_handler = ConversationHandler(
        entry_points=[CommandHandler('docker', docker)],
        states={
            DOCKER_MENU_STATE: [
                CallbackQueryHandler(docker_start, pattern='^docker_start$'),
                CallbackQueryHandler(docker_stop, pattern='^docker_stop$')
            ],
            DOCKER_START_CONFIRM_STATE: [
                CallbackQueryHandler(docker_start_confirm, pattern='^docker_start_confirm$'),
                CallbackQueryHandler(docker_cancel, pattern='^docker_cancel$')
            ],
            DOCKER_STOP_CONFIRM_STATE: [
                CallbackQueryHandler(docker_stop_confirm, pattern='^docker_stop_confirm$'),
                CallbackQueryHandler(docker_cancel, pattern='^docker_cancel$')
            ]
        },
        fallbacks=[CommandHandler('docker', docker)]
    )
    application.add_handler(docker_handler)

    application.add_error_handler(error_handler)

    # Start the periodic scheduler (node ping every 60 min) and begin polling
    run_async_func(application)
    application.run_polling()

    logging.info("Bot stopped.")


if __name__ == '__main__':
    main()