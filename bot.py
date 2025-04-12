import os
import time
import psutil
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import json
from plexapi.server import PlexServer
from datetime import datetime, timedelta

# Load settings from .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID"))
PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")

# Set up the bot with all intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Global variables to store the dashboard embed message and the channel it's in.
dashboard_message = None
dashboard_channel = None

# File to store dashboard state
DASHBOARD_STATE_FILE = "dashboard_state.json"

def get_plex_connection():
    """Create a connection to Plex server"""
    try:
        return PlexServer(PLEX_URL, PLEX_TOKEN)
    except Exception as e:
        print(f"Error connecting to Plex: {e}")
        return None

def save_dashboard_state(channel_id, message_id):
    """Save the dashboard state to a file"""
    state = {
        "channel_id": channel_id,
        "message_id": message_id
    }
    with open(DASHBOARD_STATE_FILE, "w") as f:
        json.dump(state, f)

def load_dashboard_state():
    """Load the dashboard state from file"""
    try:
        with open(DASHBOARD_STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def create_health_embed():
    # Calculate uptime (since system boot) formatted as h m s.
    uptime_seconds = time.time() - psutil.boot_time()
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

    # Gather CPU and RAM usage using psutil
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Get network info with error handling
    try:
        net_io = psutil.net_io_counters()
        net_bytes_sent = net_io.bytes_sent / (1024**2)  # Convert to MB
        net_bytes_recv = net_io.bytes_recv / (1024**2)  # Convert to MB
    except:
        net_bytes_sent = 0
        net_bytes_recv = 0

    # Build the embed with modern styling
    embed = discord.Embed(
        title="",
        description="",
        color=0x00b8ff  # Plex blue color
    )

    # Title
    embed.add_field(
        name="\n💻 LIVE SYSTEM DASHBOARD 📊",
        value="━━━━━━━━━━━━━━━━━━━━━━━━",
        inline=False
    )

    # System Overview
    system_stats = (
        f"```ansi\n"
        f"\u001b[1;36mSYSTEM OVERVIEW\u001b[0m\n"
        f"┌──────────────────────────┐\n"
        f"│ Uptime: \u001b[1;33m{uptime_str}\u001b[0m\n"
        f"└──────────────────────────┘\n"
        f"```"
    )
    embed.add_field(name="", value=system_stats, inline=False)

    # Resource Usage
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

    # Network Status
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

    # Add timestamp and refresh info
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    embed.set_footer(
        text=f"🔄 Auto-updates every 30s • Last update: {current_time}",
        icon_url="https://cdn.iconscout.com/icon/free/png-256/refresh-1781197-1518571.png"
    )

    return embed


@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")
    try:
        # Sync commands to the test guild for instant availability.
        guild = discord.Object(id=TEST_GUILD_ID)
        synced = await tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} commands to guild {TEST_GUILD_ID}")
        
        # Restore dashboard if it exists
        state = load_dashboard_state()
        if state:
            try:
                channel = await bot.fetch_channel(state["channel_id"])
                message = await channel.fetch_message(state["message_id"])
                global dashboard_message, dashboard_channel
                dashboard_message = message
                dashboard_channel = channel
                if not update_dashboard.is_running():
                    update_dashboard.start()
                print("✅ Restored dashboard state")
            except discord.NotFound:
                print("❌ Could not restore dashboard - message or channel not found")
                # Clean up invalid state
                if os.path.exists(DASHBOARD_STATE_FILE):
                    os.remove(DASHBOARD_STATE_FILE)
    except Exception as e:
        print(f"❌ Sync failed: {e}")


