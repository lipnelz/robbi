import logging
import subprocess
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import CallbackContext
from services.system_monitor import get_system_stats
from services.massa_rpc import DEFAULT_MASSA_RPC_URL, measure_rpc_latency
from services.node_status import load_node_status_history
from handlers.common import auth_required
from config import BUDDY_FILE_NAME


def _get_git_commit_hash() -> str:
    """Return the short git commit hash, or 'unknown' on failure."""
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return 'unknown'


@auth_required
async def hi(update: Update, context: CallbackContext) -> None:
    """Handle /hi command: send a greeting message with a fun image."""
    logging.info(f'User {update.effective_user.id} used the /hi command.')
    commit_hash = _get_git_commit_hash()
    await update.message.reply_text(f'Hey dude! (version: {commit_hash})')
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
            f"🌡️ Container-Visible System Status\n"
            f"-----------\n"
        )

        # Per-sensor temperature details (Linux only, via psutil)
        if "temperature_details" in stats:
            formatted_string += "🌡️ Temperatures:\n"
            for temp_info in stats['temperature_details']:
                formatted_string += f"  {temp_info['sensor']} {temp_info['label']}: {temp_info['current']}°C\n"
            if "temperature_avg" in stats:
                formatted_string += f"  Average: {stats['temperature_avg']}°C\n"

        formatted_string += (
            f"-----------\n"
            f"Container-Visible CPU Usage: {stats['cpu_percent']}%\n"
            f"-----------\n"
        )

        # Per-core CPU usage breakdown
        if "cpu_cores" in stats:
            formatted_string += "CPU Cores:\n"
            for core_info in stats['cpu_cores']:
                formatted_string += f"  Core {core_info['core']}: {core_info['percent']}%\n"

        formatted_string += (
            f"-----------\n"
            f"Container-Visible RAM Usage: {stats['ram_percent']}%\n"
            f"RAM Available: {stats['ram_available_gb']} GB / {stats['ram_total_gb']} GB"
        )

        await update.message.reply_text(formatted_string)
    except Exception as e:
        logging.error(f"Error when /temperature : {e}")
        await update.message.reply_text("Error retrieving system stats")


def _calculate_observed_availability(node_status_history: dict, now: datetime = None):
    """
    Calculate the share of successful scheduled checks in the last 24 hours.

    This is observed availability, not continuous uptime between checks.
    """
    now = now or datetime.now()
    cutoff = now - timedelta(hours=24)
    checks = []
    for timestamp, is_up in node_status_history.items():
        try:
            checked_at = datetime.fromisoformat(timestamp)
        except (TypeError, ValueError):
            continue
        if checked_at.tzinfo is not None:
            checked_at = checked_at.astimezone().replace(tzinfo=None)
        if cutoff <= checked_at <= now and isinstance(is_up, bool):
            checks.append(is_up)
    if not checks:
        return None, 0, 0
    successful_checks = sum(checks)
    return round(successful_checks / len(checks) * 100, 1), successful_checks, len(checks)


def _is_recent(key: str, cutoff: datetime, now: datetime) -> bool:
    """
    Check if a history key is within the last 24 hours.
    Supports both new (YYYY/MM/DD-HH:MM) and legacy (DD/MM-HH:MM) formats.
    """
    try:
        dt = datetime.strptime(key, "%Y/%m/%d-%H:%M")
    except ValueError:
        try:
            dt = datetime.strptime(key, "%d/%m-%H:%M").replace(year=now.year)
            if dt > now + timedelta(hours=1):
                dt = dt.replace(year=now.year - 1)
        except ValueError:
            return False
    return dt >= cutoff


@auth_required
async def perf(update: Update, context: CallbackContext) -> None:
    """Handle /perf command: display RPC latency and observed node availability."""
    logging.info(f'User {update.effective_user.id} used the /perf command.')
    massa_node_address = context.bot_data['massa_node_address']
    massa_node_rpc_url = context.bot_data.get('massa_node_rpc_url', DEFAULT_MASSA_RPC_URL)
    
    try:
        # Measure RPC latency
        perf_data = measure_rpc_latency(logging, massa_node_address, massa_node_rpc_url)
        
        if "error" in perf_data:
            await update.message.reply_text(f"Error: {perf_data['error']}")
            return
        
        availability, successful_checks, check_count = _calculate_observed_availability(
            load_node_status_history()
        )
        availability_text = (
            f"Observed availability (24h): {availability}% "
            f"({successful_checks}/{check_count} successful checks)"
            if availability is not None
            else "Observed availability (24h): no scheduled checks recorded"
        )

        formatted_string = (
            f"⚡ Node Performance\n"
            f"-----------\n"
            f"RPC Latency: {perf_data['latency_ms']} ms\n"
            f"{availability_text}"
        )
        
        await update.message.reply_text(formatted_string)
    except Exception as e:
        logging.error(f"Error when /perf : {e}")
        await update.message.reply_text("Error retrieving performance stats")
