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

    # Build the embed
    embed = discord.Embed(title="🖥️ Server Health Dashboard", color=0x00FF00)
    embed.add_field(name="Uptime", value=uptime_str, inline=False)
    embed.add_field(name="CPU Usage", value=f"{cpu_usage}%", inline=True)
    embed.add_field(name="RAM Usage", value=f"{memory.percent}%", inline=True)
    embed.set_footer(text="Updated every 30 seconds")
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
    global dashboard_message, dashboard_channel
    dashboard_channel = interaction.channel

    # Send an ephemeral message so the user knows the dashboard is starting.
    await interaction.response.send_message(
        "Starting dashboard... (This message is ephemeral)", ephemeral=True
    )

    # Post the first dashboard embed publicly
    embed = create_health_embed()
    dashboard_message = await dashboard_channel.send(embed=embed)
    
    # Save the dashboard state
    save_dashboard_state(dashboard_channel.id, dashboard_message.id)

    # Start the background update loop if it isn't running already.
    if not update_dashboard.is_running():
        update_dashboard.start()


@tasks.loop(seconds=30)
async def update_dashboard():
    global dashboard_message
    if dashboard_message:
        try:
            new_embed = create_health_embed()
            await dashboard_message.edit(embed=new_embed)
        except Exception as e:
            print(f"Error updating dashboard: {e}")


@tree.command(
    name="serverhealth",
    description="Check current server health stats.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def server_health(interaction: discord.Interaction):
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

    # Disk information
    disk_info = []
    for partition in psutil.disk_partitions():
        if partition.fstype:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info.append({
                    "device": partition.device,
                    "mount": partition.mountpoint,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent
                })
            except:
                continue

    # Network information
    net_io = psutil.net_io_counters()
    net_connections = len(psutil.net_connections())

    # Build the embed
    embed = discord.Embed(title="🖥️ Detailed Server Health", color=0x00FF00)
    # System Information
    embed.add_field(
        name="System Information",
        value=f"**Uptime:** {uptime_str}\n"
              f"**CPU Cores:** {cpu_count}\n"
              f"**CPU Frequency:** {cpu_freq.current:.2f}MHz\n"
              f"**CPU Temperature:** {cpu_temp if cpu_temp else 'N/A'}°C",
        inline=False
    )

    # CPU & Memory
    embed.add_field(
        name="CPU & Memory",
        value=f"**CPU Usage:** {cpu_usage}%\n"
              f"**RAM Usage:** {memory.percent}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)\n"
              f"**Swap Usage:** {swap.percent}% ({swap.used / (1024**3):.1f}GB / {swap.total / (1024**3):.1f}GB)",
        inline=False
    )

    # Disk Information
    disk_value = ""
    for disk in disk_info:
        disk_value += (
            f"**{disk['mount']}**\n"
            f"• Total: {disk['total'] / (1024**3):.1f}GB\n"
            f"• Used: {disk['used'] / (1024**3):.1f}GB ({disk['percent']}%)\n"
            f"• Free: {disk['free'] / (1024**3):.1f}GB\n"
        )
    embed.add_field(name="Disk Usage", value=disk_value, inline=False)

    # Network Information
    embed.add_field(
        name="Network",
        value=f"**Active Connections:** {net_connections}\n"
              f"**Bytes Sent:** {net_io.bytes_sent / (1024**2):.1f}MB\n"
              f"**Bytes Received:** {net_io.bytes_recv / (1024**2):.1f}MB",
        inline=False
    )

    # Add timestamp
    embed.set_footer(text=f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    await interaction.response.send_message(embed=embed, ephemeral=True)


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
        music = plex.library.section("Music") if "Music" in [s.title for s in plex.library.sections()] else None

        # Calculate recently added items (last 7 days)
        recent_date = datetime.now() - timedelta(days=7)
        
        # Get recently added movies
        recent_movies = movies.search(sort="addedAt:desc", maxresults=10)
        recent_movies = [m for m in recent_movies if m.addedAt >= recent_date]
        
        # Get recently added shows
        recent_shows = shows.search(sort="addedAt:desc", maxresults=10)
        recent_shows = [s for s in recent_shows if s.addedAt >= recent_date]

        # Build the embed
        embed = discord.Embed(title="📊 Media Library Statistics", color=0x00FF00)
        
        # Movies Statistics
        embed.add_field(
            name="🎬 Movies",
            value=f"**Total Movies:** {movies.totalSize}\n"
                  f"**Recently Added:** {len(recent_movies)}\n"
                  f"**Total Duration:** {sum(m.duration for m in movies.all()) / 3600000:.1f} hours",
            inline=True
        )

        # TV Shows Statistics
        total_episodes = sum(len(show.episodes()) for show in shows.all())
        embed.add_field(
            name="📺 TV Shows",
            value=f"**Total Shows:** {shows.totalSize}\n"
                  f"**Total Episodes:** {total_episodes}\n"
                  f"**Recently Added:** {len(recent_shows)}",
            inline=True
        )

        # Music Statistics (if available)
        if music:
            embed.add_field(
                name="🎵 Music",
                value=f"**Total Artists:** {music.totalSize}\n"
                      f"**Total Albums:** {sum(len(artist.albums()) for artist in music.all())}\n"
                      f"**Total Tracks:** {sum(len(album.tracks()) for album in music.all())}",
                inline=True
            )

        # Recently Added Movies
        if recent_movies:
            recent_movies_str = "\n".join([f"• {m.title} ({m.year})" for m in recent_movies[:5]])
            embed.add_field(
                name="🎥 Recently Added Movies",
                value=recent_movies_str,
                inline=False
            )

        # Recently Added Shows
        if recent_shows:
            recent_shows_str = "\n".join([f"• {s.title}" for s in recent_shows[:5]])
            embed.add_field(
                name="📺 Recently Added Shows",
                value=recent_shows_str,
                inline=False
            )

        # Add timestamp
        embed.set_footer(text=f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Error fetching media statistics: {str(e)}", ephemeral=True)


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
