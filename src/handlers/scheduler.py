import logging
import functools
import asyncio
from datetime import datetime
from telegram.ext import Application
from apscheduler.schedulers.background import BackgroundScheduler
from jrequests import get_addresses
from handlers.node import extract_address_data
from services.history import save_balance_history, filter_last_24h
from config import (
    JOB_SCHED_NAME, NODE_IS_DOWN, NODE_IS_UP,
    TIMEOUT_NAME, TIMEOUT_FIRE_NAME,
)


def run_async_func(application: Application) -> None:
    """Set up the background scheduler for periodic node pinging.
    Creates or reuses an asyncio event loop, then registers a job
    that runs periodic_node_ping every 60 minutes.
    """
    try:
        # Try to reuse an existing event loop, or create a new one
        try:
            loop = asyncio.get_running_loop()
            logging.info("Use the same event loop.")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            logging.info("Create a new event loop.")

        scheduler = BackgroundScheduler()

        # Remove any stale job with the same ID
        if scheduler.get_job(JOB_SCHED_NAME):
            scheduler.remove_job(JOB_SCHED_NAME)
            logging.info(f"Previous job {JOB_SCHED_NAME} removed.")

        # Schedule periodic_node_ping to run every 60 minutes
        logging.info(f"Add periodic job {JOB_SCHED_NAME}.")
        scheduler.add_job(
            functools.partial(run_coroutine_in_loop, periodic_node_ping, application, loop),
            'interval',
            minutes=60,
            id=JOB_SCHED_NAME,
            name=JOB_SCHED_NAME
        )

        if not scheduler.running:
            scheduler.start()
            logging.info("Scheduler started.")
    except Exception as e:
        logging.error(f"Error in run_async_func: {e}")


def run_coroutine_in_loop(coroutine, application, loop) -> None:
    """Run an async coroutine from a synchronous scheduler thread.
    Uses run_coroutine_threadsafe when the loop is already running (thread-safe),
    or run_until_complete when the loop is idle.
    """
    try:
        if loop.is_running():
            # Schedule the coroutine on the running loop from this thread (thread-safe)
            logging.info("Event loop already running, scheduling coroutine.")
            asyncio.run_coroutine_threadsafe(coroutine(application), loop)
        else:
            # Run synchronously on the idle loop
            logging.info("Running coroutine in a new loop.")
            loop.run_until_complete(coroutine(application))
    except Exception as e:
        logging.error(f"Error in run_coroutine_in_loop: {e}")


async def periodic_node_ping(application: Application) -> None:
    """Periodic task (every 60 min) to check node status and notify users.
    Records balance snapshots and sends detailed reports at 7h, 12h and 21h.
    """
    logging.info('Node ping beginning...')
    allowed_user_ids = application.bot_data.get('allowed_user_ids', set())
    balance_history = application.bot_data.get('balance_history', {})
    massa_node_address = application.bot_data.get('massa_node_address', '')

    try:
        # Fetch node data via JSON-RPC
        json_data = get_addresses(logging, massa_node_address)
        if "error" in json_data:
            error_message = json_data["error"]
            # Pick the appropriate error image
            if "timed out" in error_message:
                logging.error("Timeout occurred while trying to get the status.")
                photo_path = f'media/{TIMEOUT_NAME}'
            else:
                logging.error(f"Error while getting the status: {error_message}.")
                photo_path = f'media/{TIMEOUT_FIRE_NAME}'

            # Notify all whitelisted users about the error
            for user_id in allowed_user_ids:
                try:
                    with open(photo_path, "rb") as photo:
                        await application.bot.send_photo(
                            chat_id=user_id,
                            photo=photo,
                            caption=error_message
                        )
                except (FileNotFoundError, OSError) as e:
                    logging.error(f"Error sending photo to {user_id}: {e}")
            return

        # Parse the response into individual fields
        data = extract_address_data(json_data)
        logging.info(data)

        if not data or len(data) < 6:
            logging.error("Invalid data.")
            for user_id in allowed_user_ids:
                await application.bot.send_message(chat_id=user_id, text="Ping failed, invalid data.")
            return

        logging.info(f"Extracted data: {data}")

        # Node is considered down if any NOK count is non-zero or roll count is 0
        node_is_up = not (any(data[4]) or data[1] == 0)

        if not node_is_up:
            # Alert all users immediately when node is down
            for user_id in allowed_user_ids:
                await application.bot.send_message(chat_id=user_id, text=NODE_IS_DOWN)
            logging.info("Node is down.")
        else:
            logging.info("Node is up.")

        # Record current balance snapshot with timestamp
        now = datetime.now()
        hour, minute, day, month = now.hour, now.minute, now.day, now.month
        current_time_key = f"{day:02d}/{month:02d}-{hour:02d}:{minute:02d}"
        balance_history[current_time_key] = f"Balance: {float(data[0]):.2f}"
        save_balance_history(balance_history)

        # Send a detailed status report at scheduled hours (7h, 12h, 21h)
        if node_is_up and hour in (7, 12, 21):
            if balance_history:
                # Compute balance evolution since the first recorded entry
                timestamps = list(balance_history.keys())
                balance_values = [float(balance.split(": ")[1]) for balance in balance_history.values()]

                first_balance = balance_values[0] if balance_values else 0
                first_timestamp = timestamps[0] if timestamps else "N/A"
                last_balance = balance_values[-1] if balance_values else 0
                last_timestamp = timestamps[-1] if timestamps else "N/A"
                balance_change = last_balance - first_balance
                change_percent = ((balance_change) / first_balance * 100) if first_balance != 0 else 0

                # Only show the last 24 hours in the report
                recent_history = filter_last_24h(balance_history)

                change_indicator = "📈" if balance_change >= 0 else "📉"
                tmp_string = (
                    f"{NODE_IS_UP}\n"
                    f"\n"
                    f"💰 Balance Comparison:\n"
                    f"First: {first_balance:.2f} ({first_timestamp})\n"
                    f"Current: {last_balance:.2f} ({last_timestamp})\n"
                    f"Change: {change_indicator} {balance_change:+.2f} ({change_percent:+.2f}%)\n"
                    f"\n"
                    f"📊 Last 24h History:\n"
                    f"{'─' * 40}\n" +
                    ("\n".join(f"{timestamp}: {balance}" for timestamp, balance in recent_history.items())
                     if recent_history else "No data in the last 24h.")
                )
            else:
                tmp_string = NODE_IS_UP

            for user_id in allowed_user_ids:
                await application.bot.send_message(chat_id=user_id, text=tmp_string)

    except Exception as e:
        logging.error(f"Error in periodic_node_ping: {e}")
