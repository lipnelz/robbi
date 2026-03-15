import logging
import functools
import asyncio
from datetime import datetime
from telegram.ext import Application
from apscheduler.schedulers.background import BackgroundScheduler
from services.massa_rpc import get_addresses
from services.system_monitor import get_system_stats
from handlers.node import extract_address_data
from services.history import (
    save_balance_history, filter_last_24h, filter_since_midnight,
    get_entry_balance, get_entry_temperature,
    make_time_key, build_balance_entry, format_history_entry,
)
from config import (
    JOB_SCHED_NAME, NODE_IS_DOWN, NODE_IS_UP,
    TIMEOUT_NAME, TIMEOUT_FIRE_NAME,
)


def _get_application_bot_data(application: Application) -> dict:
    """Return application.bot_data when available, else a safe local dict."""
    bot_data = getattr(application, 'bot_data', None)
    if not isinstance(bot_data, dict):
        bot_data = {}
        try:
            application.bot_data = bot_data
        except Exception:
            # Some mocked objects may reject attribute assignment.
            pass
    return bot_data


def run_async_func(application: Application) -> None:
    """Set up the background scheduler for periodic node pinging.
    Creates or reuses an asyncio event loop, then registers a job
    that runs periodic_node_ping every 60 minutes.
    """
    try:
        bot_data = _get_application_bot_data(application)
        existing_scheduler = bot_data.get('scheduler')
        if existing_scheduler and existing_scheduler.running:
            logging.info("Scheduler already running, skipping setup.")
            return

        # Try to reuse an existing event loop, or create a new one
        try:
            loop = asyncio.get_running_loop()
            owns_loop = False
            logging.info("Use the same event loop.")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            owns_loop = True
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

        bot_data['scheduler'] = scheduler
        bot_data['scheduler_loop'] = loop
        bot_data['scheduler_owns_loop'] = owns_loop
    except Exception as e:
        logging.error(f"Error in run_async_func: {e}")


def stop_async_func(application: Application) -> None:
    """Shutdown the background scheduler and close owned loop resources."""
    bot_data = _get_application_bot_data(application)
    scheduler = bot_data.get('scheduler')
    loop = bot_data.get('scheduler_loop')
    owns_loop = bot_data.get('scheduler_owns_loop', False)

    if scheduler is not None:
        try:
            if scheduler.running:
                scheduler.shutdown(wait=False)
                logging.info("Scheduler stopped.")
        except Exception as e:
            logging.error(f"Error stopping scheduler: {e}")

    if owns_loop and loop is not None:
        try:
            if not loop.is_running() and not loop.is_closed():
                loop.close()
                logging.info("Scheduler loop closed.")
        except Exception as e:
            logging.error(f"Error closing scheduler loop: {e}")


def run_coroutine_in_loop(coroutine, application, loop) -> None:
    """Run an async coroutine from a synchronous scheduler thread.
    Uses run_coroutine_threadsafe when the loop is already running (thread-safe),
    or run_until_complete when the loop is idle.
    """
    try:
        if loop.is_running():
            # Schedule the coroutine on the running loop from this thread (thread-safe)
            logging.info("Event loop already running, scheduling coroutine.")
            future = asyncio.run_coroutine_threadsafe(coroutine(application), loop)

            # Ensure any exceptions raised by the coroutine are logged instead of being silently swallowed
            def _log_future_exception(f):
                exc = f.exception()
                if exc is not None:
                    logging.error(
                        "Unhandled exception in scheduled coroutine %s: %s",
                        getattr(coroutine, "__name__", repr(coroutine)),
                        exc,
                    )

            future.add_done_callback(_log_future_exception)
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

        if data is None:
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

        # Record current balance snapshot with timestamp, including system resources
        now = datetime.now()
        hour = now.hour
        current_time_key = make_time_key(now)

        # Collect CPU temperature and RAM usage
        system_stats = get_system_stats(logging)
        entry = build_balance_entry(float(data[0]), system_stats)

        lock = application.bot_data.get('balance_lock')
        if lock:
            with lock:
                balance_history[current_time_key] = entry
                save_balance_history(balance_history)
        else:
            balance_history[current_time_key] = entry
            save_balance_history(balance_history)

        # Send a detailed status report at scheduled hours (7h, 12h, 21h)
        if node_is_up and hour in (7, 12, 21):
            if balance_history:
                # Get entries from the last 24 hours (rolling window) and since today's midnight
                recent_history = filter_last_24h(balance_history)
                midnight_history = filter_since_midnight(balance_history)

                # Pre-compute oldest balance in the 24h rolling window
                if recent_history:
                    oldest_24h_timestamp = next(iter(recent_history))
                    oldest_24h_balance = get_entry_balance(next(iter(recent_history.values())))
                else:
                    oldest_24h_timestamp = None
                    oldest_24h_balance = None

                # "First" is the first balance recorded after midnight today
                if midnight_history:
                    first_timestamp = next(iter(midnight_history))
                    first_balance = get_entry_balance(next(iter(midnight_history.values())))
                elif oldest_24h_balance is not None:
                    first_timestamp = oldest_24h_timestamp
                    first_balance = oldest_24h_balance
                else:
                    first_timestamp = "N/A"
                    first_balance = 0

                # "Current" is the most recently recorded balance
                last_timestamp = current_time_key
                last_balance = float(data[0])

                # "Change" is the difference over the last 24 hours (rolling window)
                if oldest_24h_balance is not None:
                    balance_change = last_balance - oldest_24h_balance
                    change_percent = (balance_change / oldest_24h_balance * 100) if oldest_24h_balance != 0 else 0
                else:
                    balance_change = 0
                    change_percent = 0

                change_indicator = "📈" if balance_change >= 0 else "📉"

                # Compute 24h average temperature from resource entries
                temp_samples = [
                    get_entry_temperature(v)
                    for v in recent_history.values()
                    if get_entry_temperature(v) is not None
                ]
                avg_temp_str = (
                    f"🌡️ Avg CPU Temp (24h): {sum(temp_samples) / len(temp_samples):.1f}°C\n"
                    if temp_samples else ""
                )

                tmp_string = (
                    f"{NODE_IS_UP}\n"
                    f"\n"
                    f"💰 Balance Comparison:\n"
                    f"First: {first_balance:.2f} ({first_timestamp})\n"
                    f"Current: {last_balance:.2f} ({last_timestamp})\n"
                    f"Change: {change_indicator} {balance_change:+.2f} ({change_percent:+.2f}%)\n"
                    f"\n"
                    f"{avg_temp_str}"
                    f"📊 Last 24h History:\n"
                    f"{'─' * 40}\n" +
                    ("\n".join(
                        format_history_entry(timestamp, v)
                        for timestamp, v in recent_history.items()
                    ) if recent_history else "No data in the last 24h.")
                )
            else:
                tmp_string = NODE_IS_UP

            for user_id in allowed_user_ids:
                await application.bot.send_message(chat_id=user_id, text=tmp_string)

    except Exception as e:
        logging.error(f"Error in periodic_node_ping: {e}")
