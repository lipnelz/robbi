import logging
import subprocess
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import CallbackContext
from services.system_monitor import get_system_stats
from services.massa_rpc import measure_rpc_latency
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


def _calculate_uptime(balance_history: dict) -> float:
    """
    Calculate node uptime percentage based on balance history entries.
    Assumes one entry per hour = 24 entries in 24h = 100% uptime.
    """
    if not balance_history:
        return 0.0
    
    now = datetime.now()
    cutoff = now - timedelta(hours=24)
    
    entries_in_24h = sum(
        1 for key in balance_history.keys()
        if _is_recent(key, cutoff, now)
    )
    
    # Max 24 entries in 24h = 100%
    uptime = (entries_in_24h / 24) * 100
    return round(min(uptime, 100.0), 1)


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
    """Handle /perf command: display node performance stats (RPC latency, uptime %)."""
    logging.info(f'User {update.effective_user.id} used the /perf command.')
    massa_node_address = context.bot_data['massa_node_address']
    
    try:
        # Measure RPC latency
        perf_data = measure_rpc_latency(logging, massa_node_address)
        
        if "error" in perf_data:
            await update.message.reply_text(f"Error: {perf_data['error']}")
            return
        
        # Calculate uptime from balance history
        balance_history = context.bot_data.get('balance_history', {})
        uptime_percent = _calculate_uptime(balance_history)
        
        formatted_string = (
            f"⚡ Node Performance\n"
            f"-----------\n"
            f"RPC Latency: {perf_data['latency_ms']} ms\n"
            f"Uptime (24h): {uptime_percent}%"
        )
        
        await update.message.reply_text(formatted_string)
    except Exception as e:
        logging.error(f"Error when /perf : {e}")
        await update.message.reply_text("Error retrieving performance stats")
