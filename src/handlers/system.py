import logging
from telegram import Update
from telegram.ext import CallbackContext
from jrequests import get_system_stats
from handlers.common import auth_required
from config import BUDDY_FILE_NAME


@auth_required
async def hi(update: Update, context: CallbackContext) -> None:
    """Handle /hi command: send a greeting message with a fun image."""
    logging.info(f'User {update.effective_user.id} used the /hi command.')
    await update.message.reply_text('Hey dude!')
    await update.message.reply_photo(photo=f'media/{BUDDY_FILE_NAME}')


@auth_required
async def temperature(update: Update, context: CallbackContext) -> None:
    """Handle /temperature command: display per-sensor temps, per-core CPU and RAM usage."""
    logging.info(f'User {update.effective_user.id} used the /temperature command.')

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

        # Per-sensor temperature details (Linux only, via psutil)
        if "temperature_details" in stats:
            formatted_string += "🌡️ Temperatures:\n"
            for temp_info in stats['temperature_details']:
                formatted_string += f"  {temp_info['sensor']} {temp_info['label']}: {temp_info['current']}°C\n"
            if "temperature_avg" in stats:
                formatted_string += f"  Average: {stats['temperature_avg']}°C\n"
        elif "temperature_celsius" in stats:
            # Fallback: single aggregated temperature value
            formatted_string += f"Temperature: {stats['temperature_celsius']}°C\n"

        formatted_string += (
            f"-----------\n"
            f"CPU Usage Global: {stats['cpu_percent']}%\n"
            f"-----------\n"
        )

        # Per-core CPU usage breakdown
        if "cpu_cores" in stats:
            formatted_string += "CPU Cores:\n"
            for core_info in stats['cpu_cores']:
                formatted_string += f"  Core {core_info['core']}: {core_info['percent']}%\n"

        formatted_string += (
            f"-----------\n"
            f"RAM Usage: {stats['ram_percent']}%\n"
            f"RAM Available: {stats['ram_available_gb']} GB / {stats['ram_total_gb']} GB"
        )

        await update.message.reply_text(formatted_string)
    except Exception as e:
        logging.error(f"Error when /temperature : {e}")
        await update.message.reply_text("Error retrieving system stats")
