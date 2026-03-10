import logging
import functools
import asyncio
from datetime import datetime
import discord
from discord.ext import commands
from apscheduler.schedulers.background import BackgroundScheduler
from jrequests import get_addresses
from handlers.node import extract_address_data
from services.history import save_balance_history, filter_last_24h
from config import (
    JOB_SCHED_NAME, NODE_IS_DOWN, NODE_IS_UP,
    TIMEOUT_NAME, TIMEOUT_FIRE_NAME,
)


def run_async_func(bot: commands.Bot) -> None:
    """Set up the background scheduler for periodic node pinging.
    Creates or reuses an asyncio event loop, then registers a job
    that runs periodic_node_ping every 60 minutes.
    """
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
            functools.partial(run_coroutine_in_loop, periodic_node_ping, bot, loop),
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


def run_coroutine_in_loop(coroutine, bot: commands.Bot, loop) -> None:
    """Run an async coroutine from a synchronous scheduler thread.
    Uses run_coroutine_threadsafe when the loop is already running (thread-safe),
    or run_until_complete when the loop is idle.
    """
    try:
        if loop.is_running():
            logging.info("Event loop already running, scheduling coroutine.")
            future = asyncio.run_coroutine_threadsafe(coroutine(bot), loop)

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
            logging.info("Running coroutine in a new loop.")
            loop.run_until_complete(coroutine(bot))
    except Exception as e:
        logging.error(f"Error in run_coroutine_in_loop: {e}")


async def periodic_node_ping(bot: commands.Bot) -> None:
    """Periodic task (every 60 min) to check node status and notify users via DM.
    Records balance snapshots and sends detailed reports at 7h, 12h and 21h.
    """
    logging.info('Node ping beginning...')
    allowed_user_ids = getattr(bot, 'allowed_user_ids', set())
    balance_history = getattr(bot, 'balance_history', {})
    massa_node_address = getattr(bot, 'massa_node_address', '')

    async def _dm_users(content: str | None = None, file_path: str | None = None) -> None:
        """Send a DM (with optional file) to all whitelisted users."""
        for user_id in allowed_user_ids:
            try:
                user = await bot.fetch_user(int(user_id))
                if file_path:
                    with open(file_path, "rb") as f:
                        await user.send(
                            content=content,
                            file=discord.File(f, filename=file_path.split('/')[-1])
                        )
                elif content:
                    await user.send(content)
            except Exception as e:
                logging.error(f"Error sending DM to {user_id}: {e}")

    try:
        json_data = get_addresses(logging, massa_node_address)
        if "error" in json_data:
            error_message = json_data["error"]
            if "timed out" in error_message:
                logging.error("Timeout occurred while trying to get the status.")
                await _dm_users(content=error_message, file_path=f'media/{TIMEOUT_NAME}')
            else:
                logging.error(f"Error while getting the status: {error_message}.")
                await _dm_users(content=error_message, file_path=f'media/{TIMEOUT_FIRE_NAME}')
            return

        data = extract_address_data(json_data)
        logging.info(data)

        if not data or len(data) < 6:
            logging.error("Invalid data.")
            await _dm_users(content="Ping failed, invalid data.")
            return

        logging.info(f"Extracted data: {data}")

        node_is_up = not (any(data[4]) or data[1] == 0)

        if not node_is_up:
            await _dm_users(content=NODE_IS_DOWN)
            logging.info("Node is down.")
        else:
            logging.info("Node is up.")

        now = datetime.now()
        hour, minute, day, month, year = now.hour, now.minute, now.day, now.month, now.year
        current_time_key = f"{year}/{month:02d}/{day:02d}-{hour:02d}:{minute:02d}"
        lock = getattr(bot, 'balance_lock', None)
        if lock:
            with lock:
                balance_history[current_time_key] = f"Balance: {float(data[0]):.2f}"
                save_balance_history(balance_history)
        else:
            balance_history[current_time_key] = f"Balance: {float(data[0]):.2f}"
            save_balance_history(balance_history)

        if node_is_up and hour in (7, 12, 21):
            if balance_history:
                timestamps = list(balance_history.keys())
                balance_values = [float(balance.split(": ")[1]) for balance in balance_history.values()]

                first_balance = balance_values[0] if balance_values else 0
                first_timestamp = timestamps[0] if timestamps else "N/A"
                last_balance = balance_values[-1] if balance_values else 0
                last_timestamp = timestamps[-1] if timestamps else "N/A"
                balance_change = last_balance - first_balance
                change_percent = ((balance_change) / first_balance * 100) if first_balance != 0 else 0

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

            await _dm_users(content=tmp_string)

    except Exception as e:
        logging.error(f"Error in periodic_node_ping: {e}")
