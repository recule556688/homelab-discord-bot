"""System extension - server health, ping, and commands list."""

import time
import discord
import psutil
from discord import app_commands

from ..bot import bot, tree
from ..config import TEST_GUILD_ID
from ..utils import format_uptime


@tree.command(
    name="serverhealth",
    description="Check current server health stats.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def server_health(interaction: discord.Interaction):
    """Display detailed server health statistics."""
    await interaction.response.defer(ephemeral=True)

    try:
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_str = format_uptime(uptime_seconds)

        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        cpu_temp = None
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if "coretemp" in temps:
                    cpu_temp = max(temp.current for temp in temps["coretemp"])
        except Exception:
            cpu_temp = "N/A"

        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        try:
            net_io = psutil.net_io_counters()
            net_bytes_sent = net_io.bytes_sent
            net_bytes_recv = net_io.bytes_recv
            try:
                net_connections = len(psutil.net_connections())
            except (psutil.AccessDenied, PermissionError):
                net_connections = "N/A (Permission denied)"
        except Exception:
            net_bytes_sent = 0
            net_bytes_recv = 0
            net_connections = "N/A"

        embed = discord.Embed(title="", description="", color=0x00B8FF)

        embed.add_field(
            name="\n💻 SYSTEM HEALTH DASHBOARD 📊",
            value="━━━━━━━━━━━━━━━━━━━━━━━━",
            inline=False,
        )

        system_stats = (
            f"```ansi\n"
            f"\u001b[1;36mSYSTEM OVERVIEW\u001b[0m\n"
            f"┌──────────────────────────┐\n"
            f"│ Uptime: \u001b[1;33m{uptime_str}\u001b[0m\n"
            f"│ CPU Cores: \u001b[1;33m{cpu_count}\u001b[0m\n"
            f"│ CPU Freq: \u001b[1;33m{cpu_freq.current:.0f}MHz\u001b[0m\n"
            f"│ Temperature: \u001b[1;33m{cpu_temp if cpu_temp else 'N/A'}°C\u001b[0m\n"
            f"└──────────────────────────┘\n"
            f"```"
        )
        embed.add_field(name="", value=system_stats, inline=False)

        resource_stats = (
            f"```ansi\n"
            f"\u001b[1;35mRESOURCE USAGE\u001b[0m\n"
            f"┌──────────────────────────┐\n"
            f"│ CPU: \u001b[1;{33 if cpu_usage < 80 else 31}m{cpu_usage}%\u001b[0m\n"
            f"│ RAM: \u001b[1;{33 if memory.percent < 80 else 31}m{memory.percent}%\u001b[0m ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)\n"
            f"│ Swap: \u001b[1;{33 if swap.percent < 80 else 31}m{swap.percent}%\u001b[0m ({swap.used / (1024**3):.1f}GB / {swap.total / (1024**3):.1f}GB)\n"
            f"└──────────────────────────┘\n"
            f"```"
        )
        embed.add_field(name="", value=resource_stats, inline=True)

        network_stats = (
            f"```ansi\n"
            f"\u001b[1;35mNETWORK STATUS\u001b[0m\n"
            f"┌──────────────────────────┐\n"
            f"│ Connections: \u001b[1;33m{net_connections}\u001b[0m\n"
            f"│ Sent: \u001b[1;36m{net_bytes_sent / (1024**2):.1f}MB\u001b[0m\n"
            f"│ Received: \u001b[1;36m{net_bytes_recv / (1024**2):.1f}MB\u001b[0m\n"
            f"└──────────────────────────┘\n"
            f"```"
        )
        embed.add_field(name="", value=network_stats, inline=True)

        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(
            text=f"📊 Stats as of {current_time} • Use /serverhealth to refresh",
            icon_url="https://cdn.iconscout.com/icon/free/png-256/refresh-1781197-1518571.png",
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch server health:\n```ansi\n\u001b[1;31m{str(e)}\u001b[0m```",
            color=0xFF0000,
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)


@tree.command(
    name="ping",
    description="Check the bot's latency.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def ping(interaction: discord.Interaction):
    """Check bot latency."""
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(
        f"🏓 Pong! Latency: {latency}ms", ephemeral=True
    )


@tree.command(
    name="commands",
    description="List all available commands",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def list_commands(interaction: discord.Interaction):
    """List all available slash commands."""
    commands_list = []
    for cmd in tree.get_commands(guild=discord.Object(id=TEST_GUILD_ID)):
        commands_list.append(f"`/{cmd.name}` - {cmd.description}")
    embed = discord.Embed(
        title="🤖 Available Commands",
        description="\n".join(commands_list),
        color=0x00FF00,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
