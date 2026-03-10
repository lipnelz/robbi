import logging
import asyncio
import subprocess
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from jrequests import get_system_stats, measure_rpc_latency
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


def setup_system_commands(bot: commands.Bot) -> None:
    """Register /hi, /temperature and /perf slash commands on the bot's application command tree."""

    @bot.tree.command(name='hi', description='Say hi to Robbi')
    @auth_required
    async def hi(interaction: discord.Interaction) -> None:
        """Handle /hi command: send a greeting message with a fun image."""
        logging.info(f'User {interaction.user.id} used the /hi command.')
        await interaction.response.defer()
        commit_hash = _get_git_commit_hash()
        await interaction.followup.send(f'Hey dude! (version: {commit_hash})')
        await interaction.followup.send(file=discord.File(f'media/{BUDDY_FILE_NAME}'))

    @bot.tree.command(name='temperature', description='Get system temperature, CPU and RAM')
    @auth_required
    async def temperature(interaction: discord.Interaction) -> None:
        """Handle /temperature command: display per-sensor temps, per-core CPU and RAM usage."""
        logging.info(f'User {interaction.user.id} used the /temperature command.')
        await interaction.response.defer()

        try:
            stats = get_system_stats(logging)
            if "error" in stats:
                error_message = stats["error"]
                logging.error(f"Error while getting system stats: {error_message}")
                await interaction.followup.send(f"Error: {error_message}")
                return

            formatted_string = (
                "🌡️ System Status\n"
                "-----------\n"
            )

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

            if "cpu_cores" in stats:
                formatted_string += "CPU Cores:\n"
                for core_info in stats['cpu_cores']:
                    formatted_string += f"  Core {core_info['core']}: {core_info['percent']}%\n"

            formatted_string += (
                f"-----------\n"
                f"RAM Usage: {stats['ram_percent']}%\n"
                f"RAM Available: {stats['ram_available_gb']} GB / {stats['ram_total_gb']} GB"
            )

            await interaction.followup.send(formatted_string)
        except Exception as e:
            logging.error(f"Error when /temperature : {e}")
            await interaction.followup.send("Error retrieving system stats")

    @bot.tree.command(name='perf', description='Get node performance stats (RPC latency, uptime)')
    @auth_required
    async def perf(interaction: discord.Interaction) -> None:
        """Handle /perf command: display node performance stats (RPC latency, uptime %)."""
        logging.info(f'User {interaction.user.id} used the /perf command.')
        await interaction.response.defer()
        massa_node_address = interaction.client.massa_node_address

        try:
            loop = asyncio.get_running_loop()
            perf_data = await loop.run_in_executor(
                None, measure_rpc_latency, logging, massa_node_address
            )

            if "error" in perf_data:
                await interaction.followup.send(f"Error: {perf_data['error']}")
                return

            balance_history = interaction.client.balance_history
            uptime_percent = _calculate_uptime(balance_history)

            formatted_string = (
                f"⚡ Node Performance\n"
                f"-----------\n"
                f"RPC Latency: {perf_data['latency_ms']} ms\n"
                f"Uptime (24h): {uptime_percent}%"
            )

            await interaction.followup.send(formatted_string)
        except Exception as e:
            logging.error(f"Error when /perf : {e}")
            await interaction.followup.send("Error retrieving performance stats")
