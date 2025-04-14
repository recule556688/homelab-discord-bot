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
from discord.ui import Button, View
import asyncio

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
DASHBOARD_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "dashboard_state.json")

def get_plex_connection():
    """Create a connection to Plex server"""
    try:
        return PlexServer(PLEX_URL, PLEX_TOKEN)
    except Exception as e:
        print(f"Error connecting to Plex: {e}")
        return None

def save_dashboard_state(channel_id, message_id):
    """Save the dashboard state to a file"""
    try:
        state = {
            "channel_id": channel_id,
            "message_id": message_id
        }
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(DASHBOARD_STATE_FILE), exist_ok=True)
        with open(DASHBOARD_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Error saving dashboard state: {e}")

def load_dashboard_state():
    """Load the dashboard state from file"""
    try:
        if os.path.exists(DASHBOARD_STATE_FILE):
            with open(DASHBOARD_STATE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading dashboard state: {e}")
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
        # Set status to DND with a custom activity
        await bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="You and all your hardware 😏"
            )
        )
        # Get the test guild
        guild = discord.Object(id=TEST_GUILD_ID)
        # Sync the commands
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

async def setup_commands():
    """Set up all slash commands"""
    guild = discord.Object(id=TEST_GUILD_ID)
    
    # Commands list
    commands = [
        app_commands.Command(
            name="setup_homelab",
            description="Set up the homelab server layout with roles and channels.",
            callback=setup_homelab
        ),
        app_commands.Command(
            name="dashboard",
            description="Start a persistent server health dashboard.",
            callback=dashboard
        ),
        app_commands.Command(
            name="serverhealth",
            description="Check current server health stats.",
            callback=server_health
        ),
        app_commands.Command(
            name="ping",
            description="Check the bot's latency.",
            callback=ping
        ),
        app_commands.Command(
            name="sync",
            description="Sync slash commands (Admin only)",
            callback=sync
        ),
        app_commands.Command(
            name="commands",
            description="List all available commands",
            callback=list_commands
        ),
        app_commands.Command(
            name="media_stats",
            description="Show statistics from your media libraries",
            callback=media_stats
        ),
        app_commands.Command(
            name="send_intro_embed",
            description="Send the onboarding embed to the start-here channel.",
            callback=send_intro_embed
        ),
        app_commands.Command(
            name="send_invite_embed",
            description="Send the get-invite embed to the channel.",
            callback=send_invite_embed
        )
    ]
    
    # Add each command to the tree
    for cmd in commands:
        tree.add_command(cmd, guild=guild)