@tree.command(
    name="dashboard",
    description="Start a persistent server health dashboard.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def dashboard(interaction: discord.Interaction):
    await interaction.response.defer()
    
    try:
        global dashboard_message, dashboard_channel
        dashboard_channel = interaction.channel

        # Create data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Update the dashboard state file path
        global DASHBOARD_STATE_FILE
        DASHBOARD_STATE_FILE = os.path.join(data_dir, "dashboard_state.json")

        # Send an ephemeral message so the user knows the dashboard is starting
        await interaction.followup.send(
            "🚀 Starting system dashboard... (This message will disappear)", 
            ephemeral=True
        )

        # Post the first dashboard embed publicly
        embed = create_health_embed()
        dashboard_message = await dashboard_channel.send(embed=embed)

        # Save the dashboard state
        save_dashboard_state(dashboard_channel.id, dashboard_message.id)

        # Start the background update loop if it isn't running already
        if not update_dashboard.is_running():
            update_dashboard.start()

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to start dashboard:\n```ansi\n\u001b[1;31m{str(e)}\u001b[0m```",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)


@tasks.loop(seconds=30)
async def update_dashboard():
    global dashboard_message
    if dashboard_message:
        try:
            new_embed = create_health_embed()
            await dashboard_message.edit(embed=new_embed)
        except Exception as e:
            print(f"Error updating dashboard: {e}")
            # If we lost the message reference, try to restore it
            try:
                state = load_dashboard_state()
                if state:
                    channel = await bot.fetch_channel(state["channel_id"])
                    dashboard_message = await channel.fetch_message(state["message_id"])
                    await dashboard_message.edit(embed=new_embed)
            except Exception as restore_error:
                print(f"Failed to restore dashboard: {restore_error}")


@tree.command(
    name="serverhealth",
    description="Check current server health stats.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def server_health(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        # System uptime
        uptime_seconds = time.time() - psutil.boot_time()
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

        # CPU information
        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        cpu_temp = None
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if "coretemp" in temps:
                    cpu_temp = max(temp.current for temp in temps["coretemp"])
        except:
            cpu_temp = "N/A"

        # Memory information
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Network information - handle permissions gracefully
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

        # Build the embed with a modern layout
        embed = discord.Embed(
            title="",
            description="",
            color=0x00b8ff
        )

        # Modern title with emoji
        embed.add_field(
            name="\n💻 SYSTEM HEALTH DASHBOARD 📊",
            value="━━━━━━━━━━━━━━━━━━━━━━━━",
            inline=False
        )

        # System Stats
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

        # Resource Usage
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

        # Network Stats
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

        # Add timestamp
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(
            text=f"📊 Stats as of {current_time} • Use /serverhealth to refresh",
            icon_url="https://cdn.iconscout.com/icon/free/png-256/refresh-1781197-1518571.png"
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch server health:\n```ansi\n\u001b[1;31m{str(e)}\u001b[0m```",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)


@tree.command(
    name="ping",
    description="Check the bot's latency.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(
        f"🏓 Pong! Latency: {latency}ms", ephemeral=True
    )


@tree.command(
    name="setup_homelab",
    description="Set up the homelab server layout with roles and channels.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_homelab(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild

    roles = {
        "🛡️ Admin": discord.Permissions(administrator=True),
        "👀 Observer": discord.Permissions(view_channel=True),
        "🔧 Maintainer": discord.Permissions(manage_messages=True),
        "🤖 Bot": discord.Permissions(send_messages=True),
        "🎮 Gamer": discord.Permissions(read_messages=True),
    }

    # Create roles
    for name, perms in roles.items():
        await guild.create_role(name=name, permissions=perms)

    categories = {
        "📊 System & Status": [
            "📈｜system-health",
            "📦｜docker-containers",
            "🕒｜uptime-status",
            "🧰｜maintenance-log",
        ],
        "📽️ Media Center": [
            "🎬｜radarr-status",
            "📺｜sonarr-status",
            "🎶｜lidarr-status",
            "📤｜download-queue",
            "🧞｜overseerr-requests",
        ],
        "🎮 Game Servers": [
            "🎮｜server-status",
            "⚙️｜console-logs",
            "👥｜player-activity",
            "📌｜how-to-join",
        ],
        "🛰️ Overseerr & Requests": [
            "📥｜new-requests",
            "✅｜approved-downloads",
            "❌｜rejected-requests",
        ],
        "🤖 Bot Commands": ["🤖｜commands", "📜｜logs", "🔒｜admin-cmds"],
        "🚨 Alerts": ["🔥｜alerts", "👀｜watchdog"],
    }

    # Create each category and its channels.
    for category_name, channels in categories.items():
        category = await guild.create_category(category_name)
        for ch in channels:
            await guild.create_text_channel(ch, category=category)

    await interaction.followup.send("🎉 Server structure created successfully!")


@tree.command(
    name="sync",
    description="Sync slash commands (Admin only)",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def sync(interaction: discord.Interaction):
    """Manually sync slash commands"""
    await interaction.response.defer(ephemeral=True)
    try:
        # Sync to test guild
        guild = discord.Object(id=TEST_GUILD_ID)
        synced = await tree.sync(guild=guild)
        await interaction.followup.send(
            f"✅ Successfully synced {len(synced)} commands to guild {TEST_GUILD_ID}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to sync commands: {e}",
            ephemeral=True
        )


@tree.command(
    name="commands",
    description="List all available commands",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def list_commands(interaction: discord.Interaction):
    """List all available commands with their descriptions"""
    commands_list = []
    for cmd in tree.get_commands(guild=discord.Object(id=TEST_GUILD_ID)):
        commands_list.append(f"`/{cmd.name}` - {cmd.description}")
    embed = discord.Embed(
        title="🤖 Available Commands",
        description="\n".join(commands_list),
        color=0x00FF00
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(
    name="media_stats",
    description="Show statistics from your media libraries",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def media_stats(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    plex = get_plex_connection()
    if not plex:
        await interaction.followup.send("❌ Could not connect to Plex server. Please check your configuration.", ephemeral=True)
        return

    try:
        # Get library sections
        movies = plex.library.section("Movies")
        shows = plex.library.section("TV Shows")

        # Calculate recently added items (last 7 days)
        recent_date = datetime.now() - timedelta(days=7)
        
        # Get recently added movies and shows
        recent_movies = movies.search(sort="addedAt:desc", maxresults=10)
        recent_movies = [m for m in recent_movies if m.addedAt >= recent_date]
        
        recent_shows = shows.search(sort="addedAt:desc", maxresults=10)
        recent_shows = [s for s in recent_shows if s.addedAt >= recent_date]

        # Calculate total duration for movies
        total_movie_minutes = sum(m.duration for m in movies.all()) / 60000  # Convert ms to minutes
        movie_days = int(total_movie_minutes // 1440)  # minutes in a day
        movie_hours = int((total_movie_minutes % 1440) // 60)
        movie_minutes = int(total_movie_minutes % 60)

        # Calculate total duration for TV shows
        total_show_minutes = 0
        total_episodes = 0
        for show in shows.all():
            for episode in show.episodes():
                if hasattr(episode, 'duration'):
                    total_show_minutes += episode.duration / 60000  # Convert ms to minutes
                    total_episodes += 1

        show_days = int(total_show_minutes // 1440)
        show_hours = int((total_show_minutes % 1440) // 60)
        show_minutes = int(total_show_minutes % 60)

        # Calculate combined total duration
        total_minutes = total_movie_minutes + total_show_minutes
        total_days = int(total_minutes // 1440)
        total_hours = int((total_minutes % 1440) // 60)
        total_minutes = int(total_minutes % 60)

        # Build the embed with a modern layout
        embed = discord.Embed(
            title="",  # We'll use a field for the title to make it more stylish
            description="",
            color=0x00b8ff  # Plex blue color
        )

        # Modern title with emoji
        embed.add_field(
            name="\n🎬 PLEX MEDIA STATISTICS 📊",
            value="━━━━━━━━━━━━━━━━━━━━━━━━",
            inline=False
        )

        # Total Collection Stats with modern formatting
        total_stats = (
            f"```ansi\n"
            f"\u001b[1;36m📼 TOTAL COLLECTION\u001b[0m\n"
            f"┌──────────────────────────┐\n"
            f"│ Duration: \u001b[1;33m{total_days}d {total_hours}h {total_minutes}m\u001b[0m │\n"
            f"│ Content: \u001b[1;33m{(total_minutes + total_hours * 60 + total_days * 1440):,}min\u001b[0m │\n"
            f"└──────────────────────────┘\n"
            f"```"
        )
        embed.add_field(name="", value=total_stats, inline=False)

        # Movies Statistics with modern formatting
        movies_stats = (
            f"```ansi\n"
            f"\u001b[1;35m🎥 MOVIES\u001b[0m\n"
            f"┌──────────────────────────┐\n"
            f"│ Total: \u001b[1;33m{movies.totalSize:,} movies\u001b[0m\n"
            f"│ Duration: \u001b[1;36m{movie_days}d {movie_hours}h {movie_minutes}m\u001b[0m\n"
            f"│ Average: \u001b[1;32m{(total_movie_minutes / movies.totalSize):.1f}min\u001b[0m\n"
            f"│ New: \u001b[1;31m+{len(recent_movies)} this week\u001b[0m\n"
            f"└──────────────────────────┘\n"
            f"```"
        )
        embed.add_field(name="", value=movies_stats, inline=True)

        # TV Shows Statistics with modern formatting
        shows_stats = (
            f"```ansi\n"
            f"\u001b[1;35m📺 TV SHOWS\u001b[0m\n"
            f"┌──────────────────────────┐\n"
            f"│ Shows: \u001b[1;33m{shows.totalSize:,} series\u001b[0m\n"
            f"│ Episodes: \u001b[1;33m{total_episodes:,} total\u001b[0m\n"
            f"│ Duration: \u001b[1;36m{show_days}d {show_hours}h {show_minutes}m\u001b[0m\n"
            f"│ Average: \u001b[1;32m{(total_show_minutes / total_episodes):.1f}min\u001b[0m\n"
            f"│ New: \u001b[1;31m+{len(recent_shows)} this week\u001b[0m\n"
            f"└──────────────────────────┘\n"
            f"```"
        )
        embed.add_field(name="", value=shows_stats, inline=True)

        # Divider
        embed.add_field(name="", value="━━━━━━━━━━━━━━━━━━━━━━━━", inline=False)

        # Recently Added Content with modern formatting
        if recent_movies:
            recent_content = "```ansi\n\u001b[1;35mRECENT ADDITIONS\u001b[0m\n"
            recent_content += "\u001b[1;33mMovies:\u001b[0m\n"
            for m in recent_movies[:3]:
                recent_content += f"• \u001b[1;36m{m.title}\u001b[0m ({m.year}) - \u001b[1;32m{m.duration // 60000}min\u001b[0m\n"
            
            if recent_shows:
                recent_content += "\n\u001b[1;33mTV Shows:\u001b[0m\n"
                for s in recent_shows[:3]:
                    recent_content += f"• \u001b[1;36m{s.title}\u001b[0m - \u001b[1;32m{len(s.episodes())} episodes\u001b[0m\n"
            
            recent_content += "```"
            embed.add_field(name="", value=recent_content, inline=False)

        # Modern footer with timestamp
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(
            text=f"📊 Stats as of {current_time} • Use /media_stats to refresh",
            icon_url="https://cdn.iconscout.com/icon/free/png-256/refresh-1781197-1518571.png"
        )

        # Add Plex logo
        embed.set_thumbnail(url="https://cdn.iconscout.com/icon/free/png-256/plex-3521495-2944935.png")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch media statistics:\n```ansi\n\u001b[1;31m{str(e)}\u001b[0m```",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)


def start_bot():
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN is not set")
        return
    if not TEST_GUILD_ID:
        print("❌ Error: TEST_GUILD_ID is not set")
        return
    bot.run(TOKEN)


if __name__ == "__main__":
    start_bot()
