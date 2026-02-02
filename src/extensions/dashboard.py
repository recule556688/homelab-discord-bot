"""Dashboard extension - system health dashboard with auto-refresh."""

import os
import time
import discord
from discord import app_commands
from discord.ext import tasks

from ..bot import bot, tree
from ..config import DASHBOARD_STATE_FILE, TEST_GUILD_ID
from ..utils import format_uptime, load_dashboard_state, save_dashboard_state

# Global variables for dashboard state
dashboard_message = None
dashboard_channel = None


def create_health_embed():
    """Create the system health embed for the dashboard."""
    import psutil

    uptime_seconds = time.time() - psutil.boot_time()
    uptime_str = format_uptime(uptime_seconds)

    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    try:
        net_io = psutil.net_io_counters()
        net_bytes_sent = net_io.bytes_sent / (1024**2)
        net_bytes_recv = net_io.bytes_recv / (1024**2)
    except Exception:
        net_bytes_sent = 0
        net_bytes_recv = 0

    embed = discord.Embed(title="", description="", color=0x00B8FF)

    embed.add_field(
        name="\n💻 LIVE SYSTEM DASHBOARD 📊",
        value="━━━━━━━━━━━━━━━━━━━━━━━━",
        inline=False,
    )

    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)

    system_stats = (
        f"```ansi\n"
        f"\u001b[1;36mSYSTEM OVERVIEW\u001b[0m\n"
        f"┌──────────────────────────┐\n"
    )
    if days > 0:
        system_stats += f"│ Uptime: \u001b[1;31m{days}d \u001b[1;33m{hours}h {minutes}m {seconds}s\u001b[0m\n"
    else:
        system_stats += f"│ Uptime: \u001b[1;33m{hours}h {minutes}m {seconds}s\u001b[0m\n"
    system_stats += f"└──────────────────────────┘\n```"
    embed.add_field(name="", value=system_stats, inline=False)

    resource_stats = (
        f"```ansi\n"
        f"\u001b[1;35mRESOURCE USAGE\u001b[0m\n"
        f"┌──────────────────────────┐\n"
        f"│ CPU: \u001b[1;{33 if cpu_usage < 80 else 31}m{cpu_usage}%\u001b[0m\n"
        f"│ RAM: \u001b[1;{33 if memory.percent < 80 else 31}m{memory.percent}%\u001b[0m\n"
        f"│ Used: \u001b[1;36m{memory.used / (1024**3):.1f}GB\u001b[0m / \u001b[1;33m{memory.total / (1024**3):.1f}GB\u001b[0m\n"
        f"└──────────────────────────┘\n"
        f"```"
    )
    embed.add_field(name="", value=resource_stats, inline=True)

    network_stats = (
        f"```ansi\n"
        f"\u001b[1;35mNETWORK STATUS\u001b[0m\n"
        f"┌──────────────────────────┐\n"
        f"│ Upload: \u001b[1;32m{net_bytes_sent:.1f} MB\u001b[0m\n"
        f"│ Download: \u001b[1;32m{net_bytes_recv:.1f} MB\u001b[0m\n"
        f"└──────────────────────────┘\n"
        f"```"
    )
    embed.add_field(name="", value=network_stats, inline=True)

    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    embed.set_footer(
        text=f"🔄 Auto-updates every 30s • Last update: {current_time}",
        icon_url="https://cdn.iconscout.com/icon/free/png-256/refresh-1781197-1518571.png",
    )
    return embed


@tree.command(
    name="dashboard",
    description="Start a persistent server health dashboard.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def dashboard(interaction: discord.Interaction):
    """Start the system health dashboard."""
    global dashboard_message, dashboard_channel

    await interaction.response.defer()

    try:
        # Delete existing dashboard if it exists
        try:
            state = load_dashboard_state()
            if state:
                try:
                    old_channel = await bot.fetch_channel(state["channel_id"])
                    old_message = await old_channel.fetch_message(state["message_id"])
                    await old_message.delete()
                except Exception:
                    pass

                if os.path.exists(DASHBOARD_STATE_FILE):
                    os.remove(DASHBOARD_STATE_FILE)
        except Exception:
            pass

        dashboard_channel = interaction.channel

        await interaction.followup.send(
            "🚀 Starting system dashboard... (This message will disappear)",
            ephemeral=True,
        )

        embed = create_health_embed()
        dashboard_message = await dashboard_channel.send(embed=embed)

        save_dashboard_state(dashboard_channel.id, dashboard_message.id)

        if not update_dashboard.is_running():
            update_dashboard.start()

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to start dashboard:\n```ansi\n\u001b[1;31m{str(e)}\u001b[0m```",
            color=0xFF0000,
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)


@tasks.loop(seconds=30)
async def update_dashboard():
    """Background task to refresh the dashboard embed."""
    global dashboard_message
    if dashboard_message:
        try:
            print("Refreshing dashboard...")
            new_embed = create_health_embed()
            await dashboard_message.edit(embed=new_embed)
            print("Dashboard updated successfully")
        except Exception as e:
            print(f"Error updating dashboard: {e}")
            try:
                state = load_dashboard_state()
                if state:
                    channel = await bot.fetch_channel(state["channel_id"])
                    dashboard_message = await channel.fetch_message(state["message_id"])
                    new_embed = create_health_embed()
                    await dashboard_message.edit(embed=new_embed)
            except Exception as restore_error:
                print(f"Failed to restore dashboard: {restore_error}")


def get_dashboard_state():
    """Return dashboard message and channel for events (e.g. on_ready restore)."""
    return dashboard_message, dashboard_channel


def set_dashboard_state(message, channel):
    """Set dashboard state from events."""
    global dashboard_message, dashboard_channel
    dashboard_message = message
    dashboard_channel = channel