@tree.command(
    name="dashboard",
    description="Start a persistent server health dashboard.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def dashboard(interaction: discord.Interaction):
    await interaction.response.defer()
    
    try:
        global dashboard_message, dashboard_channel

        # Delete existing dashboard if it exists
        try:
            state = load_dashboard_state()
            if state:
                try:
                    old_channel = await bot.fetch_channel(state["channel_id"])
                    old_message = await old_channel.fetch_message(state["message_id"])
                    await old_message.delete()
                except:
                    pass  # Ignore if message doesn't exist or can't be deleted
                
                # Clean up the state file
                if os.path.exists(DASHBOARD_STATE_FILE):
                    os.remove(DASHBOARD_STATE_FILE)
        except:
            pass  # Ignore any errors during cleanup

        dashboard_channel = interaction.channel

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

    # Define roles with their permissions
    roles = {
        "🛡️ Admin": discord.Permissions(administrator=True),
        "👀 Observer": discord.Permissions(view_channel=True),
        "🔧 Maintainer": discord.Permissions(manage_messages=True),
        "🤖 Bot": discord.Permissions(send_messages=True),
        "🎮 Gamer": discord.Permissions(read_messages=True),
        "🎟️ Approved": discord.Permissions(read_messages=True),  # Role for approved users
        "⏳ Pending": discord.Permissions(read_messages=True),    # Role for pending users
        "❌ Denied": discord.Permissions(read_messages=True),     # New role for denied users
    }

    # Create or update roles
    for name, perms in roles.items():
        existing_role = discord.utils.get(guild.roles, name=name)
        if not existing_role:
            await guild.create_role(name=name, permissions=perms)
            print(f"Created role: {name}")

    # Define categories and their channels
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
        "👋 Onboarding": [  # New category for onboarding
            "📖｜start-here",
            "📬｜get-invite",
            "🎫｜access-requests",
        ],
    }

    # Create or update categories and channels
    for category_name, channels in categories.items():
        # Check if category exists
        existing_category = discord.utils.get(guild.categories, name=category_name)
        if not existing_category:
            category = await guild.create_category(category_name)
            print(f"Created category: {category_name}")
        else:
            category = existing_category
            print(f"Using existing category: {category_name}")

        # Create or update channels in the category
        for channel_name in channels:
            existing_channel = discord.utils.get(guild.channels, name=channel_name)
            if not existing_channel:
                # Set up channel permissions based on category
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                }
                
                # Special permissions for onboarding channels
                if category_name == "👋 Onboarding":
                    if channel_name == "📖｜start-here":
                        # Everyone can read start-here
                        overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=True)
                    elif channel_name == "📬｜get-invite":
                        # Only approved users can see get-invite
                        approved_role = discord.utils.get(guild.roles, name="🎟️ Approved")
                        if approved_role:
                            overwrites[approved_role] = discord.PermissionOverwrite(read_messages=True)
                    elif channel_name == "🎫｜access-requests":
                        # Only mods and admins can see access requests
                        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
                        maintainer_role = discord.utils.get(guild.roles, name="🔧 Maintainer")
                        if admin_role:
                            overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True)
                        if maintainer_role:
                            overwrites[maintainer_role] = discord.PermissionOverwrite(read_messages=True)

                await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
                print(f"Created channel: {channel_name}")

    await interaction.followup.send("🎉 Server structure created/updated successfully!")


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


class OnboardingView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="🎟 Request Access", style=discord.ButtonStyle.primary, custom_id="request_access"))

class AccessRequestView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="approve_request")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Get the thread
            thread = interaction.channel
            
            # Acknowledge the interaction first
            await interaction.response.defer()
            
            try:
                user = await interaction.guild.fetch_member(self.user_id)
                if not user:
                    await interaction.followup.send("❌ Error: Could not find the user who requested access.", ephemeral=True)
                    return
                    
                # Remove denied role if they had it
                denied_role = discord.utils.get(interaction.guild.roles, name="❌ Denied")
                if denied_role and denied_role in user.roles:
                    await user.remove_roles(denied_role)
                
                # Add approved role
                approved_role = discord.utils.get(interaction.guild.roles, name="🎟️ Approved")
                if approved_role:
                    await user.add_roles(approved_role)
                    
                    # Send approval message in thread
                    embed = discord.Embed(
                        title="✅ Request Approved",
                        description=f"{user.mention} has been approved for access!\n\nThey can now access the invite channel.",
                        color=0x00ff00
                    )
                    await interaction.followup.send(embed=embed)

                    # Send a single DM to the user
                    try:
                        dm_embed = discord.Embed(
                            title="🎉 Access Approved!",
                            description="Your access request has been approved! You can now access the invite channel.",
                            color=0x00ff00
                        )
                        await user.send(embed=dm_embed)
                    except:
                        # If DM fails, add a note to the thread
                        await thread.send("Note: Could not send DM to user (they may have DMs disabled)")

                    # Archive the thread after a delay
                    await asyncio.sleep(5)
                    await thread.edit(archived=True, locked=True)
                else:
                    await interaction.followup.send("❌ Error: Could not find the Approved role.", ephemeral=True)
            except discord.NotFound:
                await interaction.followup.send("❌ Error: Could not find the user who requested access.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ Error while approving: {str(e)}", ephemeral=True)

        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="deny_request")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Get the thread
            thread = interaction.channel
            
            # Acknowledge the interaction first
            await interaction.response.defer()
            
            try:
                user = await interaction.guild.fetch_member(self.user_id)
                if not user:
                    await interaction.followup.send("❌ Error: Could not find the user who requested access.", ephemeral=True)
                    return

                # Remove approved role if they had it
                approved_role = discord.utils.get(interaction.guild.roles, name="🎟️ Approved")
                if approved_role and approved_role in user.roles:
                    await user.remove_roles(approved_role)
                
                # Add denied role
                denied_role = discord.utils.get(interaction.guild.roles, name="❌ Denied")
                if denied_role:
                    await user.add_roles(denied_role)

                # Send denial message in thread
                embed = discord.Embed(
                    title="❌ Request Denied",
                    description=f"{user.mention}'s access request has been denied.",
                    color=0xff0000
                )
                await interaction.followup.send(embed=embed)

                # Send a single DM to the user
                try:
                    dm_embed = discord.Embed(
                        title="❌ Access Denied",
                        description="Your access request has been denied. Please contact a moderator if you have questions.",
                        color=0xff0000
                    )
                    await user.send(embed=dm_embed)
                except:
                    # If DM fails, add a note to the thread
                    await thread.send("Note: Could not send DM to user (they may have DMs disabled)")

                # Archive the thread after a delay
                await asyncio.sleep(5)
                await thread.edit(archived=True, locked=True)
            except discord.NotFound:
                await interaction.followup.send("❌ Error: Could not find the user who requested access.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ Error while denying: {str(e)}", ephemeral=True)

        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

def create_onboarding_embed():
    embed = discord.Embed(
        title="🎬 Welcome to Our Media Server!",
        description="",
        color=0x00b8ff
    )

    # English Section
    embed.add_field(
        name="🇬🇧 English",
        value=(
            "**How to Get Started:**\n"
            "1. Click the 'Request Access' button below\n"
            "2. Wait for moderator approval\n"
            "3. Once approved, you'll receive a Plex invite via Wizarr\n"
            "4. Use Overseerr to request new content\n"
            "5. Enjoy your media on Plex!\n\n"
        ),
        inline=False
    )

    # French Section
    embed.add_field(
        name="🇫🇷 Français",
        value=(
            "**Comment commencer:**\n"
            "1. Cliquez sur le bouton 'Demander l'accès' ci-dessous\n"
            "2. Attendez l'approbation d'un modérateur\n"
            "3. Une fois approuvé, vous recevrez une invitation Plex via Wizarr\n"
            "4. Utilisez Overseerr pour demander du nouveau contenu\n"
            "5. Profitez de vos médias sur Plex!\n\n"
        ),
        inline=False
    )

    return embed

@tree.command(
    name="send_intro_embed",
    description="Send the onboarding embed to the start-here channel.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def send_intro_embed(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Find the start-here channel
        start_here_channel = discord.utils.get(interaction.guild.channels, name="📖｜start-here")
        if not start_here_channel:
            await interaction.followup.send("❌ Could not find the start-here channel!", ephemeral=True)
            return

        # Create and send the embed
        embed = create_onboarding_embed()
        view = OnboardingView()
        await start_here_channel.send(embed=embed, view=view)
        
        await interaction.followup.send("✅ Onboarding embed sent successfully!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data["custom_id"] == "request_access":
            await handle_access_request(interaction)

async def handle_access_request(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Find the access-requests channel
        requests_channel = discord.utils.get(interaction.guild.channels, name="🎫｜access-requests")
        if not requests_channel:
            await interaction.followup.send("❌ Could not find the access-requests channel!", ephemeral=True)
            return

        # Create a thread for the request
        thread = await requests_channel.create_thread(
            name=f"Access Request - {interaction.user.name}",
            type=discord.ChannelType.private_thread
        )

        # Add the user to the thread
        await thread.add_user(interaction.user)

        # Create the request embed
        embed = discord.Embed(
            title="🎟 New Access Request",
            description=f"User: {interaction.user.mention}\n\nPlease explain why you want access to the media server:",
            color=0x00b8ff
        )

        # Create view with user ID
        view = AccessRequestView(interaction.user.id)
        await thread.send(embed=embed, view=view)

        # Send confirmation to the user
        await interaction.followup.send(
            "✅ Your access request has been submitted! Please check the thread for updates.",
            ephemeral=True
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

def create_invite_embed():
    embed = discord.Embed(
        title="🎟️ Get Your Media Server Invite",
        description=(
            "Welcome to the invite channel! Here's your direct invite link:\n\n"
            "**🔗 [Click Here to Join](https://wizarr.tessdev.fr/i/ETHUDN)**\n\n"
            "Follow the steps below to get started with our media server."
        ),
        color=0x00b8ff
    )

    # English Section
    embed.add_field(
        name="🇬🇧 Getting Started",
        value=(
            "**Step 1: Get Your Plex Invite**\n"
            "• Click the invite link above\n"
            "• Sign up with your email\n"
            "• Accept the Plex invitation\n\n"
            "**Step 2: Access Content**\n"
            "• Download [Plex](https://www.plex.tv/downloads)\n"
            "• Sign in with your account\n"
            "• Start streaming!\n\n"
            "**Step 3: Request Content**\n"
            "• Use [Overseerr](https://overseer.tessdev.fr) to request movies and shows\n"
            "• Track your requests status\n"
            "• Get notified when content is available"
        ),
        inline=False
    )

    # French Section
    embed.add_field(
        name="🇫🇷 Pour Commencer",
        value=(
            "**Étape 1: Obtenir Votre Invitation Plex**\n"
            "• Cliquez sur le lien d'invitation ci-dessus\n"
            "• Inscrivez-vous avec votre email\n"
            "• Acceptez l'invitation Plex\n\n"
            "**Étape 2: Accéder au Contenu**\n"
            "• Téléchargez [Plex](https://www.plex.tv/downloads)\n"
            "• Connectez-vous avec votre compte\n"
            "• Commencez à streamer!\n\n"
            "**Étape 3: Demander du Contenu**\n"
            "• Utilisez [Overseerr](https://overseer.tessdev.fr) pour demander des films et séries\n"
            "• Suivez le statut de vos demandes\n"
            "• Soyez notifié quand le contenu est disponible"
        ),
        inline=False
    )

    # Important Notes
    embed.add_field(
        name="ℹ️ Important Notes | Notes Importantes",
        value=(
            "**🇬🇧**\n"
            "• This invite link is for approved members only\n"
            "• Keep your login information secure\n"
            "• Don't share your account with others\n"
            "• For support, contact an admin\n\n"
            "**🇫🇷**\n"
            "• Ce lien d'invitation est réservé aux membres approuvés\n"
            "• Gardez vos informations de connexion sécurisées\n"
            "• Ne partagez pas votre compte\n"
            "• Pour le support, contactez un admin"
        ),
        inline=False
    )

    embed.set_footer(
        text="🔐 Access is limited to approved members only | Accès limité aux membres approuvés",
        icon_url="https://cdn.discordapp.com/emojis/1039485258276737024.webp?size=96&quality=lossless"
    )

    return embed

@tree.command(
    name="send_invite_embed",
    description="Send the get-invite embed to the channel.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def send_invite_embed(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Find the get-invite channel
        invite_channel = discord.utils.get(interaction.guild.channels, name="📬｜get-invite")
        if not invite_channel:
            await interaction.followup.send("❌ Could not find the get-invite channel!", ephemeral=True)
            return

        # Create and send the embed
        embed = create_invite_embed()
        await invite_channel.send(embed=embed)
        
        await interaction.followup.send("✅ Invite embed sent successfully!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

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
